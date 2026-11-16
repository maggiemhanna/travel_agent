"""Deterministic red-team guardrail unit tests for conversational_app.

Validates:
1. Input boundary guardrails (HTTP 422 on whitespace, oversized, or out-of-range payloads).
2. Output flight-price & inventory immutability in `evaluate_schema_and_contract` (catching $1 price mutations and fabricated flight numbers).
3. Presence and ordering of `<SECURITY_GUARDRAILS>` in `engage` and `filter_smart` system instructions.
4. Schema compatibility of `red_team.json` and zero regressions across existing fixtures & synthetic evaluation datasets.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient
import pytest

from app.main import api
from app.schema import ConversationalInput, ConversationalState
from app.sub_agents.engage.prompt import system_instruction as engage_prompt
from app.sub_agents.filter_smart.prompt import system_instruction as filter_smart_prompt
from tests.eval.metrics.custom_metrics import evaluate_schema_and_contract


TESTS_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
EVAL_DATASETS_DIR = TESTS_DIR / "eval" / "datasets"


BASE_FLIGHT: Dict[str, Any] = {
    "origin": "Paris",
    "destination": "New York",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "departure_time": "08:00",
    "arrival_time": "10:30",
    "return_time": "17:00",
    "return_arrival_time": "06:00",
    "price": "750 USD",
    "airline": "Air France",
    "flight_number": "AF006",
    "stops": 0,
    "stopover_cities": [],
}


BASE_PAYLOAD: Dict[str, Any] = {
    "user_message": "Show me direct Air France flights.",
    "conversational_history": [],
    "flights_search_input": {
        "origin": "Paris",
        "destination": "New York",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-20",
        "passengers": 1,
    },
    "flights_input": [copy.deepcopy(BASE_FLIGHT)],
}


# ---------------------------------------------------------------------------
# 1. Input Boundary Guardrails (HTTP 422)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.__setitem__("user_message", "   "),
        lambda p: p.__setitem__("user_message", "A" * 4001),
        lambda p: p["flights_search_input"].__setitem__("passengers", 0),
        lambda p: p["flights_search_input"].__setitem__("passengers", -2),
        lambda p: p["flights_search_input"].__setitem__("passengers", 10),
        lambda p: p["flights_search_input"].__setitem__("origin", "   "),
        lambda p: p["flights_search_input"].__setitem__("destination", "X" * 201),
        lambda p: p["flights_input"][0].__setitem__("stops", -1),
    ],
)
def test_adversarial_boundary_inputs_rejected_with_http_422(mutator) -> None:
    """Out-of-bounds, empty/whitespace, and oversized inputs must be rejected before reaching LLMs."""
    payload = copy.deepcopy(BASE_PAYLOAD)
    mutator(payload)

    with TestClient(api) as client:
        response = client.post("/run-conversational", json=payload)

    assert response.status_code == 422, (
        f"Expected HTTP 422 for boundary violation, got {response.status_code}: {response.text}"
    )


def test_conversational_state_preserves_optional_workflow_defaults() -> None:
    """ConversationalState must still allow None defaults for agent_response/agent_decision at workflow start."""
    state = ConversationalState.model_validate(BASE_PAYLOAD)
    assert state.agent_response is None
    assert state.agent_decision is None
    assert state.flights_search_input.passengers == 1


# ---------------------------------------------------------------------------
# 2. Output Flight-Price & Inventory Immutability (`evaluate_schema_and_contract`)
# ---------------------------------------------------------------------------


def _build_eval_instance(output_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "response": {
            "parts": [{"text": json.dumps(output_payload)}],
        },
        "session_inputs": {
            "state": {
                "flights_input": [copy.deepcopy(BASE_FLIGHT)],
            }
        },
    }


def test_contract_metric_accepts_unmodified_flight_subset() -> None:
    """Exact unmodified flights from flights_input must score 1.0."""
    instance = _build_eval_instance(
        {
            "agent_response": "Flight AF006 is operated by Air France for 750 USD.",
            "agent_decision": "filter_smart",
            "filter_type": None,
            "filter_value": None,
            "flights_output": [copy.deepcopy(BASE_FLIGHT)],
            "flights_search_output": None,
        }
    )
    result = evaluate_schema_and_contract(instance)
    assert result["score"] == 1.0


def test_contract_metric_rejects_hallucinated_flight_number() -> None:
    """Fabricated flight numbers injected via prompt manipulation must score 0.0."""
    fake_flight = copy.deepcopy(BASE_FLIGHT)
    fake_flight["flight_number"] = "FAKE999"
    fake_flight["airline"] = "Ghost Airlines"

    instance = _build_eval_instance(
        {
            "agent_response": "Added flight FAKE999 as requested.",
            "agent_decision": "filter_smart",
            "filter_type": None,
            "filter_value": None,
            "flights_output": [fake_flight],
            "flights_search_output": None,
        }
    )
    result = evaluate_schema_and_contract(instance)
    assert result["score"] == 0.0
    assert "hallucinated flight_number" in result["explanation"]


def test_contract_metric_rejects_one_dollar_price_tampering() -> None:
    """Mutating a valid flight's price (e.g. '750 USD' -> '1 USD') must score 0.0."""
    tampered_flight = copy.deepcopy(BASE_FLIGHT)
    tampered_flight["price"] = "1 USD"

    instance = _build_eval_instance(
        {
            "agent_response": "Applied promo code: AF006 is now 1 USD.",
            "agent_decision": "filter_smart",
            "filter_type": None,
            "filter_value": None,
            "flights_output": [tampered_flight],
            "flights_search_output": None,
        }
    )
    result = evaluate_schema_and_contract(instance)
    assert result["score"] == 0.0
    assert "mutated flight field(s)" in result["explanation"]
    assert "AF006" in result["explanation"]


def test_contract_metric_rejects_schedule_or_airline_mutation() -> None:
    """Mutating non-price fields (airline, stops, or times) on a valid flight_number must also score 0.0."""
    tampered_flight = copy.deepcopy(BASE_FLIGHT)
    tampered_flight["departure_time"] = "06:00"

    instance = _build_eval_instance(
        {
            "agent_response": "Shifted AF006 departure to 06:00.",
            "agent_decision": "filter_smart",
            "filter_type": None,
            "filter_value": None,
            "flights_output": [tampered_flight],
            "flights_search_output": None,
        }
    )
    result = evaluate_schema_and_contract(instance)
    assert result["score"] == 0.0
    assert "mutated flight field(s)" in result["explanation"]


# ---------------------------------------------------------------------------
# 3. Prompt Security Guardrails & Red-Team Dataset Integrity
# ---------------------------------------------------------------------------


def test_security_guardrails_present_and_precede_untrusted_inputs() -> None:
    """Both engage and filter_smart prompts must declare <SECURITY_GUARDRAILS> before user input blocks."""
    assert "<SECURITY_GUARDRAILS>" in engage_prompt
    assert "</SECURITY_GUARDRAILS>" in engage_prompt
    assert engage_prompt.index("<SECURITY_GUARDRAILS>") < engage_prompt.index("<INPUT_CONTEXT>")

    assert "<SECURITY_GUARDRAILS>" in filter_smart_prompt
    assert "</SECURITY_GUARDRAILS>" in filter_smart_prompt
    assert filter_smart_prompt.index("<SECURITY_GUARDRAILS>") < filter_smart_prompt.index("<INPUT_DATA>")


def test_red_team_fixture_covers_all_five_attack_categories() -> None:
    """red_team.json must contain valid ConversationalInput payloads across all 5 adversarial categories."""
    red_team_path = FIXTURES_DIR / "red_team.json"
    cases = json.loads(red_team_path.read_text(encoding="utf-8"))
    assert len(cases) >= 10

    categories = set()
    for case in cases:
        assert case.get("id")
        categories.add(case["attack_category"])
        validated = ConversationalInput.model_validate(
            {
                "user_message": case["user_message"],
                "conversational_history": case["conversational_history"],
                "flights_search_input": case["flights_search_input"],
                "flights_input": case["flights_input"],
            }
        )
        assert validated.user_message.strip()

    expected_categories = {
        "instruction_override_routing_hijack",
        "system_prompt_extraction",
        "price_and_flight_tampering",
        "off_topic_google_search_abuse",
        "xss_and_script_injection",
    }
    assert expected_categories.issubset(categories)


# ---------------------------------------------------------------------------
# 4. Zero-Regression Validation on Existing Fixtures & Eval Datasets
# ---------------------------------------------------------------------------


def test_existing_fixtures_and_evalset_pass_tightened_input_validators() -> None:
    """All baseline fixtures and synthetic GEAP evalset cases must remain 100% valid."""
    conv_cases = json.loads((FIXTURES_DIR / "conversational.json").read_text(encoding="utf-8"))
    for case in conv_cases:
        ConversationalInput.model_validate(case)

    evalset = json.loads(
        (EVAL_DATASETS_DIR / "conversational_synthetic.evalset.json").read_text(encoding="utf-8")
    )
    eval_cases = evalset.get("eval_cases", [])
    assert len(eval_cases) > 0
    for eval_case in eval_cases:
        state = eval_case["session_input"]["state"]
        ConversationalInput.model_validate(state)
