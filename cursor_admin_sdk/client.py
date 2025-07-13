"""Cursor Admin API Client implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp
from yarl import URL

from cursor_admin_sdk.models import (
    TeamMember, 
    DailyUsageData, 
    DailyUsageResponse,
    UsageMetrics,
    SpendData,
    FilteredUsageEvents,
    PaginationInfo,
    DashboardAnalyticsResponse,
    TeamSpendResponse
)
from cursor_admin_sdk.exceptions import (
    CursorAPIError,
    CursorAuthError,
    CursorNetworkError,
    CursorRateLimitError,
    CursorServerError,
    CursorTimeoutError,
    CursorValidationError,
)
from cursor_admin_sdk.retry import RetryConfig, RetryHandler

logger = logging.getLogger(__name__)


class CursorAdminClient:
    """Async client for interacting with the Cursor Admin API.
    
    Provides methods to fetch team member data, usage metrics, and spending information.
    Uses API key authentication and supports async context manager pattern.
    """
    
    BASE_URL = "https://api.cursor.com"
    
    def __init__(
        self, 
        api_key: str, 
        base_url: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: int = 30
    ) -> None:
        """Initialize the Cursor Admin API client.
        
        Args:
            api_key: Your Cursor Admin API key
            base_url: Optional base URL override (defaults to https://api.cursor.com)
            retry_config: Configuration for retry behavior
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key
        self.base_url = URL(base_url or self.BASE_URL)
        self.retry_handler = RetryHandler(retry_config or RetryConfig())
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self) -> "CursorAdminClient":
        """Enter async context manager, creating the aiohttp session."""
        # Configure connector for production use
        connector = aiohttp.TCPConnector(
            limit=100,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        self._session = aiohttp.ClientSession(
            base_url=str(self.base_url),
            auth=aiohttp.BasicAuth(self.api_key, ""),
            connector=connector,
            timeout=self.timeout,
            headers={
                "User-Agent": "cursor-admin-sdk/0.1.0",
                "Accept": "application/json"
            },
            raise_for_status=False  # Handle status codes manually
        )
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager, closing the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request with comprehensive error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for the request
            
        Returns:
            Parsed JSON response data
            
        Raises:
            CursorValidationError: If session is not initialized
            Various CursorSDK exceptions based on error type
        """
        if not self._session:
            raise CursorValidationError("Client must be used as an async context manager")
        
        try:
            async with self._session.request(method, endpoint, **kwargs) as response:
                # Handle different response scenarios
                if response.status == 401:
                    raise CursorAuthError("Authentication failed - check your API key", response.status, response)
                
                elif response.status == 403:
                    raise CursorAuthError("Access forbidden - insufficient permissions", response.status, response)
                
                elif response.status == 429:
                    retry_after = self._extract_retry_after(response)
                    error_text = await response.text()
                    raise CursorRateLimitError(
                        f"Rate limit exceeded: {error_text}",
                        retry_after=retry_after,
                        response=response
                    )
                
                elif 400 <= response.status < 500:
                    error_text = await response.text()
                    raise CursorAPIError(f"Client error {response.status}: {error_text}", response.status, response)
                
                elif response.status >= 500:
                    error_text = await response.text()
                    raise CursorServerError(f"Server error {response.status}: {error_text}", response.status, response)
                
                # Success case
                return await response.json()
                
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error for {method} {endpoint}")
            raise CursorTimeoutError(f"Request timed out after {self.timeout.total}s") from e
            
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {e}")
            raise CursorNetworkError(f"Connection failed: {e}") from e
            
        except aiohttp.ClientError as e:
            logger.error(f"Client error: {e}")
            raise CursorNetworkError(f"HTTP client error: {e}") from e
    
    def _extract_retry_after(self, response: aiohttp.ClientResponse) -> Optional[int]:
        """Extract Retry-After header value in seconds."""
        retry_after = response.headers.get('Retry-After')
        if not retry_after:
            return None
        
        try:
            return int(retry_after)
        except ValueError:
            logger.warning(f"Invalid Retry-After header: {retry_after}")
            return None
    
    async def get_team_members(self) -> List[TeamMember]:
        """Fetch all team members.
        
        Returns:
            List of TeamMember models containing name, email, and role
            
        Raises:
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        async def _fetch_members():
            data = await self._make_request("GET", "/teams/members")
            return [TeamMember.model_validate(member) for member in data]
        
        return await self.retry_handler.execute_with_retry(_fetch_members)
    
    async def get_daily_usage_data(
        self, start_date: datetime, end_date: datetime
    ) -> DailyUsageData:
        """Fetch daily usage data for a specific date range.
        
        Args:
            start_date: Start date for the usage data query
            end_date: End date for the usage data query
            
        Returns:
            DailyUsageData model containing usage metrics for each day
            
        Raises:
            CursorValidationError: If date range is invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Validate date range (90-day limit)
        date_diff = end_date - start_date
        if date_diff.days > 90:
            raise CursorValidationError(
                f"Date range cannot exceed 90 days. Got {date_diff.days} days."
            )
        
        if date_diff.days < 0:
            raise CursorValidationError("End date must be after start date")
        
        # Convert dates to epoch milliseconds
        start_epoch_ms = int(start_date.timestamp() * 1000)
        end_epoch_ms = int(end_date.timestamp() * 1000)
        
        async def _fetch_usage_data():
            payload = {
                "startDate": start_epoch_ms,
                "endDate": end_epoch_ms
            }
            
            data = await self._make_request("POST", "/teams/daily-usage-data", json=payload)
            
            # Parse the response into models
            usage_metrics = [UsageMetrics.model_validate(metric) for metric in data]
            
            return DailyUsageData(
                usage_data=usage_metrics,
                start_date=start_date,
                end_date=end_date
            )
        
        return await self.retry_handler.execute_with_retry(_fetch_usage_data)
    
    async def get_detailed_daily_usage(
        self, start_date: datetime, end_date: datetime
    ) -> DailyUsageResponse:
        """Fetch detailed daily usage data with comprehensive metrics.
        
        Args:
            start_date: Start date for the usage data query
            end_date: End date for the usage data query
            
        Returns:
            DailyUsageResponse containing detailed daily metrics
            
        Raises:
            CursorValidationError: If date range is invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Validate date range (90-day limit)
        date_diff = end_date - start_date
        if date_diff.days > 90:
            raise CursorValidationError(
                f"Date range cannot exceed 90 days. Got {date_diff.days} days."
            )
        
        if date_diff.days < 0:
            raise CursorValidationError("End date must be after start date")
        
        # Convert dates to epoch milliseconds
        start_epoch_ms = int(start_date.timestamp() * 1000)
        end_epoch_ms = int(end_date.timestamp() * 1000)
        
        async def _fetch_detailed_usage_data():
            payload = {
                "startDate": start_epoch_ms,
                "endDate": end_epoch_ms
            }
            
            data = await self._make_request("POST", "/teams/daily-usage-data", json=payload)
            
            # Debug: Check if the response contains per-user data
            if data.get("data") and len(data["data"]) > 0:
                logger.debug(f"Daily usage response contains {len(data['data'])} entries with per-user data")
            
            return DailyUsageResponse.model_validate(data)
        
        return await self.retry_handler.execute_with_retry(_fetch_detailed_usage_data)
    
    async def get_spend_data(
        self,
        page: int = 1,
        page_size: Optional[int] = None,
        search_term: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_direction: str = "desc"
    ) -> SpendData:
        """Fetch team spending data with pagination and filtering.
        
        Args:
            page: Page number (1-indexed, default: 1)
            page_size: Results per page (optional)
            search_term: Search users by name/email (optional)
            sort_by: Sort by 'amount', 'date', or 'user' (optional)
            sort_direction: Sort direction 'asc' or 'desc' (default: 'desc')
            
        Returns:
            SpendData model containing spending information with pagination
            
        Raises:
            CursorValidationError: If parameters are invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Validate parameters
        if page < 1:
            raise CursorValidationError("Page must be >= 1")
        
        if sort_direction not in ("asc", "desc"):
            raise CursorValidationError("sort_direction must be 'asc' or 'desc'")
        
        if sort_by is not None and sort_by not in ("amount", "date", "user"):
            raise CursorValidationError("sort_by must be 'amount', 'date', or 'user'")
        
        async def _fetch_spend_data():
            # Build payload
            payload = {
                "page": page,
                "sortDirection": sort_direction
            }
            
            if page_size is not None:
                payload["pageSize"] = page_size
            if search_term is not None:
                payload["searchTerm"] = search_term
            if sort_by is not None:
                payload["sortBy"] = sort_by
            
            data = await self._make_request("POST", "/teams/spend", json=payload)
            return SpendData.model_validate(data)
        
        return await self.retry_handler.execute_with_retry(_fetch_spend_data)
    
    async def get_usage_events(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        email: Optional[str] = None
    ) -> FilteredUsageEvents:
        """Fetch filtered usage events with pagination.
        
        Args:
            page: Page number (1-indexed, default: 1)
            page_size: Results per page (default: 10)
            start_date: Filter events from this date (optional)
            end_date: Filter events until this date (optional)
            user_id: Filter by specific user ID (optional)
            email: Filter by user email (optional)
            
        Returns:
            FilteredUsageEvents model containing events with pagination
            
        Raises:
            CursorValidationError: If parameters are invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Validate parameters
        if page < 1:
            raise CursorValidationError("Page must be >= 1")
        
        if page_size < 1:
            raise CursorValidationError("page_size must be >= 1")
        
        if start_date and end_date and start_date > end_date:
            raise CursorValidationError("start_date must be before end_date")
        
        async def _fetch_usage_events():
            # Build payload
            payload = {
                "page": page,
                "pageSize": page_size
            }
            
            # Add optional filters
            if start_date is not None:
                payload["startDate"] = int(start_date.timestamp() * 1000)
            if end_date is not None:
                payload["endDate"] = int(end_date.timestamp() * 1000)
            if user_id is not None:
                payload["userId"] = user_id
            if email is not None:
                payload["email"] = email
            
            data = await self._make_request("POST", "/teams/filtered-usage-events", json=payload)
            
            # Debug: Log the first event to see actual structure
            if data.get("usageEvents") and len(data["usageEvents"]) > 0:
                logger.debug(f"Sample raw event from API: {data['usageEvents'][0]}")
            
            return FilteredUsageEvents.model_validate(data)
        
        return await self.retry_handler.execute_with_retry(_fetch_usage_events)
    
    async def get_dashboard_analytics(
        self,
        cookie_string: str,
        team_id: int,
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> DashboardAnalyticsResponse:
        """Fetch user analytics from the dashboard API endpoint.
        
        This uses a different authentication mechanism (cookies) and returns
        different data structure than the Admin API endpoints.
        
        Args:
            cookie_string: Raw cookie string from authenticated browser session
            team_id: Team ID from Cursor dashboard
            user_id: User ID from Cursor dashboard
            start_date: Start date for analytics query
            end_date: End date for analytics query
            
        Returns:
            DashboardAnalyticsResponse containing daily metrics and team statistics
            
        Raises:
            CursorAuthError: If cookies are invalid or expired
            CursorValidationError: If parameters are invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Save current session state
        original_headers = dict(self._session.headers) if self._session else {}
        
        try:
            # Parse cookies from string
            cookies = self._parse_cookie_string(cookie_string)
            
            # Convert dates to epoch milliseconds strings
            start_epoch_ms = str(int(start_date.timestamp() * 1000))
            end_epoch_ms = str(int(end_date.timestamp() * 1000))
            
            # Prepare dashboard-specific headers
            dashboard_headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "origin": "https://cursor.com",
                "referer": "https://cursor.com/dashboard",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "priority": "u=1, i"
            }
            
            # Update session headers temporarily
            if self._session:
                self._session.headers.update(dashboard_headers)
            
            async def _fetch_dashboard_analytics():
                payload = {
                    "teamId": team_id,
                    "userId": user_id,
                    "startDate": start_epoch_ms,
                    "endDate": end_epoch_ms
                }
                
                # Make request with cookies
                data = await self._make_request(
                    "POST", 
                    "https://cursor.com/api/dashboard/get-user-analytics",
                    json=payload,
                    cookies=cookies
                )
                
                return DashboardAnalyticsResponse.model_validate(data)
            
            return await self.retry_handler.execute_with_retry(_fetch_dashboard_analytics)
            
        finally:
            # Restore original headers
            if self._session and original_headers:
                self._session.headers.clear()
                self._session.headers.update(original_headers)
    
    def _parse_cookie_string(self, cookie_string: str) -> Dict[str, str]:
        """Parse a raw cookie string into a dictionary.
        
        Args:
            cookie_string: Raw cookie string in format "name1=value1; name2=value2"
            
        Returns:
            Dictionary of cookie names to values
        """
        from urllib.parse import unquote_plus
        
        cookies = {}
        for chunk in cookie_string.split(";"):
            chunk = chunk.strip()
            if not chunk or "=" not in chunk:
                continue
            name, value = chunk.split("=", 1)
            cookies[name.strip()] = unquote_plus(value.strip())
        return cookies
    
    async def get_team_spend(
        self,
        cookie_string: str,
        team_id: int
    ) -> TeamSpendResponse:
        """Fetch team spending information from the dashboard API endpoint.
        
        This uses the dashboard API with cookie authentication to get detailed
        spending information for all team members.
        
        Args:
            cookie_string: Raw cookie string from authenticated browser session
            team_id: Team ID from Cursor dashboard
            
        Returns:
            TeamSpendResponse containing spending information for all team members
            
        Raises:
            CursorAuthError: If cookies are invalid or expired
            CursorValidationError: If parameters are invalid
            CursorSDKError: Various SDK-specific exceptions based on error type
        """
        # Save current session state
        original_headers = dict(self._session.headers) if self._session else {}
        
        try:
            # Parse cookies from string
            cookies = self._parse_cookie_string(cookie_string)
            
            # Prepare dashboard-specific headers
            dashboard_headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "origin": "https://cursor.com",
                "referer": "https://cursor.com/dashboard",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "priority": "u=1, i"
            }
            
            # Update session headers temporarily
            if self._session:
                self._session.headers.update(dashboard_headers)
            
            async def _fetch_team_spend():
                payload = {
                    "teamId": team_id
                }
                
                # Make request with cookies
                data = await self._make_request(
                    "POST", 
                    "https://cursor.com/api/dashboard/get-team-spend",
                    json=payload,
                    cookies=cookies
                )
                
                return TeamSpendResponse.model_validate(data)
            
            return await self.retry_handler.execute_with_retry(_fetch_team_spend)
            
        finally:
            # Restore original headers
            if self._session and original_headers:
                self._session.headers.clear()
                self._session.headers.update(original_headers)