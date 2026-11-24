# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Step 2: Run 1-turn agent inference, AI cost estimation, and GEAP evaluation."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.evaluation.eval_set import EvalSet
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm
import vertexai
from vertexai import types as vertex_types

from app.agent import APP_NAME, app, conversational
from app.app_utils.logging import format_table_for_logs, setup_logging
from tests.eval.metrics.cost_estimator import (
    DEFAULT_PRICING_CONFIG_PATH,
    aggregate_invocation_cost,
    build_dataset_cost_overview,
    extract_step_usage_and_cost,
    load_pricing_catalog,
    parse_model_overrides,
    reprice_traced_records,
)
from tests.eval.metrics.custom_metrics import (
    CUSTOM_PYTHON_METRICS_REGISTRY,
    build_evaluation_metrics,
)
from tests.eval.scripts.generate_scenarios import build_agent_adapter_from_workflow

logger = setup_logging(name=__name__)

EVAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EVALSET_PATH = os.path.join(
    EVAL_DIR, "datasets", "conversational_synthetic.evalset.json"
)
DEFAULT_EVAL_CONFIG_PATH = os.path.join(
    EVAL_DIR, "configs", "eval_config.json"
)
DEFAULT_RESULTS_DIR = os.path.join(EVAL_DIR, "results")
DEFAULT_BASELINE_DIR = os.path.join(DEFAULT_RESULTS_DIR, "baseline")
DEFAULT_HISTORY_PATH = os.path.join(
    DEFAULT_RESULTS_DIR, "experiments_history.md"
)

TRACES_FILENAME = "eval_dataset_with_traces.json"
RESULTS_FILENAME = "eval_results.json"
SUMMARY_FILENAME = "eval_summary.md"
METADATA_FILENAME = "run_metadata.json"


def resolve_pricing_catalog_for_eval(
    eval_config: Mapping[str, Any],
    eval_config_path: str = DEFAULT_EVAL_CONFIG_PATH,
    pricing_config_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolves and loads pricing_config.json from CLI override, env, eval_config, or app defaults."""
    if pricing_config_override:
        return load_pricing_catalog(pricing_config_override)
    if os.getenv("PRICING_CONFIG_PATH"):
        return load_pricing_catalog(os.getenv("PRICING_CONFIG_PATH"))
    rel_or_abs = eval_config.get("pricing_config_path")
    if isinstance(rel_or_abs, str) and rel_or_abs.strip():
        candidate = (
            rel_or_abs
            if os.path.isabs(rel_or_abs)
            else os.path.normpath(
                os.path.join(os.path.dirname(eval_config_path), rel_or_abs)
            )
        )
        if os.path.isfile(candidate):
            return load_pricing_catalog(candidate)
    return load_pricing_catalog(DEFAULT_PRICING_CONFIG_PATH)


def extract_agent_models_map(workflow: Workflow) -> Dict[str, str]:
    """Maps each workflow sub-agent name to its configured Gemini model string."""
    models_map: Dict[str, str] = {}
    graph = workflow._require_graph()
    for node in graph.nodes:
        if not isinstance(node, Agent):
            continue
        model_obj = getattr(node, "model", None)
        model_name = getattr(model_obj, "model", str(model_obj))
        models_map[node.name] = str(model_name)
    return models_map


def build_agent_info() -> vertex_types.evals.AgentInfo:
    """Builds Vertex AI AgentInfo with explicit multi-agent workflow topology."""
    workflow_adapter = build_agent_adapter_from_workflow(conversational)
    agent_info = vertex_types.evals.AgentInfo.load_from_agent(workflow_adapter)

    if agent_info.agents:
        if "engage" in agent_info.agents:
            agent_info.agents["engage"].sub_agents = [
                "filter",
                "filter_smart",
                "inspiration",
            ]
        if "filter" in agent_info.agents:
            agent_info.agents["filter"].sub_agents = []
        if "filter_smart" in agent_info.agents:
            agent_info.agents["filter_smart"].sub_agents = [
                "json_parser",
            ]
        if "json_parser" in agent_info.agents:
            agent_info.agents["json_parser"].sub_agents = []
        if "inspiration" in agent_info.agents:
            agent_info.agents["inspiration"].sub_agents = []

    return agent_info


def extract_grounding_search_events(
    raw_event: Any,
    author: str,
    event_time: datetime,
) -> tuple[
    List[vertex_types.evals.AgentEvent],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """Bridges ADK server-side GoogleSearchTool grounding_metadata into explicit FunctionCall/FunctionResponse events."""
    gm = getattr(raw_event, "grounding_metadata", None)
    if not gm:
        return [], [], []

    queries = [
        str(q).strip()
        for q in (getattr(gm, "web_search_queries", None) or [])
        if str(q).strip()
    ]
    sources: List[Dict[str, str]] = []
    for chunk in getattr(gm, "grounding_chunks", None) or []:
        web = getattr(chunk, "web", None)
        if web:
            sources.append(
                {
                    "title": str(getattr(web, "title", "") or ""),
                    "uri": str(getattr(web, "uri", "") or ""),
                    "domain": str(getattr(web, "domain", "") or ""),
                }
            )

    grounded_claims: List[str] = []
    for support in getattr(gm, "grounding_supports", None) or []:
        seg = getattr(support, "segment", None)
        seg_text = getattr(seg, "text", None) if seg else None
        if seg_text:
            grounded_claims.append(str(seg_text))

    if not queries and not sources and not grounded_claims:
        return [], [], []

    combined_query = (
        " | ".join(queries) if queries else "airline flight amenities research"
    )
    response_payload: Dict[str, Any] = {
        "queries": queries,
        "sources": sources,
        "grounded_claims": grounded_claims,
    }

    call_content = genai_types.Content(
        role="model",
        parts=[
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name="google_search",
                    args={"query": combined_query},
                )
            )
        ],
    )
    resp_content = genai_types.Content(
        role="model",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    name="google_search",
                    response=response_payload,
                )
            )
        ],
    )

    agent_events = [
        vertex_types.evals.AgentEvent(
            author=author,
            content=call_content,
            event_time=event_time,
        ),
        vertex_types.evals.AgentEvent(
            author=author,
            content=resp_content,
            event_time=event_time,
        ),
    ]
    inter_events = [
        {
            "event_id": str(uuid4())[:8],
            "author": author,
            "content": call_content.model_dump(mode="json", exclude_none=True),
            "creation_timestamp": event_time.isoformat(),
        },
        {
            "event_id": str(uuid4())[:8],
            "author": author,
            "content": resp_content.model_dump(mode="json", exclude_none=True),
            "creation_timestamp": event_time.isoformat(),
        },
    ]
    tool_call_records = [
        {
            "tool_name": "google_search",
            "author": author,
            "args": {"query": combined_query},
            "response": response_payload,
        }
    ]
    return agent_events, inter_events, tool_call_records


async def run_single_case_inference(
    eval_case: Any,
    agents_map: Dict[str, vertex_types.evals.AgentConfig],
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    agent_models_map: Optional[Mapping[str, str]] = None,
    pricing_catalog: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Executes 1-turn inference for a single EvalCase and builds its trace & cost record."""
    eval_id = eval_case.eval_id or str(uuid4())[:8]
    scenario = eval_case.conversation_scenario
    starting_prompt = scenario.starting_prompt if scenario else ""
    conversation_plan = scenario.conversation_plan if scenario else ""
    models_lookup = dict(agent_models_map or extract_agent_models_map(conversational))
    catalog = pricing_catalog or load_pricing_catalog()

    session_input_dict = (
        eval_case.session_input.model_dump(mode="json", exclude_none=True)
        if eval_case.session_input
        else {"app_name": APP_NAME, "user_id": "eval_user", "state": {}}
    )
    initial_state = dict(session_input_dict.get("state") or {})
    initial_state["user_message"] = starting_prompt
    session_input_dict["state"] = initial_state

    base_context_payload: Dict[str, Any] = {
        "flights_search_input": initial_state.get("flights_search_input"),
        "flights_input": initial_state.get("flights_input"),
    }

    async with semaphore:
        for attempt in range(max_retries):
            session_id = str(uuid4())
            user_id = session_input_dict.get("user_id") or f"eval_user_{eval_id}"
            service = InMemorySessionService()
            await service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state=dict(initial_state),
            )
            runner = Runner(
                app=app,
                app_name=APP_NAME,
                session_service=service,
            )

            try:
                user_content = genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=starting_prompt)],
                )
                turn_events: List[vertex_types.evals.AgentEvent] = [
                    vertex_types.evals.AgentEvent(
                        author="user",
                        content=user_content,
                        event_time=datetime.now(timezone.utc),
                    )
                ]
                intermediate_events: List[Dict[str, Any]] = []
                sub_agent_latencies: List[Dict[str, Any]] = []
                sub_agent_usages: List[Dict[str, Any]] = []
                tool_calls_made: List[Dict[str, Any]] = []
                final_response_text = ""

                turn_start_perf = time.perf_counter()
                last_step_perf = turn_start_perf

                async for raw_event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_content,
                ):
                    if not raw_event or getattr(raw_event, "partial", False):
                        continue

                    raw_author = raw_event.author or "conversational"
                    now_perf = time.perf_counter()
                    step_elapsed = round(now_perf - last_step_perf, 4)

                    has_llm_telemetry = (
                        raw_author
                        not in {
                            "user",
                            "finalize_output",
                            "route_engage",
                            "parse_filter_smart",
                        }
                        and (
                            getattr(raw_event, "usage_metadata", None) is not None
                            or getattr(raw_event, "grounding_metadata", None)
                            is not None
                            or bool(
                                (
                                    getattr(raw_event, "custom_metadata", None)
                                    or {}
                                ).get("response_cache_hit")
                            )
                        )
                    )
                    if has_llm_telemetry:
                        sub_agent_usages.append(
                            extract_step_usage_and_cost(
                                author=raw_author,
                                llm_response=raw_event,
                                configured_model=models_lookup.get(raw_author),
                                latency_seconds=step_elapsed,
                                catalog=catalog,
                            )
                        )

                    if not raw_event.content or not raw_event.content.parts:
                        continue

                    author = raw_author
                    if author == "finalize_output":
                        author = "conversational"
                    elif author in {"route_engage", "parse_filter_smart"}:
                        continue

                    last_step_perf = now_perf
                    sub_agent_latencies.append(
                        {
                            "author": author,
                            "latency_seconds": step_elapsed,
                        }
                    )

                    content_dump = raw_event.content.model_dump(
                        mode="json", exclude_none=True
                    )
                    if author != "user":
                        content_dump["role"] = "model"
                    validated_content = genai_types.Content.model_validate(
                        content_dump
                    )
                    event_time = (
                        datetime.fromtimestamp(
                            raw_event.timestamp, tz=timezone.utc
                        )
                        if getattr(raw_event, "timestamp", None)
                        else datetime.now(timezone.utc)
                    )

                    (
                        search_agent_events,
                        search_inter_events,
                        search_tool_records,
                    ) = extract_grounding_search_events(
                        raw_event=raw_event,
                        author=author,
                        event_time=event_time,
                    )
                    if search_agent_events:
                        turn_events.extend(search_agent_events)
                        intermediate_events.extend(search_inter_events)
                        tool_calls_made.extend(search_tool_records)

                    turn_events.append(
                        vertex_types.evals.AgentEvent(
                            author=author,
                            content=validated_content,
                            event_time=event_time,
                        )
                    )

                    for part in validated_content.parts or []:
                        if part.text:
                            final_response_text = part.text

                    intermediate_events.append(
                        {
                            "event_id": getattr(raw_event, "id", None)
                            or str(uuid4())[:8],
                            "author": author,
                            "content": content_dump,
                            "creation_timestamp": event_time.isoformat(),
                        }
                    )

                total_latency_sec = round(
                    time.perf_counter() - turn_start_perf, 4
                )

                if len(intermediate_events) > 1:
                    intermediate_events = intermediate_events[:-1]
                else:
                    intermediate_events = []

                context_payload = dict(base_context_payload)
                if tool_calls_made:
                    context_payload["google_search_grounding"] = tool_calls_made
                context_str = json.dumps(context_payload, ensure_ascii=False)

                agent_data = vertex_types.evals.AgentData(
                    agents=agents_map,
                    turns=[
                        vertex_types.evals.ConversationTurn(
                            turn_index=0,
                            turn_id="turn_0",
                            events=turn_events,
                        )
                    ],
                )
                cost_summary = aggregate_invocation_cost(sub_agent_usages)

                return {
                    "eval_id": eval_id,
                    "prompt": starting_prompt,
                    "conversation_plan": conversation_plan,
                    "context": context_str,
                    "tool_calls": json.dumps(
                        tool_calls_made, ensure_ascii=False
                    ),
                    "session_inputs": session_input_dict,
                    "response": final_response_text,
                    "latency_seconds": total_latency_sec,
                    "sub_agent_latencies_seconds": sub_agent_latencies,
                    "sub_agent_usages": sub_agent_usages,
                    "cost_summary": cost_summary,
                    "intermediate_events": intermediate_events,
                    "agent_data": agent_data.model_dump(
                        mode="json", exclude_none=True
                    ),
                }

            except Exception as exc:
                if attempt < max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"Case {eval_id} attempt {attempt + 1}/{max_retries} failed ({exc}). "
                        f"Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                else:
                    total_latency_sec = round(
                        time.perf_counter() - turn_start_perf, 4
                    )
                    logger.error(
                        f"Case {eval_id} failed after {max_retries} attempts: {exc}"
                    )
                    error_json = json.dumps({"error": str(exc)})
                    user_content = genai_types.Content(
                        role="user",
                        parts=[genai_types.Part(text=starting_prompt)],
                    )
                    model_content = genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(text=error_json)],
                    )
                    fallback_agent_data = vertex_types.evals.AgentData(
                        agents=agents_map,
                        turns=[
                            vertex_types.evals.ConversationTurn(
                                turn_index=0,
                                turn_id="turn_0",
                                events=[
                                    vertex_types.evals.AgentEvent(
                                        author="user", content=user_content
                                    ),
                                    vertex_types.evals.AgentEvent(
                                        author="conversational",
                                        content=model_content,
                                    ),
                                ],
                            )
                        ],
                    )
                    return {
                        "eval_id": eval_id,
                        "prompt": starting_prompt,
                        "conversation_plan": conversation_plan,
                        "context": json.dumps(
                            base_context_payload, ensure_ascii=False
                        ),
                        "tool_calls": "[]",
                        "session_inputs": session_input_dict,
                        "response": error_json,
                        "latency_seconds": total_latency_sec,
                        "sub_agent_latencies_seconds": [],
                        "sub_agent_usages": [],
                        "cost_summary": aggregate_invocation_cost([]),
                        "intermediate_events": [],
                        "agent_data": fallback_agent_data.model_dump(
                            mode="json", exclude_none=True
                        ),
                    }


async def run_batch_inference(
    eval_set: EvalSet,
    agent_info: vertex_types.evals.AgentInfo,
    limit: Optional[int] = None,
    concurrency: int = 4,
    pricing_catalog: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Runs 1-turn inference across EvalSet cases with bounded concurrency."""
    cases = eval_set.eval_cases
    if limit is not None and limit > 0:
        cases = cases[:limit]

    logger.info(
        f"Running 1-turn inference on {len(cases)} EvalCase(s) (concurrency={concurrency})..."
    )
    semaphore = asyncio.Semaphore(concurrency)
    agents_map = agent_info.agents or {}
    agent_models_map = extract_agent_models_map(conversational)
    catalog = pricing_catalog or load_pricing_catalog()

    tasks = [
        run_single_case_inference(
            case,
            agents_map,
            semaphore,
            agent_models_map=agent_models_map,
            pricing_catalog=catalog,
        )
        for case in cases
    ]

    results: List[Dict[str, Any]] = []
    for coro in tqdm(
        asyncio.as_completed(tasks),
        total=len(tasks),
        desc="Phase 2A: 1-Turn Agent Inference",
    ):
        results.append(await coro)

    order_map = {case.eval_id: idx for idx, case in enumerate(cases)}
    results.sort(key=lambda r: order_map.get(r["eval_id"], 999999))
    return results


def sanitize_run_name(run_name: str) -> str:
    """Sanitizes a run name for safe filesystem directory naming."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", run_name.strip()).strip("_")
    return cleaned or "run"


def extract_git_info() -> Dict[str, Any]:
    """Captures current git commit SHA, branch, and working tree dirty status."""
    git_info: Dict[str, Any] = {
        "commit_sha": "unknown",
        "branch": "unknown",
        "dirty": False,
    }
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=EVAL_DIR,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=EVAL_DIR,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=EVAL_DIR,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        git_info["commit_sha"] = sha
        git_info["branch"] = branch
        git_info["dirty"] = bool(status)
    except Exception:
        pass
    return git_info


def extract_agent_config_snapshot(workflow: Workflow) -> Dict[str, Any]:
    """Extracts model, parameters, tools, and prompt hashes for all workflow sub-agents."""
    snapshot: Dict[str, Any] = {}
    graph = workflow._require_graph()

    for node in graph.nodes:
        if not isinstance(node, Agent):
            continue

        model_obj = getattr(node, "model", None)
        model_name = getattr(model_obj, "model", str(model_obj))
        client_kwargs = getattr(model_obj, "client_kwargs", None)
        use_interactions_api = getattr(model_obj, "use_interactions_api", None)

        instruction_str = str(getattr(node, "instruction", "") or "")
        instruction_hash = hashlib.sha256(
            instruction_str.encode("utf-8")
        ).hexdigest()[:12]

        tools_list = [
            getattr(t, "name", str(t))
            for t in (getattr(node, "tools", None) or [])
        ]

        planner_obj = getattr(node, "planner", None)
        planner_info = None
        if planner_obj is not None:
            thinking_cfg = getattr(planner_obj, "thinking_config", None)
            planner_info = {
                "type": type(planner_obj).__name__,
                "thinking_config": (
                    thinking_cfg.model_dump(exclude_none=True)
                    if hasattr(thinking_cfg, "model_dump")
                    else str(thinking_cfg)
                ),
            }

        gen_cfg = getattr(node, "generate_content_config", None)
        gen_cfg_dict = (
            gen_cfg.model_dump(exclude_none=True)
            if hasattr(gen_cfg, "model_dump")
            else None
        )

        snapshot[node.name] = {
            "model": model_name,
            "client_kwargs": client_kwargs,
            "use_interactions_api": use_interactions_api,
            "instruction_sha256": instruction_hash,
            "instruction_length": len(instruction_str),
            "include_contents": getattr(node, "include_contents", None),
            "tools": tools_list,
            "planner": planner_info,
            "generate_content_config": gen_cfg_dict,
        }

    return snapshot


def find_latest_baseline_dir(
    results_dir: str,
    exclude_run_id: Optional[str] = None,
) -> Optional[str]:
    """Finds the most recent timestamped run directory marked with is_baseline=True."""
    if not os.path.isdir(results_dir):
        return None
    for entry in sorted(os.listdir(results_dir), reverse=True):
        if entry == exclude_run_id:
            continue
        candidate_dir = os.path.join(results_dir, entry)
        if not os.path.isdir(candidate_dir):
            continue
        meta_path = os.path.join(candidate_dir, METADATA_FILENAME)
        results_path = os.path.join(candidate_dir, RESULTS_FILENAME)
        if os.path.isfile(meta_path) and os.path.isfile(results_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("is_baseline"):
                    return candidate_dir
            except Exception:
                continue
    return None


def resolve_traces_source_path(
    reuse_run: Optional[str],
    skip_inference: bool,
    results_dir: str,
    exclude_run_id: Optional[str] = None,
) -> Optional[str]:
    """Resolves the path to an existing eval_dataset_with_traces.json when reusing traces."""
    if reuse_run:
        if os.path.isfile(reuse_run):
            return reuse_run
        if os.path.isdir(reuse_run):
            candidate = os.path.join(reuse_run, TRACES_FILENAME)
            if os.path.isfile(candidate):
                return candidate
        candidate_in_results = os.path.join(
            results_dir, reuse_run, TRACES_FILENAME
        )
        if os.path.isfile(candidate_in_results):
            return candidate_in_results
        if os.path.isdir(results_dir):
            suffix_matches = sorted(
                [
                    d
                    for d in os.listdir(results_dir)
                    if d != exclude_run_id
                    and os.path.isdir(os.path.join(results_dir, d))
                    and d.endswith(f"_{reuse_run}")
                    and os.path.isfile(
                        os.path.join(results_dir, d, TRACES_FILENAME)
                    )
                ],
                reverse=True,
            )
            if suffix_matches:
                return os.path.join(
                    results_dir, suffix_matches[0], TRACES_FILENAME
                )
        raise FileNotFoundError(
            f"Could not find {TRACES_FILENAME} for --reuse-run '{reuse_run}'"
        )

    if skip_inference:
        latest_base_dir = find_latest_baseline_dir(
            results_dir=results_dir, exclude_run_id=exclude_run_id
        )
        if latest_base_dir:
            baseline_traces = os.path.join(latest_base_dir, TRACES_FILENAME)
            if os.path.isfile(baseline_traces):
                return baseline_traces
        raise FileNotFoundError(
            f"--skip-inference was set, but no baseline traces found in {results_dir}"
        )

    return None


def load_reference_baseline(
    baseline_run: Optional[str],
    results_dir: str,
    exclude_run_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Loads the reference baseline eval_results.json from --baseline-run or the latest baseline folder."""
    if baseline_run:
        if os.path.isfile(baseline_run):
            target_path = baseline_run
        elif os.path.isdir(baseline_run):
            target_path = os.path.join(baseline_run, RESULTS_FILENAME)
        else:
            target_path = os.path.join(
                results_dir, baseline_run, RESULTS_FILENAME
            )
        if os.path.isfile(target_path):
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"Reference baseline not found at {target_path}")
        return None

    latest_base_dir = find_latest_baseline_dir(
        results_dir=results_dir, exclude_run_id=exclude_run_id
    )
    if latest_base_dir:
        default_baseline_results = os.path.join(
            latest_base_dir, RESULTS_FILENAME
        )
        if os.path.isfile(default_baseline_results):
            with open(default_baseline_results, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def evaluate_local_python_metrics_only(
    traced_records: List[Dict[str, Any]],
    eval_config: Mapping[str, Any],
    existing_source_report: Optional[Mapping[str, Any]] = None,
) -> vertex_types.EvaluationResult:
    """Evaluates deterministic custom_python metrics locally at $0 API cost (preserving existing LLM scores if available)."""
    prior_case_metrics: Dict[int, Dict[str, Any]] = {}
    if existing_source_report:
        for c in existing_source_report.get("eval_case_results") or []:
            c_idx = int(c.get("eval_case_index", -1))
            if c_idx >= 0 and isinstance(c.get("metric_results"), dict):
                prior_case_metrics[c_idx] = c["metric_results"]

    configured_metrics = list(eval_config.get("metrics") or [])
    scores_by_metric: Dict[str, List[float]] = {}
    errors_by_metric: Dict[str, int] = {}
    eval_case_results: List[vertex_types.common.EvalCaseResult] = []

    for idx, rec in enumerate(traced_records):
        instance = dict(rec)
        # Match Vertex Eval SDK instance format for response text when evaluate_schema_and_contract runs
        resp_val = instance.get("response")
        if isinstance(resp_val, str):
            instance["response"] = {"parts": [{"text": resp_val}]}

        sdk_metric_results: Dict[str, Any] = {}
        prior_map = prior_case_metrics.get(idx, {})

        for m_cfg in configured_metrics:
            m_name = m_cfg.get("name")
            m_type = m_cfg.get("type")
            if not m_name:
                continue

            if m_type == "custom_python" and m_name in CUSTOM_PYTHON_METRICS_REGISTRY:
                fn = CUSTOM_PYTHON_METRICS_REGISTRY[m_name]
                out = fn(instance)
                raw_score = out.get("score")
                score_val = float(raw_score) if raw_score is not None else None
                sdk_metric_results[m_name] = (
                    vertex_types.common.EvalCaseMetricResult(
                        metric_name=m_name,
                        score=score_val,
                        explanation=str(out.get("explanation") or ""),
                    )
                )
                if score_val is not None:
                    scores_by_metric.setdefault(m_name, []).append(score_val)
            elif m_name in prior_map and isinstance(prior_map[m_name], dict):
                restored = (
                    vertex_types.common.EvalCaseMetricResult.model_validate(
                        prior_map[m_name]
                    )
                )
                sdk_metric_results[m_name] = restored
                if restored.score is not None and restored.error_message is None:
                    scores_by_metric.setdefault(m_name, []).append(
                        float(restored.score)
                    )
                elif restored.error_message:
                    errors_by_metric[m_name] = errors_by_metric.get(m_name, 0) + 1

        eval_case_results.append(
            vertex_types.common.EvalCaseResult(
                eval_case_index=idx,
                response_candidate_results=[
                    vertex_types.common.ResponseCandidateResult(
                        response_index=0,
                        metric_results=sdk_metric_results,
                    )
                ],
            )
        )

    summary_metrics: List[vertex_types.common.AggregatedMetricResult] = []
    n_total = len(traced_records)
    for m_cfg in configured_metrics:
        m_name = m_cfg.get("name")
        if not m_name:
            continue
        vals = scores_by_metric.get(m_name, [])
        err_cnt = errors_by_metric.get(m_name, 0)
        if not vals and m_cfg.get("type") != "custom_python":
            continue
        mean_s = (sum(vals) / len(vals)) if vals else None
        if len(vals) >= 2 and mean_s is not None:
            variance = sum((v - mean_s) ** 2 for v in vals) / (len(vals) - 1)
            stdev_s = math.sqrt(variance)
        elif len(vals) == 1:
            stdev_s = 0.0
        else:
            stdev_s = None

        summary_metrics.append(
            vertex_types.common.AggregatedMetricResult(
                metric_name=m_name,
                mean_score=mean_s,
                stdev_score=stdev_s,
                num_cases_total=n_total,
                num_cases_valid=len(vals),
                num_cases_error=err_cnt,
            )
        )

    return vertex_types.EvaluationResult(
        eval_case_results=eval_case_results,
        summary_metrics=summary_metrics,
    )


def serialize_evaluation_results(
    eval_result: vertex_types.EvaluationResult,
    traced_records: List[Dict[str, Any]],
    eval_config: Dict[str, Any],
    run_id: str,
    run_name: str,
    description: str,
    timestamp_iso: str,
    baseline_report: Optional[Dict[str, Any]] = None,
    pricing_catalog: Optional[Mapping[str, Any]] = None,
    inference_reused: bool = False,
    evaluation_executed: bool = True,
) -> Dict[str, Any]:
    """Combines summary metrics, baseline deltas, AI cost overview, and per-case results into a JSON report."""
    metric_cfg_map = {m["name"]: m for m in eval_config.get("metrics", [])}

    baseline_scores: Dict[str, Optional[float]] = {}
    baseline_run_id: Optional[str] = None
    baseline_cost_overview: Optional[Dict[str, Any]] = None
    if baseline_report and baseline_report.get("run_id") != run_id:
        baseline_run_id = baseline_report.get("run_id", "baseline")
        baseline_cost_overview = baseline_report.get("cost_overview")
        for b_item in baseline_report.get("summary_metrics", []):
            baseline_scores[b_item["metric_name"]] = b_item.get("mean_score")

    per_case_list: List[Dict[str, Any]] = []
    case_scores_by_metric: Dict[str, List[float]] = {}

    for case_res in eval_result.eval_case_results or []:
        idx = case_res.eval_case_index or 0
        record = traced_records[idx] if 0 <= idx < len(traced_records) else {}

        agent_trajectory: List[str] = []
        agent_data_dict = record.get("agent_data") or {}
        for turn in agent_data_dict.get("turns") or []:
            for ev in turn.get("events") or []:
                author = ev.get("author")
                if author and author != "user":
                    if not agent_trajectory or agent_trajectory[-1] != author:
                        agent_trajectory.append(author)

        raw_tool_calls = record.get("tool_calls")
        if isinstance(raw_tool_calls, str):
            try:
                parsed_tool_calls = json.loads(raw_tool_calls)
            except json.JSONDecodeError:
                parsed_tool_calls = []
        elif isinstance(raw_tool_calls, list):
            parsed_tool_calls = raw_tool_calls
        else:
            parsed_tool_calls = []

        cand_results = case_res.response_candidate_results or []
        metric_map: Dict[str, Any] = {}
        if cand_results and cand_results[0].metric_results:
            for m_name, m_res in cand_results[0].metric_results.items():
                metric_map[m_name] = m_res.model_dump(
                    mode="json", exclude_none=True
                )
                if m_res.score is not None and m_res.error_message is None:
                    case_scores_by_metric.setdefault(m_name, []).append(
                        float(m_res.score)
                    )

        per_case_list.append(
            {
                "eval_case_index": idx,
                "eval_id": record.get("eval_id"),
                "prompt": record.get("prompt"),
                "conversation_plan": record.get("conversation_plan"),
                "agent_trajectory": agent_trajectory,
                "tool_calls": parsed_tool_calls,
                "latency_seconds": record.get("latency_seconds"),
                "sub_agent_latencies_seconds": record.get(
                    "sub_agent_latencies_seconds"
                ),
                "sub_agent_usages": record.get("sub_agent_usages"),
                "cost_summary": record.get("cost_summary"),
                "response": record.get("response"),
                "metric_results": metric_map,
            }
        )

    summary_list: List[Dict[str, Any]] = []
    task_success_mean: Optional[float] = None

    for agg in eval_result.summary_metrics or []:
        m_name = agg.metric_name or "unknown"
        m_cfg = metric_cfg_map.get(m_name, {})
        threshold = float(m_cfg.get("threshold", 0.8))
        direction = m_cfg.get("direction", "higher_is_better")
        unit = m_cfg.get("unit", "")
        mean_val = agg.mean_score
        if m_name == "multi_turn_task_success_v1" and mean_val is not None:
            task_success_mean = float(mean_val)

        if mean_val is not None:
            if direction == "lower_is_better":
                passed = mean_val <= threshold
            else:
                passed = mean_val >= threshold
        else:
            passed = False

        pass_rate = agg.pass_rate
        if pass_rate is None:
            valid_scores = case_scores_by_metric.get(m_name, [])
            if valid_scores:
                if direction == "lower_is_better":
                    passing_count = sum(
                        1 for s in valid_scores if s <= threshold
                    )
                else:
                    passing_count = sum(
                        1 for s in valid_scores if s >= threshold
                    )
                pass_rate = passing_count / len(valid_scores)

        base_val = baseline_scores.get(m_name)
        delta_val = (
            (mean_val - base_val)
            if (mean_val is not None and base_val is not None)
            else None
        )

        summary_list.append(
            {
                "metric_name": m_name,
                "direction": direction,
                "unit": unit,
                "mean_score": mean_val,
                "baseline_mean_score": base_val,
                "delta_mean_score": delta_val,
                "pass_rate": pass_rate,
                "stdev_score": agg.stdev_score,
                "threshold": threshold,
                "passed_threshold": passed,
                "num_cases_total": agg.num_cases_total,
                "num_cases_valid": agg.num_cases_valid,
                "num_cases_error": agg.num_cases_error,
            }
        )

    cost_overview = build_dataset_cost_overview(
        traced_records=traced_records,
        eval_config=eval_config,
        catalog=pricing_catalog,
        task_success_mean_score=task_success_mean,
        inference_reused=inference_reused,
        evaluation_executed=evaluation_executed,
    )

    return {
        "run_id": run_id,
        "run_name": run_name,
        "description": description,
        "baseline_run_id": baseline_run_id,
        "eval_set_id": eval_config.get(
            "eval_set_id", "conversational_synthetic"
        ),
        "timestamp": timestamp_iso,
        "num_cases_evaluated": len(traced_records),
        "summary_metrics": summary_list,
        "cost_overview": cost_overview,
        "baseline_cost_overview": baseline_cost_overview,
        "eval_case_results": per_case_list,
    }


def _build_cost_markdown_sections(report: Mapping[str, Any]) -> str:
    """Formats AI cost breakdown, sub-agent attribution, and analytical caching tables for eval_summary.md."""
    cost_ov = report.get("cost_overview")
    if not isinstance(cost_ov, dict):
        return ""

    base_ov = report.get("baseline_cost_overview")
    has_base_cost = isinstance(base_ov, dict) and "cost_per_1k_requests_usd" in base_ov

    def _fmt_usd_delta(cur: Optional[float], base_key: str) -> tuple[str, str]:
        if not has_base_cost or not isinstance(base_ov, dict):
            return "-", "-"
        b_val = base_ov.get(base_key)
        if cur is None or b_val is None:
            return "N/A", "N/A"
        diff = float(cur) - float(b_val)
        return f"${float(b_val):.4f}", f"{diff:+.4f}"

    cost_1k = float(cost_ov.get("cost_per_1k_requests_usd", 0.0))
    tok_1k = float(cost_ov.get("llm_token_cost_per_1k_usd", 0.0))
    gnd_1k = float(cost_ov.get("search_grounding_cost_per_1k_usd", 0.0))
    qual_adj = cost_ov.get("cost_per_1k_successful_tasks_usd")
    tok_avgs = cost_ov.get("token_averages_per_request") or {}
    wf_eff = cost_ov.get("workflow_efficiency") or {}
    judge_est = cost_ov.get("eval_judge_overhead_estimate") or {}

    kpi_rows = [
        [
            "Total SUT Cost / 1,000 Requests",
            f"${cost_1k:.4f}",
            *_fmt_usd_delta(cost_1k, "cost_per_1k_requests_usd"),
            "LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)",
        ],
        [
            "LLM Token-Only Cost / 1,000 Requests",
            f"${tok_1k:.4f} ({cost_ov.get('llm_token_share_of_cost_pct', 0.0):.1f}%)",
            *_fmt_usd_delta(tok_1k, "llm_token_cost_per_1k_usd"),
            "Uncached input + cached input + visible output + thinking tokens",
        ],
        [
            "Google Search Grounding Cost / 1,000 Requests",
            f"${gnd_1k:.4f} ({cost_ov.get('search_grounding_share_of_cost_pct', 0.0):.1f}%)",
            *_fmt_usd_delta(gnd_1k, "search_grounding_cost_per_1k_usd"),
            f"Grounded turns: {wf_eff.get('grounded_turn_rate_pct', 0.0):.1f}% (avg {wf_eff.get('mean_search_queries_per_request', 0.0):.2f} queries/req)",
        ],
        [
            "Quality-Adjusted Cost / 1,000 Successful Tasks",
            f"${float(qual_adj):.4f}" if qual_adj is not None else "N/A",
            *_fmt_usd_delta(qual_adj, "cost_per_1k_successful_tasks_usd"),
            "Total Cost/1k divided by multi_turn_task_success_v1 mean score",
        ],
        [
            "Per-Request Cost Distribution (Mean / P50 / P95 / Max)",
            (
                f"${cost_ov.get('mean_cost_per_request_usd', 0.0):.5f} / "
                f"${cost_ov.get('p50_cost_per_request_usd', 0.0):.5f} / "
                f"${cost_ov.get('p95_cost_per_request_usd', 0.0):.5f} / "
                f"${cost_ov.get('max_cost_per_request_usd', 0.0):.5f}"
            ),
            "-",
            "-",
            f"Modeled {cost_ov.get('num_cases', 0)}-case batch SUT total: ${cost_ov.get('sut_modeled_run_cost_usd', 0.0):.5f}",
        ],
        [
            "Mean Tokens / Request (Prompt / Cached / Out / Thoughts)",
            (
                f"{tok_avgs.get('mean_prompt_tokens', 0.0):.0f} / "
                f"{tok_avgs.get('mean_cached_input_tokens', 0.0):.0f} / "
                f"{tok_avgs.get('mean_candidates_output_tokens', 0.0):.0f} / "
                f"{tok_avgs.get('mean_thoughts_tokens', 0.0):.0f}"
            ),
            "-",
            "-",
            f"Total avg: {tok_avgs.get('mean_total_tokens', 0.0):.0f} tok (thinking = {tok_avgs.get('thoughts_share_of_output_pct', 0.0):.1f}% of billable output)",
        ],
        [
            "Workflow Calls & Self-Healing JSON Repair Rate",
            f"{wf_eff.get('mean_llm_calls_per_request', 0.0):.2f} calls/req",
            "-",
            "-",
            f"json_parser fallback rate: {wf_eff.get('json_repair_rate_pct', 0.0):.1f}%",
        ],
    ]
    if not has_base_cost:
        kpi_rows = [[r[0], r[1], r[4]] for r in kpi_rows]
        kpi_headers = ["Cost / Efficiency Dimension", "Current Run", "Notes"]
    else:
        kpi_headers = [
            "Cost / Efficiency Dimension",
            "Current Run",
            "Baseline",
            "Delta (Δ)",
            "Notes",
        ]

    kpi_md = tabulate(kpi_rows, headers=kpi_headers, tablefmt="github")

    # Per-sub-agent attribution table
    sub_agent_rows = []
    for ag_name, ag_stats in (cost_ov.get("per_sub_agent_breakdown") or {}).items():
        models_str = ", ".join(ag_stats.get("models") or [])
        sub_agent_rows.append(
            [
                f"`{ag_name}`",
                f"`{models_str}`",
                f"{ag_stats.get('calls', 0)} ({ag_stats.get('case_invocation_rate_pct', 0.0):.1f}%)",
                f"{ag_stats.get('mean_prompt_tokens_per_call', 0.0):.0f}",
                f"{ag_stats.get('mean_output_tokens_per_call', 0.0):.0f}",
                f"{ag_stats.get('mean_thoughts_tokens_per_call', 0.0):.0f}",
                str(ag_stats.get("total_search_queries", 0)),
                f"${ag_stats.get('amortized_cost_per_1k_requests_usd', 0.0):.4f}",
                f"{ag_stats.get('share_of_total_sut_cost_pct', 0.0):.1f}%",
            ]
        )
    sub_agent_md = (
        tabulate(
            sub_agent_rows,
            headers=[
                "Sub-Agent",
                "Model(s)",
                "Calls (Case %)",
                "Avg Prompt Tok",
                "Avg Out Tok",
                "Avg Thoughts Tok",
                "Search Queries",
                "Amortized $/1k Reqs",
                "Share of Cost",
            ],
            tablefmt="github",
        )
        if sub_agent_rows
        else "_No LLM sub-agent telemetry recorded in traces._"
    )

    # Analytical cache-hit projections
    projections = cost_ov.get("analytical_cache_projections") or {}
    resp_proj_rows = [
        [
            f"{p.get('hit_rate_pct', 0.0):.0f}%",
            f"${p.get('effective_cost_per_1k_usd', 0.0):.4f}",
            f"-${p.get('savings_per_1k_usd', 0.0):.4f} (-{p.get('cost_reduction_pct', 0.0):.1f}%)",
            f"{p.get('effective_mean_latency_seconds', 0.0):.3f}s",
        ]
        for p in (projections.get("response_cache_sensitivity") or [])
    ]
    resp_proj_md = tabulate(
        resp_proj_rows,
        headers=[
            "Response Cache Hit Rate",
            "Projected Cost / 1k Reqs",
            "Projected Savings / 1k Reqs",
            "Projected Mean AI Latency",
        ],
        tablefmt="github",
    )

    ctx_proj_rows = [
        [
            f"{p.get('prefix_hit_rate_pct', 0.0):.0f}%",
            f"${p.get('theoretical_effective_cost_per_1k_usd', 0.0):.4f} (-{p.get('theoretical_cost_reduction_pct', 0.0):.1f}%)",
            f"${p.get('threshold_gated_effective_cost_per_1k_usd', 0.0):.4f} (-{p.get('threshold_gated_cost_reduction_pct', 0.0):.1f}%)",
            f"-${p.get('theoretical_input_savings_per_1k_usd', 0.0):.4f}",
        ]
        for p in (projections.get("context_cache_prefix_sensitivity") or [])
    ]
    ctx_proj_md = tabulate(
        ctx_proj_rows,
        headers=[
            "Prefix Cache Hit Rate",
            "Theoretical Cost / 1k (All Prompts)",
            "Threshold-Gated Cost / 1k (>= Min Tok)",
            "Max Input Token Savings / 1k",
        ],
        tablefmt="github",
    )

    elig_map = projections.get("agent_context_cache_eligibility") or {}
    elig_notes = [
        (
            f"`{ag}`: avg `{info.get('mean_prompt_tokens', 0.0):.0f}` prompt tok "
            f"(max `{info.get('max_prompt_tokens', 0)}`, min required `{info.get('min_cache_tokens_required', 4096)}` "
            f"-> `{info.get('eligible_call_rate_pct', 0.0):.0f}%` calls eligible)"
        )
        for ag, info in elig_map.items()
    ]
    elig_line = (
        "\n- **Context Cache Prefix Threshold Eligibility**: "
        + "; ".join(elig_notes)
        + "\n"
        if elig_notes
        else ""
    )

    sut_live_spend = float(cost_ov.get("sut_live_inference_spend_usd", 0.0))
    judge_spend = float(judge_est.get("estimated_judge_cost_usd", 0.0))
    judge_calls = int(judge_est.get("estimated_judge_calls", 0))
    judge_model = judge_est.get("judge_model", "gemini-2.5-flash")

    return (
        f"## AI Cost & Token Breakdown (`{cost_ov.get('pricing_catalog_version')}` — Standard PayGo)\n\n"
        f"{kpi_md}\n\n"
        f"- **Evaluation Run Spend Separation**: SUT live inference spend = `${sut_live_spend:.5f}` "
        f"| Estimated Phase 2B Judge overhead (`{judge_model}`, ~{judge_calls} judge evaluations) = `${judge_spend:.5f}` _(excluded from SUT production cost metrics)_.\n\n"
        f"### Per-Sub-Agent Cost & Token Attribution\n\n"
        f"{sub_agent_md}\n\n"
        f"### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)\n\n"
        f"#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)\n\n"
        f"{resp_proj_md}\n\n"
        f"#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)\n\n"
        f"{ctx_proj_md}\n"
        f"{elig_line}\n"
    )


def log_summary_table(
    report: Dict[str, Any],
    run_metadata: Dict[str, Any],
    summary_output_path: Optional[str] = None,
) -> None:
    """Logs formatted summary & cost tables and saves a Markdown report to the run directory."""
    has_baseline = report.get("baseline_run_id") is not None
    rows = []

    for item in report.get("summary_metrics", []):
        unit = item.get("unit") or ""
        direction = item.get("direction", "higher_is_better")
        mean_str = (
            f"{item['mean_score']:.3f}{unit}"
            if item.get("mean_score") is not None
            else "N/A"
        )
        pass_rate_str = (
            f"{item['pass_rate'] * 100:.1f}%"
            if item.get("pass_rate") is not None
            else "N/A"
        )
        stdev_str = (
            f"{item['stdev_score']:.3f}{unit}"
            if item.get("stdev_score") is not None
            else "N/A"
        )
        op_prefix = "<= " if direction == "lower_is_better" else ">= "
        threshold_str = f"{op_prefix}{item['threshold']:.2f}{unit}"
        status_str = "PASS" if item.get("passed_threshold") else "FAIL"

        if has_baseline:
            base_val = item.get("baseline_mean_score")
            delta_val = item.get("delta_mean_score")
            base_str = (
                f"{base_val:.3f}{unit}" if base_val is not None else "N/A"
            )
            delta_str = (
                f"{delta_val:+.3f}{unit}" if delta_val is not None else "N/A"
            )
            rows.append(
                [
                    item["metric_name"],
                    mean_str,
                    base_str,
                    delta_str,
                    pass_rate_str,
                    stdev_str,
                    threshold_str,
                    f"{item['num_cases_valid']}/{item['num_cases_total']}",
                    status_str,
                ]
            )
        else:
            rows.append(
                [
                    item["metric_name"],
                    mean_str,
                    pass_rate_str,
                    stdev_str,
                    threshold_str,
                    f"{item['num_cases_valid']}/{item['num_cases_total']}",
                    status_str,
                ]
            )

    run_id = report.get("run_id", "unknown")
    title = (
        f"GEAP EVALUATION SUMMARY — {run_id} "
        f"({report.get('num_cases_evaluated')} EvalCases)"
    )
    if has_baseline:
        headers = [
            "Metric Name",
            "Mean Score",
            "Baseline",
            "Delta (Δ)",
            "Pass Rate",
            "Std Dev",
            "Threshold",
            "Valid/Total",
            "Status",
        ]
    else:
        headers = [
            "Metric Name",
            "Mean Score",
            "Pass Rate",
            "Std Dev",
            "Threshold",
            "Valid/Total",
            "Status",
        ]

    logger.info(
        format_table_for_logs(
            title=title,
            rows=rows,
            headers=headers,
            width=118 if has_baseline else 100,
        )
    )

    cost_ov = report.get("cost_overview") or {}
    if cost_ov:
        logger.info(
            f"AI COST SUMMARY ({cost_ov.get('pricing_catalog_version')}) — "
            f"Total SUT Cost: ${cost_ov.get('cost_per_1k_requests_usd', 0.0):.4f}/1k reqs "
            f"(LLM tokens: ${cost_ov.get('llm_token_cost_per_1k_usd', 0.0):.4f}/1k, "
            f"Google Search grounding: ${cost_ov.get('search_grounding_cost_per_1k_usd', 0.0):.4f}/1k) | "
            f"Judge Est.: ${(cost_ov.get('eval_judge_overhead_estimate') or {}).get('estimated_judge_cost_usd', 0.0):.5f}"
        )

    if summary_output_path:
        os.makedirs(os.path.dirname(summary_output_path), exist_ok=True)
        md_table = tabulate(rows, headers=headers, tablefmt="github")
        cost_sections_md = _build_cost_markdown_sections(report)

        agent_rows = []
        for agent_name, cfg in (
            run_metadata.get("agent_configs") or {}
        ).items():
            tools_str = ", ".join(cfg.get("tools") or []) or "none"
            agent_rows.append(
                [
                    f"`{agent_name}`",
                    f"`{cfg.get('model')}`",
                    f"`{cfg.get('instruction_sha256')}`",
                    tools_str,
                ]
            )
        agent_md_table = tabulate(
            agent_rows,
            headers=["Sub-Agent", "Model", "Prompt Hash (SHA-256)", "Tools"],
            tablefmt="github",
        )

        git_info = run_metadata.get("git_info") or {}
        git_str = (
            f"`{git_info.get('commit_sha', 'unknown')}` "
            f"(branch: `{git_info.get('branch', 'unknown')}`, "
            f"dirty: `{git_info.get('dirty', False)}`)"
        )
        baseline_ref = report.get("baseline_run_id") or (
            "Pinned as active baseline"
            if run_metadata.get("is_baseline")
            else "None"
        )

        md_content = (
            f"# {title}\n\n"
            f"## Run Metadata\n\n"
            f"- **Run ID**: `{run_id}`\n"
            f"- **Run Name**: `{report.get('run_name')}`\n"
            f"- **Description**: {report.get('description') or '_No description provided_'}\n"
            f"- **Baseline Reference**: `{baseline_ref}`\n"
            f"- **Eval Set ID**: `{report.get('eval_set_id')}`\n"
            f"- **Timestamp (UTC)**: `{report.get('timestamp')}`\n"
            f"- **Cases Evaluated**: `{report.get('num_cases_evaluated')}`\n"
            f"- **Git Revision**: {git_str}\n\n"
            f"## Aggregated Metric Scores\n\n"
            f"{md_table}\n\n"
            f"{cost_sections_md}"
            f"## Agent Configuration Snapshot\n\n"
            f"{agent_md_table}\n"
        )
        with open(summary_output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Saved formatted summary report to {summary_output_path}")


METRIC_DISPLAY_LABELS: Dict[str, str] = {
    "multi_turn_task_success_v1": "Task Success Rate",
    "multi_turn_trajectory_quality_v1": "Trajectory Quality",
    "tool_use_quality": "Tool Use Quality",
    "coherence": "Response Coherence",
    "schema_and_contract_valid": "Schema & Contract Validity",
    "conversation_plan_alignment": "Conversation Plan Alignment",
    "latency_seconds": "Latency (in seconds)",
    "cost_per_1k_requests_usd": "Total Cost per 1k Requests (USD)",
    "llm_token_cost_per_1k_usd": "LLM Token Cost per 1k Requests (USD)",
    "total_billable_tokens": "Total Billable Tokens (avg/req)",
}

SUB_AGENT_DISPLAY_ORDER: tuple[str, ...] = (
    "engage",
    "filter",
    "filter_smart",
    "inspiration",
    "json_parser",
)


def _format_metric_label(metric_name: str) -> str:
    """Maps raw metric identifiers to concise human-readable display labels."""
    return METRIC_DISPLAY_LABELS.get(
        metric_name, metric_name.replace("_", " ").title()
    )


def _parse_existing_markdown_table(
    md_text: str,
) -> tuple[List[str], List[Dict[str, str]], str]:
    """Parses a GitHub Markdown table into ``(headers, row_dicts, preamble_text)``."""
    lines = md_text.splitlines()
    table_start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("|") and idx + 1 < len(lines):
            sep = lines[idx + 1].strip()
            if sep.startswith("|") and "-" in sep:
                table_start = idx
                break

    if table_start is None:
        return [], [], md_text

    preamble = "\n".join(lines[:table_start]).rstrip()
    header_cells = [
        c.strip() for c in lines[table_start].strip().strip("|").split("|")
    ]
    parsed_rows: List[Dict[str, str]] = []
    for row_line in lines[table_start + 2 :]:
        stripped = row_line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        row_map = {
            header_cells[i]: (cells[i] if i < len(cells) else "N/A")
            for i in range(len(header_cells))
        }
        parsed_rows.append(row_map)

    return header_cells, parsed_rows, preamble


def _strip_md_bold(label: str) -> str:
    cleaned = label.strip()
    if cleaned.startswith("**") and cleaned.endswith("**") and len(cleaned) >= 4:
        return cleaned[2:-2].strip()
    return cleaned


def _extract_existing_runs_as_columns(
    existing_headers: List[str],
    existing_rows: List[Dict[str, str]],
) -> tuple[List[str], List[str], List[Dict[str, str]]]:
    """Normalizes either transposed or legacy horizontal tables into ``(run_cols, row_labels, col_maps)``."""
    if not existing_headers:
        return [], [], []

    # Detect legacy horizontal table: columns are Run ID, Run Name, Baseline, Cases, ...
    if (
        len(existing_headers) >= 2
        and _strip_md_bold(existing_headers[0]) == "Run ID"
        and _strip_md_bold(existing_headers[1]) == "Run Name"
    ):
        run_cols: List[str] = []
        col_maps: List[Dict[str, str]] = []
        row_labels: List[str] = []
        for h in existing_headers[1:]:
            lbl = _format_metric_label(h) if h in METRIC_DISPLAY_LABELS else h
            if lbl not in row_labels:
                row_labels.append(lbl)
        for row in existing_rows:
            run_id_col = row.get(existing_headers[0], "unknown")
            run_cols.append(run_id_col)
            col_map: Dict[str, str] = {}
            for h in existing_headers[1:]:
                lbl = _format_metric_label(h) if h in METRIC_DISPLAY_LABELS else h
                col_map[lbl] = row.get(h, "N/A")
            col_maps.append(col_map)
        return run_cols, row_labels, col_maps

    # Transposed format: header[0] is "Run ID", header[1:] are individual Run IDs
    key_col = existing_headers[0]
    run_cols = list(existing_headers[1:])
    row_labels = [_strip_md_bold(r.get(key_col, "")) for r in existing_rows]
    col_maps = []
    for run_col in run_cols:
        col_map = {}
        for r, lbl in zip(existing_rows, row_labels):
            col_map[lbl] = r.get(run_col, "N/A")
        col_maps.append(col_map)
    return run_cols, row_labels, col_maps


def append_to_experiments_history(
    report: Dict[str, Any],
    run_metadata: Dict[str, Any],
    history_path: str = DEFAULT_HISTORY_PATH,
) -> None:
    """Appends a new Run ID column to the transposed experiments_history.md leaderboard."""
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    metric_entries = [
        (
            _format_metric_label(m["metric_name"]),
            (
                f"{m['mean_score']:.3f}{m.get('unit') or ''}"
                if m.get("mean_score") is not None
                else "N/A"
            ),
        )
        for m in report.get("summary_metrics", [])
    ]

    git_info = run_metadata.get("git_info") or {}
    commit_tag = git_info.get("commit_sha", "unknown")
    if git_info.get("dirty"):
        commit_tag += "*"

    is_base_str = "Yes" if run_metadata.get("is_baseline") else "No"
    desc_clean = (
        (report.get("description") or "-").replace("|", "/").replace("\n", " ")
    )

    agent_configs = run_metadata.get("agent_configs") or {}
    ordered_agents = [
        ag for ag in SUB_AGENT_DISPLAY_ORDER if ag in agent_configs
    ] + [ag for ag in sorted(agent_configs) if ag not in SUB_AGENT_DISPLAY_ORDER]
    model_entries = [
        (f"Model (`{ag}`)", f"`{agent_configs[ag].get('model', 'unknown')}`")
        for ag in ordered_agents
    ]

    run_col_header = f"`{report.get('run_id')}`"
    new_entries: List[tuple[str, str]] = [
        ("Run Name", f"`{report.get('run_name')}`"),
        ("Description", desc_clean),
        ("Baseline", is_base_str),
        ("Cases", str(report.get("num_cases_evaluated"))),
        ("Git", f"`{commit_tag}`"),
        *model_entries,
        *metric_entries,
    ]
    new_col_map: Dict[str, str] = dict(new_entries)
    desired_row_labels = [k for k, _ in new_entries]

    default_preamble = (
        "# GEAP Evaluation Experiments History\n\n"
        "Cumulative leaderboard of evaluation runs across model, prompt, caching, and architecture changes. "
        "Each column represents a single evaluation Run ID."
    )

    if os.path.isfile(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            existing_text = f.read()
        existing_headers, existing_rows, preamble = (
            _parse_existing_markdown_table(existing_text)
        )
        existing_run_cols, existing_row_labels, existing_col_maps = (
            _extract_existing_runs_as_columns(existing_headers, existing_rows)
        )
    else:
        existing_run_cols, existing_row_labels, existing_col_maps = [], [], []
        preamble = default_preamble

    # Preserve canonical top ordering (Run Name, Description, Baseline, Cases, Git, Models, Metrics)
    merged_row_labels: List[str] = []
    for lbl in desired_row_labels:
        if lbl not in merged_row_labels:
            merged_row_labels.append(lbl)
    for lbl in existing_row_labels:
        if lbl not in merged_row_labels:
            merged_row_labels.append(lbl)

    all_run_cols = [*existing_run_cols, run_col_header]
    all_col_maps = [*existing_col_maps, new_col_map]

    headers = ["Run ID", *all_run_cols]
    matrix = [
        [f"**{lbl}**", *[cm.get(lbl, "N/A") for cm in all_col_maps]]
        for lbl in merged_row_labels
    ]
    table_str = tabulate(matrix, headers=headers, tablefmt="github")
    final_preamble = preamble.strip() or default_preamble
    with open(history_path, "w", encoding="utf-8") as f:
        f.write(f"{final_preamble}\n\n{table_str}\n")

    logger.info(f"Updated cumulative experiment leaderboard at {history_path}")


def run_evaluation(
    evalset_path: str = DEFAULT_EVALSET_PATH,
    eval_config_path: str = DEFAULT_EVAL_CONFIG_PATH,
    results_dir: str = DEFAULT_RESULTS_DIR,
    run_name: str = "baseline",
    description: str = "",
    set_baseline: bool = False,
    baseline_run: Optional[str] = None,
    reuse_run: Optional[str] = None,
    limit: Optional[int] = None,
    skip_inference: bool = False,
    concurrency_override: Optional[int] = None,
    location_override: Optional[str] = None,
    pricing_config_path: Optional[str] = None,
    reprice_only: bool = False,
    model_overrides: Optional[List[str]] = None,
    no_history: bool = False,
) -> Dict[str, Any]:
    """Executes Phase 2A (1-turn inference + cost capture) and Phase 2B (GEAP evaluation) in an isolated run directory."""
    load_dotenv()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    with open(eval_config_path, "r", encoding="utf-8") as f:
        eval_config = json.load(f)

    pricing_catalog = resolve_pricing_catalog_for_eval(
        eval_config=eval_config,
        eval_config_path=eval_config_path,
        pricing_config_override=pricing_config_path,
    )
    parsed_overrides = parse_model_overrides(model_overrides)

    location = location_override or eval_config.get(
        "evaluation_location", "us-central1"
    )

    now_utc = datetime.now(timezone.utc)
    timestamp_slug = now_utc.strftime("%Y%m%d_%H%M%S")
    timestamp_iso = now_utc.isoformat()
    safe_name = sanitize_run_name(run_name)
    run_id = f"{timestamp_slug}_{safe_name}"

    run_dir = os.path.join(results_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    traces_output_path = os.path.join(run_dir, TRACES_FILENAME)
    results_output_path = os.path.join(run_dir, RESULTS_FILENAME)
    summary_output_path = os.path.join(run_dir, SUMMARY_FILENAME)
    metadata_output_path = os.path.join(run_dir, METADATA_FILENAME)

    logger.info(f"Starting evaluation run '{run_id}' -> {run_dir}")

    agent_info = build_agent_info()
    traces_source = resolve_traces_source_path(
        reuse_run=reuse_run,
        skip_inference=skip_inference or reprice_only,
        results_dir=results_dir,
        exclude_run_id=run_id,
    )

    existing_source_report: Optional[Dict[str, Any]] = None
    if traces_source:
        logger.info(f"Reusing existing agent traces from {traces_source}...")
        with open(traces_source, "r", encoding="utf-8") as f:
            traced_records = json.load(f)
        if limit is not None and limit > 0:
            traced_records = traced_records[:limit]
        for rec in traced_records:
            for turn in (rec.get("agent_data") or {}).get("turns") or []:
                for ev in turn.get("events") or []:
                    if ev.get("author") != "user" and isinstance(
                        ev.get("content"), dict
                    ):
                        ev["content"]["role"] = "model"
        traced_records = reprice_traced_records(
            traced_records=traced_records,
            catalog=pricing_catalog,
            model_overrides=parsed_overrides,
        )
        cases_with_usage = sum(
            1 for r in traced_records if r.get("sub_agent_usages")
        )
        if traced_records and cases_with_usage == 0:
            logger.warning(
                f"Reused traces from '{traces_source}' contain no token/cost telemetry "
                "(sub_agent_usages is empty across all cases — likely a legacy run captured "
                "before cost tracking was added). Cost and token metrics will report N/A. "
                "Run a fresh live baseline without --reuse-run / --reprice-only first "
                "(e.g. `python3 -m tests.eval.scripts.run_evaluation --run-name baseline_with_cost --set-baseline`)."
            )
        sibling_results = os.path.join(
            os.path.dirname(traces_source), RESULTS_FILENAME
        )
        if os.path.isfile(sibling_results):
            try:
                with open(sibling_results, "r", encoding="utf-8") as f:
                    existing_source_report = json.load(f)
            except Exception:
                existing_source_report = None
    else:
        with open(evalset_path, "r", encoding="utf-8") as f:
            eval_set = EvalSet.model_validate_json(f.read())

        concurrency = concurrency_override or eval_config.get(
            "inference_concurrency", 4
        )
        traced_records = asyncio.run(
            run_batch_inference(
                eval_set=eval_set,
                agent_info=agent_info,
                limit=limit,
                concurrency=concurrency,
                pricing_catalog=pricing_catalog,
            )
        )
        if parsed_overrides:
            traced_records = reprice_traced_records(
                traced_records=traced_records,
                catalog=pricing_catalog,
                model_overrides=parsed_overrides,
            )

    with open(traces_output_path, "w", encoding="utf-8") as f:
        json.dump(traced_records, f, indent=2, ensure_ascii=False)
    logger.info(
        f"Saved {len(traced_records)} execution trace(s) to {traces_output_path}"
    )

    existing_baseline_dir = find_latest_baseline_dir(
        results_dir=results_dir, exclude_run_id=run_id
    )
    become_baseline = set_baseline or (
        existing_baseline_dir is None and baseline_run is None
    )

    baseline_report = None
    if not set_baseline or baseline_run is not None:
        baseline_report = load_reference_baseline(
            baseline_run=baseline_run,
            results_dir=results_dir,
            exclude_run_id=run_id,
        )

    run_metadata: Dict[str, Any] = {
        "run_id": run_id,
        "run_name": safe_name,
        "description": description,
        "timestamp": timestamp_iso,
        "eval_set_id": eval_config.get(
            "eval_set_id", "conversational_synthetic"
        ),
        "num_cases_evaluated": len(traced_records),
        "is_baseline": become_baseline,
        "reused_traces_from": traces_source,
        "reprice_only": bool(reprice_only),
        "pricing_model_overrides": parsed_overrides or None,
        "git_info": extract_git_info(),
        "agent_configs": extract_agent_config_snapshot(conversational),
        "pricing_catalog": pricing_catalog,
        "eval_config": eval_config,
    }
    with open(metadata_output_path, "w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved run metadata & pricing snapshot to {metadata_output_path}")

    if reprice_only:
        logger.info(
            "Running offline deterministic Python & cost metrics only (--reprice-only; $0 API spend)..."
        )
        eval_result = evaluate_local_python_metrics_only(
            traced_records=traced_records,
            eval_config=eval_config,
            existing_source_report=existing_source_report,
        )
    else:
        logger.info(
            f"Initializing Vertex AI Client (project={project_id}, location={location})..."
        )
        client = vertexai.Client(
            project=project_id,
            location=location,
            http_options=genai_types.HttpOptions(timeout=180_000),
        )
        metrics = build_evaluation_metrics(client=client, eval_config=eval_config)

        eval_df = pd.DataFrame(traced_records)
        eval_dataset = vertex_types.EvaluationDataset(
            eval_dataset_df=eval_df,
            candidate_name=APP_NAME,
        )

        qps = float(eval_config.get("evaluation_service_qps", 5.0))
        from vertexai._genai import _evals_common

        _evals_common.MAX_WORKERS = 20
        logger.info(
            f"Running GEAP evaluation across {len(traced_records)} case(s) with {len(metrics)} metrics "
            f"(qps={qps}, workers={_evals_common.MAX_WORKERS})..."
        )
        eval_result = client.evals.evaluate(
            dataset=eval_dataset,
            metrics=metrics,
            agent_info=agent_info,
            config=vertex_types.EvaluateMethodConfig(
                evaluation_service_qps=qps,
            ),
        )

    report = serialize_evaluation_results(
        eval_result=eval_result,
        traced_records=traced_records,
        eval_config=eval_config,
        run_id=run_id,
        run_name=safe_name,
        description=description,
        timestamp_iso=timestamp_iso,
        baseline_report=baseline_report,
        pricing_catalog=pricing_catalog,
        inference_reused=bool(traces_source),
        evaluation_executed=not reprice_only,
    )

    with open(results_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved full GEAP evaluation results to {results_output_path}")

    log_summary_table(
        report=report,
        run_metadata=run_metadata,
        summary_output_path=summary_output_path,
    )

    if become_baseline:
        logger.info(
            f"Marked run '{run_id}' as the active reference baseline (is_baseline=True in {metadata_output_path})"
        )

    if not no_history:
        append_to_experiments_history(
            report=report,
            run_metadata=run_metadata,
            history_path=os.path.join(results_dir, "experiments_history.md"),
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 2: Run 1-turn agent inference, AI cost estimation, and GEAP evaluation."
    )
    parser.add_argument(
        "--run-name",
        default="baseline",
        help="Short name for this evaluation run (e.g. 'baseline', 'prompt_v2', 'gemini_2_5_pro')",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Optional description of what changed in this experiment",
    )
    parser.add_argument(
        "--set-baseline",
        action="store_true",
        help="Mark this run as the active reference baseline for subsequent delta comparisons",
    )
    parser.add_argument(
        "--baseline-run",
        default=None,
        help="Optional run ID or directory to compare against instead of the latest baseline run",
    )
    parser.add_argument(
        "--reuse-run",
        default=None,
        help="Reuse Phase 2A agent traces from a previous run ID or path (skips live inference)",
    )
    parser.add_argument(
        "--evalset",
        default=DEFAULT_EVALSET_PATH,
        help="Path to conversational_synthetic.evalset.json",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_EVAL_CONFIG_PATH,
        help="Path to eval_config.json",
    )
    parser.add_argument(
        "--pricing-config",
        default=None,
        help="Optional path to custom pricing_config.json catalog",
    )
    parser.add_argument(
        "--reprice-only",
        action="store_true",
        help="Offline $0 mode: reprice existing traces and run deterministic Python metrics without calling Vertex Eval API",
    )
    parser.add_argument(
        "--override-model",
        action="append",
        default=None,
        help="Counterfactual pricing override: 'model_id' (all sub-agents) or 'agent_name=model_id' (repeatable)",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append this run to experiments_history.md (useful for quick counterfactual repricing checks)",
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help="Base directory where timestamped run folders are created",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of EvalCases to run (e.g. --limit 5)",
    )
    parser.add_argument(
        "--skip-inference",
        action="store_true",
        help="Skip agent inference and reuse traces from the latest baseline run",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Override max concurrent agent runs during Phase 2A",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Optional GCP location override for Vertex Eval API",
    )
    args = parser.parse_args()

    run_evaluation(
        evalset_path=args.evalset,
        eval_config_path=args.config,
        results_dir=args.results_dir,
        run_name=args.run_name,
        description=args.description,
        set_baseline=args.set_baseline,
        baseline_run=args.baseline_run,
        reuse_run=args.reuse_run,
        limit=args.limit,
        skip_inference=args.skip_inference,
        concurrency_override=args.concurrency,
        location_override=args.location,
        pricing_config_path=args.pricing_config,
        reprice_only=args.reprice_only,
        model_overrides=args.override_model,
        no_history=args.no_history,
    )


if __name__ == "__main__":
    main()
