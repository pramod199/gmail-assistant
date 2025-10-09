from pydantic import BaseModel
from typing import Optional


class GmailAuthStatus(BaseModel):
    """Gmail OAuth authorization status."""
    is_authorized: bool
    user_id: str
    auth_url: Optional[str] = None


class GmailCallbackResponse(BaseModel):
    """Gmail OAuth callback response."""
    success: bool
    message: str
    user_id: Optional[str] = None
    next_step: Optional[str] = None
    error: Optional[str] = None


class RevokeResponse(BaseModel):
    """OAuth revocation response."""
    message: str
