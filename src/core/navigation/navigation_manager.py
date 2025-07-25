from typing import List, Optional, Dict, Any


class NavigationManager:
    def __init__(self, max_history: int = 5):
        self.token_stack: List[Optional[str]] = [None]  # [None, token1, token2, ...] - None for first page
        self.current_index: int = 0  # Current position in stack
        self.max_history: int = max_history  # Limit memory usage
        self.current_query: str = ""
        self.current_limit: int = 10
    
    def start_new_search(self, query: str, limit: int):
        """Start a new search, reset navigation"""
        self.token_stack = [None]  # First page has no token
        self.current_index = 0
        self.current_query = query
        self.current_limit = limit
    
    def set_next_page_token(self, next_page_token: Optional[str]):
        """Store the next page token from search results"""
        self.next_available_token = next_page_token
    
    def navigate_next(self) -> Optional[str]:
        """Navigate to next page using stored token"""
        if not hasattr(self, 'next_available_token') or self.next_available_token is None:
            return None  # No next page available
        
        next_page_token = self.next_available_token
        
        # If we're not at the end of stack, just move forward
        if self.current_index + 1 < len(self.token_stack):
            self.current_index += 1
            return self.token_stack[self.current_index]
        
        # Add new page to stack
        self.token_stack.append(next_page_token)
        
        # Trim stack if too large (keep most recent pages)
        if len(self.token_stack) > self.max_history:
            self.token_stack.pop(0)  # Remove oldest page
            self.current_index = len(self.token_stack) - 1
        else:
            self.current_index += 1
        
        return self.token_stack[self.current_index]
    
    def navigate_previous(self) -> Optional[str]:
        """Navigate to previous page"""
        if self.current_index <= 0:
            return None  # Already at first page
        
        self.current_index -= 1
        return self.token_stack[self.current_index]
    
    def get_current_page_token(self) -> Optional[str]:
        """Get current page token"""
        if 0 <= self.current_index < len(self.token_stack):
            return self.token_stack[self.current_index]
        return None
    
    def can_go_next(self) -> bool:
        """Check if next navigation is possible"""
        # Can go next if we have a stored next token OR if we're not at end of our stack
        has_next_token = hasattr(self, 'next_available_token') and self.next_available_token is not None
        return has_next_token or (self.current_index + 1 < len(self.token_stack))
    
    def can_go_previous(self) -> bool:
        """Check if previous navigation is possible"""
        return self.current_index > 0
    
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
        return {
            "current_page": self.current_index + 1,
            "stack_size": len(self.token_stack),
            "can_go_previous": self.can_go_previous(),
            "current_token": self.get_current_page_token(),
            "query": self.current_query
        }