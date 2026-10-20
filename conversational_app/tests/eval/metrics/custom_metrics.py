# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Custom deterministic and LLM-as-a-Judge metrics for conversational_app."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List

from pydantic import ValidationError
import vertexai
from vertexai import types as vertex_types

from app.app_utils.logging import setup_logging
from app.schema import ConversationalOutput, FlightParams

logger = setup_logging(name=__name__)


CONVERSATION_PLAN_ALIGNMENT_TEMPLATE = """# Instruction
You are an expert evaluator grading a flight booking multi-agent system (`conversational_app`).
Your task is to evaluate whether the agent's final JSON response (`ConversationalOutput`) accurately satisfies the expected ground-truth criteria specified in the `Expected Conversation Plan`.

The agent's final response is a JSON object conforming to `ConversationalOutput`:
- `agent_response` (str): Natural language message to the user.
- `agent_decision` (Literal['filter', 'filter_smart', 'inspiration_agent', 'continue']): Routing decision selected by the agent.
- `filter_type` (Optional[Literal['direct', 'max_price', 'max_stops']]): Present when `agent_decision == 'filter'`.
- `filter_value` (Optional[int]): Present when `agent_decision == 'filter'`.
- `flights_output` (Optional[List[Flight]]): Filtered subset of session flights, present when `agent_decision == 'filter_smart'`.
- `flights_search_output` (Optional[FlightParams]): Updated search parameters (`origin`, `destination`, `departure_date`, `return_date`, `passengers`), present when `agent_decision == 'inspiration_agent'`.

# Evaluation
## Criteria
1. Routing Decision Match: `agent_decision` in the response must match the expected decision described in the `Expected Conversation Plan`.
2. Structured Output Match:
   - If `agent_decision == 'filter'`, `filter_type` and `filter_value` must match the expected filter type and value in the plan.
   - If `agent_decision == 'filter_smart'`, `flights_output` must contain the flights from the session context that satisfy the user's filter criteria as described in the plan.
   - If `agent_decision == 'inspiration_agent'`, `flights_search_output` must contain concrete, valid destination/date search parameters matching the user's request as described in the plan.
   - If `agent_decision == 'continue'`, the agent must not fabricate filters or flights and must provide a helpful clarifying response.
3. Natural Language Response Alignment: `agent_response` must accurately reflect the action taken and address the user's prompt.

## Rating Scores
1: Pass - The `ConversationalOutput` JSON satisfies all expected ground-truth criteria in the `Expected Conversation Plan`.
0: Fail - The `ConversationalOutput` JSON has an incorrect `agent_decision`, wrong/missing structured output fields, or contradicts the `Expected Conversation Plan`.

## Evaluation Steps
Step 1: Compare `agent_decision` and the structured fields (`filter_type`, `filter_value`, `flights_output`, `flights_search_output`, `agent_response`) in the AI-generated Response against the `Expected Conversation Plan`.
Step 2: Assign a score of 1 (Pass) or 0 (Fail) and provide a concise rationale.

# User Inputs and AI-generated Response
## User Prompt
<prompt>{prompt}</prompt>

## Expected Conversation Plan (Ground Truth)
<conversation_plan>{conversation_plan}</conversation_plan>

## Session Context (Available Flights & Search Params)
<context>{context}</context>

## AI-generated Response
<response>{response}</response>

# Output Format
Output ONLY a valid JSON object with double-quoted keys "score" (number: 1 or 0) and "explanation" (string), without markdown code fences. Example:
{"score": 1, "explanation": "Concise rationale here."}
"""


COHERENCE_FALLBACK_TEMPLATE = """# Instruction
You are an expert evaluator assessing the coherence and clarity of an AI travel assistant's response.
Note that the AI system outputs a structured JSON object (`ConversationalOutput`) containing an `agent_response` text field along with structured routing/filter fields. Evaluate the coherence of the `agent_response` message and its consistency with the structured JSON fields.

# Evaluation
## Criteria
1. Logical Flow & Clarity: The `agent_response` text is well-structured, grammatically sound, easy to understand, and logically organized.
2. Internal Consistency: The natural language `agent_response` is completely consistent with the accompanying structured fields (`agent_decision`, `filter_type`, `filter_value`, `flights_output`, `flights_search_output`) in the JSON output.

## Rating Scores
1: Coherent - The response is clear, logically structured, and internally consistent.
0: Incoherent - The response is confusing, poorly structured, self-contradictory, or inconsistent with its structured fields.

## Evaluation Steps
Step 1: Inspect the `agent_response` text and structured fields in the AI-generated Response.
Step 2: Assign a score of 1 or 0 with a brief explanation.

# User Inputs and AI-generated Response
## User Prompt
<prompt>{prompt}</prompt>

## AI-generated Response
<response>{response}</response>

# Output Format
Output ONLY a valid JSON object with double-quoted keys "score" (number: 1 or 0) and "explanation" (string), without markdown code fences. Example:
{"score": 1, "explanation": "Concise rationale here."}
"""


TOOL_USE_QUALITY_TEMPLATE = """# Instruction
You are an expert evaluator grading external tool usage (`google_search`) in a flight booking multi-agent workflow (`conversational_app`).

## Architecture & Tool Definitions
- `engage`, `filter`, `filter_smart`, `inspiration`, and `json_parser` are internal workflow sub-agents, NOT external function tools. Routing between these sub-agents is normal internal workflow orchestration and must NOT be treated as a tool call.
- `google_search` (available exclusively to the `filter_smart` sub-agent) is the ONLY external function tool in the application.
  - Tool declaration: `google_search(query: str)` — Performs a Google web search to research qualitative flight/airline amenities not present in the structured `flights_input` session data (such as Wi-Fi availability/reliability/speed, seat pitch/legroom, aircraft cabin features, and in-flight entertainment).

# Evaluation
## Criteria
1. When External Research Is Required (Positive Tool Constraint):
   - If the User Prompt or `Expected Conversation Plan` asks to filter or evaluate flights based on qualitative amenities not explicitly present in `flights_input` (e.g., Wi-Fi quality/reliability, legroom/seat pitch, entertainment, cabin comfort), `filter_smart` MUST call `google_search` (`Recorded External Tool Calls` must contain at least one `google_search` call).
   - The `google_search` call must adhere to its schema (`args.query` must be a non-empty string) and its `query` must be semantically relevant to the requested amenity and candidate airlines/flights.
   - The final `response` must incorporate the external search findings accurately.
2. When Internal Session Data Is Sufficient (Negative Tool Constraint):
   - If the User Prompt can be answered strictly using existing session state (`flights_input` or `flights_search_input` — such as hard database filters `direct`/`max_price`/`max_stops`, explicit airline or departure time window filters, travel inspiration destination/date changes, or conversational clarification), `google_search` must NOT be called (`Recorded External Tool Calls` must be empty `[]`).

## Rating Scores
1: Pass - External tool usage is completely appropriate: either `google_search` was required and called with a valid, relevant `query` whose findings were used, OR `google_search` was not required and no unnecessary external tool calls were made.
0: Fail - External tool usage is incorrect: either `google_search` was required by the prompt/plan but was not called (or called with an invalid/irrelevant `query`), OR `google_search` was called unnecessarily when internal session data was sufficient.

## Evaluation Steps
Step 1: Determine from the User Prompt and `Expected Conversation Plan` whether external web research via `google_search` is required or whether internal session state is sufficient.
Step 2: Inspect `Recorded External Tool Calls` (`<tool_calls>`) and the AI-generated Response (`<response>`) against Criteria 1 and 2.
Step 3: Output a score of 1 (Pass) or 0 (Fail) and a concise rationale.

# User Inputs, Tool Calls, and AI-generated Response
## User Prompt
<prompt>{prompt}</prompt>

## Expected Conversation Plan
<conversation_plan>{conversation_plan}</conversation_plan>

## Recorded External Tool Calls (`google_search`)
<tool_calls>{tool_calls}</tool_calls>

## AI-generated Response
<response>{response}</response>

# Output Format
Output ONLY a valid JSON object with double-quoted keys "score" (number: 1 or 0) and "explanation" (string), without markdown code fences. Example:
{"score": 1, "explanation": "Concise rationale here."}
"""


def evaluate_schema_and_contract(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Custom deterministic Python metric validating ConversationalOutput schema and invariants."""
    response_obj = instance.get("response") or {}
    parts = response_obj.get("parts") or []
    response_text = "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and part.get("text")
    )

    if not response_text.strip():
        return {"score": 0.0, "explanation": "Empty response text from agent."}

    try:
        raw_dict = json.loads(response_text)
    except json.JSONDecodeError as exc:
        return {"score": 0.0, "explanation": f"Response is not valid JSON: {exc}"}

    try:
        parsed = ConversationalOutput.model_validate(raw_dict)
    except ValidationError as exc:
        return {
            "score": 0.0,
            "explanation": f"ConversationalOutput Pydantic validation failed: {exc}",
        }

    if not parsed.agent_response or not parsed.agent_response.strip():
        return {"score": 0.0, "explanation": "agent_response is empty."}

    decision = parsed.agent_decision

    if decision == "filter":
        if parsed.filter_type not in {"direct", "max_price", "max_stops"}:
            return {
                "score": 0.0,
                "explanation": (
                    f"Invalid filter_type '{parsed.filter_type}' for agent_decision='filter'. "
                    "Expected one of {'direct', 'max_price', 'max_stops'}."
                ),
            }
        if parsed.filter_value is None or not isinstance(parsed.filter_value, int):
            return {
                "score": 0.0,
                "explanation": (
                    f"Missing or non-integer filter_value '{parsed.filter_value}' "
                    "for agent_decision='filter'."
                ),
            }
        if parsed.filter_type == "direct" and parsed.filter_value != 1:
            return {
                "score": 0.0,
                "explanation": (
                    f"For filter_type='direct', expected filter_value=1, got {parsed.filter_value}."
                ),
            }
        return {
            "score": 1.0,
            "explanation": (
                f"Valid ConversationalOutput for decision='filter' "
                f"(filter_type='{parsed.filter_type}', filter_value={parsed.filter_value})."
            ),
        }

    if decision == "filter_smart":
        if parsed.flights_output is None or not isinstance(parsed.flights_output, list):
            return {
                "score": 0.0,
                "explanation": "flights_output must be a list when agent_decision='filter_smart'.",
            }
        session_inputs = instance.get("session_inputs") or {}
        if isinstance(session_inputs, str):
            try:
                session_inputs = json.loads(session_inputs)
            except json.JSONDecodeError:
                session_inputs = {}
        state = session_inputs.get("state") or {}
        input_flights = state.get("flights_input") or []
        allowed_flight_numbers = {
            f.get("flight_number")
            for f in input_flights
            if isinstance(f, dict) and f.get("flight_number")
        }
        if allowed_flight_numbers:
            returned_numbers = {f.flight_number for f in parsed.flights_output}
            unknown_flights = returned_numbers - allowed_flight_numbers
            if unknown_flights:
                return {
                    "score": 0.0,
                    "explanation": (
                        f"flights_output contains hallucinated flight_number(s) not in "
                        f"session flights_input: {sorted(unknown_flights)}."
                    ),
                }
        return {
            "score": 1.0,
            "explanation": (
                f"Valid ConversationalOutput for decision='filter_smart' "
                f"({len(parsed.flights_output)} valid subset flight(s) returned)."
            ),
        }

    if decision == "inspiration_agent":
        if parsed.flights_search_output is None or not isinstance(
            parsed.flights_search_output, FlightParams
        ):
            return {
                "score": 0.0,
                "explanation": (
                    "flights_search_output must be a valid FlightParams object "
                    "when agent_decision='inspiration_agent'."
                ),
            }
        fp = parsed.flights_search_output
        if not (fp.origin and fp.destination and fp.departure_date and fp.return_date):
            return {
                "score": 0.0,
                "explanation": f"flights_search_output has empty required fields: {fp.model_dump()}",
            }
        return {
            "score": 1.0,
            "explanation": (
                f"Valid ConversationalOutput for decision='inspiration_agent' "
                f"({fp.origin} -> {fp.destination}, {fp.departure_date} to {fp.return_date})."
            ),
        }

    if decision == "continue":
        if any(
            v is not None
            for v in (
                parsed.filter_type,
                parsed.filter_value,
                parsed.flights_output,
                parsed.flights_search_output,
            )
        ):
            return {
                "score": 0.0,
                "explanation": (
                    "For agent_decision='continue', filter_type, filter_value, "
                    "flights_output, and flights_search_output must all be null."
                ),
            }
        return {
            "score": 1.0,
            "explanation": "Valid ConversationalOutput for decision='continue'.",
        }

    return {"score": 0.0, "explanation": f"Unsupported agent_decision: {decision}"}


def evaluate_latency_seconds(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Custom deterministic Python metric returning end-to-end turn latency in seconds."""
    latency_sec = instance.get("latency_seconds")

    if latency_sec is None:
        agent_data = instance.get("agent_data") or {}
        turns = agent_data.get("turns") or []
        if turns:
            events = turns[0].get("events") or []
            timestamps = []
            for ev in events:
                ts_str = ev.get("event_time")
                if isinstance(ts_str, str):
                    try:
                        timestamps.append(
                            datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        )
                    except ValueError:
                        pass
            if len(timestamps) >= 2:
                latency_sec = max(
                    0.0, (timestamps[-1] - timestamps[0]).total_seconds()
                )

    if latency_sec is None:
        return {
            "score": 0.0,
            "explanation": "Latency data unavailable in trace record.",
        }

    latency_val = round(float(latency_sec), 4)
    step_latencies = instance.get("sub_agent_latencies_seconds") or []
    if isinstance(step_latencies, list) and step_latencies:
        breakdown = ", ".join(
            f"{step.get('author')}: {float(step.get('latency_seconds', 0.0)):.3f}s"
            for step in step_latencies
            if isinstance(step, dict) and step.get("author")
        )
        explanation = f"End-to-end turn latency: {latency_val:.3f}s ({breakdown})."
    else:
        explanation = f"End-to-end turn latency: {latency_val:.3f}s."

    return {
        "score": latency_val,
        "explanation": explanation,
    }


CUSTOM_PYTHON_METRICS_REGISTRY = {
    "schema_and_contract_valid": evaluate_schema_and_contract,
    "latency_seconds": evaluate_latency_seconds,
}

CUSTOM_LLM_TEMPLATES_REGISTRY = {
    "conversation_plan_alignment": CONVERSATION_PLAN_ALIGNMENT_TEMPLATE,
    "tool_use_quality": TOOL_USE_QUALITY_TEMPLATE,
}


def build_evaluation_metrics(
    client: vertexai.Client,
    eval_config: Dict[str, Any],
) -> List[Any]:
    """Resolves predefined and custom GEAP metrics defined in eval_config.json."""
    raw_judge_model = eval_config.get("judge_model")
    judge_model = (
        raw_judge_model
        if isinstance(raw_judge_model, str)
        and (
            raw_judge_model.startswith("publishers/")
            or raw_judge_model.startswith("projects/")
        )
        else None
    )
    metrics: List[Any] = []

    for m_cfg in eval_config.get("metrics", []):
        m_type = m_cfg.get("type")
        m_name = m_cfg.get("name")

        if m_type == "predefined_rubric":
            rubric_attr = m_cfg.get("rubric_metric")
            if rubric_attr == "COHERENCE":
                metrics.append(
                    vertex_types.LLMMetric(
                        name="coherence",
                        prompt_template=COHERENCE_FALLBACK_TEMPLATE,
                        judge_model=judge_model,
                    )
                )
            elif rubric_attr == "MULTI_TURN_TOOL_USE_QUALITY":
                metrics.append(
                    vertex_types.LLMMetric(
                        name=m_name or "tool_use_quality",
                        prompt_template=TOOL_USE_QUALITY_TEMPLATE,
                        judge_model=judge_model,
                    )
                )
            else:
                metrics.append(getattr(vertex_types.RubricMetric, rubric_attr))

        elif m_type == "predefined":
            metrics.append(vertex_types.Metric(name=m_name))

        elif m_type == "custom_python":
            fn = CUSTOM_PYTHON_METRICS_REGISTRY.get(m_name)
            if not fn:
                raise ValueError(f"Unknown custom_python metric: {m_name}")
            metrics.append(
                vertex_types.Metric(
                    name=m_name,
                    custom_function=fn,
                )
            )

        elif m_type == "custom_llm":
            template = CUSTOM_LLM_TEMPLATES_REGISTRY.get(m_name)
            if not template:
                raise ValueError(f"Unknown custom_llm metric: {m_name}")
            metrics.append(
                vertex_types.LLMMetric(
                    name=m_name,
                    prompt_template=template,
                    judge_model=judge_model,
                )
            )

    return metrics

