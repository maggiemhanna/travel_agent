# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Pytest session hook reporting aggregated AI token & Standard PayGo USD cost across integration tests."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.agent import app as workflow_app, fallback_app as workflow_fallback_app
from app.app_utils.cost_tracker import aggregate_invocation_cost
from app.app_utils.logging import format_table_for_logs, setup_logging
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from app.sub_agents.engage.agent import (
    app as engage_app,
    fallback_app as engage_fallback_app,
)
from app.sub_agents.filter.agent import (
    app as filter_app,
    fallback_app as filter_fallback_app,
)
from app.sub_agents.filter_smart.agent import (
    app as filter_smart_app,
    fallback_app as filter_smart_fallback_app,
)
from app.sub_agents.inspiration.agent import (
    app as inspiration_app,
    fallback_app as inspiration_fallback_app,
)
from app.sub_agents.json_parser.agent import (
    app as json_parser_app,
    fallback_app as json_parser_fallback_app,
)

logger = setup_logging(name=__name__)


def _iter_registered_telemetry_plugins() -> List[ExecutionTelemetryPlugin]:
    candidate_apps = [
        workflow_app,
        workflow_fallback_app,
        engage_app,
        engage_fallback_app,
        filter_app,
        filter_fallback_app,
        filter_smart_app,
        filter_smart_fallback_app,
        inspiration_app,
        inspiration_fallback_app,
        json_parser_app,
        json_parser_fallback_app,
    ]
    plugins: List[ExecutionTelemetryPlugin] = []
    seen_ids: set[int] = set()
    for adk_app in candidate_apps:
        if adk_app is None:
            continue
        for plugin in getattr(adk_app, "plugins", None) or []:
            if isinstance(plugin, ExecutionTelemetryPlugin) and id(plugin) not in seen_ids:
                seen_ids.add(id(plugin))
                plugins.append(plugin)
    return plugins


@pytest.fixture(scope="session", autouse=True)
def _report_integration_suite_ai_cost():
    plugins = _iter_registered_telemetry_plugins()
    for p in plugins:
        p.clear_completed_runs()

    yield

    completed_runs: List[Dict[str, Any]] = []
    for p in plugins:
        completed_runs.extend(p.get_completed_runs())

    if not completed_runs:
        return

    all_steps = [
        step
        for rec in completed_runs
        for step in (rec.get("steps") or [])
    ]
    summary = aggregate_invocation_cost(all_steps)
    n_invocations = len(completed_runs)
    avg_cost_1k = (summary["total_cost_usd"] / n_invocations) * 1000.0

    rows = []
    for ag, info in (summary.get("by_agent") or {}).items():
        rows.append(
            [
                ag,
                info.get("model", "-"),
                info.get("calls", 0),
                info.get("prompt_tokens", 0),
                info.get("cached_input_tokens", 0),
                info.get("candidates_output_tokens", 0),
                info.get("thoughts_tokens", 0),
                info.get("search_queries_count", 0),
                f"${info.get('total_cost_usd', 0.0):.6f}",
            ]
        )

    title = (
        f"INTEGRATION SUITE AI COST RECEIPT | invocations={n_invocations} "
        f"| total_tokens={summary['total_tokens']} "
        f"| suite_spend=${summary['total_cost_usd']:.6f} "
        f"(avg=${avg_cost_1k:.4f}/1k reqs)"
    )
    logger.info(
        format_table_for_logs(
            title=title,
            rows=rows,
            headers=[
                "Agent",
                "Model",
                "Calls",
                "Prompt Tok",
                "Cached Tok",
                "Out Tok",
                "Thoughts Tok",
                "Search Q",
                "Spend ($)",
            ],
            width=118,
        )
    )
