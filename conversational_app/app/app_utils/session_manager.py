# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Bounded in-memory ADK session manager with TTL, LRU eviction, and per-session locking."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from google.adk.events import Event, EventActions
from google.adk.sessions import InMemorySessionService, Session

from app.app_utils.logging import setup_logging
from app.config import (
    MAX_HISTORY_MESSAGES,
    MAX_IN_MEMORY_SESSIONS,
    SESSION_TTL_SECONDS,
)

logger = setup_logging(name=__name__)

SessionKey = Tuple[str, str]


class BoundedInMemorySessionManager:
    """Wraps a process-wide ADK InMemorySessionService with TTL, LRU eviction, and locks."""

    def __init__(
        self,
        *,
        app_name: str,
        ttl_seconds: float = SESSION_TTL_SECONDS,
        max_sessions: int = MAX_IN_MEMORY_SESSIONS,
        max_history_messages: int = MAX_HISTORY_MESSAGES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0.")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be > 0.")
        if max_history_messages <= 0:
            raise ValueError("max_history_messages must be > 0.")

        self._app_name = app_name
        self._ttl_seconds = float(ttl_seconds)
        self._max_sessions = int(max_sessions)
        self._max_history_messages = int(max_history_messages)
        self._clock = clock

        self.service = InMemorySessionService()
        self._last_access: OrderedDict[SessionKey, float] = OrderedDict()
        self._locks: Dict[SessionKey, asyncio.Lock] = {}

    @property
    def active_session_count(self) -> int:
        """Returns the number of currently tracked in-memory sessions."""
        return len(self._last_access)

    def get_lock(self, *, user_id: str, session_id: str) -> asyncio.Lock:
        """Returns a per-session asyncio.Lock to serialize concurrent turns."""
        key: SessionKey = (user_id, session_id)
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def evict_expired(self) -> int:
        """Deletes all sessions whose idle time exceeds ttl_seconds."""
        now = self._clock()
        expired_keys: List[SessionKey] = []
        for key, last_ts in self._last_access.items():
            if now - last_ts >= self._ttl_seconds:
                expired_keys.append(key)
            else:
                # OrderedDict is sorted by recency (oldest first), so we can stop early.
                break

        for user_id, session_id in expired_keys:
            await self._delete_key((user_id, session_id))

        if expired_keys:
            logger.info("Evicted %d expired in-memory session(s).", len(expired_keys))
        return len(expired_keys)

    async def prepare_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_state: Dict[str, Any],
    ) -> Tuple[Session, List[str]]:
        """Loads an existing session (preserving history) or transparently creates a fresh one.

        Returns:
            A tuple of ``(session, history_snapshot)`` representing the pre-turn state.
        """
        await self.evict_expired()
        key: SessionKey = (user_id, session_id)

        existing = await self.service.get_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )

        if existing is not None:
            history = list(existing.state.get("conversational_history") or [])
            history = self._trim_history(history)
            state_delta = {
                **turn_state,
                "conversational_history": history,
            }
            await self.service.append_event(
                existing,
                Event(
                    invocation_id=f"turn-init-{uuid4().hex}",
                    author="user",
                    actions=EventActions(state_delta=state_delta),
                ),
            )
            self._touch(key)
            refreshed = await self.service.get_session(
                app_name=self._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            return refreshed or existing, history

        # Enforce LRU capacity before creating a new session
        while len(self._last_access) >= self._max_sessions:
            oldest_key, _ = next(iter(self._last_access.items()))
            await self._delete_key(oldest_key)

        seed_history = self._trim_history(
            list(turn_state.get("conversational_history") or [])
        )
        initial_state = {
            **turn_state,
            "conversational_history": seed_history,
        }
        created = await self.service.create_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state,
        )
        self._touch(key)
        return created, seed_history

    async def reset_session_for_retry(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_state: Dict[str, Any],
        history_snapshot: List[str],
    ) -> Session:
        """Rebuilds a clean session from the pre-turn snapshot before backup-model failover."""
        key: SessionKey = (user_id, session_id)
        await self.service.delete_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )
        recreated = await self.service.create_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
            state={
                **turn_state,
                "conversational_history": self._trim_history(list(history_snapshot)),
            },
        )
        self._touch(key)
        return recreated

    async def append_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        agent_response: Optional[str],
    ) -> List[str]:
        """Appends the completed user/bot exchange to the session's conversational_history."""
        session = await self.service.get_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session is None:
            return []

        history = list(session.state.get("conversational_history") or [])
        history.append(f"user: {user_message}")
        if agent_response:
            history.append(f"bot: {agent_response}")
        history = self._trim_history(history)

        await self.service.append_event(
            session,
            Event(
                invocation_id=f"turn-commit-{uuid4().hex}",
                author="user",
                actions=EventActions(state_delta={"conversational_history": history}),
            ),
        )
        self._touch((user_id, session_id))
        return history

    async def delete_session(self, *, user_id: str, session_id: str) -> bool:
        """Deletes a session if present. Returns True if it existed."""
        key: SessionKey = (user_id, session_id)
        existed = key in self._last_access or (
            await self.service.get_session(
                app_name=self._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            is not None
        )
        await self._delete_key(key)
        return existed

    async def clear(self) -> None:
        """Clears all tracked sessions from memory (useful for test isolation)."""
        for key in list(self._last_access.keys()):
            await self._delete_key(key)
        self._locks.clear()

    def _touch(self, key: SessionKey) -> None:
        self._last_access[key] = self._clock()
        self._last_access.move_to_end(key)

    def _trim_history(self, history: List[str]) -> List[str]:
        if len(history) <= self._max_history_messages:
            return history
        return history[-self._max_history_messages :]

    async def _delete_key(self, key: SessionKey) -> None:
        user_id, session_id = key
        self._last_access.pop(key, None)
        lock = self._locks.get(key)
        if lock is not None and not lock.locked():
            self._locks.pop(key, None)
        await self.service.delete_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )
