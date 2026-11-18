# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Cross-cutting ADK BasePlugin for workflow latency, token usage, search grounding, and AI cost telemetry."""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
import os
import time
from typing import Any, Dict, List, Mapping, Optional

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin

from app.app_utils.cost_tracker import (
    aggregate_invocation_cost,
    extract_step_usage_and_cost,
    load_pricing_catalog,
)
from app.app_utils.logging import format_table_for_logs, setup_logging
from app.config import (
    DEFAULT_GEMINI_MODEL,
    ENABLE_TELEMETRY_PLUGIN,
    EXPOSE_TELEMETRY_HEADER,
    PRICING_CONFIG_PATH,
)

logger = setup_logging(name=__name__)

TELEMETRY_HEADER_NAME = "X-AI-Telemetry"

_REQUEST_TELEMETRY_VAR: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar(
    "conversational_request_ai_telemetry", default=None
)


def is_telemetry_header_enabled() -> bool:
    """Checks whether X-AI-Telemetry HTTP header emission is enabled (supports dynamic env overrides)."""
    raw = os.getenv("EXPOSE_TELEMETRY_HEADER")
    if raw is None:
        return EXPOSE_TELEMETRY_HEADER
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def begin_request_telemetry_scope():
    """Starts an async-isolated request telemetry collector and returns its ContextVar token."""
    return _REQUEST_TELEMETRY_VAR.set([])


def end_request_telemetry_scope(token) -> List[Dict[str, Any]]:
    """Collects completed invocation summaries from the current request scope and resets the ContextVar."""
    collected = list(_REQUEST_TELEMETRY_VAR.get() or [])
    _REQUEST_TELEMETRY_VAR.reset(token)
    return collected


class ExecutionTelemetryPlugin(BasePlugin):
    """ADK runtime plugin capturing per-agent latency, token counts, search queries, and Standard PayGo USD cost.

    State is isolated per ``invocation_id`` so a single plugin instance attached to ``App``
    remains safe across concurrent asynchronous FastAPI requests. Completed summaries are
    stored in a bounded ``_completed_runs`` ring buffer for programmatic inspection in tests
    and evaluations while ``_runs`` is cleaned up immediately on completion or error.
    """

    def __init__(
        self,
        name: str = "execution_telemetry",
        *,
        pricing_catalog: Optional[Mapping[str, Any]] = None,
        max_completed_runs: int = 256,
    ) -> None:
        super().__init__(name=name)
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._completed_runs: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_completed_runs = max(1, int(max_completed_runs))
        self._pricing_catalog = (
            dict(pricing_catalog)
            if pricing_catalog is not None
            else load_pricing_catalog(PRICING_CONFIG_PATH)
        )

    def get_completed_run(
        self, invocation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Returns the completed cost & token summary for ``invocation_id``, if retained."""
        return self._completed_runs.get(invocation_id)

    def get_latest_run(self) -> Optional[Dict[str, Any]]:
        """Returns the most recently completed invocation telemetry summary."""
        if not self._completed_runs:
            return None
        last_key = next(reversed(self._completed_runs))
        return self._completed_runs[last_key]

    def get_completed_runs(self) -> List[Dict[str, Any]]:
        """Returns all retained completed invocation telemetry summaries in chronological order."""
        return list(self._completed_runs.values())

    def clear_completed_runs(self) -> None:
        """Clears the retained completed invocation history buffer."""
        self._completed_runs.clear()

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        self._runs[invocation_context.invocation_id] = {
            "t0": time.perf_counter(),
            "agent_starts": {},
            "agent_models": {},
            "rows": [],
            "steps": [],
            "in_tokens": 0,
            "out_tokens": 0,
            "cached_tokens": 0,
            "thoughts_tokens": 0,
            "total_cost_usd": 0.0,
        }
        return None

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        run = self._runs.get(callback_context.invocation_id)
        if run is not None:
            run["agent_starts"][agent.name] = time.perf_counter()
            model_obj = getattr(agent, "model", None)
            configured_model = (
                getattr(model_obj, "model", None)
                or (model_obj if isinstance(model_obj, str) else None)
                or DEFAULT_GEMINI_MODEL
            )
            run["agent_models"][agent.name] = str(configured_model)
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        if getattr(llm_response, "partial", False):
            return None

        run = self._runs.get(callback_context.invocation_id)
        if run is None:
            return None

        agent_name = callback_context.agent_name
        started = run["agent_starts"].get(agent_name, run["t0"])
        elapsed_s = max(0.0, time.perf_counter() - started)

        configured_model = run["agent_models"].get(
            agent_name, DEFAULT_GEMINI_MODEL
        )
        step_cost = extract_step_usage_and_cost(
            author=agent_name,
            llm_response=llm_response,
            configured_model=configured_model,
            latency_seconds=elapsed_s,
            catalog=self._pricing_catalog,
        )

        in_tok = step_cost["prompt_tokens"]
        out_tok = step_cost["candidates_output_tokens"]
        cached_tok = step_cost["cached_input_tokens"]
        thoughts_tok = step_cost["thoughts_tokens"]

        run["in_tokens"] += in_tok
        run["out_tokens"] += out_tok
        run["cached_tokens"] += cached_tok
        run["thoughts_tokens"] += thoughts_tok
        run["total_cost_usd"] += step_cost["total_cost_usd"]
        run["steps"].append(step_cost)

        queries = step_cost["web_search_queries"]
        queries_str = " | ".join(queries) if queries else "-"

        run["rows"].append(
            [
                agent_name,
                f"{elapsed_s:.3f}s",
                in_tok,
                out_tok,
                queries_str,
                cached_tok,
                thoughts_tok,
                f"${step_cost['total_cost_usd']:.6f}",
            ]
        )
        return None

    async def on_model_error_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> Optional[LlmResponse]:
        logger.warning(
            "[%s] Model error in agent '%s' (invocation=%s): %s: %s",
            self.name,
            callback_context.agent_name,
            callback_context.invocation_id[:8],
            type(error).__name__,
            error,
        )
        return None

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        run = self._runs.pop(invocation_context.invocation_id, None)
        if not run or not run["rows"]:
            return None

        total_s = max(0.0, time.perf_counter() - run["t0"])
        cost_summary = aggregate_invocation_cost(run["steps"])
        completed_record = {
            "invocation_id": invocation_context.invocation_id,
            "latency_seconds": round(total_s, 4),
            "steps": run["steps"],
            "cost_summary": cost_summary,
        }

        self._completed_runs[invocation_context.invocation_id] = (
            completed_record
        )
        while len(self._completed_runs) > self._max_completed_runs:
            self._completed_runs.popitem(last=False)

        req_collector = _REQUEST_TELEMETRY_VAR.get()
        if req_collector is not None:
            req_collector.append(completed_record)

        total_tok = cost_summary["total_tokens"]
        est_cost = cost_summary["total_cost_usd"]
        cost_1k = cost_summary["cost_per_1k_requests_usd"]
        title = (
            f"ADK Plugin Telemetry | invocation={invocation_context.invocation_id[:8]} "
            f"| total_latency={total_s:.3f}s | total_tokens={total_tok} "
            f"(in={run['in_tokens']}, cached={run['cached_tokens']}, "
            f"out={run['out_tokens']}, thoughts={run['thoughts_tokens']}) "
            f"| est_cost=${est_cost:.6f} (${cost_1k:.3f}/1k reqs)"
        )
        logger.info(
            format_table_for_logs(
                title=title,
                rows=run["rows"],
                headers=[
                    "Agent",
                    "Latency",
                    "In Tokens",
                    "Out Tokens",
                    "Google Search Grounding Queries",
                    "Cached In",
                    "Thoughts",
                    "Est. Cost ($)",
                ],
                width=118,
            )
        )
        return None

    async def on_run_error_callback(
        self, *, invocation_context: InvocationContext, error: Exception
    ) -> None:
        self._runs.pop(invocation_context.invocation_id, None)
        return None


def build_plugins(enabled: bool = ENABLE_TELEMETRY_PLUGIN) -> List[BasePlugin]:
    """Returns configured ADK application plugins when enabled."""
    return [ExecutionTelemetryPlugin()] if enabled else []
