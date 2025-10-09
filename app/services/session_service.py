from typing import Dict, Any, Optional, List
import time
import logging
from datetime import datetime, timezone
from app.services.redis_client import redis_service

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage user sessions for voice interactions (async version)"""

    def __init__(self):
        self.redis = redis_service
        self.session_prefix = "session:"
        self.draft_prefix = "draft:"
        self.message_prefix = "current_message:"
        self.gemini_prefix = "gemini_session:"

    def _get_session_key(self, firebase_uid: str) -> str:
        """Generate Redis key for session state"""
        return f"{self.session_prefix}{firebase_uid}"

    def _get_draft_key(self, firebase_uid: str) -> str:
        """Generate Redis key for draft storage"""
        return f"{self.draft_prefix}{firebase_uid}"

    def _get_message_key(self, firebase_uid: str) -> str:
        """Generate Redis key for current message"""
        return f"{self.message_prefix}{firebase_uid}"

    def _get_gemini_key(self, firebase_uid: str) -> str:
        """Generate Redis key for Gemini session"""
        return f"{self.gemini_prefix}{firebase_uid}"

    # Session State Management
    async def store_session_state(self, firebase_uid: str, session_data: Dict[str, Any]) -> bool:
        """Store user session state"""
        session_data["last_active"] = int(time.time())
        key = self._get_session_key(firebase_uid)
        return await self.redis.set_json(key, session_data)

    async def get_session_state(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get user session state"""
        key = self._get_session_key(firebase_uid)
        data = await self.redis.get(key)
        if data:
            import json
            return json.loads(data)
        return None

    async def update_session_navigation(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific navigation fields in session"""
        session = await self.get_session_state(firebase_uid) or {}
        session.update(kwargs)
        return await self.store_session_state(firebase_uid, session)

    async def clear_session_state(self, firebase_uid: str) -> bool:
        """Clear user session state"""
        key = self._get_session_key(firebase_uid)
        result = await self.redis.delete(key)
        return result > 0 if isinstance(result, int) else bool(result)

    # Draft Storage
    async def store_draft(self, firebase_uid: str, draft_data: Dict[str, Any]) -> bool:
        """Store temporary draft"""
        draft_data["created_at"] = int(time.time())
        draft_data["modified_at"] = int(time.time())
        key = self._get_draft_key(firebase_uid)
        return await self.redis.set_json(key, draft_data)

    async def get_draft(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get user's temporary draft"""
        key = self._get_draft_key(firebase_uid)
        data = await self.redis.get(key)
        if data:
            import json
            return json.loads(data)
        return None

    async def update_draft(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific draft fields"""
        draft = await self.get_draft(firebase_uid) or {}
        draft.update(kwargs)
        draft["modified_at"] = int(time.time())
        return await self.store_draft(firebase_uid, draft)

    async def clear_draft(self, firebase_uid: str) -> bool:
        """Clear user's temporary draft"""
        key = self._get_draft_key(firebase_uid)
        result = await self.redis.delete(key)
        return result > 0 if isinstance(result, int) else bool(result)

    # Helper Methods
    async def init_session_state(self, firebase_uid: str) -> Dict[str, Any]:
        """Initialize default session state"""
        default_session = {
            "current_message_id": None,
            "message_queue": [],
            "current_filter": "unread",
            "current_index": 0,
            "total_messages": 0,
            "next_page_token": None,
            "last_active": int(time.time())
        }
        await self.store_session_state(firebase_uid, default_session)
        return default_session

    async def get_or_init_session(self, firebase_uid: str) -> Dict[str, Any]:
        """Get existing session or initialize new one"""
        session = await self.get_session_state(firebase_uid)
        if not session:
            session = await self.init_session_state(firebase_uid)
        return session
    
    # Current Message Caching (using string keys with TTL)
    async def store_current_message(self, firebase_uid: str, message_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Store current message with TTL (default 1 hour)"""
        key = self._get_message_key(firebase_uid)
        return await self.redis.setex_json(key, ttl, message_data)

    async def get_current_message(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get cached current message"""
        key = self._get_message_key(firebase_uid)
        return await self.redis.get_json(key)

    async def clear_current_message(self, firebase_uid: str) -> bool:
        """Clear cached current message"""
        key = self._get_message_key(firebase_uid)
        return await self.redis.delete(key)

    async def cleanup_user_data(self, firebase_uid: str) -> bool:
        """Remove all user data (session, drafts, cached messages)"""
        session_removed = await self.clear_session_state(firebase_uid)
        draft_removed = await self.clear_draft(firebase_uid)
        message_removed = await self.clear_current_message(firebase_uid)
        gemini_removed = await self.clear_gemini_session_data(firebase_uid)

        logger.info(f"User cleanup for {firebase_uid}: session={session_removed}, draft={draft_removed}, message={message_removed}, gemini={gemini_removed}")
        return session_removed or draft_removed or message_removed or gemini_removed

    # Gemini Session Management
    async def store_gemini_resumption_token(self, firebase_uid: str, token: str) -> bool:
        """
        Store Gemini resumption token for user

        Args:
            firebase_uid: User identifier
            token: Resumption token from Gemini session

        Returns:
            True if successfully stored
        """
        try:
            session_data = {
                "resumption_token": token,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": int(datetime.now(timezone.utc).timestamp() + 7200)  # 2 hours from now
            }

            key = self._get_gemini_key(firebase_uid)
            success = await self.redis.setex_json(key, 7200, session_data)  # 2-hour TTL

            if success:
                logger.info(f"Stored Gemini resumption token for user {firebase_uid}")
            else:
                logger.error(f"Failed to store Gemini resumption token for user {firebase_uid}")

            return success

        except Exception as e:
            logger.error(f"Error storing Gemini resumption token for user {firebase_uid}: {e}")
            return False

    async def get_gemini_resumption_token(self, firebase_uid: str) -> Optional[str]:
        """
        Retrieve Gemini resumption token for user

        Args:
            firebase_uid: User identifier

        Returns:
            Resumption token if available and not expired, None otherwise
        """
        try:
            key = self._get_gemini_key(firebase_uid)
            session_data = await self.redis.get_json(key)

            if not session_data:
                logger.debug(f"No Gemini resumption token found for user {firebase_uid}")
                return None

            # Check if token is expired
            expires_at = session_data.get("expires_at", 0)
            if datetime.now(timezone.utc).timestamp() > expires_at:
                logger.info(f"Gemini resumption token expired for user {firebase_uid}")
                await self.clear_gemini_session_data(firebase_uid)
                return None

            token = session_data.get("resumption_token")
            if token:
                logger.info(f"Retrieved valid Gemini resumption token for user {firebase_uid}")

            return token

        except Exception as e:
            logger.error(f"Error retrieving Gemini resumption token for user {firebase_uid}: {e}")
            return None

    async def clear_gemini_session_data(self, firebase_uid: str) -> bool:
        """
        Clear Gemini session data for user

        Args:
            firebase_uid: User identifier

        Returns:
            True if successfully cleared
        """
        try:
            key = self._get_gemini_key(firebase_uid)
            success = await self.redis.delete(key)
            if success:
                logger.info(f"Cleared Gemini session data for user {firebase_uid}")
            return success

        except Exception as e:
            logger.error(f"Error clearing Gemini session data for user {firebase_uid}: {e}")
            return False

    async def handle_gemini_goaway(self, firebase_uid: str, goaway_data: Dict[str, Any]) -> bool:
        """
        Handle GoAway message from Gemini API by storing session state

        Args:
            firebase_uid: User identifier
            goaway_data: GoAway message data from Gemini

        Returns:
            True if session state saved successfully
        """
        try:
            logger.info(f"Handling Gemini GoAway message for user {firebase_uid}: {goaway_data}")

            # Extract resumption token from GoAway data
            resumption_token = goaway_data.get("resumption_token")
            if resumption_token:
                return await self.store_gemini_resumption_token(firebase_uid, resumption_token)
            else:
                logger.warning(f"No resumption token in GoAway message for user {firebase_uid}")
                return False

        except Exception as e:
            logger.error(f"Error handling Gemini GoAway message for user {firebase_uid}: {e}")
            return False