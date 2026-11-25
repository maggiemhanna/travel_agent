import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.runners import Runner
from pydantic import ValidationError

from app.agent import (
    _finalize_output_fn,
    _parse_filter_smart_fn,
    app,
    fallback_app,
    load_json_with_markdown,
)
from app.app_utils.health import evaluate_readiness
from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from app.main import api
from app.sub_agents.engage.agent import EngageOutput
from app.sub_agents.engage.main import api as engage_api
from app.sub_agents.filter_smart.main import api as filter_smart_api
from app.sub_agents.json_parser.schema import JSONParserOutput

FIXTURES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
    "conversational.json",
)


def _load_sample_payload() -> dict:
    with open(FIXTURES_PATH) as f:
        sample = json.load(f)[0]
    return {
        "user_message": sample["user_message"],
        "conversational_history": sample["conversational_history"],
        "flights_search_input": sample["flights_search_input"],
        "flights_input": sample["flights_input"],
    }


def _mock_text_event(text: str):
    return SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)])
    )


def test_parse_filter_smart_fault_injection_and_self_healing_routing():
    """Inject syntax-broken, markdown-wrapped, and schema-broken JSON into _parse_filter_smart_fn."""
    sample = _load_sample_payload()
    valid_flight = sample["flights_input"][0]
    ctx = SimpleNamespace(state={"agent_decision": "filter_smart"})

    # 1. Valid raw JSON -> routes directly to 'parsed'
    valid_json = json.dumps(
        {
            "agent_response": "Filtered to Air France.",
            "flights_output": [valid_flight],
        }
    )
    ev_valid = _parse_filter_smart_fn(ctx, valid_json)
    assert ev_valid.actions.route == "parsed"
    assert ev_valid.output["flights_output"][0]["flight_number"] == valid_flight["flight_number"]

    # 2. Markdown-fenced JSON -> cleanly extracted and routed to 'parsed'
    fenced_json = f"Here are the matching flights:\n```json\n{valid_json}\n```"
    ev_fenced = _parse_filter_smart_fn(ctx, fenced_json)
    assert ev_fenced.actions.route == "parsed"
    assert len(ev_fenced.output["flights_output"]) == 1

    # 3. Truncated / syntax-corrupted JSON -> routes to 'repair_json' (json_parser)
    truncated_json = '{"agent_response": "Filtered flights", "flights_output": [{"origin": "Paris"'
    ev_truncated = _parse_filter_smart_fn(ctx, truncated_json)
    assert ev_truncated.actions.route == "repair_json"
    assert ev_truncated.actions.state_delta == {"agent_response": truncated_json}

    # 4. Valid JSON syntax with broken schema types -> routes to 'repair_json' instead of crashing finalize
    schema_broken_json = json.dumps(
        {
            "agent_response": "I found none.",
            "flights_output": "not_a_list",
        }
    )
    ev_schema_broken = _parse_filter_smart_fn(ctx, schema_broken_json)
    assert ev_schema_broken.actions.route == "repair_json"
    assert ev_schema_broken.actions.state_delta == {"agent_response": schema_broken_json}

    # 5. Top-level JSON array instead of object -> routes to 'repair_json'
    array_json = json.dumps([valid_flight])
    ev_array = _parse_filter_smart_fn(ctx, array_json)
    assert ev_array.actions.route == "repair_json"

    # 6. Verify _finalize_output_fn normalizes both dict ('parsed') and JSONParserOutput ('repair_json')
    repaired_model = JSONParserOutput(
        agent_response="Repaired explanation.",
        flights_output=[valid_flight],
    )
    ev_final_repaired = _finalize_output_fn(ctx, repaired_model)
    assert ev_final_repaired.output["agent_decision"] == "filter_smart"
    assert ev_final_repaired.output["agent_response"] == "Repaired explanation."
    assert len(ev_final_repaired.output["flights_output"]) == 1


def test_standalone_filter_smart_json_repair_fallback():
    """Verify standalone filter_smart API falls back to json_parser service when LLM emits broken JSON."""
    sample = _load_sample_payload()
    valid_flight = sample["flights_input"][0]
    filter_smart_payload = {
        "user_message": sample["user_message"],
        "conversational_history": sample["conversational_history"],
        "flights_input": sample["flights_input"],
    }

    async def _broken_llm_reply(runner_self, *args, **kwargs):
        return [_mock_text_event("```json\n{\"agent_response\": \"broken\", }\n```")]

    repaired_api_payload = {
        "status": "success",
        "results": [
            {
                "agent_response": "Repaired by standalone json_parser.",
                "flights_output": [valid_flight],
            }
        ],
    }

    with TestClient(filter_smart_api) as client:
        with (
            patch.object(Runner, "run_debug", autospec=True, side_effect=_broken_llm_reply),
            patch(
                "app.sub_agents.filter_smart.main.call_json_parser_api",
                return_value=repaired_api_payload,
            ) as mock_repair_call,
        ):
            resp = client.post("/run-filter-smart", json=filter_smart_payload)
            assert resp.status_code == 200
            assert mock_repair_call.call_count == 1
            assert (
                resp.json()["results"][0]["agent_response"]
                == "Repaired by standalone json_parser."
            )


def test_constrained_decoding_truncation_triggers_backup_failover():
    """Simulate MAX_TOKENS / Pydantic ValidationError on constrained-decoding sub-agents triggering fallback_app."""
    payload = _load_sample_payload()
    seen_apps = []

    async def _primary_schema_truncation(runner_self, *args, **kwargs):
        seen_apps.append(runner_self.app)
        if runner_self.app is app:
            # Simulate ADK raising ValidationError when constrained decoding truncates at MAX_TOKENS
            EngageOutput.model_validate_json('{"agent_response": "truncated')
        return [
            _mock_text_event(
                json.dumps(
                    {
                        "agent_response": "Recovered via gemini-3.6-flash after primary truncation.",
                        "agent_decision": "continue",
                    }
                )
            )
        ]

    with TestClient(api) as client:
        with patch.object(
            Runner, "run_debug", autospec=True, side_effect=_primary_schema_truncation
        ):
            resp = client.post("/run-conversational", json=payload)
            assert resp.status_code == 200
            assert seen_apps == [app, fallback_app]
            assert (
                resp.json()["results"]["agent_response"]
                == "Recovered via gemini-3.6-flash after primary truncation."
            )


def test_plain_text_non_json_reply_graceful_degradation():
    """Inject unexpected plain-text LLM replies and empty event parts to verify zero 500 crashes."""
    payload = _load_sample_payload()

    async def _plain_text_reply(runner_self, *args, **kwargs):
        empty_event = SimpleNamespace(content=None)
        text_event = _mock_text_event("I am temporarily returning plain text instead of JSON.")
        return [empty_event, text_event]

    with TestClient(api) as client:
        with patch.object(Runner, "run_debug", autospec=True, side_effect=_plain_text_reply):
            resp = client.post("/run-conversational", json=payload)
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "success"
            assert isinstance(body.get("session_id"), str) and body["session_id"]
            assert body["results"] == {
                "raw_text": "I am temporarily returning plain text instead of JSON."
            }

    # Verify standalone sub-agent also degrades safely to {"raw_text": ...}
    engage_payload = {
        "user_message": payload["user_message"],
        "conversational_history": payload["conversational_history"],
    }
    with TestClient(engage_api) as sub_client:
        with patch.object(Runner, "run_debug", autospec=True, side_effect=_plain_text_reply):
            sub_resp = sub_client.post("/run-engage", json=engage_payload)
            assert sub_resp.status_code == 200
            assert sub_resp.json()["results"] == [
                {"raw_text": "I am temporarily returning plain text instead of JSON."}
            ]


def test_telemetry_model_error_and_readiness_fault_injection():
    """Inject model errors into ExecutionTelemetryPlugin and broken app/model states into evaluate_readiness."""

    async def _exercise_error_hooks():
        plugin = ExecutionTelemetryPlugin()
        inv_ctx = SimpleNamespace(invocation_id="inv-fault-99887766")
        cb_ctx = SimpleNamespace(
            invocation_id="inv-fault-99887766", agent_name="filter_smart"
        )
        await plugin.before_run_callback(invocation_context=inv_ctx)

        # Model error callback logs warning and returns None so ADK retries/failover proceed untouched
        err_result = await plugin.on_model_error_callback(
            callback_context=cb_ctx,
            llm_request=SimpleNamespace(),
            error=TimeoutError("408 Deadline Exceeded"),
        )
        assert err_result is None
        await plugin.on_run_error_callback(
            invocation_context=inv_ctx,
            error=TimeoutError("408 Deadline Exceeded"),
        )
        assert "inv-fault-99887766" not in plugin._runs

    asyncio.run(_exercise_error_hooks())

    # Readiness probe fault injection: uninitialized ADK app + blank sub-agent model name + missing location
    with patch.dict(
        os.environ,
        {
            "GOOGLE_GENAI_USE_VERTEXAI": "1",
            "GOOGLE_CLOUD_PROJECT": "travel-agent-test",
            "GOOGLE_CLOUD_LOCATION": "",
        },
        clear=False,
    ):
        unready = evaluate_readiness(
            service_name="conversational-app",
            adk_app=None,
            models={"engage": "gemini-3.5-flash-lite", "filter": "   "},
        )
        assert unready.status_code == 503
        body = json.loads(unready.body.decode("utf-8"))
        assert body["status"] == "not_ready"
        assert len(body["errors"]) == 3
