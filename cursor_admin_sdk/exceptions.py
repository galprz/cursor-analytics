"""Custom exceptions for the Cursor Admin SDK."""

from typing import Optional
import aiohttp


class CursorSDKError(Exception):
    """Base exception for all Cursor SDK errors."""
    
    def __init__(self, message: str, response: Optional[aiohttp.ClientResponse] = None):
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code = response.status if response else None


class CursorAPIError(CursorSDKError):
    """Raised when the Cursor API returns an error response."""
    
    def __init__(self, message: str, status_code: int, response: Optional[aiohttp.ClientResponse] = None):
        super().__init__(message, response)
        self.status_code = status_code


class CursorAuthError(CursorAPIError):
    """Raised when authentication fails (401, 403)."""
    pass


class CursorRateLimitError(CursorAPIError):
    """Raised when rate limiting is encountered (429)."""
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[int] = None,
        response: Optional[aiohttp.ClientResponse] = None
    ):
        super().__init__(message, 429, response)
        self.retry_after = retry_after


class CursorServerError(CursorAPIError):
    """Raised when the server returns a 5xx error."""
    pass


class CursorNetworkError(CursorSDKError):
    """Raised when network connectivity issues occur."""
    pass


class CursorTimeoutError(CursorSDKError):
    """Raised when requests timeout."""
    pass


class CursorValidationError(CursorSDKError):
    """Raised when input validation fails."""
    pass


class CursorRetryExhaustedError(CursorSDKError):
    """Raised when all retry attempts have been exhausted."""
    
    def __init__(self, message: str, attempts: int, last_exception: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception