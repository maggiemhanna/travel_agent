# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
import re
from typing import Any, Dict

from google.adk import Context, Event, Workflow
from google.adk.apps import App
from google.adk.workflow import START, node

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.app_utils.telemetry_plugin import build_plugins
from app.config import (
    ENGAGE_FALLBACK_MODEL,
    ENGAGE_MODEL,
    FILTER_FALLBACK_MODEL,
    FILTER_MODEL,
    FILTER_SMART_FALLBACK_MODEL,
    FILTER_SMART_MODEL,
    INSPIRATION_FALLBACK_MODEL,
    INSPIRATION_MODEL,
    JSON_PARSER_FALLBACK_MODEL,
    JSON_PARSER_MODEL,
)
from app.schema import ConversationalOutput, ConversationalState
from app.sub_agents.engage.agent import build_engage_agent, engage
from app.sub_agents.engage.schema import EngageOutput
from app.sub_agents.filter.agent import build_filter_agent, filter
from app.sub_agents.filter_smart.agent import build_filter_smart_agent, filter_smart
from app.sub_agents.inspiration.agent import build_inspiration_agent, inspiration
from app.sub_agents.json_parser.agent import build_json_parser_agent, json_parser

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def load_json_with_markdown(data: str) -> Dict[str, Any]:
    """Extracts and parses JSON from raw text or markdown code blocks."""
    cleaned = data.strip()
    match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)
    return json.loads(cleaned)


def _route_engage_fn(ctx: Context, node_input: EngageOutput) -> Event:
    """Routes execution based on the Engage Agent's decision and saves engage state."""
    decision = node_input.agent_decision
    logger.info(
        f"--- Engage Decision: {decision} ---\n{format_dict_for_logs(node_input.model_dump())}"
    )
    return Event(
        route=decision,
        state=node_input.model_dump(),
    )


def _parse_filter_smart_fn(ctx: Context, node_input: str) -> Event:
    """Parses the Filter Smart Agent's text response, falling back to json_parser on invalid JSON."""
    try:
        parsed = load_json_with_markdown(node_input)
        return Event(route="parsed", output=parsed)
    except json.JSONDecodeError:
        logger.warning(
            "Filter Smart response was not valid JSON. Routing to json_parser."
        )
        return Event(
            route="repair_json",
            state={"agent_response": node_input},
        )


def _finalize_output_fn(ctx: Context, node_input: Any = None) -> Event:
    """Terminal node for all branches, populating sub-agent responses into ConversationalOutput."""
    decision = ctx.state.get("agent_decision", "continue")
    data = (
        node_input.model_dump()
        if hasattr(node_input, "model_dump")
        else (dict(node_input) if isinstance(node_input, dict) else {})
    )

    output = ConversationalOutput(
        agent_response=data.get("agent_response")
        or ctx.state.get("agent_response", ""),
        agent_decision=decision,
        filter_type=data.get("filter_type"),
        filter_value=data.get("filter_value"),
        flights_output=data.get("flights_output"),
        flights_search_output=data.get("flights_search_output"),
    )

    results = output.model_dump(exclude_none=True)
    return Event(output=results, message=json.dumps(results))


def build_conversational_workflow(
    *,
    engage_agent=None,
    filter_agent=None,
    filter_smart_agent=None,
    inspiration_agent=None,
    json_parser_agent=None,
):
    """Builds an isolated ADK v2 Workflow graph with dedicated routing nodes and sub-agents."""
    route_node = node(_route_engage_fn, name="route_engage")
    parse_node = node(_parse_filter_smart_fn, name="parse_filter_smart")
    finalize_node = node(_finalize_output_fn, name="finalize_output")

    e_agent = engage_agent or engage
    f_agent = filter_agent or filter
    fs_agent = filter_smart_agent or filter_smart
    i_agent = inspiration_agent or inspiration
    jp_agent = json_parser_agent or json_parser

    wf = Workflow(
        name="conversational",
        description="Conversational workflow for flight triage, hard filtering, smart semantic filtering, and travel inspiration.",
        state_schema=ConversationalState,
        output_schema=ConversationalOutput,
        edges=[
            (START, e_agent, route_node),
            (
                route_node,
                {
                    "continue": finalize_node,
                    "filter": f_agent,
                    "filter_smart": fs_agent,
                    "inspiration_agent": i_agent,
                },
            ),
            (f_agent, finalize_node),
            (fs_agent, parse_node),
            (
                parse_node,
                {
                    "parsed": finalize_node,
                    "repair_json": jp_agent,
                },
            ),
            (jp_agent, finalize_node),
            (i_agent, finalize_node),
        ],
    )
    return wf, route_node, parse_node, finalize_node


def build_conversational_app(
    *,
    engage_model: str,
    filter_model: str,
    filter_smart_model: str,
    inspiration_model: str,
    json_parser_model: str,
) -> App:
    """Builds a completely isolated Conversational ADK App for backup model failover."""
    wf, _, _, _ = build_conversational_workflow(
        engage_agent=build_engage_agent(engage_model),
        filter_agent=build_filter_agent(filter_model),
        filter_smart_agent=build_filter_smart_agent(filter_smart_model),
        inspiration_agent=build_inspiration_agent(inspiration_model),
        json_parser_agent=build_json_parser_agent(json_parser_model),
    )
    return App(
        name=APP_NAME,
        root_agent=wf,
        plugins=build_plugins(),
    )


# Create the primary root ADK v2 Workflow connecting all primary sub-agents
conversational, route_engage, parse_filter_smart, finalize_output = (
    build_conversational_workflow()
)

root_agent = conversational

# Create the main primary App
app = App(
    name=APP_NAME,
    root_agent=root_agent,
    plugins=build_plugins(),
)

# Create isolated backup App (gemini-3.6-flash by default) for automatic model failover
_has_distinct_fallback = all(
    [
        ENGAGE_FALLBACK_MODEL,
        FILTER_FALLBACK_MODEL,
        FILTER_SMART_FALLBACK_MODEL,
        INSPIRATION_FALLBACK_MODEL,
        JSON_PARSER_FALLBACK_MODEL,
    ]
) and (
    (
        ENGAGE_FALLBACK_MODEL,
        FILTER_FALLBACK_MODEL,
        FILTER_SMART_FALLBACK_MODEL,
        INSPIRATION_FALLBACK_MODEL,
        JSON_PARSER_FALLBACK_MODEL,
    )
    != (
        ENGAGE_MODEL,
        FILTER_MODEL,
        FILTER_SMART_MODEL,
        INSPIRATION_MODEL,
        JSON_PARSER_MODEL,
    )
)

fallback_app = (
    build_conversational_app(
        engage_model=ENGAGE_FALLBACK_MODEL,
        filter_model=FILTER_FALLBACK_MODEL,
        filter_smart_model=FILTER_SMART_FALLBACK_MODEL,
        inspiration_model=INSPIRATION_FALLBACK_MODEL,
        json_parser_model=JSON_PARSER_FALLBACK_MODEL,
    )
    if _has_distinct_fallback
    else None
)
