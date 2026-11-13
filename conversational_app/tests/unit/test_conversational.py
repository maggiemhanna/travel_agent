import asyncio
import json
import os
import sys
from types import SimpleNamespace
from fastapi.testclient import TestClient
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

from app.agent import app
from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin, build_plugins
from app.main import api, setup_session_and_runner
from app.schema import ConversationalInput

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "conversational.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Conversational Agent Service is running. Use the /run-conversational endpoint via POST."}


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


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info("Running unit tests manually without pytest...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_conversational_schema...")
        test_conversational_schema()
        logger.info("✅ test_conversational_schema passed!")

        logger.info("Running test_telemetry_plugin_registration_and_lifecycle...")
        test_telemetry_plugin_registration_and_lifecycle()
        logger.info("✅ test_telemetry_plugin_registration_and_lifecycle passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
