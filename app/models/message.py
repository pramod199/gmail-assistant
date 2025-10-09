from pydantic import BaseModel
from typing import Optional, List, Dict


class GmailMessage(BaseModel):
    """Gmail message domain model."""
    id: str
    thread_id: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    body: Optional[str] = None
    labels: List[str] = []
    is_unread: bool = False
    is_starred: bool = False
