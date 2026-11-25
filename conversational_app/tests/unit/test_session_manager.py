# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Unit tests for BoundedInMemorySessionManager and stateful multi-turn sessions."""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

from app.app_utils.logging import setup_logging
from app.app_utils.session_manager import BoundedInMemorySessionManager
from app.config import DEFAULT_SESSION_USER_ID
from app.main import api, session_manager

logger = setup_logging(name=__name__)

BASE_FLIGHT_PARAMS = {
    "origin": "Paris",
    "destination": "New York",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "passengers": 1,
}


def test_session_manager_ttl_and_lru_eviction() -> None:
    """Verify TTL expiration, LRU eviction order, and history length capping."""
    current_time = 100.0

    def fake_clock() -> float:
        return current_time

    async def _run() -> None:
        nonlocal current_time
        mgr = BoundedInMemorySessionManager(
            app_name="test_app",
            ttl_seconds=60.0,
            max_sessions=2,
            max_history_messages=4,
            clock=fake_clock,
        )

        # Create two sessions (at capacity)
        await mgr.prepare_turn(
            user_id="u1",
            session_id="s1",
            turn_state={"user_message": "hi"},
        )
        current_time += 10.0
        await mgr.prepare_turn(
            user_id="u1",
            session_id="s2",
            turn_state={"user_message": "hello"},
        )
        assert mgr.active_session_count == 2

        # Touch s1 so s2 becomes least-recently-used
        current_time += 10.0
        await mgr.append_turn(
            user_id="u1",
            session_id="s1",
            user_message="hi",
            agent_response="welcome",
        )

        # Adding s3 must evict s2 (LRU), keeping s1 and s3
        current_time += 10.0
        await mgr.prepare_turn(
            user_id="u1",
            session_id="s3",
            turn_state={"user_message": "third"},
        )
        assert mgr.active_session_count == 2
        assert (
            await mgr.service.get_session(
                app_name="test_app", user_id="u1", session_id="s2"
            )
            is None
        )
        assert (
            await mgr.service.get_session(
                app_name="test_app", user_id="u1", session_id="s1"
            )
            is not None
        )

        # Verify history capping at max_history_messages=4
        for idx in range(3):
            await mgr.append_turn(
                user_id="u1",
                session_id="s1",
                user_message=f"msg-{idx}",
                agent_response=f"resp-{idx}",
            )
        s1 = await mgr.service.get_session(
            app_name="test_app", user_id="u1", session_id="s1"
        )
        assert s1 is not None
        assert len(s1.state["conversational_history"]) == 4
        assert s1.state["conversational_history"] == [
            "user: msg-1",
            "bot: resp-1",
            "user: msg-2",
            "bot: resp-2",
        ]

        # Advance past TTL -> all sessions evicted on next check
        current_time += 120.0
        evicted = await mgr.evict_expired()
        assert evicted == 2
        assert mgr.active_session_count == 0

    asyncio.run(_run())


def test_multi_turn_stateful_conversation_without_frontend_history() -> None:
    """Verify backend persists conversational_history across turns using only session_id."""
    asyncio.run(session_manager.clear())
    seen_instructions: list[str] = []

    async def _fake_generate_content_async(self, llm_request, stream=False):
        sys_inst = getattr(llm_request.config, "system_instruction", "") or ""
        seen_instructions.append(str(sys_inst))
        turn_num = len(seen_instructions)
        body = {
            "agent_response": f"Reply number {turn_num}",
            "agent_decision": "continue",
        }
        yield LlmResponse(
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(text=json.dumps(body))],
            ),
            partial=False,
        )

    with patch.object(
        Gemini, "generate_content_async", new=_fake_generate_content_async
    ):
        with TestClient(api) as client:
            # Turn 1: no session_id, no conversational_history
            resp1 = client.post(
                "/api/v1/run-conversational",
                json={
                    "user_message": "Hello, I want to fly to New York",
                    "flights_search_input": BASE_FLIGHT_PARAMS,
                    "flights_input": [],
                },
            )
            assert resp1.status_code == 200
            body1 = resp1.json()
            session_id = body1["session_id"]
            assert session_id
            assert body1["results"]["agent_response"] == "Reply number 1"

            # Turn 2: pass ONLY session_id (no conversational_history)
            resp2 = client.post(
                "/api/v1/run-conversational",
                json={
                    "session_id": session_id,
                    "user_message": "Can you keep it under 600 EUR?",
                    "flights_search_input": BASE_FLIGHT_PARAMS,
                    "flights_input": [],
                },
            )
            assert resp2.status_code == 200
            body2 = resp2.json()
            assert body2["session_id"] == session_id
            assert body2["results"]["agent_response"] == "Reply number 2"

            # Turn 2's prompt must contain Turn 1's user + bot history from server memory
            assert len(seen_instructions) == 2
            assert "user: Hello, I want to fly to New York" in seen_instructions[1]
            assert "bot: Reply number 1" in seen_instructions[1]

            # Simulate an instance switch: clear in-memory store, reuse same session_id
            asyncio.run(session_manager.clear())
            resp3 = client.post(
                "/api/v1/run-conversational",
                json={
                    "session_id": session_id,
                    "user_message": "Are there direct options?",
                    "flights_search_input": BASE_FLIGHT_PARAMS,
                    "flights_input": [],
                },
            )
            assert resp3.status_code == 200
            body3 = resp3.json()
            assert body3["session_id"] == session_id
            # Fresh session transparently created on new instance (no error, empty prior history)
            assert "user: Hello, I want to fly to New York" not in seen_instructions[2]

            # Verify DELETE /api/v1/sessions/{session_id}
            del1 = client.delete(f"/api/v1/sessions/{session_id}")
            assert del1.status_code == 200
            assert del1.json() == {"status": "deleted", "session_id": session_id}

            del2 = client.delete(f"/api/v1/sessions/{session_id}")
            assert del2.status_code == 200
            assert del2.json() == {"status": "not_found", "session_id": session_id}

            stored = asyncio.run(
                session_manager.service.get_session(
                    app_name="conversational_app",
                    user_id=DEFAULT_SESSION_USER_ID,
                    session_id=session_id,
                )
            )
            assert stored is None


if __name__ == "__main__":
    try:
        test_session_manager_ttl_and_lru_eviction()
        logger.info("✅ test_session_manager_ttl_and_lru_eviction passed!")
        test_multi_turn_stateful_conversation_without_frontend_history()
        logger.info("✅ test_multi_turn_stateful_conversation_without_frontend_history passed!")
        logger.info("🎉 All session manager unit tests passed!")
    except Exception as exc:
        logger.exception(f"❌ Session manager test failed: {exc}")
        sys.exit(1)
