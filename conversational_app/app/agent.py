# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
import re
from typing import Any, Dict

from google.adk import Context, Event, Workflow
from google.adk.apps import App
from google.adk.workflow import START, node

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.schema import ConversationalOutput, ConversationalState
from app.sub_agents.engage.agent import engage
from app.sub_agents.engage.schema import EngageOutput
from app.sub_agents.filter.agent import filter as filter_agent
from app.sub_agents.filter_smart.agent import filter_smart as filter_smart_agent
from app.sub_agents.inspiration.agent import inspiration as inspiration_agent
from app.sub_agents.json_parser.agent import json_parser as json_parser_agent

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def load_json_with_markdown(data: str) -> Dict[str, Any]:
    """Extracts and parses JSON from raw text or markdown code blocks."""
    cleaned = data.strip()
    match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)
    return json.loads(cleaned)


@node(name="route_engage")
def route_engage(ctx: Context, node_input: EngageOutput) -> Event:
    """Routes execution based on the Engage Agent's decision and saves engage state."""
    decision = node_input.agent_decision
    logger.info(
        f"--- Engage Decision: {decision} ---\n{format_dict_for_logs(node_input.model_dump())}"
    )
    return Event(
        route=decision,
        state=node_input.model_dump(),
    )


@node(name="parse_filter_smart")
def parse_filter_smart(ctx: Context, node_input: str) -> Event:
    """Parses the Filter Smart Agent's text response, falling back to json_parser_agent on invalid JSON."""
    try:
        parsed = load_json_with_markdown(node_input)
        return Event(route="parsed", output=parsed)
    except json.JSONDecodeError:
        logger.warning(
            "Filter Smart response was not valid JSON. Routing to json_parser_agent."
        )
        return Event(
            route="repair_json",
            state={"agent_response": node_input},
        )


@node(name="finalize_output")
def finalize_output(ctx: Context, node_input: Any = None) -> Event:
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


# Create the root ADK v2 Workflow connecting all sub-agents
conversational = Workflow(
    name="conversational",
    description="Conversational workflow for flight triage, hard filtering, smart semantic filtering, and travel inspiration.",
    state_schema=ConversationalState,
    output_schema=ConversationalOutput,
    edges=[
        (START, engage, route_engage),
        (
            route_engage,
            {
                "continue": finalize_output,
                "filter": filter_agent,
                "filter_smart": filter_smart_agent,
                "inspiration_agent": inspiration_agent,
            },
        ),
        (filter_agent, finalize_output),
        (filter_smart_agent, parse_filter_smart),
        (
            parse_filter_smart,
            {
                "parsed": finalize_output,
                "repair_json": json_parser_agent,
            },
        ),
        (json_parser_agent, finalize_output),
        (inspiration_agent, finalize_output),
    ],
)

root_agent = conversational

# Create the main App
app = App(
    name=APP_NAME,
    root_agent=root_agent,
)
