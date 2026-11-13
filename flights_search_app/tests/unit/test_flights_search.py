import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.genai import types as genai_types

from app.agent import app, fallback_app
from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin, build_plugins
from app.config import FLIGHTS_SEARCH_FALLBACK_MODEL
from app.main import api, setup_session_and_runner
from app.schema import FlightsSearchInput

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "flights_search.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Flights Search Agent Service is running. Use the /run-flights-search endpoint via POST."}


def test_healthz_and_readyz_endpoints():
    """Test /healthz liveness and /readyz readiness (200 valid vs 503 misconfigured)."""
    with TestClient(api) as client:
        health_resp = client.get("/healthz")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok", "service": "flights-search-app"}

        with patch.dict(
            os.environ,
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "1",
                "GOOGLE_CLOUD_PROJECT": "travel-agent-test",
                "GOOGLE_CLOUD_LOCATION": "europe-west9",
            },
            clear=False,
        ):
            ready_resp = client.get("/readyz")
            assert ready_resp.status_code == 200
            body = ready_resp.json()
            assert body["status"] == "ready"
            assert body["service"] == "flights-search-app"
            assert "flights_search" in body["models"]
            assert body["fallback_model"] == FLIGHTS_SEARCH_FALLBACK_MODEL

        with patch.dict(
            os.environ,
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "1",
                "GOOGLE_CLOUD_PROJECT": "",
                "GOOGLE_CLOUD_LOCATION": "europe-west9",
            },
            clear=False,
        ):
            unready_resp = client.get("/readyz")
            assert unready_resp.status_code == 503
            unready_body = unready_resp.json()
            assert unready_body["status"] == "not_ready"
            assert any("GOOGLE_CLOUD_PROJECT" in err for err in unready_body["errors"])


def test_flights_search_schema():
    """Test input schema validation against fixtures and reject invalid payloads."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    with TestClient(api) as client:
        for test in tests:
            payload = {
                "origin": test["origin"],
                "destination": test["destination"],
                "departure_date": test["departure_date"],
                "return_date": test["return_date"],
                "passengers": test["passengers"],
                "filters": test["filters"],
            }
            logger.info(f"Validating Payload:\n{format_dict_for_logs(payload)}")

            validated = FlightsSearchInput(**payload)
            assert validated.origin == test["origin"]
            assert validated.destination == test["destination"]
            assert validated.passengers == test["passengers"]

        # Verify invalid empty payload is rejected with 422 Unprocessable Entity
        invalid_response = client.post("/run-flights-search", json={})
        assert invalid_response.status_code == 422, f"Expected 422, got {invalid_response.status_code}"


def test_telemetry_plugin_registration_and_lifecycle():
    """Verify ExecutionTelemetryPlugin is registered on App/Runner and tracks invocation metrics cleanly."""
    assert build_plugins(enabled=False) == []
    enabled_plugins = build_plugins(enabled=True)
    assert len(enabled_plugins) == 1 and isinstance(enabled_plugins[0], ExecutionTelemetryPlugin)
    assert any(isinstance(p, ExecutionTelemetryPlugin) for p in app.plugins)

    async def _exercise_plugin():
        _, runner = await setup_session_and_runner(
            session_id="test-session-1",
            user_id="test-user-1",
            initial_state={},
        )
        assert runner.plugin_manager.get_plugin("execution_telemetry") is not None

        plugin = ExecutionTelemetryPlugin()
        inv_ok = SimpleNamespace(invocation_id="inv-ok-12345678")
        inv_err = SimpleNamespace(invocation_id="inv-err-87654321")
        cb_ctx = SimpleNamespace(
            invocation_id="inv-ok-12345678",
            agent_name="flights_search",
        )
        agent_stub = SimpleNamespace(name="flights_search")

        await plugin.before_run_callback(invocation_context=inv_ok)
        await plugin.before_run_callback(invocation_context=inv_err)
        await plugin.before_agent_callback(agent=agent_stub, callback_context=cb_ctx)

        # Streaming partial chunks should be ignored
        partial_resp = LlmResponse(partial=True)
        assert await plugin.after_model_callback(callback_context=cb_ctx, llm_response=partial_resp) is None
        assert len(plugin._runs["inv-ok-12345678"]["rows"]) == 0

        # Final model response records tokens and returns None (non-intrusive)
        final_resp = LlmResponse(
            partial=False,
            usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                prompt_token_count=320,
                candidates_token_count=940,
            ),
        )
        assert await plugin.after_model_callback(callback_context=cb_ctx, llm_response=final_resp) is None
        assert plugin._runs["inv-ok-12345678"]["in_tokens"] == 320
        assert plugin._runs["inv-ok-12345678"]["out_tokens"] == 940
        assert len(plugin._runs["inv-ok-12345678"]["rows"]) == 1

        # Cleanup on both normal completion and error without cross-invocation interference
        await plugin.after_run_callback(invocation_context=inv_ok)
        assert "inv-ok-12345678" not in plugin._runs
        assert "inv-err-87654321" in plugin._runs

        await plugin.on_run_error_callback(invocation_context=inv_err, error=RuntimeError("boom"))
        assert "inv-err-87654321" not in plugin._runs

    asyncio.run(_exercise_plugin())


def test_automatic_backup_model_failover():
    """Verify primary success skips fallback, primary failure fails over to gemini-3.6-flash, and dual failure returns 500."""
    assert fallback_app is not None
    assert fallback_app is not app
    assert fallback_app.root_agent is not app.root_agent
    assert fallback_app.root_agent.model.model == "gemini-3.6-flash"

    with open(FIXTURES_PATH) as f:
        sample = json.load(f)[0]
    payload = {
        "origin": sample["origin"],
        "destination": sample["destination"],
        "departure_date": sample["departure_date"],
        "return_date": sample["return_date"],
        "passengers": sample["passengers"],
        "filters": sample["filters"],
    }

    def _mock_event(flights_payload: dict):
        return SimpleNamespace(
            content=SimpleNamespace(
                parts=[SimpleNamespace(text=json.dumps(flights_payload))]
            )
        )

    with TestClient(api) as client:
        # 1. Primary succeeds -> backup model is never called
        seen_apps = []

        async def _primary_ok(runner_self, *args, **kwargs):
            seen_apps.append(runner_self.app)
            return [_mock_event({"flights": [{"flight_number": "AF001"}]})]

        with patch.object(Runner, "run_debug", autospec=True, side_effect=_primary_ok):
            resp = client.post("/run-flights-search", json=payload)
            assert resp.status_code == 200
            assert resp.json()["results"] == [{"flights": [{"flight_number": "AF001"}]}]
            assert seen_apps == [app]

        # 2. Primary raises 429/503 -> automatically fails over to isolated fallback_app (gemini-3.6-flash)
        seen_apps.clear()
        seen_sessions = []

        async def _primary_fails_backup_succeeds(runner_self, *args, **kwargs):
            seen_apps.append(runner_self.app)
            seen_sessions.append(kwargs.get("session_id"))
            if runner_self.app is app:
                raise RuntimeError("429 Resource Exhausted on primary model")
            return [_mock_event({"flights": [{"flight_number": "AF999-BACKUP"}]})]

        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_primary_fails_backup_succeeds
        ):
            resp = client.post("/run-flights-search", json=payload)
            assert resp.status_code == 200
            assert resp.json()["results"] == [{"flights": [{"flight_number": "AF999-BACKUP"}]}]
            assert seen_apps == [app, fallback_app]
            assert len(set(seen_sessions)) == 2  # Fresh isolated session per attempt

        # 3. Both primary and backup fail -> HTTP 500
        with patch.object(
            Runner,
            "run_debug",
            new=AsyncMock(side_effect=RuntimeError("Total Vertex AI outage")),
        ):
            resp = client.post("/run-flights-search", json=payload)
            assert resp.status_code == 500


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info("Running unit tests manually without pytest...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_healthz_and_readyz_endpoints...")
        test_healthz_and_readyz_endpoints()
        logger.info("✅ test_healthz_and_readyz_endpoints passed!")

        logger.info("Running test_flights_search_schema...")
        test_flights_search_schema()
        logger.info("✅ test_flights_search_schema passed!")

        logger.info("Running test_telemetry_plugin_registration_and_lifecycle...")
        test_telemetry_plugin_registration_and_lifecycle()
        logger.info("✅ test_telemetry_plugin_registration_and_lifecycle passed!")

        logger.info("Running test_automatic_backup_model_failover...")
        test_automatic_backup_model_failover()
        logger.info("✅ test_automatic_backup_model_failover passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
