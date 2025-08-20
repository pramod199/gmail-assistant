import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException properly to preserve status codes"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


async def firebase_auth_exception_handler(request: Request, exc: InvalidIdTokenError):
    """Handle Firebase authentication errors"""
    logger.warning(f"Firebase auth error: {exc}")
    return JSONResponse(
        status_code=401,
        content={"error": "Invalid or expired Firebase token", "status_code": 401}
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )