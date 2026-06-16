"""Conversation Manager — multi-turn conversation support for agents.

Provides session-based conversation history, message accumulation,
and context windowing for LLM agents.

DTP §E1: Multi-turn conversation support.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConversationMessage:
    """A single message in a conversation turn."""

    def __init__(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.role = role
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = time.time()
        self.message_id = str(uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            **self.metadata,
        }


class ConversationSession:
    """Manages multi-turn conversation history for a single agent-session pair.

    Supports:
    - Message accumulation across turns
    - Context windowing (max messages, token budget)
    - Session persistence (in-memory, pluggable backend)
    - History pruning and summarization hooks
    """

    def __init__(
        self,
        session_id: str,
        agent_role: str,
        max_messages: int = 50,
        max_tokens: int = 8000,
    ):
        self.session_id = session_id
        self.agent_role = agent_role
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._messages: deque[ConversationMessage] = deque(maxlen=max_messages)
        self._created_at = time.time()
        self._last_turn_at: float | None = None
        self._turn_count = 0

    def add_user_message(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a user message to the conversation."""
        msg = ConversationMessage("user", content, metadata)
        self._messages.append(msg)
        self._last_turn_at = time.time()
        self._turn_count += 1

    def add_assistant_message(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add an assistant message to the conversation."""
        msg = ConversationMessage("assistant", content, metadata)
        self._messages.append(msg)

    def get_history(self, max_messages: int = 0) -> list[dict[str, Any]]:
        """Get conversation history as a list of message dicts.

        Args:
            max_messages: Max messages to return (0 = all).
        """
        msgs = list(self._messages)
        if max_messages > 0:
            msgs = msgs[-max_messages:]
        return [m.to_dict() for m in msgs]

    def get_context_messages(self, include_system: bool = True) -> list[dict[str, str]]:
        """Get messages formatted for LLM API calls.

        Returns messages in the format: [{"role": "user", "content": "..."}, ...]
        Applies token budget windowing to stay within context limits.
        """
        messages = []
        total_chars = 0
        char_budget = self.max_tokens * 4  # rough chars-per-token estimate

        for msg in reversed(self._messages):
            msg_chars = len(msg.content)
            if total_chars + msg_chars > char_budget:
                break
            messages.append({"role": msg.role, "content": msg.content})
            total_chars += msg_chars

        messages.reverse()
        return messages

    def clear(self) -> None:
        """Clear conversation history."""
        self._messages.clear()
        self._turn_count = 0

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def get_stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_role": self.agent_role,
            "turn_count": self._turn_count,
            "message_count": len(self._messages),
            "created_at": self._created_at,
            "last_turn_at": self._last_turn_at,
        }


class ConversationManager:
    """Global conversation manager — tracks sessions across all agents.

    Provides session creation, lookup, and cleanup. Sessions are keyed
    by (session_id, agent_role) for multi-agent missions.
    """

    def __init__(self, max_sessions: int = 1000):
        self._sessions: dict[str, ConversationSession] = {}
        self._max_sessions = max_sessions

    def get_or_create(
        self,
        session_id: str,
        agent_role: str,
        max_messages: int = 50,
        max_tokens: int = 8000,
    ) -> ConversationSession:
        """Get an existing session or create a new one."""
        key = f"{session_id}:{agent_role}"
        if key not in self._sessions:
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest()
            self._sessions[key] = ConversationSession(
                session_id=session_id,
                agent_role=agent_role,
                max_messages=max_messages,
                max_tokens=max_tokens,
            )
        return self._sessions[key]

    def get(self, session_id: str, agent_role: str) -> ConversationSession | None:
        """Get a session by ID and role."""
        return self._sessions.get(f"{session_id}:{agent_role}")

    def end_session(self, session_id: str, agent_role: str) -> None:
        """End and remove a session."""
        key = f"{session_id}:{agent_role}"
        self._sessions.pop(key, None)

    def list_sessions(self, agent_role: str = "") -> list[dict[str, Any]]:
        """List all active sessions, optionally filtered by agent role."""
        sessions = []
        for key, session in self._sessions.items():
            if agent_role and session.agent_role != agent_role:
                continue
            sessions.append(session.get_stats())
        return sessions

    def _evict_oldest(self) -> None:
        """Evict the oldest session when at capacity."""
        if not self._sessions:
            return
        oldest_key = min(
            self._sessions.keys(),
            key=lambda k: self._sessions[k]._created_at,
        )
        del self._sessions[oldest_key]
        logger.debug("Evicted oldest session: %s", oldest_key)

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Remove sessions older than max_age_seconds. Returns count removed."""
        now = time.time()
        expired = [
            key for key, session in self._sessions.items()
            if session._last_turn_at and (now - session._last_turn_at) > max_age_seconds
        ]
        for key in expired:
            del self._sessions[key]
        return len(expired)


# Module-level singleton
conversation_manager = ConversationManager()
