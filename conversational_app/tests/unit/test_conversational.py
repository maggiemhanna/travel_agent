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
from app.config import FALLBACK_GEMINI_MODEL
from app.main import api, setup_session_and_runner
from app.schema import ConversationalInput
from app.sub_agents.engage.agent import app as engage_app, fallback_app as engage_fallback_app
from app.sub_agents.engage.main import api as engage_api
from app.sub_agents.filter.agent import fallback_app as filter_fallback_app
from app.sub_agents.filter.main import api as filter_api
from app.sub_agents.filter_smart.agent import fallback_app as filter_smart_fallback_app
from app.sub_agents.filter_smart.main import api as filter_smart_api
from app.sub_agents.inspiration.agent import fallback_app as inspiration_fallback_app
from app.sub_agents.inspiration.main import api as inspiration_api
from app.sub_agents.json_parser.agent import fallback_app as json_parser_fallback_app
from app.sub_agents.json_parser.main import api as json_parser_api

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "conversational.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Conversational Agent Service is running. Use the /run-conversational endpoint via POST."}


def test_healthz_and_readyz_endpoints():
    """Test /healthz and /readyz on main orchestrator and all 5 standalone sub-agent APIs."""
    valid_env = {
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_PROJECT": "travel-agent-test",
        "GOOGLE_CLOUD_LOCATION": "europe-west9",
    }
    invalid_env = {
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_PROJECT": "",
        "GOOGLE_CLOUD_LOCATION": "europe-west9",
    }

    with TestClient(api) as client:
        health_resp = client.get("/healthz")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok", "service": "conversational-app"}

        with patch.dict(os.environ, valid_env, clear=False):
            ready_resp = client.get("/readyz")
            assert ready_resp.status_code == 200
            body = ready_resp.json()
            assert body["status"] == "ready"
            assert body["service"] == "conversational-app"
            assert body["fallback_model"] == FALLBACK_GEMINI_MODEL
            assert set(body["models"].keys()) == {
                "engage",
                "filter",
                "filter_smart",
                "inspiration",
                "json_parser",
            }

        with patch.dict(os.environ, invalid_env, clear=False):
            unready_resp = client.get("/readyz")
            assert unready_resp.status_code == 503
            assert unready_resp.json()["status"] == "not_ready"

    for expected_name, sub_api in [
        ("engage", engage_api),
        ("filter", filter_api),
        ("filter_smart", filter_smart_api),
        ("inspiration", inspiration_api),
        ("json_parser", json_parser_api),
    ]:
        with TestClient(sub_api) as sub_client:
            assert sub_client.get("/healthz").json() == {
                "status": "ok",
                "service": expected_name,
            }
            with patch.dict(os.environ, valid_env, clear=False):
                sub_ready = sub_client.get("/readyz")
                assert sub_ready.status_code == 200
                assert sub_ready.json()["fallback_model"] == FALLBACK_GEMINI_MODEL
            with patch.dict(os.environ, invalid_env, clear=False):
                assert sub_client.get("/readyz").status_code == 503


def test_conversational_schema():
    """Test input schema validation against fixtures and reject invalid payloads."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    with TestClient(api) as client:
        for test in tests:
            payload = {
                "user_message": test["user_message"],
                "conversational_history": test["conversational_history"],
                "flights_search_input": test["flights_search_input"],
                "flights_input": test["flights_input"],
            }
            logger.info(f"Validating Payload:\n{format_dict_for_logs(payload)}")

            validated = ConversationalInput(**payload)
            assert validated.user_message == test["user_message"]
            assert len(validated.flights_input) == len(test["flights_input"])

        # Verify invalid empty payload is rejected with 422 Unprocessable Entity
        invalid_response = client.post("/run-conversational", json={})
        assert invalid_response.status_code == 422, f"Expected 422, got {invalid_response.status_code}"


def test_telemetry_plugin_registration_and_lifecycle():
    """Verify ExecutionTelemetryPlugin is registered on App/Runner and captures sub-agent tokens & search queries."""
    assert build_plugins(enabled=False) == []
    enabled_plugins = build_plugins(enabled=True)
    assert len(enabled_plugins) == 1 and isinstance(enabled_plugins[0], ExecutionTelemetryPlugin)
    assert any(isinstance(p, ExecutionTelemetryPlugin) for p in app.plugins)

    async def _exercise_plugin():
        _, runner = await setup_session_and_runner(
            session_id="test-conv-session-1",
            user_id="test-conv-user-1",
            initial_state={},
        )
        assert runner.plugin_manager.get_plugin("execution_telemetry") is not None

        plugin = ExecutionTelemetryPlugin()
        inv_ok = SimpleNamespace(invocation_id="inv-conv-12345678")
        inv_err = SimpleNamespace(invocation_id="inv-conv-87654321")

        await plugin.before_run_callback(invocation_context=inv_ok)
        await plugin.before_run_callback(invocation_context=inv_err)

        # Simulate engage -> filter_smart (with server-side Google Search grounding)
        engage_ctx = SimpleNamespace(invocation_id="inv-conv-12345678", agent_name="engage")
        await plugin.before_agent_callback(agent=SimpleNamespace(name="engage"), callback_context=engage_ctx)
        engage_resp = LlmResponse(
            partial=False,
            usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                prompt_token_count=180,
                candidates_token_count=45,
            ),
        )
        assert await plugin.after_model_callback(callback_context=engage_ctx, llm_response=engage_resp) is None

        smart_ctx = SimpleNamespace(invocation_id="inv-conv-12345678", agent_name="filter_smart")
        await plugin.before_agent_callback(agent=SimpleNamespace(name="filter_smart"), callback_context=smart_ctx)
        smart_resp = LlmResponse(
            partial=False,
            usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                prompt_token_count=620,
                candidates_token_count=210,
            ),
            grounding_metadata=genai_types.GroundingMetadata(
                web_search_queries=["Air France AF006 WiFi reliability"],
            ),
        )
        assert await plugin.after_model_callback(callback_context=smart_ctx, llm_response=smart_resp) is None

        run_state = plugin._runs["inv-conv-12345678"]
        assert run_state["in_tokens"] == 800
        assert run_state["out_tokens"] == 255
        assert len(run_state["rows"]) == 2
        assert run_state["rows"][0][4] == "-"
        assert run_state["rows"][1][4] == "Air France AF006 WiFi reliability"

        await plugin.after_run_callback(invocation_context=inv_ok)
        assert "inv-conv-12345678" not in plugin._runs
        assert "inv-conv-87654321" in plugin._runs

        await plugin.on_run_error_callback(invocation_context=inv_err, error=RuntimeError("simulated failure"))
        assert "inv-conv-87654321" not in plugin._runs

    asyncio.run(_exercise_plugin())


def test_automatic_backup_model_failover():
    """Verify isolated fallback_app (gemini-3.6-flash) across workflow & standalone sub-agents."""
    assert fallback_app is not None
    assert fallback_app is not app
    assert fallback_app.root_agent is not app.root_agent

    # Verify all 5 standalone sub-agent fallback_apps are bound to gemini-3.6-flash
    for sub_fb in [
        engage_fallback_app,
        filter_fallback_app,
        filter_smart_fallback_app,
        inspiration_fallback_app,
        json_parser_fallback_app,
    ]:
        assert sub_fb is not None
        assert sub_fb.root_agent.model.model == "gemini-3.6-flash"

    with open(FIXTURES_PATH) as f:
        sample = json.load(f)[0]
    payload = {
        "user_message": sample["user_message"],
        "conversational_history": sample["conversational_history"],
        "flights_search_input": sample["flights_search_input"],
        "flights_input": sample["flights_input"],
    }

    def _mock_event(body: dict):
        return SimpleNamespace(
            content=SimpleNamespace(parts=[SimpleNamespace(text=json.dumps(body))])
        )

    with TestClient(api) as client:
        # 1. Primary workflow succeeds -> fallback_app is not called
        seen_apps = []

        async def _primary_ok(runner_self, *args, **kwargs):
            seen_apps.append(runner_self.app)
            return [
                _mock_event(
                    {
                        "agent_response": "Primary response",
                        "agent_decision": "continue",
                    }
                )
            ]

        with patch.object(Runner, "run_debug", autospec=True, side_effect=_primary_ok):
            resp = client.post("/run-conversational", json=payload)
            assert resp.status_code == 200
            assert resp.json()["results"]["agent_response"] == "Primary response"
            assert seen_apps == [app]

        # 2. Primary workflow fails -> automatic failover to isolated fallback_app (gemini-3.6-flash)
        seen_apps.clear()
        seen_sessions = []

        async def _primary_fails_backup_succeeds(runner_self, *args, **kwargs):
            seen_apps.append(runner_self.app)
            seen_sessions.append(kwargs.get("session_id"))
            if runner_self.app is app:
                raise RuntimeError("503 Service Unavailable on primary workflow")
            return [
                _mock_event(
                    {
                        "agent_response": "Backup gemini-3.6-flash response",
                        "agent_decision": "continue",
                    }
                )
            ]

        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_primary_fails_backup_succeeds
        ):
            resp = client.post("/run-conversational", json=payload)
            assert resp.status_code == 200
            assert (
                resp.json()["results"]["agent_response"]
                == "Backup gemini-3.6-flash response"
            )
            assert seen_apps == [app, fallback_app]
            assert len(set(seen_sessions)) == 2

        # 3. Both primary and backup fail -> HTTP 500
        with patch.object(
            Runner,
            "run_debug",
            new=AsyncMock(side_effect=RuntimeError("Both models unavailable")),
        ):
            resp = client.post("/run-conversational", json=payload)
            assert resp.status_code == 500

    # 4. Standalone sub-agent failover check (engage_api)
    with TestClient(engage_api) as sub_client:
        seen_sub_apps = []

        async def _sub_failover(runner_self, *args, **kwargs):
            seen_sub_apps.append(runner_self.app)
            if runner_self.app is engage_app:
                raise RuntimeError("429 on primary engage")
            return [
                _mock_event(
                    {"agent_response": "Engage backup ok", "agent_decision": "continue"}
                )
            ]

        with patch.object(Runner, "run_debug", autospec=True, side_effect=_sub_failover):
            sub_resp = sub_client.post("/run-engage", json=payload)
            assert sub_resp.status_code == 200
            assert sub_resp.json()["results"] == [
                {"agent_response": "Engage backup ok", "agent_decision": "continue"}
            ]
            assert seen_sub_apps == [engage_app, engage_fallback_app]


def test_inspiration_workflow_routing_and_contract():
    """Verify end-to-end ADK Workflow routing for agent_decision='inspiration' and contract metric alignment."""
    from google.adk.models.google_llm import Gemini
    from tests.eval.metrics.custom_metrics import evaluate_schema_and_contract
    from tests.eval.scripts.run_evaluation import build_agent_info

    call_index = 0

    async def _fake_generate_content_async(self, llm_request, stream=False):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            body = {
                "agent_response": "Let me suggest a warm destination!",
                "agent_decision": "inspiration",
            }
        else:
            body = {
                "agent_response": "How about Lisbon in May for sunny coastal weather?",
                "flights_search_output": {
                    "origin": "Paris",
                    "destination": "Lisbon",
                    "departure_date": "2026-05-10",
                    "return_date": "2026-05-20",
                    "passengers": 1,
                },
            }
        yield LlmResponse(
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(text=json.dumps(body))],
            ),
            partial=False,
        )

    payload = {
        "user_message": "Take me somewhere warm and sunny in Europe instead",
        "conversational_history": [],
        "flights_search_input": {
            "origin": "Paris",
            "destination": "New York",
            "departure_date": "2026-05-10",
            "return_date": "2026-05-20",
            "passengers": 1,
        },
        "flights_input": [],
    }

    with patch.object(Gemini, "generate_content_async", new=_fake_generate_content_async):
        with TestClient(api) as client:
            resp = client.post("/api/v1/run-conversational", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    results = data["results"]
    assert call_index == 2
    assert results["agent_decision"] == "inspiration"
    assert results["agent_response"] == "How about Lisbon in May for sunny coastal weather?"
    assert results["flights_search_output"] == {
        "origin": "Paris",
        "destination": "Lisbon",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-20",
        "passengers": 1,
    }

    # Verify custom_metrics accepts 'inspiration' and rejects legacy 'inspiration_agent'
    valid_eval = evaluate_schema_and_contract(
        {
            "response": {"parts": [{"text": json.dumps(results)}]},
            "session_inputs": {"state": {"flights_input": []}},
        }
    )
    assert valid_eval["score"] == 1.0

    legacy_eval = evaluate_schema_and_contract(
        {
            "response": {
                "parts": [
                    {
                        "text": json.dumps(
                            {**results, "agent_decision": "inspiration_agent"}
                        )
                    }
                ]
            },
            "session_inputs": {"state": {"flights_input": []}},
        }
    )
    assert legacy_eval["score"] == 0.0

    agent_info = build_agent_info()
    assert "inspiration" in agent_info.agents
    assert "inspiration" in agent_info.agents["engage"].sub_agents


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

        logger.info("Running test_conversational_schema...")
        test_conversational_schema()
        logger.info("✅ test_conversational_schema passed!")

        logger.info("Running test_telemetry_plugin_registration_and_lifecycle...")
        test_telemetry_plugin_registration_and_lifecycle()
        logger.info("✅ test_telemetry_plugin_registration_and_lifecycle passed!")

        logger.info("Running test_automatic_backup_model_failover...")
        test_automatic_backup_model_failover()
        logger.info("✅ test_automatic_backup_model_failover passed!")

        logger.info("Running test_inspiration_workflow_routing_and_contract...")
        test_inspiration_workflow_routing_and_contract()
        logger.info("✅ test_inspiration_workflow_routing_and_contract passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
