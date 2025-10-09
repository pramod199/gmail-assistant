"""
Async wrapper for Firebase operations to prevent blocking the event loop.
"""

import asyncio
import concurrent.futures
from typing import Optional, Dict
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging
from functools import partial

logger = logging.getLogger(__name__)

# Thread pool for running synchronous Firebase operations
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="firebase")


async def verify_id_token_async(token: str) -> Dict:
    """
    Async wrapper for firebase_auth.verify_id_token.
    Runs the synchronous operation in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    try:
        # Run the synchronous operation in the thread pool
        decoded_token = await loop.run_in_executor(
            _executor,
            firebase_auth.verify_id_token,
            token
        )
        return decoded_token
    except Exception as e:
        # Re-raise the exception to be handled by the caller
        raise


async def get_user_async(uid: str) -> Optional[firebase_auth.UserRecord]:
    """
    Async wrapper for firebase_auth.get_user.
    Runs the synchronous operation in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    try:
        user_record = await loop.run_in_executor(
            _executor,
            firebase_auth.get_user,
            uid
        )
        return user_record
    except firebase_auth.UserNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error fetching user {uid} from Firebase: {e}")
        raise


async def create_custom_token_async(uid: str, developer_claims: Optional[Dict] = None) -> bytes:
    """
    Async wrapper for firebase_auth.create_custom_token.
    Runs the synchronous operation in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    try:
        if developer_claims:
            custom_token = await loop.run_in_executor(
                _executor,
                partial(firebase_auth.create_custom_token, uid, developer_claims=developer_claims)
            )
        else:
            custom_token = await loop.run_in_executor(
                _executor,
                firebase_auth.create_custom_token,
                uid
            )
        return custom_token
    except Exception as e:
        logger.error(f"Error creating custom token for user {uid}: {e}")
        raise


def cleanup_executor():
    """
    Cleanup function to properly shutdown the thread pool executor.
    Should be called on application shutdown.
    """
    _executor.shutdown(wait=True)
    logger.info("Firebase async executor shutdown complete")
