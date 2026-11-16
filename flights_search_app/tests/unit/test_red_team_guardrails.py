"""Deterministic boundary and red-team guardrail unit tests for flights_search_app.

Validates:
1. HTTP 422 rejection of negative `max_price`/`max_stops`, out-of-range `passengers`, and whitespace/oversized route or date fields on `/run-flights-search`.
2. Non-negative `stops` invariant on `Flight`.
3. Zero regressions against `tests/fixtures/flights_search.json` and preserved JSON Schema compatibility for Gemini `response_schema`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import api
from app.schema import Flight, FlightsSearchInput, FlightsSearchOutput


FIXTURES_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "flights_search.json"


BASE_SEARCH_PAYLOAD: Dict[str, Any] = {
    "origin": "Paris",
    "destination": "New York",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "passengers": 2,
    "filters": {
        "direct": False,
        "max_price": 900,
        "max_stops": 1,
    },
}


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.__setitem__("origin", "   "),
        lambda p: p.__setitem__("destination", "Z" * 201),
        lambda p: p.__setitem__("departure_date", ""),
        lambda p: p.__setitem__("return_date", "   "),
        lambda p: p.__setitem__("passengers", 0),
        lambda p: p.__setitem__("passengers", -3),
        lambda p: p.__setitem__("passengers", 10),
        lambda p: p["filters"].__setitem__("max_price", -100),
        lambda p: p["filters"].__setitem__("max_stops", -1),
    ],
)
def test_flights_search_boundary_violations_rejected_with_http_422(mutator) -> None:
    """Invalid passengers, negative filter bounds, and empty/oversized strings must return HTTP 422."""
    payload = copy.deepcopy(BASE_SEARCH_PAYLOAD)
    mutator(payload)

    with TestClient(api) as client:
        response = client.post("/run-flights-search", json=payload)

    assert response.status_code == 422, (
        f"Expected HTTP 422 for boundary violation, got {response.status_code}: {response.text}"
    )


def test_flight_model_rejects_negative_stops() -> None:
    """Flight objects with negative stops must fail Pydantic validation."""
    with pytest.raises(ValidationError):
        Flight(
            origin="Paris",
            destination="New York",
            departure_date="2026-05-10",
            return_date="2026-05-20",
            departure_time="08:00",
            arrival_time="10:30",
            return_time="17:00",
            return_arrival_time="06:00",
            price="750 USD",
            airline="Air France",
            flight_number="AF006",
            stops=-1,
            stopover_cities=[],
        )


def test_existing_flights_search_fixtures_and_output_json_schema_remain_valid() -> None:
    """Baseline fixtures must validate cleanly and FlightsSearchOutput JSON Schema must remain intact."""
    cases = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    for case in cases:
        validated = FlightsSearchInput.model_validate(case)
        assert validated.passengers >= 1

    output_schema = FlightsSearchOutput.model_json_schema()
    assert "flights" in output_schema["properties"]
