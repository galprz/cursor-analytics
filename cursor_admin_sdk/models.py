"""Pydantic models for Cursor Admin API responses."""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class TeamMember(BaseModel):
    """Represents a team member in the Cursor organization."""
    
    name: str
    email: str
    role: str
    
    model_config = ConfigDict(extra="forbid")


class UsageMetrics(BaseModel):
    """Daily usage metrics for a user."""
    
    user_email: str
    date: datetime
    lines_added: int = Field(default=0, ge=0)
    lines_deleted: int = Field(default=0, ge=0)
    ai_suggestion_accepts: int = Field(default=0, ge=0)
    ai_suggestion_rejects: int = Field(default=0, ge=0)
    tab_completions: int = Field(default=0, ge=0)
    requests_by_type: Dict[str, int] = Field(default_factory=dict)
    model_usage: Dict[str, int] = Field(default_factory=dict)
    client_version: Optional[str] = None
    
    model_config = ConfigDict(extra="ignore")


class DailyUsageMetrics(BaseModel):
    """Daily usage metrics with detailed statistics."""
    
    date: int  # Unix timestamp
    is_active: bool = Field(alias="isActive")
    total_lines_added: int = Field(ge=0, alias="totalLinesAdded")
    total_lines_deleted: int = Field(ge=0, alias="totalLinesDeleted")
    accepted_lines_added: int = Field(ge=0, alias="acceptedLinesAdded")
    accepted_lines_deleted: int = Field(ge=0, alias="acceptedLinesDeleted")
    total_applies: int = Field(ge=0, alias="totalApplies")
    total_accepts: int = Field(ge=0, alias="totalAccepts")
    total_rejects: int = Field(ge=0, alias="totalRejects")
    total_tabs_shown: int = Field(ge=0, alias="totalTabsShown")
    total_tabs_accepted: int = Field(ge=0, alias="totalTabsAccepted")
    composer_requests: int = Field(ge=0, alias="composerRequests")
    chat_requests: int = Field(ge=0, alias="chatRequests")
    agent_requests: int = Field(ge=0, alias="agentRequests")
    cmdk_usages: int = Field(ge=0, alias="cmdkUsages")
    subscription_included_reqs: int = Field(ge=0, alias="subscriptionIncludedReqs")
    api_key_reqs: int = Field(ge=0, alias="apiKeyReqs")
    usage_based_reqs: int = Field(ge=0, alias="usageBasedReqs")
    bugbot_usages: int = Field(ge=0, alias="bugbotUsages")
    most_used_model: Optional[str] = Field(default="Unknown", alias="mostUsedModel")
    apply_most_used_extension: Optional[str] = Field(default=None, alias="applyMostUsedExtension")
    tab_most_used_extension: Optional[str] = Field(default=None, alias="tabMostUsedExtension")
    client_version: Optional[str] = Field(default=None, alias="clientVersion")
    email: Optional[str] = None
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class DailyUsagePeriod(BaseModel):
    """Period information for daily usage data."""
    
    start_date: int = Field(alias="startDate")
    end_date: int = Field(alias="endDate")
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DailyUsageResponse(BaseModel):
    """Response containing daily usage data with period information."""
    
    data: List[DailyUsageMetrics]
    period: DailyUsagePeriod
    
    model_config = ConfigDict(extra="forbid")


class DailyUsageData(BaseModel):
    """Container for daily usage data response (legacy)."""
    
    usage_data: List[UsageMetrics]
    start_date: datetime
    end_date: datetime
    
    model_config = ConfigDict(extra="forbid")


class TeamMemberSpend(BaseModel):
    """Individual team member spending information."""
    
    email: str
    name: str
    spend_amount: float = Field(ge=0, alias="spendAmount")
    request_count: int = Field(ge=0, alias="requestCount")
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PaginationInfo(BaseModel):
    """Pagination metadata used across endpoints."""
    
    num_pages: int = Field(ge=1, alias="numPages")
    current_page: int = Field(ge=1, alias="currentPage") 
    page_size: int = Field(ge=1, alias="pageSize")
    has_next_page: bool = Field(default=False, alias="hasNextPage")
    has_previous_page: bool = Field(default=False, alias="hasPreviousPage")
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SpendData(BaseModel):
    """Spending data response with pagination info."""
    
    team_members: List[TeamMemberSpend] = Field(alias="teamMembers")
    total_members: int = Field(ge=0, alias="totalMembers")
    pagination: PaginationInfo
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UsageEvent(BaseModel):
    """Individual usage event with detailed information."""
    
    timestamp: Union[datetime, str, int]
    cursor_model: Optional[str] = Field(default=None, alias="model")
    kind: Optional[str] = None  # e.g., "Included in Business"
    max_mode: Optional[bool] = Field(default=False, alias="maxMode")
    requests_costs: Optional[float] = Field(default=0.0, ge=0, alias="requestsCosts")
    is_token_based_call: Optional[bool] = Field(default=False, alias="isTokenBasedCall")
    user_email: Optional[str] = Field(default=None, alias="userEmail")
    
    # Fields that might exist in some responses
    prompt_tokens: Optional[int] = Field(default=0, ge=0, alias="promptTokens")
    completion_tokens: Optional[int] = Field(default=0, ge=0, alias="completionTokens") 
    total_tokens: Optional[int] = Field(default=0, ge=0, alias="totalTokens")
    query: Optional[str] = None
    provider: Optional[str] = None
    user_id: Optional[str] = Field(default=None, alias="userID")
    event_type: Optional[str] = Field(default="query")
    
    # Computed property for backward compatibility
    @property
    def cost(self) -> float:
        """Get cost from requests_costs field."""
        return self.requests_costs or 0.0
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        """Parse timestamp from various formats."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try to parse as epoch milliseconds string
            try:
                epoch_ms = int(v)
                return datetime.fromtimestamp(epoch_ms / 1000)
            except ValueError:
                # Try ISO format
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
        if isinstance(v, (int, float)):
            # Assume epoch milliseconds if the number is large
            if v > 1e10:
                return datetime.fromtimestamp(v / 1000)
            else:
                return datetime.fromtimestamp(v)
        raise ValueError(f"Cannot parse timestamp: {v}")


class FilteredUsageEvents(BaseModel):
    """Filtered usage events response with pagination."""
    
    events: List[UsageEvent] = Field(alias="usageEvents")
    total_usage_events_count: int = Field(ge=0, alias="totalUsageEventsCount")
    pagination: PaginationInfo
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# Dashboard API Models (different from Admin API)
class ModelUsage(BaseModel):
    """Model usage statistics in dashboard."""
    name: str
    count: int = Field(ge=0)
    
    model_config = ConfigDict(extra="forbid")


class ExtensionUsage(BaseModel):
    """Extension usage statistics in dashboard."""
    name: str
    count: int = Field(ge=0)
    
    model_config = ConfigDict(extra="forbid")


class DashboardDailyMetric(BaseModel):
    """Daily metrics from the dashboard API."""
    
    date: str  # Epoch milliseconds as string
    active_users: Optional[int] = Field(default=0, alias="activeUsers")
    lines_added: Optional[int] = Field(default=0, ge=0, alias="linesAdded")
    lines_deleted: Optional[int] = Field(default=0, ge=0, alias="linesDeleted") 
    accepted_lines_added: Optional[int] = Field(default=0, ge=0, alias="acceptedLinesAdded")
    accepted_lines_deleted: Optional[int] = Field(default=0, ge=0, alias="acceptedLinesDeleted")
    total_applies: Optional[int] = Field(default=0, ge=0, alias="totalApplies")
    total_accepts: Optional[int] = Field(default=0, ge=0, alias="totalAccepts")
    total_rejects: Optional[int] = Field(default=0, ge=0, alias="totalRejects")
    total_tabs_shown: Optional[int] = Field(default=0, ge=0, alias="totalTabsShown")
    total_tabs_accepted: Optional[int] = Field(default=0, ge=0, alias="totalTabsAccepted")
    agent_requests: Optional[int] = Field(default=0, ge=0, alias="agentRequests")
    composer_requests: Optional[int] = Field(default=0, ge=0, alias="composerRequests")
    subscription_included_reqs: Optional[int] = Field(default=0, ge=0, alias="subscriptionIncludedReqs")
    usage_based_reqs: Optional[int] = Field(default=0, ge=0, alias="usageBasedReqs")
    model_usage: Optional[List[ModelUsage]] = Field(default_factory=list, alias="modelUsage")
    extension_usage: Optional[List[ExtensionUsage]] = Field(default_factory=list, alias="extensionUsage")
    tab_extension_usage: Optional[List[ExtensionUsage]] = Field(default_factory=list, alias="tabExtensionUsage")
    client_version_usage: Optional[List[ExtensionUsage]] = Field(default_factory=list, alias="clientVersionUsage")
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    @property
    def timestamp(self) -> datetime:
        """Convert date string to datetime."""
        return datetime.fromtimestamp(int(self.date) / 1000)


class DashboardAnalyticsPeriod(BaseModel):
    """Period info for dashboard analytics."""
    
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DashboardAnalyticsResponse(BaseModel):
    """Response from dashboard get-user-analytics endpoint."""
    
    daily_metrics: List[DashboardDailyMetric] = Field(alias="dailyMetrics")
    period: DashboardAnalyticsPeriod
    apply_lines_rank: Optional[int] = Field(default=None, alias="applyLinesRank")
    tabs_accepted_rank: Optional[int] = Field(default=None, alias="tabsAcceptedRank") 
    total_team_members: Optional[int] = Field(default=None, alias="totalTeamMembers")
    total_apply_lines: Optional[int] = Field(default=None, alias="totalApplyLines")
    team_average_apply_lines: Optional[int] = Field(default=None, alias="teamAverageApplyLines")
    total_tabs_accepted: Optional[int] = Field(default=None, alias="totalTabsAccepted")
    team_average_tabs_accepted: Optional[int] = Field(default=None, alias="teamAverageTabsAccepted")
    total_members_in_team: Optional[int] = Field(default=None, alias="totalMembersInTeam")
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TeamMemberSpendInfo(BaseModel):
    """Individual team member spend information from the dashboard API."""
    
    user_id: int = Field(alias="userId")
    email: str
    role: str
    hard_limit_override_dollars: int = Field(alias="hardLimitOverrideDollars")
    spend_cents: Optional[int] = Field(default=None, alias="spendCents")
    fast_premium_requests: Optional[int] = Field(default=None, alias="fastPremiumRequests")
    name: Optional[str] = None
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TeamSpendResponse(BaseModel):
    """Response from dashboard get-team-spend endpoint."""
    
    team_member_spend: List[TeamMemberSpendInfo] = Field(alias="teamMemberSpend")
    subscription_cycle_start: str = Field(alias="subscriptionCycleStart")
    total_members: int = Field(alias="totalMembers")
    total_pages: int = Field(alias="totalPages")
    
    model_config = ConfigDict(extra="ignore", populate_by_name=True)