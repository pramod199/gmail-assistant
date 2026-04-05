"""
Redis-based Voice Session Management for Gmail Assistant

This module provides persistent session storage using Redis instead of in-memory dictionaries.
Sessions survive server restarts and can be shared across multiple server instances.
"""

import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from app.config import settings
from app.services.redis_client import redis_service
import logging

logger = logging.getLogger(__name__)


class VoiceSessionData(BaseModel):
    """Voice session data that can be serialized to Redis."""
    id: str
    user_id: str
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceSession:
    """
    Redis-backed voice session.

    Non-serializable attributes (queues, Gemini sessions, handlers) are kept in memory
    but the core session data is persisted to Redis.
    """

    def __init__(self, session_data: VoiceSessionData):
        self.data = session_data

        # In-memory only attributes (not persisted)
        self.gemini_session: Optional[Any] = None
        self.gemini_client: Optional[Any] = None
        self.session_context: Optional[Any] = None
        self.function_handler: Optional[Any] = None
        self.gmail_service: Optional[Any] = None
        self.response_task: Optional[asyncio.Task] = None
        self.response_monitor_active: bool = False
        self.websocket: Optional[Any] = None
        self.voice_persona: Dict[str, Any] = {}  # Loaded from UserConfigManager at connect time

    @property
    def id(self) -> str:
        return self.data.id

    @property
    def user_id(self) -> str:
        return self.data.user_id

    @property
    def active(self) -> bool:
        return self.data.active

    @active.setter
    def active(self, value: bool):
        self.data.active = value


class VoiceSessionManager:
    """Manages voice sessions with Redis persistence."""

    SESSION_PREFIX = "voice_session:"
    USER_SESSIONS_PREFIX = "user_voice_sessions:"
    SESSION_TTL = settings.VOICE_SESSION_TTL  # From settings

    def __init__(self):
        # In-memory cache of active sessions (for non-serializable attributes)
        self._active_sessions: Dict[str, VoiceSession] = {}

    async def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"{self.SESSION_PREFIX}{session_id}"

    async def _get_user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's session set."""
        return f"{self.USER_SESSIONS_PREFIX}{user_id}"

    async def create_session(
        self,
        user_id: str
    ) -> VoiceSession:
        """Create a new voice session and persist to Redis."""

        # Create session data
        session_data = VoiceSessionData(
            id=str(uuid.uuid4()),
            user_id=user_id
        )

        try:
            # Save to Redis
            session_key = await self._get_session_key(session_data.id)
            await redis_service.setex_json(
                session_key,
                self.SESSION_TTL,
                json.loads(session_data.model_dump_json())
            )

            # Add to user's session set
            user_sessions_key = await self._get_user_sessions_key(user_id)
            await redis_service.sadd(user_sessions_key, session_data.id)
            await redis_service.expire(user_sessions_key, self.SESSION_TTL)
        except Exception as e:
            logger.error(f"Failed to save session to Redis: {e}")
            # Continue anyway - session will work but won't persist
            logger.warning(f"Session {session_data.id} created in memory only due to Redis error")

        # Create session object
        session = VoiceSession(session_data)
        self._active_sessions[session_data.id] = session

        logger.info(f"Created voice session {session_data.id} for user {user_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get a session by ID, loading from Redis if needed."""
        # Check in-memory cache first
        if session_id in self._active_sessions:
            logger.debug(f"Session {session_id} found in memory cache")
            return self._active_sessions[session_id]

        # Load from Redis
        session_key = await self._get_session_key(session_id)
        logger.debug(f"Looking for session in Redis with key: {session_key}")
        session_json = await redis_service.get(session_key)

        if not session_json:
            logger.warning(f"Session {session_id} not found in Redis (key: {session_key})")
            return None

        try:
            logger.debug(f"Loading session {session_id} from Redis")
            session_data = VoiceSessionData.model_validate_json(session_json)
            session = VoiceSession(session_data)
            self._active_sessions[session_id] = session
            logger.info(f"Successfully loaded session {session_id} from Redis")
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id} from Redis: {e}")
            return None

    async def update_session(self, session: VoiceSession) -> bool:
        """Update session data in Redis."""
        session_key = await self._get_session_key(session.id)

        # Update timestamp
        session.data.updated_at = datetime.utcnow()

        # Save to Redis
        result = await redis_service.setex_json(
            session_key,
            self.SESSION_TTL,
            json.loads(session.data.model_dump_json())
        )

        return result

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis and memory."""
        # Get session to find user_id
        session = await self.get_session(session_id)
        if not session:
            return False

        # Mark as inactive
        session.active = False
        await self.update_session(session)

        # Remove from user's session set
        user_sessions_key = await self._get_user_sessions_key(session.user_id)
        await redis_service.srem(user_sessions_key, session_id)

        # Delete from Redis
        session_key = await self._get_session_key(session_id)
        await redis_service.delete(session_key)

        # Remove from memory cache
        self._active_sessions.pop(session_id, None)

        logger.info(f"Deleted voice session {session_id}")
        return True

    async def get_user_sessions(self, user_id: str) -> list[str]:
        """Get all session IDs for a user."""
        user_sessions_key = await self._get_user_sessions_key(user_id)
        session_ids = await redis_service.smembers(user_sessions_key)
        return list(session_ids) if session_ids else []

    async def count_user_active_sessions(self, user_id: str) -> int:
        """Count active sessions for a user."""
        session_ids = await self.get_user_sessions(user_id)
        active_count = 0

        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session and session.active:
                active_count += 1

        return active_count

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from memory cache."""
        cleaned = 0

        # Check all cached sessions
        for session_id in list(self._active_sessions.keys()):
            session_key = await self._get_session_key(session_id)
            exists = await redis_service.exists(session_key)

            if not exists:
                # Session expired in Redis, remove from memory
                self._active_sessions.pop(session_id, None)
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired voice sessions from memory cache")

        return cleaned

    def get_cached_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get session from memory cache only (no Redis lookup)."""
        return self._active_sessions.get(session_id)


# Global voice session manager instance
voice_session_manager = VoiceSessionManager()
