"""
WebSocket helper utilities for safe connection management
"""

import logging
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


async def safe_websocket_close(websocket: WebSocket, code: int = 1000, reason: str = ""):
    """
    Safely close a WebSocket connection.

    Handles various WebSocket states and prevents errors during close operations.

    Args:
        websocket: The WebSocket connection to close
        code: Close code (default 1000 = normal closure)
        reason: Optional close reason string
    """
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code, reason=reason)
            logger.debug(f"WebSocket closed with code {code}, reason: '{reason}'")
        elif websocket.application_state == WebSocketState.CONNECTING and websocket.client_state == WebSocketState.CONNECTING:
            logger.debug(f"WebSocket in connecting state, cannot send close frame. Client will timeout.")
        else:
            logger.debug(
                f"WebSocket already in state: client={websocket.client_state}, app={websocket.application_state}. Not sending close frame.")
    except RuntimeError as e:
        logger.debug(f"RuntimeError closing WebSocket (often harmless during shutdown): {e}")
    except Exception as e:
        logger.debug(f"Error closing WebSocket (this is usually harmless): {e}")


def is_websocket_connected(websocket: WebSocket) -> bool:
    """
    Check if WebSocket is in connected state.

    Args:
        websocket: The WebSocket connection to check

    Returns:
        True if connected, False otherwise
    """
    return websocket.client_state == WebSocketState.CONNECTED


async def send_json_safe(websocket: WebSocket, data: dict) -> bool:
    """
    Safely send JSON data over WebSocket.

    Args:
        websocket: The WebSocket connection
        data: Dictionary to send as JSON

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        if is_websocket_connected(websocket):
            await websocket.send_json(data)
            return True
        else:
            logger.warning("Attempted to send JSON on disconnected WebSocket")
            return False
    except Exception as e:
        logger.error(f"Error sending JSON over WebSocket: {e}")
        return False


async def send_text_safe(websocket: WebSocket, text: str) -> bool:
    """
    Safely send text data over WebSocket.

    Args:
        websocket: The WebSocket connection
        text: Text to send

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(text)
            return True
        else:
            logger.warning("Attempted to send text on disconnected WebSocket")
            return False
    except Exception as e:
        logger.error(f"Error sending text over WebSocket: {e}")
        return False


async def send_bytes_safe(websocket: WebSocket, data: bytes) -> bool:
    """
    Safely send binary data over WebSocket.

    Args:
        websocket: The WebSocket connection
        data: Binary data to send

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        if is_websocket_connected(websocket):
            await websocket.send_bytes(data)
            return True
        else:
            logger.warning("Attempted to send bytes on disconnected WebSocket")
            return False
    except Exception as e:
        logger.error(f"Error sending bytes over WebSocket: {e}")
        return False
