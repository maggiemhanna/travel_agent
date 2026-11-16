"""Degraded-conditions and brownout resilience unit tests for conversational_app.

Validates:
1. Non-blocking async concurrency (`asyncio.gather` over 12 simultaneous requests) mixing slow primary brownout failovers with fast healthy requests, proving zero `InMemorySessionService` or `ExecutionTelemetryPlugin` cross-contamination.
2. Graceful operation under degraded upstream context (`flights_input=[]` when Flight Search is unavailable/empty).
3. Resilience of `extract_grounding_search_events` when Google Search returns missing, empty, or partial `grounding_metadata`.
4. Zero-hop extraction of noisy unfenced preamble/postamble JSON in `load_json_with_markdown` and `_parse_filter_smart_fn`.
5. Exponential-backoff retry-policy contract invariants across all 5 primary and 5 fallback Gemini sub-agents.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
import json
import time
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.runners import Runner
import httpx

from app.agent import (
    _finalize_output_fn,
    _parse_filter_smart_fn,
    app as primary_workflow_app,
    fallback_app as fallback_workflow_app,
    load_json_with_markdown,
)
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from app.main import APP_NAME, api
from app.sub_agents.engage import agent as engage_mod
from app.sub_agents.filter import agent as filter_mod
from app.sub_agents.filter_smart import agent as filter_smart_mod
from app.sub_agents.inspiration import agent as inspiration_mod
from app.sub_agents.json_parser import agent as json_parser_mod
from tests.eval.metrics.custom_metrics import evaluate_schema_and_contract
from tests.eval.scripts.run_evaluation import extract_grounding_search_events


SAMPLE_FLIGHT: Dict[str, Any] = {
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


def _make_payload(idx: int, *, empty_flights: bool = False) -> Dict[str, Any]:
    flight = copy.deepcopy(SAMPLE_FLIGHT)
    flight["flight_number"] = f"AF{100 + idx}"
    return {
        "user_message": f"Request #{idx}: filter Air France flights",
        "conversational_history": [f"user: turn-{idx}"],
        "flights_search_input": {
            "origin": "Paris",
            "destination": "New York",
            "departure_date": "2026-05-10",
            "return_date": "2026-05-20",
            "passengers": 1,
        },
        "flights_input": [] if empty_flights else [flight],
    }


def _mock_text_event(text: str) -> Any:
    return SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text=text)]))


# ---------------------------------------------------------------------------
# 1. Concurrent Async Brownout & Per-Request State/Telemetry Isolation
# ---------------------------------------------------------------------------


def test_concurrent_async_brownout_non_blocking_and_session_isolation() -> None:
    """12 concurrent requests (6 slow brownouts failing over + 6 fast healthy) must not block or leak state."""
    shared_telemetry = ExecutionTelemetryPlugin()

    async def _run_scenario() -> None:
        async def _brownout_run_debug(runner_self, *args, **kwargs):
            session = await runner_self.session_service.get_session(
                app_name=APP_NAME,
                user_id=kwargs["user_id"],
                session_id=kwargs["session_id"],
            )
            state = session.state
            user_msg = state["user_message"]
            flight = state["flights_input"][0]
            is_brownout_req = any(f"#{i}:" in user_msg for i in range(6))

            inv_id = f"inv-{kwargs['session_id']}"
            inv_ctx = SimpleNamespace(invocation_id=inv_id)
            cb_ctx = SimpleNamespace(invocation_id=inv_id, agent_name="engage")
            await shared_telemetry.before_run_callback(invocation_context=inv_ctx)
            await shared_telemetry.before_agent_callback(
                agent=SimpleNamespace(name="engage"), callback_context=cb_ctx
            )

            if is_brownout_req and runner_self.app is primary_workflow_app:
                await asyncio.sleep(0.08)
                err = RuntimeError("429 Resource Exhausted: Vertex AI brownout")
                await shared_telemetry.on_run_error_callback(
                    invocation_context=inv_ctx, error=err
                )
                raise err

            await asyncio.sleep(0.02 if is_brownout_req else 0.01)
            await shared_telemetry.after_model_callback(
                callback_context=cb_ctx,
                llm_response=SimpleNamespace(
                    partial=False,
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=40, candidates_token_count=20
                    ),
                    grounding_metadata=None,
                ),
            )
            await shared_telemetry.after_run_callback(invocation_context=inv_ctx)

            reply = {
                "agent_response": f"Processed {user_msg}",
                "agent_decision": "filter_smart",
                "flights_output": [flight],
            }
            return [_mock_text_event(json.dumps(reply))]

        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            with patch.object(Runner, "run_debug", new=_brownout_run_debug):
                t0 = time.perf_counter()
                responses = await asyncio.gather(
                    *[
                        client.post("/run-conversational", json=_make_payload(i))
                        for i in range(12)
                    ]
                )
                elapsed = time.perf_counter() - t0

        # Sequential brownout execution alone would exceed 6 * 0.10s = 0.60s.
        assert elapsed < 0.50, (
            f"Expected non-blocking concurrent execution (<0.50s), took {elapsed:.3f}s"
        )

        for idx, resp in enumerate(responses):
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            results = data["results"]
            assert results["agent_response"] == f"Processed Request #{idx}: filter Air France flights"
            assert len(results["flights_output"]) == 1
            assert results["flights_output"][0]["flight_number"] == f"AF{100 + idx}"

        # Shared telemetry plugin must clean up all invocation entries cleanly.
        assert shared_telemetry._runs == {}

    asyncio.run(_run_scenario())


# ---------------------------------------------------------------------------
# 2. Degraded Upstream Context (`flights_input=[]` & Partial Grounding)
# ---------------------------------------------------------------------------


def test_degraded_empty_flights_context_handled_gracefully() -> None:
    """When Flight Search returns 0 flights (or hasn't run yet), conversational_app must degrade gracefully."""
    empty_payload = _make_payload(0, empty_flights=True)
    ctx = SimpleNamespace(state={"agent_decision": "filter_smart"})
    raw_llm = json.dumps(
        {
            "agent_response": "There are currently no flights loaded to filter. Try searching a route first.",
            "flights_output": [],
        }
    )

    ev_parsed = _parse_filter_smart_fn(ctx, raw_llm)
    assert ev_parsed.actions.route == "parsed"
    ev_final = _finalize_output_fn(ctx, ev_parsed.output)
    assert ev_final.output["flights_output"] == []

    async def _empty_inventory_reply(runner_self, *args, **kwargs):
        return [_mock_text_event(json.dumps(ev_final.output))]

    with TestClient(api) as client:
        with patch.object(Runner, "run_debug", new=_empty_inventory_reply):
            resp = client.post("/run-conversational", json=empty_payload)

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results["flights_output"] == []

    metric = evaluate_schema_and_contract(
        {
            "response": {"parts": [{"text": json.dumps(results)}]},
            "session_inputs": {"state": {"flights_input": []}},
        }
    )
    assert metric["score"] == 1.0


def test_degraded_missing_or_partial_grounding_metadata_resilience() -> None:
    """extract_grounding_search_events must handle missing, empty, or partial grounding_metadata safely."""
    now = datetime.now(timezone.utc)

    # 1. Missing grounding_metadata attribute altogether
    assert extract_grounding_search_events(SimpleNamespace(), "filter_smart", now) == (
        [],
        [],
        [],
    )

    # 2. Empty grounding_metadata arrays/nulls
    empty_gm = SimpleNamespace(
        grounding_metadata=SimpleNamespace(
            web_search_queries=None,
            grounding_chunks=[],
            grounding_supports=None,
        )
    )
    assert extract_grounding_search_events(empty_gm, "filter_smart", now) == (
        [],
        [],
        [],
    )

    # 3. Partial grounding_metadata: chunks with web=None + grounded_claims without explicit query string
    partial_gm = SimpleNamespace(
        grounding_metadata=SimpleNamespace(
            web_search_queries=["   "],
            grounding_chunks=[SimpleNamespace(web=None)],
            grounding_supports=[
                SimpleNamespace(segment=SimpleNamespace(text="Air France offers high-speed Wi-Fi."))
            ],
        )
    )
    agent_events, inter_events, tool_call_records = extract_grounding_search_events(
        partial_gm, "filter_smart", now
    )
    assert len(agent_events) == 2
    assert len(inter_events) == 2
    assert len(tool_call_records) == 1
    assert tool_call_records[0]["tool_name"] == "google_search"
    assert tool_call_records[0]["args"] == {"query": "airline flight amenities research"}
    assert tool_call_records[0]["response"]["grounded_claims"] == [
        "Air France offers high-speed Wi-Fi."
    ]


def test_noisy_unfenced_preamble_and_postamble_json_extraction() -> None:
    """Unfenced conversational preamble/postamble around valid JSON must parse in 0ms without json_parser hop."""
    noisy_output = (
        "Based on partial Google Search grounding, here is the filtered JSON result:\n"
        + json.dumps(
            {
                "agent_response": "Kept AF006 based on Wi-Fi research.",
                "flights_output": [SAMPLE_FLIGHT],
            }
        )
        + "\nLet me know if you would like another airline!"
    )

    parsed = load_json_with_markdown(noisy_output)
    assert parsed["flights_output"][0]["flight_number"] == "AF006"

    ctx = SimpleNamespace(state={"agent_decision": "filter_smart"})
    ev = _parse_filter_smart_fn(ctx, noisy_output)
    assert ev.actions.route == "parsed"


# ---------------------------------------------------------------------------
# 3. Retry-Policy Contract Invariants Across All Primary & Fallback Agents
# ---------------------------------------------------------------------------


def test_all_primary_and_fallback_sub_agents_preserve_retry_policy_contract() -> None:
    """Every primary and backup Gemini sub-agent must preserve 5-attempt exponential backoff on transient codes."""
    modules = [
        engage_mod,
        filter_mod,
        filter_smart_mod,
        inspiration_mod,
        json_parser_mod,
    ]
    expected_codes = [408, 429, 500, 502, 503, 504]

    assert fallback_workflow_app is not None

    for mod in modules:
        assert mod.fallback_app is not None, f"{mod.__name__} missing fallback_app"
        for target_agent in (mod.app.root_agent, mod.fallback_app.root_agent):
            retry = target_agent.model.retry_options
            assert retry is not None, f"{target_agent.name} missing retry_options"
            assert retry.attempts == 5
            assert retry.initial_delay == 5.0
            assert retry.max_delay == 60.0
            assert retry.exp_base == 2.0
            assert list(retry.http_status_codes) == expected_codes
