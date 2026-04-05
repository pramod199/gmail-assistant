from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """User profile response model"""
    user_id: str
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    login_count: int


class UserStats(BaseModel):
    """User statistics response model"""
    total_users: int


class DeleteUserResponse(BaseModel):
    """Delete user response model"""
    message: str
    user_id: str
    note: str
