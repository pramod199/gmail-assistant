"""
User Model for Gmail Assistant

Stores basic user profile data.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """User profile model."""
    
    # Primary identifiers  
    firebase_uid: str = Field(..., description="Firebase user ID")
    email: Optional[str] = Field(None, description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        # JSON encoders for serialization
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }