import asyncio
import logging
from typing import Callable, Any, Optional
from dataclasses import dataclass
import websockets

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 8.0
    backoff_factor: float = 2.0


class RetryHandler:
    """Generic retry handler with exponential backoff"""
    
    @staticmethod
    def calculate_delay(attempt_number: int, config: RetryConfig) -> float:
        """
        Calculate exponential backoff delay
        
        Args:
            attempt_number: Current attempt (1-based)
            config: Retry configuration
            
        Returns:
            Delay in seconds
        """
        if attempt_number <= 1:
            return 0.0
        
        # Exponential backoff: base_delay * (backoff_factor ^ (attempt - 2))
        delay = config.base_delay * (config.backoff_factor ** (attempt_number - 2))
        return min(delay, config.max_delay)
    
    @staticmethod
    def is_retryable_error(exception: Exception) -> bool:
        """
        Determine if an error is retryable
        
        Args:
            exception: Exception to check
            
        Returns:
            True if error should be retried
        """
        # Network and timeout errors are retryable
        if isinstance(exception, (
            websockets.exceptions.ConnectionClosedError,
            websockets.exceptions.ConnectionClosedOK,
            asyncio.TimeoutError,
            ConnectionError,
            OSError
        )):
            return True
        
        # Check for specific error messages
        error_msg = str(exception).lower()
        retryable_messages = [
            "deadline expired",
            "timeout",
            "connection reset",
            "connection closed",
            "network unreachable",
            "temporary failure"
        ]
        
        return any(msg in error_msg for msg in retryable_messages)
    
    @staticmethod
    async def execute_with_retry(
        async_func: Callable,
        config: RetryConfig = None,
        context_name: str = "operation"
    ) -> Any:
        """
        Execute async function with retry logic
        
        Args:
            async_func: Async function to execute
            config: Retry configuration (uses default if None)
            context_name: Name for logging context
            
        Returns:
            Result from successful function execution
            
        Raises:
            Last exception if all retries failed
        """
        if config is None:
            config = RetryConfig()
        
        last_exception = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                logger.debug(f"{context_name}: Attempt {attempt}/{config.max_attempts}")
                result = await async_func()
                
                if attempt > 1:
                    logger.info(f"{context_name}: Succeeded on attempt {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt == config.max_attempts:
                    logger.error(f"{context_name}: All {config.max_attempts} attempts failed. Last error: {e}")
                    break
                
                if not RetryHandler.is_retryable_error(e):
                    logger.error(f"{context_name}: Non-retryable error on attempt {attempt}: {e}")
                    break
                
                delay = RetryHandler.calculate_delay(attempt + 1, config)
                logger.warning(f"{context_name}: Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s")
                
                if delay > 0:
                    await asyncio.sleep(delay)
        
        # All attempts failed, raise the last exception
        raise last_exception
    
    @staticmethod
    def create_config(max_attempts: int = 3, base_delay: float = 1.0) -> RetryConfig:
        """
        Create retry configuration with common settings
        
        Args:
            max_attempts: Maximum number of attempts
            base_delay: Base delay for exponential backoff
            
        Returns:
            RetryConfig instance
        """
        return RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=8.0,
            backoff_factor=2.0
        )


class ConnectionRetryHandler:
    """Specialized retry handler for connection operations"""
    
    def __init__(self, max_attempts: int = 3):
        self.config = RetryHandler.create_config(max_attempts=max_attempts)
        self.active_retries = {}  # Track retries per user
    
    async def execute_connection_with_retry(
        self,
        user_id: str,
        async_func: Callable,
        context_name: str = "connection"
    ) -> Any:
        """
        Execute connection function with per-user retry tracking
        
        Args:
            user_id: User identifier for tracking retries
            async_func: Async function to execute
            context_name: Name for logging context
            
        Returns:
            Result from successful function execution
            
        Raises:
            Last exception if all retries failed
        """
        retry_key = f"{user_id}:{context_name}"
        
        try:
            # Track this retry attempt
            current_attempt = self.active_retries.get(retry_key, 0) + 1
            self.active_retries[retry_key] = current_attempt
            
            if current_attempt > self.config.max_attempts:
                logger.error(f"Max retry attempts ({self.config.max_attempts}) exceeded for user {user_id} {context_name}")
                raise RuntimeError(f"Maximum retry attempts exceeded for {context_name}")
            
            # Execute with retry logic
            result = await RetryHandler.execute_with_retry(
                async_func,
                self.config,
                f"{context_name} (user: {user_id})"
            )
            
            # Success - clear retry counter
            self.active_retries.pop(retry_key, None)
            return result
            
        except Exception as e:
            # Keep retry counter for next attempt
            logger.error(f"Connection retry failed for user {user_id} {context_name}: {e}")
            raise
    
    def reset_retry_count(self, user_id: str, context_name: str = "connection"):
        """Reset retry count for user and context"""
        retry_key = f"{user_id}:{context_name}"
        self.active_retries.pop(retry_key, None)
        logger.debug(f"Reset retry count for {retry_key}")
    
    def get_retry_count(self, user_id: str, context_name: str = "connection") -> int:
        """Get current retry count for user and context"""
        retry_key = f"{user_id}:{context_name}"
        return self.active_retries.get(retry_key, 0)
    
    def cleanup_user_retries(self, user_id: str):
        """Clean up all retry counters for a user"""
        keys_to_remove = [key for key in self.active_retries.keys() if key.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self.active_retries[key]
        logger.debug(f"Cleaned up retry counters for user {user_id}")