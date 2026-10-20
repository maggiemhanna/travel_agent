# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Step 2: Run 1-turn agent inference and GEAP evaluation."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
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

from app.agent import APP_NAME, conversational
from app.app_utils.logging import format_table_for_logs, setup_logging
from tests.eval.metrics.custom_metrics import build_evaluation_metrics
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

    combined_query = " | ".join(queries) if queries else "airline flight amenities research"
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
) -> Dict[str, Any]:
    """Executes 1-turn inference for a single EvalCase and builds its trace record."""
    eval_id = eval_case.eval_id or str(uuid4())[:8]
    scenario = eval_case.conversation_scenario
    starting_prompt = scenario.starting_prompt if scenario else ""
    conversation_plan = scenario.conversation_plan if scenario else ""

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
                agent=conversational,
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
                tool_calls_made: List[Dict[str, Any]] = []
                final_response_text = ""

                turn_start_perf = time.perf_counter()
                last_step_perf = turn_start_perf

                async for raw_event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_content,
                ):
                    if not raw_event or not raw_event.content or not raw_event.content.parts:
                        continue

                    author = raw_event.author or "conversational"
                    if author == "finalize_output":
                        author = "conversational"
                    elif author in {"route_engage", "parse_filter_smart"}:
                        continue

                    now_perf = time.perf_counter()
                    step_latency_sec = round(now_perf - last_step_perf, 4)
                    last_step_perf = now_perf
                    sub_agent_latencies.append(
                        {
                            "author": author,
                            "latency_seconds": step_latency_sec,
                        }
                    )

                    content_dump = raw_event.content.model_dump(
                        mode="json", exclude_none=True
                    )
                    if author != "user":
                        content_dump["role"] = "model"
                    validated_content = genai_types.Content.model_validate(content_dump)
                    event_time = (
                        datetime.fromtimestamp(raw_event.timestamp, tz=timezone.utc)
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
                            "event_id": getattr(raw_event, "id", None) or str(uuid4())[:8],
                            "author": author,
                            "content": content_dump,
                            "creation_timestamp": event_time.isoformat(),
                        }
                    )

                total_latency_sec = round(time.perf_counter() - turn_start_perf, 4)

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

                return {
                    "eval_id": eval_id,
                    "prompt": starting_prompt,
                    "conversation_plan": conversation_plan,
                    "context": context_str,
                    "tool_calls": json.dumps(tool_calls_made, ensure_ascii=False),
                    "session_inputs": session_input_dict,
                    "response": final_response_text,
                    "latency_seconds": total_latency_sec,
                    "sub_agent_latencies_seconds": sub_agent_latencies,
                    "intermediate_events": intermediate_events,
                    "agent_data": agent_data.model_dump(mode="json", exclude_none=True),
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
                    total_latency_sec = round(time.perf_counter() - turn_start_perf, 4)
                    logger.error(f"Case {eval_id} failed after {max_retries} attempts: {exc}")
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
                                        author="conversational", content=model_content
                                    ),
                                ],
                            )
                        ],
                    )
                    return {
                        "eval_id": eval_id,
                        "prompt": starting_prompt,
                        "conversation_plan": conversation_plan,
                        "context": json.dumps(base_context_payload, ensure_ascii=False),
                        "tool_calls": "[]",
                        "session_inputs": session_input_dict,
                        "response": error_json,
                        "latency_seconds": total_latency_sec,
                        "sub_agent_latencies_seconds": [],
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

    tasks = [run_single_case_inference(case, agents_map, semaphore) for case in cases]

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


def resolve_traces_source_path(
    reuse_run: Optional[str],
    skip_inference: bool,
    results_dir: str,
    baseline_dir: str,
) -> Optional[str]:
    """Resolves the path to an existing eval_dataset_with_traces.json when reusing traces."""
    if reuse_run:
        if os.path.isfile(reuse_run):
            return reuse_run
        if os.path.isdir(reuse_run):
            candidate = os.path.join(reuse_run, TRACES_FILENAME)
            if os.path.isfile(candidate):
                return candidate
        candidate_in_results = os.path.join(results_dir, reuse_run, TRACES_FILENAME)
        if os.path.isfile(candidate_in_results):
            return candidate_in_results
        raise FileNotFoundError(
            f"Could not find {TRACES_FILENAME} for --reuse-run '{reuse_run}'"
        )

    if skip_inference:
        baseline_traces = os.path.join(baseline_dir, TRACES_FILENAME)
        if os.path.isfile(baseline_traces):
            return baseline_traces
        legacy_traces = os.path.join(results_dir, TRACES_FILENAME)
        if os.path.isfile(legacy_traces):
            return legacy_traces
        raise FileNotFoundError(
            f"--skip-inference was set, but no baseline traces found at {baseline_traces}"
        )

    return None


def load_reference_baseline(
    baseline_dir: str,
    baseline_run: Optional[str],
    results_dir: str,
) -> Optional[Dict[str, Any]]:
    """Loads the reference baseline eval_results.json if available."""
    if baseline_run:
        if os.path.isfile(baseline_run):
            target_path = baseline_run
        elif os.path.isdir(baseline_run):
            target_path = os.path.join(baseline_run, RESULTS_FILENAME)
        else:
            target_path = os.path.join(results_dir, baseline_run, RESULTS_FILENAME)
        if os.path.isfile(target_path):
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"Reference baseline not found at {target_path}")
        return None

    default_baseline_results = os.path.join(baseline_dir, RESULTS_FILENAME)
    if os.path.isfile(default_baseline_results):
        with open(default_baseline_results, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def serialize_evaluation_results(
    eval_result: vertex_types.EvaluationResult,
    traced_records: List[Dict[str, Any]],
    eval_config: Dict[str, Any],
    run_id: str,
    run_name: str,
    description: str,
    timestamp_iso: str,
    baseline_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Combines summary metrics, baseline deltas, and per-case results into a JSON report."""
    metric_cfg_map = {
        m["name"]: m for m in eval_config.get("metrics", [])
    }

    baseline_scores: Dict[str, Optional[float]] = {}
    baseline_run_id: Optional[str] = None
    if baseline_report and baseline_report.get("run_id") != run_id:
        baseline_run_id = baseline_report.get("run_id", "baseline")
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
                metric_map[m_name] = m_res.model_dump(mode="json", exclude_none=True)
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
                "response": record.get("response"),
                "metric_results": metric_map,
            }
        )

    summary_list: List[Dict[str, Any]] = []
    for agg in eval_result.summary_metrics or []:
        m_name = agg.metric_name or "unknown"
        m_cfg = metric_cfg_map.get(m_name, {})
        threshold = float(m_cfg.get("threshold", 0.8))
        direction = m_cfg.get("direction", "higher_is_better")
        unit = m_cfg.get("unit", "")
        mean_val = agg.mean_score

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
                    passing_count = sum(1 for s in valid_scores if s <= threshold)
                else:
                    passing_count = sum(1 for s in valid_scores if s >= threshold)
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

    return {
        "run_id": run_id,
        "run_name": run_name,
        "description": description,
        "baseline_run_id": baseline_run_id,
        "eval_set_id": eval_config.get("eval_set_id", "conversational_synthetic"),
        "timestamp": timestamp_iso,
        "num_cases_evaluated": len(traced_records),
        "summary_metrics": summary_list,
        "eval_case_results": per_case_list,
    }


def log_summary_table(
    report: Dict[str, Any],
    run_metadata: Dict[str, Any],
    summary_output_path: Optional[str] = None,
) -> None:
    """Logs a formatted summary table and saves a Markdown report to the run directory."""
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
            width=110 if has_baseline else 95,
        )
    )

    if summary_output_path:
        os.makedirs(os.path.dirname(summary_output_path), exist_ok=True)
        md_table = tabulate(rows, headers=headers, tablefmt="github")

        agent_rows = []
        for agent_name, cfg in (run_metadata.get("agent_configs") or {}).items():
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
            f"## Agent Configuration Snapshot\n\n"
            f"{agent_md_table}\n"
        )
        with open(summary_output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Saved formatted summary report to {summary_output_path}")


def append_to_experiments_history(
    report: Dict[str, Any],
    run_metadata: Dict[str, Any],
    history_path: str = DEFAULT_HISTORY_PATH,
) -> None:
    """Appends a single-row summary of the run to tests/eval/results/experiments_history.md."""
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    metric_names = [m["metric_name"] for m in report.get("summary_metrics", [])]
    score_map = {
        m["metric_name"]: (
            f"{m['mean_score']:.3f}{m.get('unit') or ''}"
            if m.get("mean_score") is not None
            else "N/A"
        )
        for m in report.get("summary_metrics", [])
    }

    git_info = run_metadata.get("git_info") or {}
    commit_tag = git_info.get("commit_sha", "unknown")
    if git_info.get("dirty"):
        commit_tag += "*"

    is_base_str = "Yes" if run_metadata.get("is_baseline") else "No"
    desc_clean = (report.get("description") or "-").replace("|", "/").replace("\n", " ")

    headers = [
        "Run ID",
        "Run Name",
        "Baseline",
        "Cases",
        "Git",
        *metric_names,
        "Description",
    ]
    row = [
        f"`{report.get('run_id')}`",
        f"`{report.get('run_name')}`",
        is_base_str,
        str(report.get("num_cases_evaluated")),
        f"`{commit_tag}`",
        *[score_map.get(m, "N/A") for m in metric_names],
        desc_clean,
    ]

    if not os.path.isfile(history_path):
        table_str = tabulate([row], headers=headers, tablefmt="github")
        content = (
            "# GEAP Evaluation Experiments History\n\n"
            "Cumulative leaderboard of evaluation runs across model, prompt, and architecture changes.\n\n"
            f"{table_str}\n"
        )
        with open(history_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        row_line = "| " + " | ".join(row) + " |\n"
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(row_line)

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
) -> Dict[str, Any]:
    """Executes Phase 2A (1-turn inference) and Phase 2B (GEAP evaluation) in an isolated run directory."""
    load_dotenv()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    with open(eval_config_path, "r", encoding="utf-8") as f:
        eval_config = json.load(f)

    location = location_override or eval_config.get(
        "evaluation_location", "us-central1"
    )

    now_utc = datetime.now(timezone.utc)
    timestamp_slug = now_utc.strftime("%Y%m%d_%H%M%S")
    timestamp_iso = now_utc.isoformat()
    safe_name = sanitize_run_name(run_name)
    run_id = f"{timestamp_slug}_{safe_name}"

    run_dir = os.path.join(results_dir, run_id)
    baseline_dir = os.path.join(results_dir, "baseline")
    os.makedirs(run_dir, exist_ok=True)

    traces_output_path = os.path.join(run_dir, TRACES_FILENAME)
    results_output_path = os.path.join(run_dir, RESULTS_FILENAME)
    summary_output_path = os.path.join(run_dir, SUMMARY_FILENAME)
    metadata_output_path = os.path.join(run_dir, METADATA_FILENAME)

    logger.info(f"Starting evaluation run '{run_id}' -> {run_dir}")

    agent_info = build_agent_info()
    traces_source = resolve_traces_source_path(
        reuse_run=reuse_run,
        skip_inference=skip_inference,
        results_dir=results_dir,
        baseline_dir=baseline_dir,
    )

    if traces_source:
        logger.info(f"Reusing existing agent traces from {traces_source}...")
        with open(traces_source, "r", encoding="utf-8") as f:
            traced_records = json.load(f)
        if limit is not None and limit > 0:
            traced_records = traced_records[:limit]
        for rec in traced_records:
            for turn in (rec.get("agent_data") or {}).get("turns") or []:
                for ev in turn.get("events") or []:
                    if ev.get("author") != "user" and isinstance(ev.get("content"), dict):
                        ev["content"]["role"] = "model"
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
            )
        )

    with open(traces_output_path, "w", encoding="utf-8") as f:
        json.dump(traced_records, f, indent=2, ensure_ascii=False)
    logger.info(
        f"Saved {len(traced_records)} execution trace(s) to {traces_output_path}"
    )

    baseline_exists = os.path.isfile(os.path.join(baseline_dir, RESULTS_FILENAME))
    become_baseline = set_baseline or (not baseline_exists and baseline_run is None)

    baseline_report = None
    if not set_baseline or baseline_run is not None:
        baseline_report = load_reference_baseline(
            baseline_dir=baseline_dir,
            baseline_run=baseline_run,
            results_dir=results_dir,
        )

    run_metadata: Dict[str, Any] = {
        "run_id": run_id,
        "run_name": safe_name,
        "description": description,
        "timestamp": timestamp_iso,
        "eval_set_id": eval_config.get("eval_set_id", "conversational_synthetic"),
        "num_cases_evaluated": len(traced_records),
        "is_baseline": become_baseline,
        "reused_traces_from": traces_source,
        "git_info": extract_git_info(),
        "agent_configs": extract_agent_config_snapshot(conversational),
        "eval_config": eval_config,
    }
    with open(metadata_output_path, "w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved run metadata & agent snapshot to {metadata_output_path}")

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
        os.makedirs(baseline_dir, exist_ok=True)
        for fname in (
            METADATA_FILENAME,
            TRACES_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ):
            shutil.copy2(
                os.path.join(run_dir, fname),
                os.path.join(baseline_dir, fname),
            )
        logger.info(
            f"Pinned run '{run_id}' as the active reference baseline in {baseline_dir}"
        )

    append_to_experiments_history(
        report=report,
        run_metadata=run_metadata,
        history_path=os.path.join(results_dir, "experiments_history.md"),
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 2: Run 1-turn agent inference and GEAP evaluation."
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
        help="Pin this run as the new reference baseline in tests/eval/results/baseline/",
    )
    parser.add_argument(
        "--baseline-run",
        default=None,
        help="Optional run ID or directory to compare against instead of results/baseline/",
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
        help="Skip agent inference and reuse traces from results/baseline/",
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
    )


if __name__ == "__main__":
    main()
