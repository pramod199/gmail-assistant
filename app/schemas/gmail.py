from pydantic import BaseModel
from typing import Optional, List


class MessageListRequest(BaseModel):
    """Request for listing Gmail messages."""
    query: Optional[str] = None
    limit: int = 10
    page_token: Optional[str] = None


class MessageListResponse(BaseModel):
    """Response for message listing."""
    messages: List[dict]
    next_page_token: Optional[str] = None
    total_count: int


class MessageModifyRequest(BaseModel):
    """Request to modify a message."""
    message_id: str
    add_labels: Optional[List[str]] = None
    remove_labels: Optional[List[str]] = None


class MessageModifyResponse(BaseModel):
    """Response after modifying a message."""
    success: bool
    message: str
    message_id: str
