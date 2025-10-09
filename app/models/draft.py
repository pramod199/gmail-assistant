from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailDraft(BaseModel):
    """Email draft domain model."""
    user_id: str
    recipient: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    created_at: Optional[datetime] = None
    status: str = "editing"  # editing, saved, sent
