# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Offline CI static prompt-size & Gemini prefix-cacheability regression guardrails.

Runs in <1s at $0 API cost on every PR (.cloudbuild/pr_checks.yaml) to prevent
silent static input-token bloat, duplicate prompt sections, and cache-hostile
placement of dynamic ADK state placeholders across all workflow sub-agents.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

from google.adk import Agent
import pytest

from app.agent import conversational
from tests.eval.metrics.cost_estimator import (
    compute_step_cost_from_counts,
    load_pricing_catalog,
)

# Per-sub-agent static instruction budgets (~15% headroom above current baseline).
# If an intentional prompt edit exceeds a ceiling, run `tests/eval/scripts/run_evaluation.py`
# to verify the quality vs. cost trade-off before explicitly updating the budget here.
PROMPT_BUDGETS: Dict[str, Dict[str, Any]] = {
    "engage": {
        "max_chars": 5250,
        "max_est_tokens": 1315,
        "min_static_prefix_ratio": 0.75,
        "required_placeholders": ("{user_message}", "{conversational_history}"),
    },
    "filter": {
        "max_chars": 2800,
        "max_est_tokens": 700,
        "min_static_prefix_ratio": 0.75,
        "required_placeholders": ("{user_message}", "{conversational_history}"),
    },
    "filter_smart": {
        "max_chars": 9500,
        "max_est_tokens": 2375,
        "min_static_prefix_ratio": 0.75,
        "required_placeholders": (
            "{user_message}",
            "{conversational_history}",
            "{flights_input}",
        ),
    },
    "inspiration": {
        "max_chars": 2950,
        "max_est_tokens": 740,
        "min_static_prefix_ratio": 0.60,
        "required_placeholders": (
            "{user_message}",
            "{conversational_history}",
            "{flights_search_input}",
        ),
    },
    "json_parser": {
        "max_chars": 2750,
        "max_est_tokens": 690,
        "min_static_prefix_ratio": 0.55,
        "required_placeholders": ("{agent_response}",),
    },
}

# Combined static instruction token ceilings along each end-to-end workflow trajectory
# (cost floors priced against default model gemini-3.8-flash @ $0.75/1M input).
ROUTE_STATIC_TOKEN_CEILINGS: Dict[str, Tuple[Tuple[str, ...], int, float]] = {
    "continue": (("engage",), 1315, 1.10),
    "filter": (("engage", "filter"), 2015, 1.65),
    "inspiration": (("engage", "inspiration"), 2055, 1.70),
    "filter_smart": (("engage", "filter_smart"), 3690, 3.05),
    "filter_smart_with_repair": (
        ("engage", "filter_smart", "json_parser"),
        4380,
        3.60,
    ),
}

_STATE_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")
_TOP_LEVEL_OPEN_TAG_RE = re.compile(
    r"^\s*<([A-Z0-9_ &]+)>\s*$", re.MULTILINE
)


def _get_workflow_agents() -> Dict[str, Agent]:
    """Extracts all ADK Agent nodes directly from the live conversational Workflow graph."""
    graph = conversational._require_graph()
    return {
        node.name: node for node in graph.nodes if isinstance(node, Agent)
    }


def _estimate_tokens(text: str) -> int:
    """Deterministic ~4 chars/token heuristic for offline CI static prompt budgeting."""
    return int(math.ceil(len(text) / 4.0))


def test_every_workflow_sub_agent_has_declared_prompt_budget() -> None:
    """Any new sub-agent added to the conversational Workflow must declare a static prompt budget."""
    live_agents = _get_workflow_agents()
    assert set(live_agents.keys()) == set(PROMPT_BUDGETS.keys()), (
        f"Workflow sub-agents {sorted(live_agents.keys())} do not match declared "
        f"PROMPT_BUDGETS {sorted(PROMPT_BUDGETS.keys())}."
    )


@pytest.mark.parametrize("agent_name", sorted(PROMPT_BUDGETS.keys()))
def test_sub_agent_static_prompt_within_size_budget(agent_name: str) -> None:
    """Fail fast in CI if any sub-agent's static system instruction exceeds its char/token ceiling."""
    live_agents = _get_workflow_agents()
    budget = PROMPT_BUDGETS[agent_name]
    instruction = str(live_agents[agent_name].instruction or "")
    char_len = len(instruction)
    est_tokens = _estimate_tokens(instruction)

    assert char_len <= budget["max_chars"], (
        f"Static prompt bloat in '{agent_name}': {char_len} chars > ceiling {budget['max_chars']} "
        f"(~{est_tokens} est tokens). Trim the prompt or run `tests/eval/scripts/run_evaluation.py` "
        "to validate quality vs. cost before raising PROMPT_BUDGETS."
    )
    assert est_tokens <= budget["max_est_tokens"], (
        f"Static prompt token estimate in '{agent_name}': ~{est_tokens} tok > "
        f"ceiling {budget['max_est_tokens']} tok."
    )


@pytest.mark.parametrize("agent_name", sorted(PROMPT_BUDGETS.keys()))
def test_sub_agent_prompt_cache_friendly_prefix_and_no_duplicate_sections(
    agent_name: str,
) -> None:
    """Verify dynamic ADK placeholders stay at the tail (prefix-cacheable) and no XML sections are duplicated."""
    live_agents = _get_workflow_agents()
    budget = PROMPT_BUDGETS[agent_name]
    instruction = str(live_agents[agent_name].instruction or "")

    for placeholder in budget["required_placeholders"]:
        assert placeholder in instruction, (
            f"Expected ADK state placeholder '{placeholder}' missing from '{agent_name}' prompt."
        )

    matches = list(_STATE_PLACEHOLDER_RE.finditer(instruction))
    assert matches, f"No dynamic state placeholders found in '{agent_name}' prompt."

    earliest_match = matches[0]
    static_prefix_ratio = earliest_match.start() / max(1, len(instruction))
    min_ratio = float(budget["min_static_prefix_ratio"])
    assert static_prefix_ratio >= min_ratio, (
        f"Dynamic placeholder '{earliest_match.group(0)}' in '{agent_name}' starts at "
        f"{static_prefix_ratio:.1%} of the prompt (min required: {min_ratio:.0%}). "
        "Keep static rules/examples before dynamic state variables to preserve Gemini prefix caching."
    )

    open_tags: List[str] = _TOP_LEVEL_OPEN_TAG_RE.findall(instruction)
    duplicate_tags = sorted(
        {tag for tag in open_tags if open_tags.count(tag) > 1}
    )
    assert not duplicate_tags, (
        f"Duplicate top-level XML prompt sections detected in '{agent_name}': {duplicate_tags}."
    )


@pytest.mark.parametrize("route_name", sorted(ROUTE_STATIC_TOKEN_CEILINGS.keys()))
def test_end_to_end_route_static_prompt_token_and_cost_floor_guardrail(
    route_name: str,
) -> None:
    """Prevent cumulative static prompt bloat across multi-agent workflow trajectories."""
    live_agents = _get_workflow_agents()
    catalog = load_pricing_catalog()
    agent_chain, max_route_tokens, max_static_cost_1k_usd = (
        ROUTE_STATIC_TOKEN_CEILINGS[route_name]
    )

    total_static_tokens = 0
    total_static_cost_1k = 0.0
    for ag_name in agent_chain:
        node = live_agents[ag_name]
        est_tok = _estimate_tokens(str(node.instruction or ""))
        total_static_tokens += est_tok

        # Price static prompt floor against Standard PayGo default model (gemini-3.8-flash)
        step = compute_step_cost_from_counts(
            author=ag_name,
            resolved_model=catalog.get("default_model", "gemini-3.8-flash"),
            prompt_tokens=est_tok,
            catalog=catalog,
        )
        total_static_cost_1k += step["cost_per_1k_requests_usd"]

    assert total_static_tokens <= max_route_tokens, (
        f"Combined static prompt tokens for route '{route_name}' ({' -> '.join(agent_chain)}) "
        f"reached ~{total_static_tokens} tok > ceiling {max_route_tokens} tok."
    )
    assert total_static_cost_1k <= max_static_cost_1k_usd, (
        f"Static-only input cost floor for route '{route_name}' reached "
        f"${total_static_cost_1k:.4f}/1k reqs > ceiling ${max_static_cost_1k_usd:.4f}/1k reqs."
    )
