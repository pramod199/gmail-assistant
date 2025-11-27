"""
Session Management REST API Endpoints

Provides REST endpoints for voice session lifecycle management separate from WebSocket connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from app.auth import get_current_user
from app.models.user import User
from app.schemas.session import CreateSessionRequest, SessionResponse, SessionListResponse
from app.services.voice_session_manager import voice_session_manager
from app.services.gmail_oauth_service import UserCredentialStore
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize credential store
credential_store = UserCredentialStore()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request_data: CreateSessionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new voice session.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Flow:**
    1. Validates Firebase token from Authorization header
    2. Checks if user has authorized Gmail access
    3. Creates voice session
    4. Returns session_id and Gmail auth status

    **Response Fields:**
    - `session_id`: Use this in WebSocket connection
    - `gmail_authorized`: true if Gmail is already authorized
    - `requires_gmail_auth`: true if user needs to authorize Gmail
    - `gmail_auth_url`: OAuth URL to authorize Gmail (if needed)

    **Next Steps:**
    - If `requires_gmail_auth` is true: User must open `gmail_auth_url` in browser
    - Once authorized: Connect to WebSocket with session_id
    """
    user_id = current_user.id

    try:
        # Check Gmail authorization status
        gmail_authorized = await credential_store.has_credentials(user_id)
        gmail_auth_url = None
        requires_gmail_auth = False

        if not gmail_authorized:
            # Import the auth URL generator
            from app.routers.auth import _generate_auth_url
            gmail_auth_url = _generate_auth_url(user_id)
            requires_gmail_auth = True
            logger.warning(f"User {user_id} attempting to create session without Gmail authorization")

        # Check concurrent session limit
        active_sessions = await voice_session_manager.count_user_active_sessions(user_id)
        if active_sessions >= settings.MAX_CONCURRENT_SESSIONS_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "too_many_sessions",
                    "message": f"Maximum concurrent sessions limit ({settings.MAX_CONCURRENT_SESSIONS_PER_USER}) reached. Please close an existing session first.",
                    "active_sessions": active_sessions,
                    "max_allowed": settings.MAX_CONCURRENT_SESSIONS_PER_USER
                }
            )

        # Create session (even if Gmail not authorized - session can be used after auth)
        session = await voice_session_manager.create_session(user_id=user_id)

        logger.info(f"Created voice session {session.id} for user {user_id} (Gmail authorized: {gmail_authorized})")

        return SessionResponse(
            session_id=session.id,
            user_id=session.user_id,
            active=session.active,
            created_at=session.data.created_at,
            updated_at=session.data.updated_at,
            gmail_authorized=gmail_authorized,
            gmail_auth_url=gmail_auth_url,
            requires_gmail_auth=requires_gmail_auth
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error creating session for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create voice session"
        )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get information about a specific voice session.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`
    """
    user_id = current_user.id

    session = await voice_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this session"
        )

    return SessionResponse(
        session_id=session.id,
        user_id=session.user_id,
        active=session.active,
        created_at=session.data.created_at,
        updated_at=session.data.updated_at
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user)
):
    """
    List all voice sessions for the current user.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`
    """
    user_id = current_user.id

    try:
        session_ids = await voice_session_manager.get_user_sessions(user_id)
        sessions = []
        active_count = 0

        for session_id in session_ids:
            session = await voice_session_manager.get_session(session_id)
            if session:
                sessions.append(SessionResponse(
                    session_id=session.id,
                    user_id=session.user_id,
                    active=session.active,
                    created_at=session.data.created_at,
                    updated_at=session.data.updated_at
                ))
                if session.active:
                    active_count += 1

        return SessionListResponse(
            sessions=sessions,
            total=len(sessions),
            active_count=active_count
        )

    except Exception as e:
        logger.error(f"Error listing sessions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions"
        )


@router.post("/{session_id}/voice/start", status_code=status.HTTP_200_OK)
async def start_voice_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Start Gemini Live voice session for audio processing.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Prerequisites:**
    1. Session must exist and be active
    2. User must have authorized Gmail access
    3. WebSocket connection must be established

    **Flow:**
    1. Call this endpoint AFTER connecting to WebSocket
    2. Server initializes Gemini Live session
    3. Server starts processing audio responses
    4. Begin sending audio bytes over WebSocket

    **Returns:**
    - 200: Voice session started successfully
    - 403: Not authorized to access this session
    - 404: Session not found
    - 428: Gmail authorization required
    """
    user_id = current_user.id

    session = await voice_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )

    if not session.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )

    # Verify Gmail credentials exist
    gmail_authorized = await credential_store.has_credentials(user_id)
    if not gmail_authorized:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={
                "error": "gmail_auth_required",
                "message": "Gmail authorization required before starting voice session",
                "auth_url": f"/api/auth/gmail/authorize"
            }
        )

    # Import stateless function to start voice session
    from app.routers.websocket import start_voice_session

    # Start voice session (initializes Gemini Live)
    try:
        await start_voice_session(user_id, session)
        logger.info(f"Started voice session for {session_id}, user {user_id}")
        return {"message": "Voice session started", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to start voice session for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start voice session: {str(e)}"
        )


@router.post("/{session_id}/voice/stop", status_code=status.HTTP_200_OK)
async def stop_voice_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Stop Gemini Live voice session.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`

    **Flow:**
    1. Stops audio processing
    2. Closes Gemini Live session
    3. WebSocket remains open for new start command

    **Returns:**
    - 200: Voice session stopped successfully
    - 403: Not authorized to access this session
    - 404: Session not found
    """
    user_id = current_user.id

    session = await voice_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )

    # Import stateless function to stop voice session
    from app.routers.websocket import stop_voice_session as stop_voice

    try:
        await stop_voice(user_id, session)
        logger.info(f"Stopped voice session for {session_id}, user {user_id}")
        return {"message": "Voice session stopped", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to stop voice session for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop voice session: {str(e)}"
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a voice session and clean up resources.

    **Authentication Required:**
    - Header: `Authorization: Bearer <firebase_id_token>`
    """
    user_id = current_user.id

    session = await voice_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this session"
        )

    # Mark session as inactive and clean up
    success = await voice_session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )

    logger.info(f"Deleted voice session {session_id} for user {user_id}")
    return None  # 204 No Content
