from typing import Dict, Any, Optional, List
import time
from .redis_client import RedisClient


class SessionManager:
    """Manage user sessions for voice interactions"""
    
    # Redis hash names
    USER_SESSIONS = "user_sessions" 
    DRAFT_STORAGE = "draft_storage"
    
    def __init__(self):
        self.redis = RedisClient()
    
    # Session State Management
    def store_session_state(self, firebase_uid: str, session_data: Dict[str, Any]) -> bool:
        """Store user session state"""
        session_data["last_active"] = int(time.time())
        return self.redis.hset(self.USER_SESSIONS, firebase_uid, session_data)
    
    def get_session_state(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get user session state"""
        return self.redis.hget(self.USER_SESSIONS, firebase_uid)
    
    def update_session_navigation(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific navigation fields in session"""
        session = self.get_session_state(firebase_uid) or {}
        session.update(kwargs)
        return self.store_session_state(firebase_uid, session)
    
    def clear_session_state(self, firebase_uid: str) -> bool:
        """Clear user session state"""
        return self.redis.hdel(self.USER_SESSIONS, firebase_uid)
    
    # Draft Storage
    def store_draft(self, firebase_uid: str, draft_data: Dict[str, Any]) -> bool:
        """Store temporary draft"""
        draft_data["created_at"] = int(time.time())
        draft_data["modified_at"] = int(time.time())
        return self.redis.hset(self.DRAFT_STORAGE, firebase_uid, draft_data)
    
    def get_draft(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get user's temporary draft"""
        return self.redis.hget(self.DRAFT_STORAGE, firebase_uid)
    
    def update_draft(self, firebase_uid: str, **kwargs) -> bool:
        """Update specific draft fields"""
        draft = self.get_draft(firebase_uid) or {}
        draft.update(kwargs)
        draft["modified_at"] = int(time.time())
        return self.store_draft(firebase_uid, draft)
    
    def clear_draft(self, firebase_uid: str) -> bool:
        """Clear user's temporary draft"""
        return self.redis.hdel(self.DRAFT_STORAGE, firebase_uid)
    
    # Helper Methods
    def init_session_state(self, firebase_uid: str) -> Dict[str, Any]:
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
        self.store_session_state(firebase_uid, default_session)
        return default_session
    
    def get_or_init_session(self, firebase_uid: str) -> Dict[str, Any]:
        """Get existing session or initialize new one"""
        session = self.get_session_state(firebase_uid)
        if not session:
            session = self.init_session_state(firebase_uid)
        return session
    
    def cleanup_user_data(self, firebase_uid: str) -> bool:
        """Remove all user data (session, drafts)"""
        session_removed = self.clear_session_state(firebase_uid)
        draft_removed = self.clear_draft(firebase_uid)
        
        print(f"User cleanup for {firebase_uid}: session={session_removed}, draft={draft_removed}")
        return session_removed or draft_removed