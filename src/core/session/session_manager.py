from typing import Dict, Any, Optional, List
import time
import logging
from datetime import datetime, timezone
from .redis_client import RedisClient
from ...models import User, GmailCredentials, SessionData, DraftData
from config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage user sessions, credentials, and drafts with string-based Redis keys"""
    
    def __init__(self):
        self.redis = RedisClient()
    
    # User Management
    def store_user(self, user: User) -> bool:
        """Store user profile data"""
        key = f"user:{user.firebase_uid}"
        return self.redis.setex_json(key, settings.USER_TTL, user.dict())
    
    def get_user(self, firebase_uid: str) -> Optional[User]:
        """Get user profile data"""
        key = f"user:{firebase_uid}"
        user_data = self.redis.get_json(key)
        return User(**user_data) if user_data else None
    
    def update_user(self, user: User) -> bool:
        """Update user profile data"""
        user.updated_at = datetime.utcnow()
        return self.store_user(user)
    
    # Credentials Management
    def store_credentials(self, firebase_uid: str, credentials: GmailCredentials) -> bool:
        """Store user credentials"""
        key = f"credentials:{firebase_uid}"
        return self.redis.setex_json(key, settings.CREDENTIALS_TTL, credentials.dict())
    
    def get_credentials(self, firebase_uid: str) -> Optional[GmailCredentials]:
        """Get user credentials"""
        key = f"credentials:{firebase_uid}"
        cred_data = self.redis.get_json(key)
        return GmailCredentials(**cred_data) if cred_data else None
    
    def update_credentials(self, firebase_uid: str, credentials: GmailCredentials) -> bool:
        """Update user credentials"""
        credentials.updated_at = datetime.utcnow()
        return self.store_credentials(firebase_uid, credentials)
    
    # Session State Management
    def store_session_state(self, firebase_uid: str, session_data: SessionData) -> bool:
        """Store user session state"""
        key = f"session:{firebase_uid}"
        return self.redis.setex_json(key, settings.SESSION_TTL, session_data.dict())
    
    def get_session_state(self, firebase_uid: str) -> Optional[SessionData]:
        """Get user session state"""
        key = f"session:{firebase_uid}"
        session_data = self.redis.get_json(key)
        return SessionData(**session_data) if session_data else None
    
    def update_session_navigation(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific navigation fields in session"""
        session = self.get_session_state(firebase_uid)
        if not session:
            session = SessionData()
        
        # Update session attributes
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.update_activity()
        return self.store_session_state(firebase_uid, session)
    
    def clear_session_state(self, firebase_uid: str) -> bool:
        """Clear user session state"""
        key = f"session:{firebase_uid}"
        return self.redis.delete(key)
    
    # Draft Storage
    def store_draft(self, firebase_uid: str, draft_data: DraftData) -> bool:
        """Store temporary draft"""
        key = f"draft:{firebase_uid}"
        return self.redis.setex_json(key, settings.DRAFT_TTL, draft_data.dict())
    
    def get_draft(self, firebase_uid: str) -> Optional[DraftData]:
        """Get user's temporary draft"""
        key = f"draft:{firebase_uid}"
        draft_data = self.redis.get_json(key)
        return DraftData(**draft_data) if draft_data else None
    
    def update_draft(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific draft fields"""
        draft = self.get_draft(firebase_uid)
        if not draft:
            # Create new draft if none exists
            draft = DraftData(content="")
        
        # Update draft attributes
        for key, value in kwargs.items():
            if hasattr(draft, key):
                setattr(draft, key, value)
        
        draft.updated_at = datetime.utcnow()
        return self.store_draft(firebase_uid, draft)
    
    def clear_draft(self, firebase_uid: str) -> bool:
        """Clear user's temporary draft"""
        key = f"draft:{firebase_uid}"
        return self.redis.delete(key)
    
    # Helper Methods
    def init_session_state(self, firebase_uid: str) -> SessionData:
        """Initialize default session state"""
        default_session = SessionData()
        self.store_session_state(firebase_uid, default_session)
        return default_session
    
    def get_or_init_session(self, firebase_uid: str) -> SessionData:
        """Get existing session or initialize new one"""
        session = self.get_session_state(firebase_uid)
        if not session:
            session = self.init_session_state(firebase_uid)
        return session
    
    # Current Message Caching (using string keys with TTL)
    def store_current_message(self, firebase_uid: str, message_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Store current message with TTL (default 1 hour)"""
        key = f"current_message:{firebase_uid}"
        return self.redis.setex_json(key, ttl, message_data)
    
    def get_current_message(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get cached current message"""
        key = f"current_message:{firebase_uid}"
        return self.redis.get_json(key)
    
    def clear_current_message(self, firebase_uid: str) -> bool:
        """Clear cached current message"""
        key = f"current_message:{firebase_uid}"
        return self.redis.delete(key)

    def cleanup_user_data(self, firebase_uid: str) -> bool:
        """Remove all user data (user, credentials, session, drafts, cached messages)"""
        user_removed = self.redis.delete(f"user:{firebase_uid}")
        credentials_removed = self.redis.delete(f"credentials:{firebase_uid}")
        session_removed = self.clear_session_state(firebase_uid)
        draft_removed = self.clear_draft(firebase_uid)
        message_removed = self.clear_current_message(firebase_uid)
        gemini_removed = self.clear_gemini_session_data(firebase_uid)
        
        logger.info(f"User cleanup for {firebase_uid}: user={user_removed}, credentials={credentials_removed}, session={session_removed}, draft={draft_removed}, message={message_removed}, gemini={gemini_removed}")
        return any([user_removed, credentials_removed, session_removed, draft_removed, message_removed, gemini_removed])

    # Gemini Session Management
    def store_gemini_resumption_token(self, firebase_uid: str, token: str) -> bool:
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
            
            key = f"gemini_session:{firebase_uid}"
            success = self.redis.setex_json(key, 7200, session_data)  # 2-hour TTL
            
            if success:
                logger.info(f"Stored Gemini resumption token for user {firebase_uid}")
            else:
                logger.error(f"Failed to store Gemini resumption token for user {firebase_uid}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error storing Gemini resumption token for user {firebase_uid}: {e}")
            return False
    
    def get_gemini_resumption_token(self, firebase_uid: str) -> Optional[str]:
        """
        Retrieve Gemini resumption token for user
        
        Args:
            firebase_uid: User identifier
            
        Returns:
            Resumption token if available and not expired, None otherwise
        """
        try:
            key = f"gemini_session:{firebase_uid}"
            session_data = self.redis.get_json(key)
            
            if not session_data:
                logger.debug(f"No Gemini resumption token found for user {firebase_uid}")
                return None
            
            # Check if token is expired
            expires_at = session_data.get("expires_at", 0)
            if datetime.now(timezone.utc).timestamp() > expires_at:
                logger.info(f"Gemini resumption token expired for user {firebase_uid}")
                self.clear_gemini_session_data(firebase_uid)
                return None
            
            token = session_data.get("resumption_token")
            if token:
                logger.info(f"Retrieved valid Gemini resumption token for user {firebase_uid}")
            
            return token
            
        except Exception as e:
            logger.error(f"Error retrieving Gemini resumption token for user {firebase_uid}: {e}")
            return None
    
    def clear_gemini_session_data(self, firebase_uid: str) -> bool:
        """
        Clear Gemini session data for user
        
        Args:
            firebase_uid: User identifier
            
        Returns:
            True if successfully cleared
        """
        try:
            key = f"gemini_session:{firebase_uid}"
            success = self.redis.delete(key)
            if success:
                logger.info(f"Cleared Gemini session data for user {firebase_uid}")
            return success
            
        except Exception as e:
            logger.error(f"Error clearing Gemini session data for user {firebase_uid}: {e}")
            return False
    
    def handle_gemini_goaway(self, firebase_uid: str, goaway_data: Dict[str, Any]) -> bool:
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
                return self.store_gemini_resumption_token(firebase_uid, resumption_token)
            else:
                logger.warning(f"No resumption token in GoAway message for user {firebase_uid}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling Gemini GoAway message for user {firebase_uid}: {e}")
            return False