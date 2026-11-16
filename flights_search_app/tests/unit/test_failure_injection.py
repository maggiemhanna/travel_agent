import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.runners import Runner

from app.agent import app, fallback_app
from app.app_utils.health import evaluate_readiness
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from app.main import api
from app.schema import FlightsSearchOutput

FIXTURES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
    "flights_search.json",
)


def _load_sample_payload() -> dict:
    with open(FIXTURES_PATH) as f:
        sample = json.load(f)[0]
    return {
        "origin": sample["origin"],
        "destination": sample["destination"],
        "departure_date": sample["departure_date"],
        "return_date": sample["return_date"],
        "passengers": sample["passengers"],
        "filters": sample["filters"],
    }


def _mock_text_event(text: str):
    return SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)])
    )


def test_flights_search_truncation_triggers_backup_failover():
    """Simulate MAX_TOKENS / Pydantic ValidationError on primary flights_search triggering fallback_app."""
    payload = _load_sample_payload()
    seen_apps = []

    async def _primary_truncation(runner_self, *args, **kwargs):
        seen_apps.append(runner_self.app)
        if runner_self.app is app:
            FlightsSearchOutput.model_validate_json('{"flights": [{"origin": "Paris"')
        return [_mock_text_event(json.dumps({"flights": [{"flight_number": "AF006"}]}))]

    with TestClient(api) as client:
        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_primary_truncation
        ):
            resp = client.post("/run-flights-search", json=payload)
            assert resp.status_code == 200
            assert seen_apps == [app, fallback_app]
            assert resp.json()["results"] == [{"flights": [{"flight_number": "AF006"}]}]


def test_flights_search_plain_text_non_json_degradation():
    """Inject plain-text non-JSON response from Runner.run_debug to verify safe {'raw_text': ...} fallback."""
    payload = _load_sample_payload()

    async def _plain_text_reply(runner_self, *args, **kwargs):
        return [
            SimpleNamespace(content=None),
            _mock_text_event("Service notice: plain text fallback active."),
        ]

    with TestClient(api) as client:
        with patch.object(Runner, "run_debug", autospec=True, side_effect=_plain_text_reply):
            resp = client.post("/run-flights-search", json=payload)
            assert resp.status_code == 200
            assert resp.json() == {
                "status": "success",
                "results": [{"raw_text": "Service notice: plain text fallback active."}],
            }


def test_flights_search_telemetry_error_and_readiness_fault_injection():
    """Inject model errors into ExecutionTelemetryPlugin and broken states into evaluate_readiness."""

    async def _exercise_error_hooks():
        plugin = ExecutionTelemetryPlugin()
        inv_ctx = SimpleNamespace(invocation_id="inv-fs-fault-11223344")
        cb_ctx = SimpleNamespace(
            invocation_id="inv-fs-fault-11223344", agent_name="flights_search"
        )
        await plugin.before_run_callback(invocation_context=inv_ctx)
        err_result = await plugin.on_model_error_callback(
            callback_context=cb_ctx,
            llm_request=SimpleNamespace(),
            error=RuntimeError("503 Model Overloaded"),
        )
        assert err_result is None
        await plugin.on_run_error_callback(
            invocation_context=inv_ctx,
            error=RuntimeError("503 Model Overloaded"),
        )
        assert "inv-fs-fault-11223344" not in plugin._runs

    asyncio.run(_exercise_error_hooks())

    with patch.dict(
        os.environ,
        {
            "GOOGLE_GENAI_USE_VERTEXAI": "1",
            "GOOGLE_CLOUD_PROJECT": "",
            "GOOGLE_CLOUD_LOCATION": "",
        },
        clear=False,
    ):
        unready = evaluate_readiness(
            service_name="flights-search-app",
            adk_app=SimpleNamespace(root_agent=None),
            models={"flights_search": ""},
        )
        assert unready.status_code == 503
        body = json.loads(unready.body.decode("utf-8"))
        assert body["status"] == "not_ready"
        assert len(body["errors"]) == 4
