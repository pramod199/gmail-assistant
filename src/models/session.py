"""
Session Model for Gmail Assistant

Stores navigation state and message context for voice assistant sessions.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SessionData(BaseModel):
    """Voice session navigation state and message context."""
    
    # Current navigation state
    current_message_id: Optional[str] = Field(None, description="Currently active Gmail message ID")
    current_index: int = Field(default=0, description="Index of current message in queue")
    
    # Message queue and pagination
    message_queue: List[str] = Field(default_factory=list, description="List of Gmail message IDs in order")
    total_messages: int = Field(default=0, description="Total number of messages in current filter")
    next_page_token: Optional[str] = Field(None, description="Gmail API pagination token for next page")
    
    # Current search context
    current_query: Optional[str] = Field(None, description="Current Gmail search query")
    
    # Session metadata
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    
    class Config:
        # JSON encoders for serialization
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()