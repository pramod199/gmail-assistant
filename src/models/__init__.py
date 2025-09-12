"""
Gmail Assistant Data Models

Pydantic models for type-safe data handling with proper separation of concerns:
- User: Profile and metadata
- Credentials: OAuth tokens and auth data
- Session: Navigation state and message context
- Draft: Email draft storage
"""

from .user import User
from .credentials import GmailCredentials
from .session import SessionData
from .draft import DraftData

__all__ = [
    "User",
    "GmailCredentials", 
    "SessionData",
    "DraftData"
]