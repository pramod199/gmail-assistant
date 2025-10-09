from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CreateSessionRequest(BaseModel):
    """Request model for creating a voice session"""
    pass  # No additional parameters needed for now


class SessionResponse(BaseModel):
    """Response model for session information"""
    session_id: str
    user_id: str
    active: bool
    created_at: datetime
    updated_at: datetime
    gmail_authorized: Optional[bool] = None
    gmail_auth_url: Optional[str] = None
    requires_gmail_auth: bool = False


class SessionListResponse(BaseModel):
    """List of active sessions."""
    sessions: List[SessionResponse]
    total: int
    active_count: Optional[int] = None


class NavigationStatusResponse(BaseModel):
    """Navigation session status."""
    current_message_id: Optional[str] = None
    current_index: int
    total_messages: int
    has_more: bool
