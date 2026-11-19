# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Cross-cutting ADK BasePlugin for workflow latency, token usage, and search grounding telemetry."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin

from app.app_utils.logging import format_table_for_logs, setup_logging
from app.config import ENABLE_TELEMETRY_PLUGIN

logger = setup_logging(name=__name__)


class ExecutionTelemetryPlugin(BasePlugin):
    """ADK runtime plugin capturing per-agent latency, token counts (including cached & thinking), and Google Search queries.

    State is isolated per ``invocation_id`` so a single plugin instance attached to ``App``
    remains safe across concurrent asynchronous FastAPI requests. All callbacks return ``None``
    so agent outputs, routing decisions, and schemas pass through untouched.
    """

    def __init__(self, name: str = "execution_telemetry") -> None:
        super().__init__(name=name)
        self._runs: Dict[str, Dict[str, Any]] = {}

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        self._runs[invocation_context.invocation_id] = {
            "t0": time.perf_counter(),
            "agent_starts": {},
            "rows": [],
            "in_tokens": 0,
            "out_tokens": 0,
            "cached_tokens": 0,
            "thoughts_tokens": 0,
        }
        return None

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        run = self._runs.get(callback_context.invocation_id)
        if run is not None:
            run["agent_starts"][agent.name] = time.perf_counter()
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        if llm_response.partial:
            return None

        run = self._runs.get(callback_context.invocation_id)
        if run is None:
            return None

        agent_name = callback_context.agent_name
        started = run["agent_starts"].get(agent_name, run["t0"])
        elapsed_s = max(0.0, time.perf_counter() - started)

        usage = llm_response.usage_metadata
        in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
        out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
        cached_tok = int(getattr(usage, "cached_content_token_count", 0) or 0)
        thoughts_tok = int(getattr(usage, "thoughts_token_count", 0) or 0)

        run["in_tokens"] += in_tok
        run["out_tokens"] += out_tok
        run["cached_tokens"] += cached_tok
        run["thoughts_tokens"] += thoughts_tok

        gm = llm_response.grounding_metadata
        raw_queries = getattr(gm, "web_search_queries", None) or [] if gm else []
        queries = [str(q).strip() for q in raw_queries if str(q).strip()]
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
        total_tok = run["in_tokens"] + run["out_tokens"] + run["thoughts_tokens"]
        title = (
            f"ADK Plugin Telemetry | invocation={invocation_context.invocation_id[:8]} "
            f"| total_latency={total_s:.3f}s | total_tokens={total_tok} "
            f"(in={run['in_tokens']}, cached={run['cached_tokens']}, "
            f"out={run['out_tokens']}, thoughts={run['thoughts_tokens']})"
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
                ],
                width=110,
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
