"""
Background tasks for periodic cleanup and maintenance.
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for the application."""

    def __init__(self):
        self.tasks = []
        self.running = False

    async def start(self):
        """Start all background tasks."""
        if self.running:
            logger.warning("Background tasks already running")
            return

        self.running = True
        logger.info("Starting background tasks...")

        # Start periodic cleanup tasks
        self.tasks.append(asyncio.create_task(self._expired_session_cleanup_task()))

        logger.info(f"Started {len(self.tasks)} background tasks")

    async def stop(self):
        """Stop all background tasks."""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping background tasks...")

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.tasks.clear()
        logger.info("Background tasks stopped")

    async def _expired_session_cleanup_task(self):
        """Periodically clean up expired voice sessions from memory cache."""
        cleanup_interval = 1800  # Run every 30 minutes

        while self.running:
            try:
                logger.debug("Running expired voice session cleanup...")

                # Import here to avoid circular dependency
                from app.services.voice_session_manager import voice_session_manager

                # Clean up sessions that have expired in Redis
                cleaned_count = await voice_session_manager.cleanup_expired_sessions()

                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired voice sessions from memory cache")

                # Sleep until next cleanup
                await asyncio.sleep(cleanup_interval)

            except asyncio.CancelledError:
                logger.info("Expired session cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in expired session cleanup task: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(60)  # Brief pause before retry


# Global background task manager
background_tasks = BackgroundTaskManager()
