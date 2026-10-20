# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Step 1: Bootstrap synthetic 1-turn test scenarios using the GEAP Scenario Generator."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from typing import Any, List

from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.evaluation._vertex_ai_scenario_generation_facade import (
    ScenarioGenerator,
)
from google.adk.evaluation.conversation_scenarios import (
    ConversationGenerationConfig,
    ConversationScenario,
    ConversationScenarios,
)
from google.adk.evaluation.eval_case import EvalCase, SessionInput
from google.adk.evaluation.eval_set import EvalSet
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.genai import types as genai_types

from app.agent import conversational
from app.app_utils.logging import format_dict_for_logs, setup_logging

logger = setup_logging(name=__name__)

EVAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(
    EVAL_DIR, "configs", "scenario_generation_config.json"
)
DEFAULT_SESSION_INPUT_PATH = os.path.join(
    EVAL_DIR, "configs", "session_input.json"
)
DEFAULT_SCENARIOS_OUTPUT_PATH = os.path.join(
    EVAL_DIR, "datasets", "synthetic_scenarios.json"
)
DEFAULT_EVALSET_OUTPUT_PATH = os.path.join(
    EVAL_DIR, "datasets", "conversational_synthetic.evalset.json"
)


class _GoogleSearchToolDeclarationAdapter:
    """Wraps GoogleSearchTool with a FunctionDeclaration for AgentInfo extraction."""

    def __init__(self, tool: GoogleSearchTool) -> None:
        self._tool = tool
        self.name = tool.name
        self.description = tool.description

    def _get_declaration(self) -> genai_types.FunctionDeclaration:
        return genai_types.FunctionDeclaration(
            name="google_search",
            description=(
                "Performs a Google web search to research qualitative flight "
                "amenities such as WiFi availability/speed, seat pitch and "
                "legroom, aircraft features, and in-flight entertainment."
            ),
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "query": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="The search query for airline/flight research.",
                    )
                },
                required=["query"],
            ),
        )


class _AgentHierarchyAdapter:
    """Lightweight adapter exposing ADK v2 Workflow and sub-agents to ScenarioGenerator."""

    def __init__(
        self,
        name: str,
        description: str,
        instruction: str,
        tools: List[Any],
        sub_agents: List[Any],
        agent_type: str = "LlmAgent",
    ) -> None:
        self.name = name
        self.description = description
        self.instruction = instruction
        self.tools = tools
        self.sub_agents = sub_agents
        self.__class__ = type(agent_type, (_AgentHierarchyAdapter,), {})


def build_agent_adapter_from_workflow(workflow: Workflow) -> Any:
    """Extracts sub-agents and tools from an ADK v2 Workflow into a ScenarioGenerator-compatible hierarchy."""
    sub_agent_adapters: List[Any] = []
    graph = workflow._require_graph()

    for node in graph.nodes:
        if not isinstance(node, Agent):
            continue

        adapted_tools: List[Any] = []
        for tool in getattr(node, "tools", []) or []:
            if isinstance(tool, GoogleSearchTool):
                adapted_tools.append(_GoogleSearchToolDeclarationAdapter(tool))
            else:
                adapted_tools.append(tool)

        sub_agent_adapters.append(
            _AgentHierarchyAdapter(
                name=node.name,
                description=node.description or "",
                instruction=str(node.instruction or ""),
                tools=adapted_tools,
                sub_agents=[],
                agent_type="LlmAgent",
            )
        )

    workflow_instruction = (
        "Central conversational flight workflow orchestrator.\n"
        "ARCHITECTURE NOTE: `engage`, `filter`, `filter_smart`, `inspiration`, and `json_parser` are "
        "specialist workflow sub-agents, NOT callable function tools. The ONLY external function tool in "
        "the entire system is `google_search` (available exclusively to the `filter_smart` sub-agent when "
        "external web research is needed for qualitative flight amenities).\n"
        "WORKFLOW ROUTING:\n"
        "1. First routes the user's single-turn request to the `engage` sub-agent to classify the intent "
        "into one of four routing decisions (`agent_decision`): `filter`, `filter_smart`, `inspiration_agent`, or `continue`.\n"
        "2. When `agent_decision == 'filter'`, routes to the `filter` sub-agent to extract deterministic "
        "database filter parameters (`direct`, `max_price`, `max_stops`). No external tools are called.\n"
        "3. When `agent_decision == 'filter_smart'`, routes to the `filter_smart` sub-agent to filter candidate "
        "flights by airline or departure time window using session data, or by qualitative amenities (such as "
        "Wi-Fi quality, legroom/seat pitch, or entertainment) using the `google_search` tool (with automatic "
        "fallback to the `json_parser` sub-agent if JSON repair is needed).\n"
        "4. When `agent_decision == 'inspiration_agent'`, routes to the `inspiration` sub-agent to suggest "
        "concrete destinations and dates for open-ended travel requests. No external tools are called.\n"
        "5. When `agent_decision == 'continue'`, responds directly to the user with a clarifying message.\n"
        "FINAL WORKFLOW OUTPUT (`ConversationalOutput` JSON):\n"
        "- `agent_response` (str): Natural language response to the user.\n"
        "- `agent_decision` (Literal['filter', 'filter_smart', 'inspiration_agent', 'continue']): Selected routing decision.\n"
        "- `filter_type` (Optional[Literal['direct', 'max_price', 'max_stops']]): Present when `agent_decision == 'filter'`.\n"
        "- `filter_value` (Optional[int]): Present when `agent_decision == 'filter'` (1 for direct, budget integer for max_price, stop count integer for max_stops).\n"
        "- `flights_output` (Optional[List[Flight]]): Filtered subset of `flights_input`, present when `agent_decision == 'filter_smart'`.\n"
        "- `flights_search_output` (Optional[FlightParams]): Updated search parameters (`origin`, `destination`, `departure_date`, `return_date`, `passengers`), present when `agent_decision == 'inspiration_agent'`."
    )

    return _AgentHierarchyAdapter(
        name=workflow.name,
        description=workflow.description or "",
        instruction=workflow_instruction,
        tools=[],
        sub_agents=sub_agent_adapters,
        agent_type="RouterAgent",
    )


def generate_and_save_scenarios(
    config_path: str = DEFAULT_CONFIG_PATH,
    session_input_path: str = DEFAULT_SESSION_INPUT_PATH,
    scenarios_output_path: str = DEFAULT_SCENARIOS_OUTPUT_PATH,
    evalset_output_path: str = DEFAULT_EVALSET_OUTPUT_PATH,
    eval_set_id: str = "conversational_synthetic",
    location_override: str | None = None,
    count_override: int | None = None,
) -> tuple[ConversationScenarios, EvalSet]:
    """Runs the GEAP ScenarioGenerator and saves both ConversationScenarios and EvalSet datasets."""
    load_dotenv()

    if location_override:
        os.environ["GOOGLE_CLOUD_LOCATION"] = location_override

    with open(config_path, "r", encoding="utf-8") as f:
        config = ConversationGenerationConfig.model_validate_json(f.read())

    if count_override is not None:
        config.count = count_override

    with open(session_input_path, "r", encoding="utf-8") as f:
        base_session_input = SessionInput.model_validate_json(f.read())

    workflow_adapter = build_agent_adapter_from_workflow(conversational)
    logger.info(
        f"Prepared Workflow Agent hierarchy for '{workflow_adapter.name}' with sub-agents: "
        f"{[sa.name for sa in workflow_adapter.sub_agents]}"
    )

    try:
        generator = ScenarioGenerator()
        logger.info(
            f"Calling GEAP ScenarioGenerator (project={os.environ.get('GOOGLE_CLOUD_PROJECT')}, "
            f"location={os.environ.get('GOOGLE_CLOUD_LOCATION')}, count={config.count}, model={config.model_name})..."
        )
        scenarios: List[ConversationScenario] = generator.generate_scenarios(
            agent=workflow_adapter,
            config=config,
        )
    except Exception as exc:
        from google.auth.exceptions import DefaultCredentialsError, RefreshError

        if isinstance(exc, (RefreshError, DefaultCredentialsError)):
            raise
        current_loc = os.environ.get("GOOGLE_CLOUD_LOCATION", "")
        if current_loc != "us-central1" and not location_override:
            logger.warning(
                f"Scenario generation in location '{current_loc}' failed ({exc}). "
                "Retrying with GOOGLE_CLOUD_LOCATION='us-central1'..."
            )
            os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
            generator = ScenarioGenerator()
            scenarios = generator.generate_scenarios(
                agent=workflow_adapter,
                config=config,
            )
        else:
            raise

    logger.info(f"Generated {len(scenarios)} synthetic scenarios.")

    # 1. Save raw ConversationScenarios JSON
    os.makedirs(os.path.dirname(scenarios_output_path), exist_ok=True)
    conversation_scenarios = ConversationScenarios(scenarios=scenarios)
    with open(scenarios_output_path, "w", encoding="utf-8") as f:
        f.write(
            conversation_scenarios.model_dump_json(
                indent=2,
                exclude_none=True,
            )
        )
    logger.info(f"Saved ConversationScenarios to {scenarios_output_path}")

    # 2. Build and save ADK EvalSet JSON
    eval_cases: List[EvalCase] = []
    seen_ids: set[str] = set()
    now_ts = datetime.now().timestamp()

    for scenario in scenarios:
        scenario_str = json.dumps(scenario.model_dump(), sort_keys=True)
        eval_id = hashlib.sha256(scenario_str.encode("utf-8")).hexdigest()[:8]
        if eval_id in seen_ids:
            continue
        seen_ids.add(eval_id)

        # Populate user_message in a per-case copy of session_input.state
        case_state = dict(base_session_input.state)
        case_state["user_message"] = scenario.starting_prompt
        case_session_input = base_session_input.model_copy(
            update={"state": case_state}
        )

        eval_cases.append(
            EvalCase(
                eval_id=eval_id,
                conversation_scenario=scenario,
                session_input=case_session_input,
                creation_timestamp=now_ts,
            )
        )

    eval_set = EvalSet(
        eval_set_id=eval_set_id,
        name=eval_set_id,
        description=(
            "Synthetic 1-turn evaluation scenarios generated by the GEAP "
            "Scenario Generator covering conversational_app sub-agents and tools."
        ),
        eval_cases=eval_cases,
        creation_timestamp=now_ts,
    )

    os.makedirs(os.path.dirname(evalset_output_path), exist_ok=True)
    with open(evalset_output_path, "w", encoding="utf-8") as f:
        f.write(
            eval_set.model_dump_json(
                indent=2,
                exclude_unset=True,
                exclude_defaults=True,
                exclude_none=True,
            )
        )
    logger.info(
        f"Saved EvalSet '{eval_set_id}' ({len(eval_cases)} cases) to {evalset_output_path}"
    )

    return conversation_scenarios, eval_set


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic 1-turn scenarios using the GEAP Scenario Generator."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to scenario_generation_config.json",
    )
    parser.add_argument(
        "--session-input",
        default=DEFAULT_SESSION_INPUT_PATH,
        help="Path to session_input.json",
    )
    parser.add_argument(
        "--scenarios-output",
        default=DEFAULT_SCENARIOS_OUTPUT_PATH,
        help="Output path for synthetic_scenarios.json",
    )
    parser.add_argument(
        "--evalset-output",
        default=DEFAULT_EVALSET_OUTPUT_PATH,
        help="Output path for conversational_synthetic.evalset.json",
    )
    parser.add_argument(
        "--eval-set-id",
        default="conversational_synthetic",
        help="Identifier for the generated EvalSet",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Optional GCP location override for Vertex Eval API (e.g. us-central1)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Optional override for number of scenarios to generate (defaults to config count=50)",
    )
    args = parser.parse_args()

    scenarios_container, _ = generate_and_save_scenarios(
        config_path=args.config,
        session_input_path=args.session_input,
        scenarios_output_path=args.scenarios_output,
        evalset_output_path=args.evalset_output,
        eval_set_id=args.eval_set_id,
        location_override=args.location,
        count_override=args.count,
    )

    for idx, scenario in enumerate(scenarios_container.scenarios, start=1):
        logger.info(
            f"Scenario #{idx}:\n{format_dict_for_logs(scenario.model_dump(exclude_none=True))}"
        )


if __name__ == "__main__":
    main()
