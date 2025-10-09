from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VoiceSessionCreate(BaseModel):
    """Request to create a voice session."""
    user_id: Optional[str] = None  # Can be inferred from auth


class VoiceSessionResponse(BaseModel):
    """Voice session response."""
    session_id: str
    user_id: str
    created_at: datetime
    websocket_url: str
    is_active: bool = True


class VoiceSessionStatus(BaseModel):
    """Voice session status."""
    session_id: str
    is_active: bool
    last_active: Optional[datetime] = None
