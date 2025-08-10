from typing import List, Optional, Dict, Any
import json
import redis
from ...config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, NAVIGATION_KEY_PREFIX, NAVIGATION_TTL


class NavigationManager:
    def __init__(self, max_history: int = 5, user_id: str = "default"):
        if not user_id or user_id.strip() == "":
            raise ValueError("user_id cannot be empty")
        
        self.max_history = max_history
        self.user_id = user_id.strip()
        # Use more explicit key format for better isolation
        self.redis_key = f"{NAVIGATION_KEY_PREFIX}:{self.user_id}"
        
        print(f"[NavigationManager] Initializing for user: {self.user_id}")
        print(f"[NavigationManager] Redis key: {self.redis_key}")
        
        # Connect to Redis - fail if unavailable
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            print(f"[NavigationManager] Connected to Redis for user {user_id}")
        except Exception as e:
            print(f"[NavigationManager] FATAL: Cannot connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {e}") from e
    
    def _get_state(self) -> Dict[str, Any]:
        """Get navigation state from Redis"""
        try:
            data = self.redis_client.get(self.redis_key)
            if data:
                return json.loads(data)
            else:
                # Default state
                return {
                    "token_stack": [None],
                    "current_index": 0,
                    "current_query": "",
                    "current_limit": 10,
                    "next_available_token": None,
                    "recent_messages": []
                }
        except Exception as e:
            print(f"[NavigationManager] Error reading from Redis: {e}")
            raise
    
    def _save_state(self, state: Dict[str, Any]):
        """Save navigation state to Redis"""
        try:
            self.redis_client.setex(
                self.redis_key,
                NAVIGATION_TTL,
                json.dumps(state)
            )
        except Exception as e:
            print(f"[NavigationManager] Error saving to Redis: {e}")
            raise
    
    def start_new_search(self, query: str, limit: int):
        """Start a new search, reset navigation"""
        state = {
            "token_stack": [None],
            "current_index": 0,
            "current_query": query,
            "current_limit": limit,
            "next_available_token": None,
            "recent_messages": []
        }
        self._save_state(state)
    
    def set_next_page_token(self, next_page_token: Optional[str]):
        """Store the next page token from search results"""
        state = self._get_state()
        state["next_available_token"] = next_page_token
        self._save_state(state)
    
    def navigate_next(self) -> Optional[str]:
        """Navigate to next page using stored token"""
        state = self._get_state()
        
        if not state.get("next_available_token"):
            return None  # No next page available
        
        next_page_token = state["next_available_token"]
        token_stack = state["token_stack"]
        current_index = state["current_index"]
        
        # If we're not at the end of stack, just move forward
        if current_index + 1 < len(token_stack):
            current_index += 1
            state["current_index"] = current_index
            self._save_state(state)
            return token_stack[current_index]
        
        # Add new page to stack
        token_stack.append(next_page_token)
        
        # Trim stack if too large (keep most recent pages)
        if len(token_stack) > self.max_history:
            token_stack.pop(0)  # Remove oldest page
            current_index = len(token_stack) - 1
        else:
            current_index += 1
        
        state["token_stack"] = token_stack
        state["current_index"] = current_index
        self._save_state(state)
        
        return token_stack[current_index]
    
    def navigate_previous(self) -> Optional[str]:
        """Navigate to previous page"""
        state = self._get_state()
        current_index = state["current_index"]
        token_stack = state["token_stack"]
        
        if current_index <= 0:
            return None  # Already at first page
        
        current_index -= 1
        state["current_index"] = current_index
        self._save_state(state)
        
        return token_stack[current_index]
    
    def get_current_page_token(self) -> Optional[str]:
        """Get current page token"""
        state = self._get_state()
        current_index = state["current_index"]
        token_stack = state["token_stack"]
        
        if 0 <= current_index < len(token_stack):
            return token_stack[current_index]
        return None
    
    def can_go_next(self) -> bool:
        """Check if next navigation is possible"""
        state = self._get_state()
        has_next_token = state.get("next_available_token") is not None
        at_end_of_stack = state["current_index"] + 1 >= len(state["token_stack"])
        return has_next_token or not at_end_of_stack
    
    def can_go_previous(self) -> bool:
        """Check if previous navigation is possible"""
        state = self._get_state()
        return state["current_index"] > 0
    
    def get_navigation_commands(self) -> List[str]:
        """Generate navigation command strings for user"""
        commands = []
        
        if self.can_go_previous():
            commands.append("'previous'")
        
        if self.can_go_next():
            commands.append("'next'")
        
        return commands
    
    def get_navigation_info(self) -> Dict[str, Any]:
        """Get current navigation state for debugging"""
        state = self._get_state()
        return {
            "current_page": state["current_index"] + 1,
            "stack_size": len(state["token_stack"]),
            "can_go_previous": self.can_go_previous(),
            "current_token": self.get_current_page_token(),
            "query": state["current_query"]
        }
    
    def store_recent_messages(self, messages: List[Dict[str, Any]], max_messages: int = 10):
        """Store recent messages for draft context"""
        state = self._get_state()
        
        # Add new messages to the beginning (most recent first)
        recent_messages = messages + state.get("recent_messages", [])
        
        # Keep only the most recent max_messages
        state["recent_messages"] = recent_messages[:max_messages]
        
        self._save_state(state)
        print(f"[NavigationManager] Stored {len(messages)} messages, total recent: {len(state['recent_messages'])}")
    
    def get_recent_messages(self) -> List[Dict[str, Any]]:
        """Get recently read messages"""
        state = self._get_state()
        return state.get("recent_messages", [])
    
    def find_message_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        """Find message by reference like 'this', 'last', 'from john', etc."""
        recent_messages = self.get_recent_messages()
        
        if not recent_messages:
            return None
        
        reference_lower = reference.lower().strip()
        
        # Handle "this" or "last" - return most recent message
        if reference_lower in ["this", "last", "latest"]:
            return recent_messages[0]
        
        # Handle "from [sender]" - search by sender
        if reference_lower.startswith("from "):
            sender_name = reference_lower[5:].strip()
            for msg in recent_messages:
                sender = msg.get("sender", "").lower()
                if sender_name in sender:
                    return msg
        
        # Handle "about [subject]" - search by subject
        if reference_lower.startswith("about "):
            subject_keywords = reference_lower[6:].strip()
            for msg in recent_messages:
                subject = msg.get("subject", "").lower()
                if subject_keywords in subject:
                    return msg
        
        # Default to most recent message if reference is unclear
        return recent_messages[0]
    
    def clear_user_data(self):
        """Clear all navigation data for this user (useful for testing/logout)"""
        try:
            result = self.redis_client.delete(self.redis_key)
            print(f"[NavigationManager] Cleared data for user {self.user_id}: {result} keys deleted")
            return result > 0
        except Exception as e:
            print(f"[NavigationManager] Error clearing data: {e}")
            return False