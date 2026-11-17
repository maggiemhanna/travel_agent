# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Unit tests for Layer III.4 — API Design & Versioning (conversational_app).

Verifies:
1. Contract-First Design: Committed `openapi.json` matches live `api.openapi()` and defines typed response/probe schemas.
2. Backward Compatibility: Canonical `/api/v1/run-conversational` (plus `/api/v1/run-<sub_agent>`) and deprecated `/run-*` aliases, `X-API-Version` / `Deprecation` / `Link` headers, and safe defaults when optional containers (`conversational_history`, `flights_input`) are omitted.
3. Schema Evolution: Intra-service `Flight` & `FlightParams` deduplication, Tolerant Reader (`extra="ignore"`), cross-service `Flight` wire parity with `flights_search_app`, and Vertex AI Gemini `output_schema` safety.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.runners import Runner
import pytest

from app.app_utils.versioning import API_V1_PREFIX, API_VERSION
from app.export_openapi import OPENAPI_SNAPSHOT_PATH, generate_openapi_spec
from app.main import api
from app.schema import (
    ConversationalInput,
    ConversationalOutput,
    Flight,
    FlightParams,
)
from app.sub_agents.engage.main import api as engage_api
from app.sub_agents.engage.schema import EngageOutput
from app.sub_agents.filter.main import api as filter_api
from app.sub_agents.filter.schema import FilterOutput
from app.sub_agents.filter_smart.main import api as filter_smart_api
from app.sub_agents.filter_smart.schema import (
    FilterSmartOutput,
    Flight as FilterSmartFlight,
)
from app.sub_agents.inspiration.main import api as inspiration_api
from app.sub_agents.inspiration.schema import (
    FlightParams as InspirationFlightParams,
    InspirationOutput,
)
from app.sub_agents.json_parser.main import api as json_parser_api
from app.sub_agents.json_parser.schema import (
    Flight as JSONParserFlight,
    JSONParserOutput,
)


SAMPLE_FLIGHT: Dict[str, Any] = {
    "origin": "Paris (CDG)",
    "destination": "New York (JFK)",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "departure_time": "10:30",
    "arrival_time": "13:00",
    "return_time": "17:30",
    "return_arrival_time": "06:45 +1",
    "price": "520 EUR",
    "airline": "Air France",
    "flight_number": "AF006",
    "stops": 0,
    "stopover_cities": [],
}


def _mock_event(body: Dict[str, Any]) -> Any:
    return SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=json.dumps(body))])
    )


def _assert_no_true_additional_properties(node: Any) -> None:
    if isinstance(node, dict):
        assert node.get("additionalProperties") is not True, (
            f"Vertex AI Gemini output_schema forbids additionalProperties=True: {node}"
        )
        for value in node.values():
            _assert_no_true_additional_properties(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_true_additional_properties(item)


def test_committed_openapi_contract_snapshot_is_in_sync() -> None:
    """Live FastAPI OpenAPI 3.1 contract must match committed conversational_app/openapi.json."""
    assert OPENAPI_SNAPSHOT_PATH.exists(), (
        f"Missing OpenAPI contract snapshot at {OPENAPI_SNAPSHOT_PATH}. "
        "Run `python3 -m app.export_openapi`."
    )
    committed = json.loads(OPENAPI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    live = generate_openapi_spec()

    assert live == committed, (
        "OpenAPI contract drift detected in conversational_app! "
        "Review breaking/non-breaking changes and run `python3 -m app.export_openapi` to update openapi.json."
    )
    assert committed["openapi"].startswith("3.1.")
    assert committed["info"]["version"] == API_VERSION

    schemas = committed["components"]["schemas"]
    for required_schema in (
        "ConversationalInput",
        "ConversationalOutput",
        "ConversationalResponse",
        "Flight",
        "FlightParams",
        "RawTextFallback",
        "LivenessResponse",
        "ReadinessResponse",
        "UnreadyResponse",
    ):
        assert required_schema in schemas, f"Missing {required_schema} in OpenAPI schemas"

    assert f"{API_V1_PREFIX}/run-conversational" in committed["paths"]
    assert "/run-conversational" in committed["paths"]
    assert committed["paths"]["/run-conversational"]["post"].get("deprecated") is True
    assert (
        committed["paths"][f"{API_V1_PREFIX}/run-conversational"]["post"].get(
            "deprecated"
        )
        is not True
    )


def test_v1_and_legacy_routes_across_orchestrator_and_sub_agents() -> None:
    """Canonical /api/v1/run-* and legacy /run-* aliases must return matching payloads and expected headers."""
    minimal_payload = {
        "user_message": "Hello! Can you help me plan a trip?",
        "flights_search_input": {
            "origin": "Paris",
            "destination": "New York",
            "departure_date": "2026-05-10",
            "return_date": "2026-05-20",
            "passengers": 1,
        },
        # Intentionally omitting `conversational_history` and `flights_input` to test safe container defaults
    }

    async def _mock_conv_run(runner_self, *args, **kwargs):
        return [
            _mock_event(
                {
                    "agent_response": "Happy to help! Tell me your budget or travel preferences.",
                    "agent_decision": "continue",
                }
            )
        ]

    with TestClient(api) as client:
        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_mock_conv_run
        ):
            v1_resp = client.post(
                f"{API_V1_PREFIX}/run-conversational", json=minimal_payload
            )
            legacy_resp = client.post("/run-conversational", json=minimal_payload)

    assert v1_resp.status_code == 200
    assert legacy_resp.status_code == 200
    assert v1_resp.json() == legacy_resp.json()
    assert v1_resp.json() == {
        "status": "success",
        "results": {
            "agent_response": "Happy to help! Tell me your budget or travel preferences.",
            "agent_decision": "continue",
        },
    }

    assert v1_resp.headers.get("X-API-Version") == API_VERSION
    assert "Deprecation" not in v1_resp.headers
    assert legacy_resp.headers.get("X-API-Version") == API_VERSION
    assert legacy_resp.headers.get("Deprecation") == "true"
    assert (
        legacy_resp.headers.get("Link")
        == f'<{API_V1_PREFIX}/run-conversational>; rel="successor-version"'
    )

    # Verify all 5 standalone sub-agent APIs also expose /api/v1/run-<name> + deprecated /run-<name>
    sub_agent_cases = [
        (
            engage_api,
            "run-engage",
            {"user_message": "Direct flights"},
            {"agent_response": "Routing to filter.", "agent_decision": "filter"},
        ),
        (
            filter_api,
            "run-filter",
            {"user_message": "Direct flights"},
            {
                "agent_response": "Filtering direct flights.",
                "filter_type": "direct",
                "filter_value": 1,
            },
        ),
        (
            filter_smart_api,
            "run-filter-smart",
            {"user_message": "Air France flights"},
            {
                "agent_response": "Kept AF006.",
                "flights_output": [SAMPLE_FLIGHT],
            },
        ),
        (
            inspiration_api,
            "run-inspiration",
            {
                "user_message": "Somewhere warm",
                "flights_search_input": minimal_payload["flights_search_input"],
            },
            {
                "agent_response": "Try Lisbon!",
                "flights_search_output": {
                    "origin": "Paris",
                    "destination": "Lisbon",
                    "departure_date": "2026-05-10",
                    "return_date": "2026-05-20",
                    "passengers": 1,
                },
            },
        ),
        (
            json_parser_api,
            "run-json-parser",
            {"agent_response": '{"agent_response":"ok","flights_output":[]}'},
            {"agent_response": "ok", "flights_output": []},
        ),
    ]

    for sub_api, slug, req_body, mock_out in sub_agent_cases:
        async def _mock_sub_run(runner_self, *args, _out=mock_out, **kwargs):
            return [_mock_event(_out)]

        with TestClient(sub_api) as sub_client:
            with patch.object(
                Runner, "run_debug", autospec=True, side_effect=_mock_sub_run
            ):
                s_v1 = sub_client.post(f"{API_V1_PREFIX}/{slug}", json=req_body)
                s_leg = sub_client.post(f"/{slug}", json=req_body)
            assert s_v1.status_code == 200 and s_leg.status_code == 200
            assert s_v1.json() == s_leg.json()
            assert s_v1.headers.get("X-API-Version") == API_VERSION
            assert "Deprecation" not in s_v1.headers
            assert s_leg.headers.get("Deprecation") == "true"
            assert (
                s_leg.headers.get("Link")
                == f'<{API_V1_PREFIX}/{slug}>; rel="successor-version"'
            )


def test_intra_service_schema_deduplication_and_tolerant_reader() -> None:
    """Sub-agents must share canonical Flight/FlightParams models and tolerate unknown future fields."""
    assert FilterSmartFlight is Flight
    assert JSONParserFlight is Flight
    assert InspirationFlightParams is FlightParams

    # Safe per-request container isolation
    inp_a = ConversationalInput(
        user_message="Hi",
        flights_search_input=FlightParams(
            origin="Paris",
            destination="Rome",
            departure_date="2026-05-10",
            return_date="2026-05-20",
            passengers=1,
        ),
    )
    inp_b = ConversationalInput(
        user_message="Hello",
        flights_search_input=FlightParams(
            origin="Paris",
            destination="Madrid",
            departure_date="2026-05-10",
            return_date="2026-05-20",
            passengers=1,
        ),
    )
    assert inp_a.conversational_history == [] and inp_a.flights_input == []
    assert inp_a.conversational_history is not inp_b.conversational_history
    assert inp_a.flights_input is not inp_b.flights_input

    # Tolerant Reader: forward-compatible payload with extra unknown fields succeeds
    evolved_payload = {
        "user_message": "Filter morning flights",
        "future_locale_v2": "en-US",
        "flights_search_input": {
            "origin": "Paris",
            "destination": "New York",
            "departure_date": "2026-05-10",
            "return_date": "2026-05-20",
            "passengers": 1,
            "flexible_dates_v2": True,
        },
        "flights_input": [
            {**SAMPLE_FLIGHT, "aircraft_model_v2": "Airbus A350-900"}
        ],
    }
    validated = ConversationalInput.model_validate(evolved_payload)
    assert len(validated.flights_input) == 1
    assert validated.flights_input[0].flight_number == "AF006"


def test_adk_output_schemas_and_cross_service_flight_parity() -> None:
    """All LLM output_schema classes must avoid additionalProperties=True and match flights_search_app Flight contract."""
    for output_model in (
        ConversationalOutput,
        EngageOutput,
        FilterOutput,
        FilterSmartOutput,
        InspirationOutput,
        JSONParserOutput,
    ):
        _assert_no_true_additional_properties(output_model.model_json_schema())

    sibling_openapi = (
        Path(__file__).resolve().parents[3] / "flights_search_app" / "openapi.json"
    )
    if not sibling_openapi.exists():
        pytest.skip("flights_search_app/openapi.json not present in isolated environment")

    conv_spec = json.loads(OPENAPI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    flights_spec = json.loads(sibling_openapi.read_text(encoding="utf-8"))

    assert (
        conv_spec["components"]["schemas"]["Flight"]
        == flights_spec["components"]["schemas"]["Flight"]
    ), "Cross-service Flight wire contract drifted between conversational_app and flights_search_app!"
