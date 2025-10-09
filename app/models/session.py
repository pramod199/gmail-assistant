from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VoiceSession(BaseModel):
    """Voice session domain model."""
    session_id: str
    user_id: str
    created_at: datetime
    last_active: Optional[datetime] = None
    is_active: bool = True


class NavigationSession(BaseModel):
    """Gmail navigation session model."""
    user_id: str
    current_message_id: Optional[str] = None
    message_queue: List[str] = []
    current_filter: str = "unread"
    current_index: int = 0
    total_messages: int = 0
    next_page_token: Optional[str] = None
    last_active: Optional[datetime] = None
