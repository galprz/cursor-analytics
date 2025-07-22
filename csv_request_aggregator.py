#!/usr/bin/env python3
"""
CSV-based RequestAggregator - Drop-in replacement for API-based RequestAggregator
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pytz
import requests
import io
import json

class CSVRequestAggregator:
    """Drop-in replacement for RequestAggregator that reads from CSV instead of API calls."""
    
    def __init__(self, cookie_string: str, email_to_userid_mapping: Dict[str, Tuple[int, int]] = None, csv_file: str = None):
        """Initialize the aggregator with dynamic CSV data from Cursor API.
        
        Args:
            cookie_string: Cookie string for authentication
            email_to_userid_mapping: Optional dict mapping emails to (team_id, user_id) tuples
            csv_file: Legacy parameter for backward compatibility (ignored)
        """
        self.cookie_string = cookie_string
        self.api_key = "not_used_for_csv"   # Keep for interface compatibility
        self.email_to_userid_mapping = email_to_userid_mapping or {}
        self._team_members_cache = None
        self._team_spend_cache = None
        
        # Data will be loaded dynamically via API calls
        self.df = None
        self._data_cache = {}  # Cache data by date range to avoid redundant API calls
    
    def _fetch_csv_data(self, team_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch CSV data from Cursor API for the specified date range.
        
        Args:
            team_id: Team ID for the request
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            DataFrame with CSV data from Cursor API
        """
        # Create cache key for this request
        cache_key = f"{team_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        
        # Return cached data if available
        if cache_key in self._data_cache:
            print(f"📁 Using cached data for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            return self._data_cache[cache_key]
        
        # Convert dates to Unix timestamps in milliseconds
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        # Prepare API request
        url = "https://cursor.com/api/dashboard/get-team-raw-data?format=csv"
        headers = {
            "Cookie": self.cookie_string,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        payload = {
            "teamId": team_id,
            "startDate": start_timestamp,
            "endDate": end_timestamp
        }
        
        print(f"🌐 Fetching CSV data from Cursor API...")
        print(f"   Team ID: {team_id}")
        print(f"   Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"   Timestamps: {start_timestamp} to {end_timestamp}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            # Parse CSV response
            csv_content = response.text
            df = pd.read_csv(io.StringIO(csv_content))
            df['Date'] = pd.to_datetime(df['Date'])
            
            print(f"✅ Fetched {len(df)} records from API")
            print(f"📅 Date range in response: {df['Date'].min()} to {df['Date'].max()}")
            
            # Build email to user_id mapping if not provided
            if not self.email_to_userid_mapping:
                print("🔍 Building email-to-userid mapping from API data...")
                for _, row in df.iterrows():
                    email = row['Email']
                    user_id = row['User ID']
                    if email not in self.email_to_userid_mapping:
                        self.email_to_userid_mapping[email] = (team_id, user_id)
                print(f"✅ Built mappings for {len(self.email_to_userid_mapping)} users")
            
            # Cache the data
            self._data_cache[cache_key] = df
            return df
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching CSV data from API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response status: {e.response.status_code}")
                print(f"   Response content: {e.response.text[:500]}")
            raise
        except Exception as e:
            print(f"❌ Error processing CSV response: {e}")
            raise
    
    async def load_email_mapping_from_team_spend(self, team_id: int):
        """Load email to userID mapping from team data.
        
        This method fetches a sample of recent data to build email mappings for the team.
        
        Args:
            team_id: Team ID for building mappings
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Store team_id for later use in data fetching
            self._default_team_id = team_id
            
            # Fetch recent data (last 7 days) to build email mappings
            end_date = datetime.now(pytz.UTC)
            start_date = end_date - timedelta(days=7)
            
            print(f"🔄 Loading team member mappings from recent data...")
            df = self._fetch_csv_data(team_id, start_date, end_date)
            
            # Email mappings should now be populated by _fetch_csv_data
            member_count = len(self.email_to_userid_mapping)
            print(f"✅ Loaded email mappings for {member_count} team members")
            
            if member_count == 0:
                print("⚠️  Warning: No team members found in recent data")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Error loading email mappings: {e}")
            return False
    
    def add_email_mapping(self, email: str, team_id: int, user_id: int):
        """Add email to user ID mapping - kept for interface compatibility."""
        self.email_to_userid_mapping[email] = (team_id, user_id)
        print(f"✓ Added mapping: {email} -> Team {team_id}, User {user_id}")
    
    def get_all_team_emails(self) -> List[str]:
        """Get list of all email addresses from current mapping.
        
        Returns:
            List of email addresses that can be used for analytics
        """
        return list(self.email_to_userid_mapping.keys())
    
    def resolve_email_to_userid(self, email: str) -> Tuple[int, int]:
        """Resolve an email to (team_id, user_id) tuple.
        
        Args:
            email: Email address to resolve
            
        Returns:
            Tuple of (team_id, user_id)
            
        Raises:
            ValueError: If email cannot be resolved
        """
        if email in self.email_to_userid_mapping:
            return self.email_to_userid_mapping[email]
        else:
            raise ValueError(
                f"Email '{email}' not found in mapping. "
                f"Available emails: {list(self.email_to_userid_mapping.keys())}\n"
                f"Add mapping using: aggregator.add_email_mapping('{email}', team_id, user_id)"
            )
    
    async def aggregate_requests_for_user(
        self, 
        team_id: int, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, int]:
        """Aggregate requests for a single user from CSV data.
        
        This is the main method that replaces API calls with CSV lookups.
        Maintains exact same interface and return format as the original.
        
        Args:
            team_id: Team ID (used to find email in mapping)
            user_id: User ID (used to find email in mapping)
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dictionary with aggregated request counts (same format as API version)
        """
        # Find email for this user_id
        email = None
        for mapped_email, (mapped_team_id, mapped_user_id) in self.email_to_userid_mapping.items():
            if mapped_user_id == user_id and mapped_team_id == team_id:
                email = mapped_email
                break
        
        if not email:
            # Return empty data if user not found
            return self._empty_analytics_response()
        
        return await self.aggregate_requests_for_email(email, start_date, end_date)
    
    async def aggregate_requests_for_email(
        self,
        email: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, any]:
        """Aggregate requests for a user by email address from dynamic CSV data.
        
        Args:
            email: Email address
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dictionary with aggregated counts (same format as API version)
        """
        # Normalize dates to midnight for proper date-only comparison
        if start_date.tzinfo is None:
            start_date = pytz.UTC.localize(start_date)
        if end_date.tzinfo is None:
            end_date = pytz.UTC.localize(end_date)
        
        # Normalize to date-only by setting time to midnight
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get team_id from email mapping or use default
        team_id = None
        if email in self.email_to_userid_mapping:
            team_id, _ = self.email_to_userid_mapping[email]
        elif hasattr(self, '_default_team_id'):
            team_id = self._default_team_id
        else:
            # Fallback - we'll need team ID for the API call
            raise ValueError(f"Team ID not available. Call load_email_mapping_from_team_spend() first.")
        
        # Fetch CSV data dynamically from API
        df = self._fetch_csv_data(team_id, start_date, end_date)
        
        # Filter data for this user and date range
        user_data = df[
            (df['Email'] == email) & 
            (df['Date'] >= start_date) & 
            (df['Date'] <= end_date)
        ]
        
        if len(user_data) == 0:
            return self._empty_analytics_response()
        
        # Aggregate data from CSV columns
        # Map CSV columns to our expected metrics to match the API response format
        
        # Chat-based requests (suggested lines represent AI generation)
        total_suggested_lines_added = user_data['Chat Suggested Lines Added'].sum()
        total_suggested_lines_deleted = user_data['Chat Suggested Lines Deleted'].sum()
        total_accepted_lines_added = user_data['Chat Accepted Lines Added'].sum()
        total_accepted_lines_deleted = user_data['Chat Accepted Lines Deleted'].sum()
        
        # Calculate total lines of agent edits (all AI-generated changes)
        total_lines_of_agent_edits = total_suggested_lines_added + total_suggested_lines_deleted
        
        # Chat interactions and tab completions
        total_chat_applies = user_data['Chat Total Applies'].sum()
        total_tabs_accepted = user_data['Tabs Accepted'].sum()
        
        # For compatibility with API format, split chat applies into agent/composer
        # We'll treat "Chat Total Applies" as agent requests and use other metrics for composer
        total_agent_requests = total_chat_applies
        total_composer_requests = user_data['Ask Requests'].sum() + user_data['Agent Requests'].sum()
        total_requests = total_agent_requests + total_composer_requests
        
        # Create daily breakdown (same format as API)
        daily_breakdown = []
        for _, row in user_data.iterrows():
            # Calculate daily lines of agent edits
            daily_suggested_added = row['Chat Suggested Lines Added'] or 0
            daily_suggested_deleted = row['Chat Suggested Lines Deleted'] or 0
            daily_lines_edited = daily_suggested_added + daily_suggested_deleted
            
            daily_breakdown.append({
                'date': row['Date'].strftime('%Y-%m-%d'),
                'total_chats': int((row['Chat Total Applies'] or 0) + (row['Ask Requests'] or 0) + (row['Agent Requests'] or 0)),
                'total_tabs_accepted': int(row['Tabs Accepted'] or 0),
                'lines_of_agent_edits': int(daily_lines_edited)
            })
        
        # Calculate active days
        active_days = len([d for d in daily_breakdown if d['total_chats'] > 0 or d['lines_of_agent_edits'] > 0])
        
        # Return in exact same format as the API version (convert pandas types to Python native types for JSON serialization)
        return {
            'agent_requests': int(total_agent_requests),
            'composer_requests': int(total_composer_requests), 
            'total_requests': int(total_requests),
            'total_tabs_accepted': int(total_tabs_accepted),
            'lines_of_agent_edits': int(total_lines_of_agent_edits),
            'accepted_lines_added': int(total_accepted_lines_added),
            'accepted_lines_deleted': int(total_accepted_lines_deleted),
            'lines_added': int(total_suggested_lines_added),
            'lines_deleted': int(total_suggested_lines_deleted),
            'days_analyzed': len(user_data),
            'active_days': active_days,
            'daily_breakdown': daily_breakdown
        }
    
    def _empty_analytics_response(self) -> Dict[str, any]:
        """Return empty analytics response in the same format as API version."""
        return {
            'agent_requests': 0,
            'composer_requests': 0,
            'total_requests': 0,
            'total_tabs_accepted': 0,
            'lines_of_agent_edits': 0,
            'accepted_lines_added': 0,
            'accepted_lines_deleted': 0,
            'lines_added': 0,
            'lines_deleted': 0,
            'days_analyzed': 0,
            'active_days': 0,
            'daily_breakdown': []
        }
    
    async def aggregate_requests_for_group(
        self,
        group_members: List[Tuple[int, int]],  # List of (team_id, user_id) tuples
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, any]:
        """Aggregate requests for a group of users from CSV data.
        
        Kept for interface compatibility.
        """
        group_totals = {
            'agent_requests': 0,
            'composer_requests': 0,
            'total_requests': 0,
            'total_tabs_accepted': 0,
            'lines_of_agent_edits': 0,
            'accepted_lines_added': 0,
            'accepted_lines_deleted': 0,
            'lines_added': 0,
            'lines_deleted': 0,
            'days_analyzed': 0,
            'active_days': 0
        }
        
        for team_id, user_id in group_members:
            user_stats = await self.aggregate_requests_for_user(team_id, user_id, start_date, end_date)
            for key in group_totals:
                if key in user_stats and isinstance(user_stats[key], (int, float)):
                    group_totals[key] += user_stats[key]
        
        return group_totals 