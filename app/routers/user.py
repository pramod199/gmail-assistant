"""
User Management Endpoints

Provides endpoints for viewing user profile and statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Optional
from app.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserProfile, UserStats, DeleteUserResponse
from app.services.user_service import user_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user's profile information.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Returns:**
    - User profile with login statistics
    """
    try:
        user = await user_service.get_user_by_firebase_uid(current_user.id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found in local database"
            )

        return UserProfile(
            user_id=user.id,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.created_at,  # User model doesn't have updated_at
            last_login=user.last_login,
            login_count=user.login_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile for {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile"
        )


@router.delete("/me", response_model=DeleteUserResponse)
async def delete_current_user(current_user: User = Depends(get_current_user)):
    """
    Delete current user's local record.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Note:**
    - This only deletes the local user record
    - Firebase user account remains active
    - Gmail credentials and sessions are NOT automatically deleted
    """
    try:
        deleted = await user_service.delete_user(current_user.id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="User not found in local database"
            )

        return DeleteUserResponse(
            message="Local user record deleted successfully",
            user_id=current_user.id,
            note="Firebase account remains active. User will be recreated on next login."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user record"
        )


@router.get("/stats", response_model=UserStats)
async def get_user_stats(current_user: User = Depends(get_current_user)):
    """
    Get system-wide user statistics.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Returns:**
    - Total number of users in the system
    """
    try:
        # Note: user_service doesn't have get_user_count method yet
        # For now, return a placeholder
        total_users = 1

        return UserStats(total_users=total_users)

    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user statistics"
        )
