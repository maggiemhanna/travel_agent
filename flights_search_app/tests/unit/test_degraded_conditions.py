"""Degraded-conditions and brownout resilience unit tests for flights_search_app.

Validates:
1. Non-blocking async concurrency (`asyncio.gather` over 12 simultaneous requests) mixing slow primary brownouts (failing over to `fallback_app`) with fast healthy requests, proving zero `InMemorySessionService` or `ExecutionTelemetryPlugin` cross-contamination.
2. Graceful handling of empty flight inventory (`{"flights": []}`) under strict/impossible search filters.
3. Exponential-backoff retry-policy contract invariants across both primary and fallback Gemini agents.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.runners import Runner
import httpx

from app.agent import app as primary_app, fallback_app
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from app.main import APP_NAME, api


def _make_search_payload(idx: int) -> Dict[str, Any]:
    return {
        "origin": f"CityOrigin{idx}",
        "destination": f"CityDest{idx}",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-20",
        "passengers": 1,
        "filters": {
            "direct": idx % 2 == 0,
            "max_price": 600 + idx * 10,
            "max_stops": 1,
        },
    }


def _mock_text_event(text: str) -> Any:
    return SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text=text)]))


def test_concurrent_async_brownout_failover_and_session_isolation() -> None:
    """12 concurrent Flight Search requests under partial brownout must complete non-blockingly without state leaks."""
    shared_telemetry = ExecutionTelemetryPlugin()

    async def _run_scenario() -> None:
        async def _brownout_run_debug(runner_self, *args, **kwargs):
            session = await runner_self.session_service.get_session(
                app_name=APP_NAME,
                user_id=kwargs["user_id"],
                session_id=kwargs["session_id"],
            )
            state = session.state
            origin = state["origin"]
            dest = state["destination"]
            req_idx = int(origin.replace("CityOrigin", ""))
            is_brownout = req_idx < 6

            inv_id = f"inv-{kwargs['session_id']}"
            inv_ctx = SimpleNamespace(invocation_id=inv_id)
            cb_ctx = SimpleNamespace(invocation_id=inv_id, agent_name="flights_search")
            await shared_telemetry.before_run_callback(invocation_context=inv_ctx)
            await shared_telemetry.before_agent_callback(
                agent=SimpleNamespace(name="flights_search"), callback_context=cb_ctx
            )

            if is_brownout and runner_self.app is primary_app:
                await asyncio.sleep(0.08)
                err = RuntimeError("503 Service Unavailable: Vertex AI brownout")
                await shared_telemetry.on_run_error_callback(
                    invocation_context=inv_ctx, error=err
                )
                raise err

            await asyncio.sleep(0.02 if is_brownout else 0.01)
            await shared_telemetry.after_model_callback(
                callback_context=cb_ctx,
                llm_response=SimpleNamespace(
                    partial=False,
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=35, candidates_token_count=50
                    ),
                    grounding_metadata=None,
                ),
            )
            await shared_telemetry.after_run_callback(invocation_context=inv_ctx)

            flight_result = {
                "flights": [
                    {
                        "origin": origin,
                        "destination": dest,
                        "departure_date": state["departure_date"],
                        "return_date": state["return_date"],
                        "departure_time": "09:00",
                        "arrival_time": "11:30",
                        "return_time": "18:00",
                        "return_arrival_time": "20:30",
                        "price": f"{500 + req_idx} EUR",
                        "airline": "Air France",
                        "flight_number": f"AF{200 + req_idx}",
                        "stops": 0,
                        "stopover_cities": [],
                    }
                ]
            }
            return [_mock_text_event(json.dumps(flight_result))]

        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            with patch.object(Runner, "run_debug", new=_brownout_run_debug):
                t0 = time.perf_counter()
                responses = await asyncio.gather(
                    *[
                        client.post("/run-flights-search", json=_make_search_payload(i))
                        for i in range(12)
                    ]
                )
                elapsed = time.perf_counter() - t0

        assert elapsed < 0.50, (
            f"Expected non-blocking concurrent brownout execution (<0.50s), took {elapsed:.3f}s"
        )

        for idx, resp in enumerate(responses):
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "success"
            flights = body["results"][0]["flights"]
            assert len(flights) == 1
            assert flights[0]["origin"] == f"CityOrigin{idx}"
            assert flights[0]["destination"] == f"CityDest{idx}"
            assert flights[0]["flight_number"] == f"AF{200 + idx}"

        assert shared_telemetry._runs == {}

    asyncio.run(_run_scenario())


def test_degraded_zero_results_inventory_contract() -> None:
    """Empty flight lists returned under strict filter conditions must serialize cleanly as HTTP 200."""
    async def _empty_flights_reply(runner_self, *args, **kwargs):
        return [_mock_text_event(json.dumps({"flights": []}))]

    with TestClient(api) as client:
        with patch.object(Runner, "run_debug", new=_empty_flights_reply):
            resp = client.post("/run-flights-search", json=_make_search_payload(0))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["results"] == [{"flights": []}]


def test_primary_and_fallback_flights_search_retry_policy_contract() -> None:
    """Both primary and backup Flights Search agents must preserve 5-attempt exponential backoff."""
    assert fallback_app is not None
    expected_codes = [408, 429, 500, 502, 503, 504]

    for target_agent in (primary_app.root_agent, fallback_app.root_agent):
        retry = target_agent.model.retry_options
        assert retry is not None
        assert retry.attempts == 5
        assert retry.initial_delay == 5.0
        assert retry.max_delay == 60.0
        assert retry.exp_base == 2.0
        assert list(retry.http_status_codes) == expected_codes
