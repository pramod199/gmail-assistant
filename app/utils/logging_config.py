"""
Simple logging configuration for Gmail Assistant using colorlog
"""
import logging
import sys
import colorlog

from app.config import settings


def setup_logging():
    """
    Setup logging with colorlog library
    """
    # Set log level based on environment
    log_level = logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO
    
    # Use colorlog for colored console output
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)s%(reset)s - %(asctime)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    ))
    
    # File handler (no colors)
    file_handler = logging.FileHandler("server.log")
    file_handler.setFormatter(logging.Formatter(
        "%(levelname)s - %(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Filter third-party library noise
    third_party_loggers = [
        "uvicorn.access", "google", "firebase_admin", "urllib3",
        "urllib3.util.retry", "urllib3.connectionpool", "cachecontrol",
        "cachecontrol.controller", "google.auth", "requests", "httpx",
        "websockets.client", "websockets.server", "websockets.protocol"
    ]

    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {settings.ENVIRONMENT} environment with colorlog")