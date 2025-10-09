"""
User Management Endpoints

Provides endpoints for viewing user profile and statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from ...api.middleware.auth import get_current_user
from ...core.auth.user_store import user_store
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class UserProfile(BaseModel):
    """User profile response model"""
    user_id: str
    email: str
    created_at: datetime
    updated_at: datetime
    last_login: datetime
    login_count: int


class UserStats(BaseModel):
    """User statistics response model"""
    total_users: int


class DeleteUserResponse(BaseModel):
    """Delete user response model"""
    message: str
    user_id: str
    note: str


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile information.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Returns:**
    - User profile with login statistics
    """
    user_id = current_user["user_id"]

    try:
        user = await user_store.get_user(user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found in local database"
            )

        return UserProfile(
            user_id=user.user_id,
            email=user.email,
            created_at=datetime.fromtimestamp(user.created_at),
            updated_at=datetime.fromtimestamp(user.updated_at),
            last_login=datetime.fromtimestamp(user.last_login),
            login_count=user.login_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile"
        )


@router.delete("/me", response_model=DeleteUserResponse)
async def delete_current_user(current_user: dict = Depends(get_current_user)):
    """
    Delete current user's local record.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Note:**
    - This only deletes the local user record
    - Firebase user account remains active
    - Gmail credentials and sessions are NOT automatically deleted
    """
    user_id = current_user["user_id"]

    try:
        deleted = await user_store.delete_user(user_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="User not found in local database"
            )

        return DeleteUserResponse(
            message="Local user record deleted successfully",
            user_id=user_id,
            note="Firebase account remains active. User will be recreated on next login."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user record"
        )


@router.get("/stats", response_model=UserStats)
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """
    Get system-wide user statistics.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Returns:**
    - Total number of users in the system
    """
    try:
        total_users = await user_store.get_user_count()

        return UserStats(total_users=total_users)

    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user statistics"
        )
