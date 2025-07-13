"""Retry logic with exponential backoff for the Cursor Admin SDK."""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, Optional, Set, Type, Union
import aiohttp

from cursor_admin_sdk.exceptions import (
    CursorNetworkError,
    CursorRateLimitError,
    CursorServerError,
    CursorTimeoutError,
    CursorRetryExhaustedError,
)

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Set[Type[Exception]]] = None,
        retryable_status_codes: Optional[Set[int]] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_factor = exponential_factor
        self.jitter = jitter
        
        self.retryable_exceptions = retryable_exceptions or {
            CursorNetworkError,
            CursorServerError,
            CursorTimeoutError,
            aiohttp.ClientConnectorError,
            aiohttp.ClientTimeout,
            asyncio.TimeoutError,
        }
        
        self.retryable_status_codes = retryable_status_codes or {
            500, 502, 503, 504,  # Server errors
            429,  # Rate limiting (handled specially)
        }


class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def _calculate_delay(self, attempt: int, rate_limit_delay: Optional[float] = None) -> float:
        """Calculate delay for next retry attempt."""
        if rate_limit_delay is not None:
            # For rate limiting, respect the Retry-After header
            return rate_limit_delay
        
        # Exponential backoff: base_delay * (exponential_factor ^ attempt)
        delay = self.config.base_delay * (self.config.exponential_factor ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def _is_retryable_exception(self, exception: Exception) -> bool:
        """Check if an exception should trigger a retry."""
        return any(isinstance(exception, exc_type) for exc_type in self.config.retryable_exceptions)
    
    def _is_retryable_status_code(self, status_code: int) -> bool:
        """Check if a status code should trigger a retry."""
        return status_code in self.config.retryable_status_codes
    
    def _extract_retry_after(self, response: Optional[aiohttp.ClientResponse]) -> Optional[float]:
        """Extract Retry-After header value in seconds."""
        if not response:
            return None
        
        retry_after = response.headers.get('Retry-After')
        if not retry_after:
            return None
        
        try:
            # Retry-After can be in seconds or HTTP-date format
            # For simplicity, we'll assume it's always in seconds
            return float(retry_after)
        except ValueError:
            logger.warning(f"Invalid Retry-After header: {retry_after}")
            return None
    
    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
                
            except CursorRateLimitError as e:
                last_exception = e
                
                if attempt == self.config.max_attempts - 1:
                    break
                
                # For rate limiting, use the retry_after value
                delay = self._calculate_delay(attempt, e.retry_after)
                
                logger.warning(
                    f"Rate limited, retrying in {delay:.2f}s "
                    f"(attempt {attempt + 1}/{self.config.max_attempts})"
                )
                
                await asyncio.sleep(delay)
                continue
                
            except Exception as e:
                last_exception = e
                
                if not self._is_retryable_exception(e):
                    # Not retryable, re-raise immediately
                    raise
                
                if attempt == self.config.max_attempts - 1:
                    # Last attempt, don't retry
                    break
                
                delay = self._calculate_delay(attempt)
                
                logger.warning(
                    f"Request failed ({type(e).__name__}: {e}), "
                    f"retrying in {delay:.2f}s "
                    f"(attempt {attempt + 1}/{self.config.max_attempts})"
                )
                
                await asyncio.sleep(delay)
                continue
        
        # All retries exhausted
        raise CursorRetryExhaustedError(
            f"All {self.config.max_attempts} retry attempts exhausted",
            attempts=self.config.max_attempts,
            last_exception=last_exception
        )


def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to async functions."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        retry_handler = RetryHandler(config)
        
        async def wrapper(*args, **kwargs):
            return await retry_handler.execute_with_retry(func, *args, **kwargs)
        
        return wrapper
    return decorator