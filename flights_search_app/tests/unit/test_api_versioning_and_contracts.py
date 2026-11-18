# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Unit tests for Layer III.4 — API Design & Versioning (flights_search_app).

Verifies:
1. Contract-First Design: Committed `openapi.json` matches live `api.openapi()` and defines typed response/probe schemas.
2. Backward Compatibility: Canonical `/api/v1/run-flights-search` + deprecated `/run-flights-search` alias, `X-API-Version` / RFC 8594 `Deprecation` & `Link` headers, and safe defaults when `filters` is omitted.
3. Schema Evolution: Tolerant Reader (`extra="ignore"`), `AliasChoices` (`price`/`max_price`, `stops`/`max_stops`), cross-service `Flight` wire parity, and Vertex AI Gemini `output_schema` safety (no `additionalProperties: true`).
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
from app.schema import Filters, Flight, FlightsSearchInput, FlightsSearchOutput


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


def _mock_flights_runner(*args, **kwargs):
    return [
        SimpleNamespace(
            content=SimpleNamespace(
                parts=[
                    SimpleNamespace(
                        text=json.dumps({"flights": [SAMPLE_FLIGHT]})
                    )
                ]
            )
        )
    ]


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
    """Live FastAPI OpenAPI 3.1 contract must match committed flights_search_app/openapi.json."""
    assert OPENAPI_SNAPSHOT_PATH.exists(), (
        f"Missing OpenAPI contract snapshot at {OPENAPI_SNAPSHOT_PATH}. "
        "Run `python3 -m app.export_openapi`."
    )
    committed = json.loads(OPENAPI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    live = generate_openapi_spec()

    assert live == committed, (
        "OpenAPI contract drift detected in flights_search_app! "
        "Review breaking/non-breaking changes and run `python3 -m app.export_openapi` to update openapi.json."
    )
    assert committed["openapi"].startswith("3.1.")
    assert committed["info"]["version"] == API_VERSION

    schemas = committed["components"]["schemas"]
    for required_schema in (
        "FlightsSearchInput",
        "FlightsSearchOutput",
        "FlightsSearchResponse",
        "Flight",
        "Filters",
        "RawTextFallback",
        "LivenessResponse",
        "ReadinessResponse",
        "UnreadyResponse",
    ):
        assert required_schema in schemas, f"Missing {required_schema} in OpenAPI schemas"

    assert f"{API_V1_PREFIX}/run-flights-search" in committed["paths"]
    assert "/run-flights-search" in committed["paths"]
    assert committed["paths"]["/run-flights-search"]["post"].get("deprecated") is True
    assert (
        committed["paths"][f"{API_V1_PREFIX}/run-flights-search"]["post"].get(
            "deprecated"
        )
        is not True
    )

    # Verify validator bounds are surfaced directly in OpenAPI JSON Schema for code generators
    search_props = schemas["FlightsSearchInput"]["properties"]
    for str_field in ("origin", "destination", "departure_date", "return_date"):
        assert search_props[str_field]["minLength"] == 1
        assert search_props[str_field]["maxLength"] == 200
    assert search_props["passengers"]["minimum"] == 1
    assert search_props["passengers"]["maximum"] == 9
    assert schemas["Flight"]["properties"]["stops"]["minimum"] == 0
    for filter_field in ("max_price", "max_stops"):
        int_branch = next(
            b for b in schemas["Filters"]["properties"][filter_field]["anyOf"] if b.get("type") == "integer"
        )
        assert int_branch["minimum"] == 0


def test_v1_and_legacy_routes_preserve_backward_compatibility_and_headers() -> None:
    """Canonical /api/v1 route and legacy /run-flights-search alias must return identical payloads and expected headers."""
    minimal_payload = {
        "origin": "Paris",
        "destination": "New York",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-20",
        "passengers": 1,
        # Intentionally omitting `filters` to verify safe container default
    }

    with TestClient(api) as client:
        probe_resp = client.get("/healthz")
        assert probe_resp.status_code == 200
        assert probe_resp.headers.get("X-API-Version") == API_VERSION
        assert "Deprecation" not in probe_resp.headers

        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_mock_flights_runner
        ):
            v1_resp = client.post(
                f"{API_V1_PREFIX}/run-flights-search", json=minimal_payload
            )
            legacy_resp = client.post("/run-flights-search", json=minimal_payload)

    assert v1_resp.status_code == 200
    assert legacy_resp.status_code == 200
    assert v1_resp.json() == legacy_resp.json()
    assert v1_resp.json()["status"] == "success"
    assert v1_resp.json()["results"][0]["flights"][0]["flight_number"] == "AF006"

    # Versioned route emits X-API-Version without Deprecation headers
    assert v1_resp.headers.get("X-API-Version") == API_VERSION
    assert "Deprecation" not in v1_resp.headers
    assert "Link" not in v1_resp.headers

    # Legacy route emits X-API-Version + RFC 8594 Deprecation & successor Link headers
    assert legacy_resp.headers.get("X-API-Version") == API_VERSION
    assert legacy_resp.headers.get("Deprecation") == "true"
    assert (
        legacy_resp.headers.get("Link")
        == f'<{API_V1_PREFIX}/run-flights-search>; rel="successor-version"'
    )


def test_tolerant_reader_safe_defaults_and_alias_choices() -> None:
    """Input & domain schemas must ignore unknown future fields, isolate default containers, and honor AliasChoices."""
    # 1. Safe per-instance container defaults (no shared mutable state)
    req_a = FlightsSearchInput(
        origin="Paris",
        destination="Tokyo",
        departure_date="2026-06-01",
        return_date="2026-06-15",
        passengers=1,
    )
    req_b = FlightsSearchInput(
        origin="London",
        destination="Rome",
        departure_date="2026-07-01",
        return_date="2026-07-10",
        passengers=2,
    )
    assert req_a.filters is not req_b.filters
    assert req_a.filters.max_price is None

    # 2. AliasChoices + populate_by_name=True accepts both legacy/shorthand and canonical filter names
    shorthand = Filters.model_validate({"price": 650, "stops": 1})
    canonical = Filters.model_validate({"max_price": 650, "max_stops": 1})
    assert shorthand.max_price == 650 and shorthand.max_stops == 1
    assert canonical.max_price == 650 and canonical.max_stops == 1
    assert shorthand.model_dump() == canonical.model_dump()

    # Negative bounds on aliases must still be rejected with HTTP 422
    with TestClient(api) as client:
        bad_alias_resp = client.post(
            f"{API_V1_PREFIX}/run-flights-search",
            json={
                "origin": "Paris",
                "destination": "New York",
                "departure_date": "2026-05-10",
                "return_date": "2026-05-20",
                "passengers": 1,
                "filters": {"price": -50},
            },
        )
        assert bad_alias_resp.status_code == 422

        # 3. Tolerant Reader (Postel's Law): unknown future fields must be ignored cleanly
        forward_compatible_payload = {
            "origin": "Paris",
            "destination": "New York",
            "departure_date": "2026-05-10",
            "return_date": "2026-05-20",
            "passengers": 1,
            "cabin_class_v2": "economy_plus",
            "client_trace_id": "trace-999",
            "filters": {"price": 700, "refundable_only_v2": True},
        }
        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_mock_flights_runner
        ):
            forward_resp = client.post(
                f"{API_V1_PREFIX}/run-flights-search",
                json=forward_compatible_payload,
            )
        assert forward_resp.status_code == 200

    flight_with_future_field = Flight.model_validate(
        {**SAMPLE_FLIGHT, "co2_emissions_kg_v2": 410}
    )
    assert flight_with_future_field.flight_number == "AF006"


def test_adk_output_schema_safety_and_cross_service_flight_parity() -> None:
    """Gemini output_schema must remain free of additionalProperties=True and Flight wire schema must match conversational_app."""
    _assert_no_true_additional_properties(FlightsSearchOutput.model_json_schema())

    sibling_openapi = (
        Path(__file__).resolve().parents[3] / "conversational_app" / "openapi.json"
    )
    if not sibling_openapi.exists():
        pytest.skip("conversational_app/openapi.json not present in isolated environment")

    flights_spec = json.loads(OPENAPI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    conv_spec = json.loads(sibling_openapi.read_text(encoding="utf-8"))

    assert (
        flights_spec["components"]["schemas"]["Flight"]
        == conv_spec["components"]["schemas"]["Flight"]
    ), "Cross-service Flight wire contract drifted between flights_search_app and conversational_app!"
