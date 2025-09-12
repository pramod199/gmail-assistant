"""
Draft Model for Gmail Assistant

Stores email draft data with support for both new emails and replies.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class DraftData(BaseModel):
    """Email draft storage and management."""
    
    # Draft content
    recipient: Optional[str] = Field(None, description="Email recipient address")
    subject: Optional[str] = Field(None, description="Email subject line")
    content: str = Field(..., description="Email body content")
    
    # Reply context
    reply_to_message_id: Optional[str] = Field(None, description="Gmail message ID being replied to")
    is_reply: bool = Field(default=False, description="Whether this is a reply to an existing message")
    
    # Draft status
    status: str = Field(default="editing", description="Current draft status")
    
    # Gmail integration
    gmail_draft_id: Optional[str] = Field(None, description="Gmail draft ID if saved to Gmail")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Draft creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    class Config:
        # JSON encoders for serialization
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
    
    @validator('recipient')
    def validate_recipient_for_new_draft(cls, v, values):
        """Validate that recipient is provided for new drafts (not replies)."""
        is_reply = values.get('is_reply', False)
        if not is_reply and not v:
            raise ValueError('Recipient is required for new drafts')
        return v
    
    @validator('subject')
    def validate_subject_for_new_draft(cls, v, values):
        """Validate that subject is provided for new drafts (not replies)."""
        is_reply = values.get('is_reply', False)
        if not is_reply and not v:
            raise ValueError('Subject is required for new drafts')
        return v
    
    def update_content(self, content: str) -> None:
        """Update draft content."""
        self.content = content
        self.updated_at = datetime.utcnow()
        if self.status == "saved":
            self.status = "editing"
    
    def update_recipient(self, recipient: str) -> None:
        """Update recipient (for new drafts only)."""
        if self.is_reply:
            raise ValueError("Cannot change recipient for reply drafts")
        self.recipient = recipient
        self.updated_at = datetime.utcnow()
        if self.status == "saved":
            self.status = "editing"
    
    def update_subject(self, subject: str) -> None:
        """Update subject (for new drafts only)."""
        if self.is_reply:
            raise ValueError("Cannot change subject for reply drafts")
        self.subject = subject
        self.updated_at = datetime.utcnow()
        if self.status == "saved":
            self.status = "editing"
    
    def mark_saving(self) -> None:
        """Mark draft as being saved to Gmail."""
        self.status = "saving"
        self.updated_at = datetime.utcnow()
    
    def mark_saved(self, gmail_draft_id: str) -> None:
        """Mark draft as saved to Gmail."""
        self.status = "saved"
        self.gmail_draft_id = gmail_draft_id
        self.updated_at = datetime.utcnow()
    
    def is_editable(self) -> bool:
        """Check if draft can be edited."""
        return self.status in ["editing", "ready"]
    
    def is_complete(self) -> bool:
        """Check if draft has all required fields for sending."""
        if self.is_reply:
            return bool(self.content.strip() and self.reply_to_message_id)
        return bool(self.recipient and self.subject and self.content.strip())