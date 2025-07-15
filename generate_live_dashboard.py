#!/usr/bin/env python3
"""Generate HTML dashboard with real data from cursor_admin_sdk.

Configuration Options (Command line arguments take precedence over environment variables):
    --cookie, -c: Cookie string from authenticated browser session
    --team-id, -t: Team ID from Cursor dashboard (e.g., 1234567)
    
Environment Variables (used if command line arguments not provided):
    CURSOR_COOKIE_STRING: Cookie string from authenticated browser session
    TEAM_ID: Team ID from Cursor dashboard (e.g., 1234567)

Usage:
    # Run report on all team members (default)
    uv run python generate_live_dashboard.py

    # Run report with command line arguments
    uv run python generate_live_dashboard.py --cookie "your_cookie" --team-id 1234567

    # Run report on ai_champs group
    uv run python generate_live_dashboard.py --group ai_champs

    # Run report on specific predefined group
    uv run python generate_live_dashboard.py --group engineering

    # Show available groups
    uv run python generate_live_dashboard.py --list-groups

    # Run report with custom days (default is 7 days)
    uv run python generate_live_dashboard.py --group ai_champs --days 14

Quick Commands:
    uv run python generate_live_dashboard.py -g ai_champs     # AI Champions report
    uv run python generate_live_dashboard.py -g engineering  # Engineering report
    uv run python generate_live_dashboard.py --list-groups   # List all groups
    uv run python generate_live_dashboard.py -c "cookie" -t 1234567  # With inline auth

Available groups: ai_champs, engineering, management, qa, backend, frontend, devops, product, design
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from cursor_admin_sdk import (
    CursorAdminClient,
    CursorAuthError,
    DashboardAnalyticsResponse,
    TeamSpendResponse,
)

# Predefined groups of people for easy report generation
PREDEFINED_GROUPS = {
    "ai_champs": [
        "***1@example.com",
        "***2@example.com", 
        "***3@example.com",
        "***4@example.com",
        "***5@example.com",
        "***6@example.com",
        "***7@example.com",
        "***8@example.com",
        "***9@example.com",
        "***10@example.com",
        "***11@example.com",
        "***12@example.com",
        "***13@example.com"
    ],
    "engineering": [
        # Add engineering team emails here
        # "john.doe@example.com",
        # "jane.smith@example.com",
        # "mike.wilson@example.com"
    ],
    "management": [
        # Add management team emails here
        # "ceo@example.com",
        # "cto@example.com",
        # "vp.engineering@example.com"
    ],
    "qa": [
        # Add QA team emails here
        # "qa.lead@example.com",
        # "tester1@example.com",
        # "tester2@example.com"
    ],
    "backend": [
        # Add backend developers here
        # "backend.dev1@example.com",
        # "backend.dev2@example.com"
    ],
    "frontend": [
        # Add frontend developers here
        # "frontend.dev1@example.com",
        # "frontend.dev2@example.com"
    ],
    "devops": [
        # Add DevOps team emails here
        # "devops.lead@example.com",
        # "infrastructure@example.com"
    ],
    "product": [
        # Add product team emails here
        # "product.manager@example.com",
        # "product.owner@example.com"
    ],
    "design": [
        # Add design team emails here
        # "ui.designer@example.com",
        # "ux.designer@example.com"
    ]
}


class RequestAggregator:
    """Aggregates agent and composer requests from dashboard analytics."""
    
    def __init__(self, cookie_string: str, email_to_userid_mapping: Dict[str, Tuple[int, int]] = None):
        """Initialize the aggregator with authentication cookie.
        
        Args:
            cookie_string: Cookie string from authenticated browser session
            email_to_userid_mapping: Optional dict mapping emails to (team_id, user_id) tuples
        """
        self.cookie_string = cookie_string
        # API key is required for client initialization but won't be used for dashboard API
        self.api_key = "not_used_for_dashboard_api"
        self.email_to_userid_mapping = email_to_userid_mapping or {}
        self._team_members_cache = None
        self._team_spend_cache = None
    
    async def aggregate_requests_for_user(
        self, 
        team_id: int, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, int]:
        """Aggregate agent and composer requests for a single user.
        
        Args:
            team_id: Team ID from Cursor dashboard
            user_id: User ID from Cursor dashboard
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dictionary with aggregated request counts
        """
        async with CursorAdminClient(api_key=self.api_key) as client:
            analytics = await client.get_dashboard_analytics(
                cookie_string=self.cookie_string,
                team_id=team_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
        
        return self._aggregate_analytics(analytics)
    
    def _aggregate_analytics(self, analytics: DashboardAnalyticsResponse) -> Dict[str, any]:
        """Aggregate requests from analytics response.
        
        Args:
            analytics: Dashboard analytics response
            
        Returns:
            Dictionary with aggregated counts and daily breakdown
        """
        total_agent_requests = 0
        total_composer_requests = 0
        total_combined_requests = 0
        total_lines_of_agent_edits = 0
        total_tabs_accepted = 0
        
        # Line statistics
        total_accepted_lines_added = 0
        total_accepted_lines_deleted = 0
        total_lines_added = 0
        total_lines_deleted = 0
        
        # Daily breakdown for charts
        daily_breakdown = []
        
        for metric in analytics.daily_metrics:
            agent_reqs = metric.agent_requests or 0
            composer_reqs = metric.composer_requests or 0
            
            total_agent_requests += agent_reqs
            total_composer_requests += composer_reqs
            total_combined_requests += (agent_reqs + composer_reqs)
            
            # Aggregate tab completions
            total_tabs_accepted += metric.total_tabs_accepted or 0
            
            # Aggregate line statistics
            accepted_lines_added = metric.accepted_lines_added or 0
            accepted_lines_deleted = metric.accepted_lines_deleted or 0
            lines_added = metric.lines_added or 0
            lines_deleted = metric.lines_deleted or 0
            
            total_accepted_lines_added += accepted_lines_added
            total_accepted_lines_deleted += accepted_lines_deleted
            total_lines_added += lines_added
            total_lines_deleted += lines_deleted
            
            # Calculate Lines of Agent Edits (all line changes)
            daily_lines_edited = accepted_lines_added + accepted_lines_deleted + lines_added + lines_deleted
            total_lines_of_agent_edits += daily_lines_edited
            
            # Store daily breakdown for charts
            daily_breakdown.append({
                'date': metric.timestamp.strftime('%Y-%m-%d'),
                'total_chats': agent_reqs + composer_reqs,
                'total_tabs_accepted': metric.total_tabs_accepted or 0,
                'lines_of_agent_edits': daily_lines_edited
            })
        
        return {
            'agent_requests': total_agent_requests,
            'composer_requests': total_composer_requests,
            'total_requests': total_combined_requests,
            'total_tabs_accepted': total_tabs_accepted,
            'lines_of_agent_edits': total_lines_of_agent_edits,
            'accepted_lines_added': total_accepted_lines_added,
            'accepted_lines_deleted': total_accepted_lines_deleted,
            'lines_added': total_lines_added,
            'lines_deleted': total_lines_deleted,
            'days_analyzed': len(analytics.daily_metrics),
            'active_days': sum(1 for m in analytics.daily_metrics if (m.agent_requests or 0) + (m.composer_requests or 0) > 0),
            'daily_breakdown': daily_breakdown
        }
    
    async def aggregate_requests_for_group(
        self,
        group_members: List[Tuple[int, int]],  # List of (team_id, user_id) tuples
        start_date: datetime,
        end_date: datetime,
        group_name: str = "Group"
    ) -> Dict[str, any]:
        """Aggregate requests for a group of users.
        
        Args:
            group_members: List of (team_id, user_id) tuples representing the group
            start_date: Start date for aggregation
            end_date: End date for aggregation
            group_name: Name of the group for display purposes
            
        Returns:
            Dictionary with group aggregation results
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
            'total_active_days': 0,
            'members_analyzed': 0,
            'per_member_stats': []
        }
        
        print(f"\n📊 Aggregating requests for {group_name} ({len(group_members)} members)")
        print(f"Period: {start_date.date()} to {end_date.date()}\n")
        
        for team_id, user_id in group_members:
            try:
                user_stats = await self.aggregate_requests_for_user(
                    team_id=team_id,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Add to group totals
                group_totals['agent_requests'] += user_stats['agent_requests']
                group_totals['composer_requests'] += user_stats['composer_requests']
                group_totals['total_requests'] += user_stats['total_requests']
                group_totals['total_tabs_accepted'] += user_stats['total_tabs_accepted']
                group_totals['lines_of_agent_edits'] += user_stats['lines_of_agent_edits']
                group_totals['accepted_lines_added'] += user_stats['accepted_lines_added']
                group_totals['accepted_lines_deleted'] += user_stats['accepted_lines_deleted']
                group_totals['lines_added'] += user_stats['lines_added']
                group_totals['lines_deleted'] += user_stats['lines_deleted']
                group_totals['total_active_days'] += user_stats['active_days']
                group_totals['members_analyzed'] += 1
                
                # Store per-member stats
                group_totals['per_member_stats'].append({
                    'team_id': team_id,
                    'user_id': user_id,
                    **user_stats
                })
                
                print(f"  ✓ User {user_id} (Team {team_id}): {user_stats['total_requests']:,} total requests, {user_stats['lines_of_agent_edits']:,} lines edited")
                
            except Exception as e:
                print(f"  ✗ Error processing user {user_id} (Team {team_id}): {e}")
        
        # Calculate averages
        if group_totals['members_analyzed'] > 0:
            group_totals['avg_requests_per_member'] = group_totals['total_requests'] / group_totals['members_analyzed']
            group_totals['avg_active_days_per_member'] = group_totals['total_active_days'] / group_totals['members_analyzed']
        else:
            group_totals['avg_requests_per_member'] = 0
            group_totals['avg_active_days_per_member'] = 0
        
        return group_totals
    
    async def load_email_mapping_from_file(self, mapping_file: str = "email_mapping.json"):
        """Load email to userID mapping from a JSON file.
        
        Args:
            mapping_file: Path to JSON file with email mappings
            
        Example JSON format:
        {
            "user1@example.com": [1234567, 987654321],
            "user2@example.com": [1234567, 123456789]
        }
        """
        import json
        import os
        
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    raw_mapping = json.load(f)
                
                # Convert lists to tuples
                self.email_to_userid_mapping = {
                    email: tuple(ids) for email, ids in raw_mapping.items()
                }
                print(f"✓ Loaded email mappings for {len(self.email_to_userid_mapping)} users from {mapping_file}")
                return True
            except Exception as e:
                print(f"✗ Error loading email mapping from {mapping_file}: {e}")
                return False
        else:
            print(f"📝 Email mapping file {mapping_file} not found. You can create one manually or use direct user IDs.")
            return False
    
    def save_email_mapping_to_file(self, mapping_file: str = "email_mapping.json"):
        """Save current email to userID mapping to a JSON file."""
        import json
        
        # Convert tuples to lists for JSON serialization
        raw_mapping = {
            email: list(ids) for email, ids in self.email_to_userid_mapping.items()
        }
        
        with open(mapping_file, 'w') as f:
            json.dump(raw_mapping, f, indent=2)
        
        print(f"💾 Saved email mappings for {len(self.email_to_userid_mapping)} users to {mapping_file}")
    
    async def load_email_mapping_from_team_spend(self, team_id: int):
        """Load email to userID mapping from team spend data.
        
        This method fetches team spend information and automatically populates
        the email_to_userid_mapping dictionary with all team members.
        
        Args:
            team_id: Team ID to fetch spend data for
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with CursorAdminClient(api_key=self.api_key) as client:
                # Fetch team spend data
                spend_response = await client.get_team_spend(
                    cookie_string=self.cookie_string,
                    team_id=team_id
                )
                
                # Cache the response for later use
                self._team_spend_cache = spend_response
                
                # Build email mappings
                mapping_count = 0
                for member in spend_response.team_member_spend:
                    self.email_to_userid_mapping[member.email] = (team_id, member.user_id)
                    mapping_count += 1
                
                print(f"✅ Loaded email mappings for {mapping_count} team members from team spend data")
                print(f"📊 Team: {team_id} | Total members: {spend_response.total_members}")
                
                # Display some member info for verification
                if mapping_count > 0:
                    print(f"\n📋 Sample team members:")
                    for i, member in enumerate(spend_response.team_member_spend[:5]):  # Show first 5
                        role_info = f" ({member.role})" if member.role else ""
                        name_info = f" - {member.name}" if member.name else ""
                        print(f"  {i+1}. {member.email}{name_info}{role_info}")
                    
                    if len(spend_response.team_member_spend) > 5:
                        print(f"  ... and {len(spend_response.team_member_spend) - 5} more members")
                
                return True
                
        except Exception as e:
            print(f"❌ Error loading email mappings from team spend: {e}")
            return False
    
    def add_email_mapping(self, email: str, team_id: int, user_id: int):
        """Add a single email to userID mapping.
        
        Args:
            email: User's email address
            team_id: Team ID for the user
            user_id: User ID for the user
        """
        self.email_to_userid_mapping[email] = (team_id, user_id)
        print(f"✓ Added mapping: {email} -> Team {team_id}, User {user_id}")
    
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
    
    async def aggregate_requests_for_email(
        self,
        email: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, any]:
        """Aggregate requests for a user by email address.
        
        Args:
            email: User's email address
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dictionary with aggregated counts and daily breakdown
        """
        team_id, user_id = self.resolve_email_to_userid(email)
        return await self.aggregate_requests_for_user(team_id, user_id, start_date, end_date)
    
    async def generate_daily_charts_data_from_emails(
        self,
        emails: List[str],  # List of email addresses
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, any]:
        """Generate data for daily breakdown charts using email addresses.
        
        Args:
            emails: List of email addresses
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary with chart data for all users
        """
        all_users_data = {}
        
        print(f"\n📊 Generating daily breakdown data from emails...")
        print(f"Period: {start_date.date()} to {end_date.date()}\n")
        
        for email in emails:
            try:
                team_id, user_id = self.resolve_email_to_userid(email)
                
                user_stats = await self.aggregate_requests_for_user(
                    team_id=team_id,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Use email as display name (remove domain for cleaner display)
                display_name = email.split('@')[0] if '@' in email else email
                
                all_users_data[display_name] = {
                    'team_id': team_id,
                    'user_id': user_id,
                    'email': email,
                    'daily_breakdown': user_stats['daily_breakdown'],
                    'totals': {
                        'total_chats': user_stats['total_requests'],
                        'total_tabs_accepted': user_stats['total_tabs_accepted'],
                        'lines_of_agent_edits': user_stats['lines_of_agent_edits']
                    }
                }
                
                print(f"  ✓ {email}: {len(user_stats['daily_breakdown'])} days of data")
                
            except ValueError as e:
                print(f"  ✗ Error resolving {email}: {e}")
            except Exception as e:
                print(f"  ✗ Error processing {email}: {e}")
        
        return all_users_data
    
    def get_all_team_emails(self) -> List[str]:
        """Get list of all email addresses from current mapping.
        
        Returns:
            List of email addresses that can be used for analytics
        """
        return list(self.email_to_userid_mapping.keys())
    
    def get_team_spend_summary(self) -> Dict[str, any]:
        """Get summary of team spend data if available.
        
        Returns:
            Dictionary with team spend summary or empty dict if not available
        """
        if not self._team_spend_cache:
            return {}
        
        spend_data = self._team_spend_cache
        members_with_spend = [m for m in spend_data.team_member_spend if m.spend_cents is not None]
        members_with_requests = [m for m in spend_data.team_member_spend if m.fast_premium_requests is not None]
        
        summary = {
            'total_members': spend_data.total_members,
            'subscription_cycle_start': spend_data.subscription_cycle_start,
            'members_with_spend_data': len(members_with_spend),
            'members_with_request_data': len(members_with_requests)
        }
        
        if members_with_spend:
            total_spend_cents = sum(m.spend_cents for m in members_with_spend if m.spend_cents)
            summary['total_team_spend_dollars'] = total_spend_cents / 100
            
            # Top 3 spenders
            top_spenders = sorted(members_with_spend, key=lambda x: x.spend_cents or 0, reverse=True)[:3]
            summary['top_spenders'] = [
                {
                    'email': m.email,
                    'name': m.name,
                    'spend_dollars': (m.spend_cents or 0) / 100,
                    'requests': m.fast_premium_requests or 0
                }
                for m in top_spenders
            ]
        
        if members_with_requests:
            total_requests = sum(m.fast_premium_requests for m in members_with_requests if m.fast_premium_requests)
            summary['total_fast_premium_requests'] = total_requests
        
        return summary
    
    async def generate_daily_charts_data(
        self,
        group_members: List[Tuple[int, int, str]],  # List of (team_id, user_id, user_name) tuples
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, any]:
        """Generate data for daily breakdown charts.
        
        Args:
            group_members: List of (team_id, user_id, user_name) tuples
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary with chart data for all users
        """
        all_users_data = {}
        
        print(f"\n📊 Generating daily breakdown data...")
        print(f"Period: {start_date.date()} to {end_date.date()}\n")
        
        for team_id, user_id, user_name in group_members:
            try:
                user_stats = await self.aggregate_requests_for_user(
                    team_id=team_id,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                all_users_data[user_name] = {
                    'team_id': team_id,
                    'user_id': user_id,
                    'daily_breakdown': user_stats['daily_breakdown'],
                    'totals': {
                        'total_chats': user_stats['total_requests'],
                        'total_tabs_accepted': user_stats['total_tabs_accepted'],
                        'lines_of_agent_edits': user_stats['lines_of_agent_edits']
                    }
                }
                
                print(f"  ✓ {user_name}: {len(user_stats['daily_breakdown'])} days of data")
                
            except Exception as e:
                print(f"  ✗ Error processing {user_name}: {e}")
        
        return all_users_data
    
    def generate_html_report(self, users_data: Dict[str, any], output_file: str = "cursor_analytics_report.html"):
        """Generate HTML report with interactive charts.
        
        Args:
            users_data: Data from generate_daily_charts_data
            output_file: Output HTML file name
        """
        # Get all unique dates from all users
        all_dates = set()
        for user_data in users_data.values():
            for day in user_data['daily_breakdown']:
                all_dates.add(day['date'])
        
        sorted_dates = sorted(list(all_dates))
        
        # Prepare data for charts
        chart_data = {
            'dates': sorted_dates,
            'users': {},
            'metrics': ['total_chats', 'total_tabs_accepted', 'lines_of_agent_edits']
        }
        
        for user_name, user_data in users_data.items():
            chart_data['users'][user_name] = {
                'total_chats': [],
                'total_tabs_accepted': [],
                'lines_of_agent_edits': [],
                'totals': user_data['totals']
            }
            
            # Create lookup for user's daily data
            daily_lookup = {day['date']: day for day in user_data['daily_breakdown']}
            
            # Fill data for each date (0 if no data for that date)
            for date in sorted_dates:
                day_data = daily_lookup.get(date, {
                    'total_chats': 0,
                    'total_tabs_accepted': 0,
                    'lines_of_agent_edits': 0
                })
                
                chart_data['users'][user_name]['total_chats'].append(day_data['total_chats'])
                chart_data['users'][user_name]['total_tabs_accepted'].append(day_data['total_tabs_accepted'])
                chart_data['users'][user_name]['lines_of_agent_edits'].append(day_data['lines_of_agent_edits'])
        
        # Debug: Print chart data summary
        print(f"\n🔍 Chart Data Summary:")
        print(f"  Dates: {len(chart_data['dates'])} days from {chart_data['dates'][0]} to {chart_data['dates'][-1]}")
        for user_name, user_data in chart_data['users'].items():
            print(f"  {user_name}:")
            print(f"    - Total Chats: {sum(user_data['total_chats'])}")
            print(f"    - Total Tabs: {sum(user_data['total_tabs_accepted'])}")
            print(f"    - Total Lines: {sum(user_data['lines_of_agent_edits'])}")
            print(f"    - Daily Chats: {user_data['total_chats']}")
            print(f"    - Daily Tabs: {user_data['total_tabs_accepted']}")
            print(f"    - Daily Lines: {user_data['lines_of_agent_edits']}")
        
        # Generate HTML content
        html_content = self._generate_html_template(chart_data)
        
        # Write to file
        # with open(output_file, 'w', encoding='utf-8') as f:
        #     f.write(html_content)
        
        print(f"\n📊 HTML report generated: {output_file}")
        return output_file
    
    def _generate_html_template(self, chart_data: Dict[str, any]) -> str:
        """Generate HTML template with Chart.js visualizations."""
        
        # Generate random colors for each user
        import random
        random.seed(42)  # For consistent colors
        
        colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
        ]
        
        user_colors = {}
        for i, user_name in enumerate(chart_data['users'].keys()):
            user_colors[user_name] = colors[i % len(colors)]
        
        # Generate datasets for each chart
        def generate_datasets(metric):
            datasets = []
            for user_name, user_data in chart_data['users'].items():
                datasets.append({
                    'label': user_name,
                    'data': user_data[metric],
                    'borderColor': user_colors[user_name],
                    'backgroundColor': user_colors[user_name] + '20',
                    'fill': False,
                    'tension': 0.1
                })
            return datasets
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cursor Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .summary {{
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .summary h2 {{
            margin: 0 0 20px 0;
            color: #495057;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #6c757d;
            font-size: 0.9em;
            font-weight: 500;
            text-transform: uppercase;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #495057;
        }}
        .charts-container {{
            padding: 30px;
        }}
        .chart-section {{
            margin-bottom: 50px;
        }}
        .chart-section h2 {{
            margin: 0 0 20px 0;
            color: #495057;
            text-align: center;
            font-size: 1.8em;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}
        .legend {{
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 15px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 10px;
            background: #f8f9fa;
            border-radius: 15px;
            font-size: 0.9em;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .date-range {{
            text-align: center;
            color: #6c757d;
            font-style: italic;
            margin-bottom: 30px;
        }}
        .leaderboards {{
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .leaderboards h2 {{
            margin: 0 0 30px 0;
            color: #495057;
            text-align: center;
            font-size: 1.8em;
        }}
        .leaderboard-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        .leaderboard {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .leaderboard h3 {{
            margin: 0 0 20px 0;
            color: #495057;
            text-align: center;
            font-size: 1.3em;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}
        .leaderboard-item {{
            display: flex;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .leaderboard-item:last-child {{
            border-bottom: none;
        }}
        .rank {{
            font-size: 1.2em;
            font-weight: bold;
            width: 30px;
            text-align: center;
            color: #6c757d;
        }}
        .rank.gold {{ color: #ffd700; }}
        .rank.silver {{ color: #c0c0c0; }}
        .rank.bronze {{ color: #cd7f32; }}
        .user-info {{
            flex: 1;
            margin-left: 15px;
        }}
        .user-name {{
            font-weight: 600;
            color: #495057;
            font-size: 1em;
        }}
        .user-value {{
            font-size: 1.1em;
            font-weight: bold;
            text-align: right;
            color: #28a745;
        }}
        .trophy {{
            font-size: 1.5em;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Cursor Analytics Dashboard</h1>
            <p>Daily User Activity Breakdown</p>
        </div>
        
        <div class="date-range">
            <p>Period: {chart_data['dates'][0]} to {chart_data['dates'][-1]}</p>
        </div>
        
        <div class="summary">
            <h2>📈 Summary Statistics</h2>
            <div class="summary-grid">"""
        
        # Add summary cards for each user
        for user_name, user_data in chart_data['users'].items():
            html_template += f"""
                <div class="summary-card">
                    <h3>{user_name}</h3>
                    <div class="value" style="color: {user_colors[user_name]}">{user_data['totals']['total_chats']}</div>
                    <small>Total Chats</small>
                </div>"""
        
        html_template += """
            </div>
        </div>"""
        
        # Generate leaderboards
        # Sort users by total chats and lines of agent edits
        chat_leaders = sorted(chart_data['users'].items(), 
                             key=lambda x: x[1]['totals']['total_chats'], reverse=True)[:10]
        lines_leaders = sorted(chart_data['users'].items(), 
                              key=lambda x: x[1]['totals']['lines_of_agent_edits'], reverse=True)[:10]
        
        html_template += f"""
        <div class="leaderboards">
            <h2>🏆 Team Leaderboards</h2>
            <p style="text-align: center; color: #6c757d; margin-top: -15px; margin-bottom: 25px;">
                Period: {chart_data['dates'][0]} to {chart_data['dates'][-1]}
            </p>
            <div class="leaderboard-grid">
                <div class="leaderboard">
                    <h3><span class="trophy">💬</span>Chat Champions</h3>"""
        
        # Generate chat leaderboard
        for i, (user_name, user_data) in enumerate(chat_leaders, 1):
            rank_class = ""
            trophy_emoji = ""
            if i == 1:
                rank_class = "gold"
                trophy_emoji = "🥇"
            elif i == 2:
                rank_class = "silver" 
                trophy_emoji = "🥈"
            elif i == 3:
                rank_class = "bronze"
                trophy_emoji = "🥉"
            else:
                trophy_emoji = f"{i}"
                
            chats = user_data['totals']['total_chats']
            if chats > 0:  # Only show users with activity
                html_template += f"""
                    <div class="leaderboard-item">
                        <div class="rank {rank_class}">{trophy_emoji}</div>
                        <div class="user-info">
                            <div class="user-name">{user_name}</div>
                        </div>
                        <div class="user-value">{chats:,}</div>
                    </div>"""
        
        html_template += """
                </div>
                <div class="leaderboard">
                    <h3><span class="trophy">✏️</span>Code Edit Leaders</h3>"""
        
        # Generate lines leaderboard
        for i, (user_name, user_data) in enumerate(lines_leaders, 1):
            rank_class = ""
            trophy_emoji = ""
            if i == 1:
                rank_class = "gold"
                trophy_emoji = "🥇"
            elif i == 2:
                rank_class = "silver"
                trophy_emoji = "🥈"
            elif i == 3:
                rank_class = "bronze"
                trophy_emoji = "🥉"
            else:
                trophy_emoji = f"{i}"
                
            lines = user_data['totals']['lines_of_agent_edits']
            if lines > 0:  # Only show users with activity
                html_template += f"""
                    <div class="leaderboard-item">
                        <div class="rank {rank_class}">{trophy_emoji}</div>
                        <div class="user-info">
                            <div class="user-name">{user_name}</div>
                        </div>
                        <div class="user-value">{lines:,}</div>
                    </div>"""
        
        html_template += """
                </div>
            </div>
        </div>
        
        <div class="charts-container">"""
        
        # Generate each chart
        chart_configs = [
            ('total_chats', 'Total Chats per Day', '💬'),
            ('total_tabs_accepted', 'Tab Completions Accepted per Day', '⭐'),
            ('lines_of_agent_edits', 'Lines of Agent Edits per Day', '✏️')
        ]
        
        for metric, title, emoji in chart_configs:
            datasets = generate_datasets(metric)
            
            html_template += f"""
            <div class="chart-section">
                <h2>{emoji} {title}</h2>
                <div class="chart-container">
                    <canvas id="{metric}Chart"></canvas>
                </div>
            </div>"""
        
        html_template += """
        </div>
    </div>

    <script>
        // Chart.js configuration
        Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
        Chart.defaults.color = '#495057';
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Count'
                    },
                    beginAtZero: true
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        };"""
        
        # Generate JavaScript for each chart
        import json
        
        for metric, title, emoji in chart_configs:
            datasets = generate_datasets(metric)
            
            # Debug: Print data to console
            html_template += f"""
        
        // {title}
        console.log('Chart data for {metric}:', {{
            labels: {json.dumps(chart_data['dates'])},
            datasets: {json.dumps(datasets)}
        }});
        
        new Chart(document.getElementById('{metric}Chart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(chart_data['dates'])},
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    title: {{
                        display: true,
                        text: '{title}'
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        title: {{
                            display: true,
                            text: 'Date'
                        }}
                    }},
                    y: {{
                        display: true,
                        title: {{
                            display: true,
                            text: 'Count'
                        }},
                        beginAtZero: true,
                        min: 0
                    }}
                }},
                interaction: {{
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }}
            }}
        }});"""
        
        html_template += """
    </script>
</body>
</html>"""
        
        return html_template


def show_available_groups():
    """Show available predefined groups and their members."""
    print("\n📋 Available Predefined Groups:")
    print("═" * 50)
    
    for group_name, emails in PREDEFINED_GROUPS.items():
        print(f"\n🎯 {group_name}:")
        if emails:
            for email in emails:
                print(f"   • {email}")
        else:
            print("   (empty - add emails to use this group)")
    
    print("\n💡 To use a group, set: group_name = \"groupname\"")
    print("💡 To see this list again, call: show_available_groups()")


class LiveDashboardGenerator:
    """Generates HTML dashboard with real Cursor analytics data.
    
    Args:
        cookie_string: Authentication cookie string from Cursor dashboard
        excluded_emails: List of emails to exclude from the dashboard (optional)
        people_to_include: List of emails to include in dashboard (if provided, only these emails will be processed)
        group_name: Name of predefined group to run report on (optional)
    
    Filtering Logic:
        1. If group_name is provided: use emails from that predefined group
        2. If people_to_include is provided: only include those specific emails
        3. If neither is provided: include all team members
        4. Then apply excluded_emails filter as a secondary filter
    """
    
    def __init__(self, cookie_string: str, excluded_emails: List[str] = None, people_to_include: List[str] = None, group_name: str = None):
        self.cookie_string = cookie_string
        self.aggregator = RequestAggregator(cookie_string)
        self.excluded_emails = excluded_emails or []
        self.people_to_include = people_to_include or []
        self.group_name = group_name
        
        # If group_name is provided, override people_to_include with the group's emails
        if self.group_name:
            if self.group_name not in PREDEFINED_GROUPS:
                available_groups = list(PREDEFINED_GROUPS.keys())
                raise ValueError(f"Group '{self.group_name}' not found. Available groups: {available_groups}")
            
            group_emails = PREDEFINED_GROUPS[self.group_name]
            if not group_emails:
                raise ValueError(f"Group '{self.group_name}' is empty. Please add emails to this group in PREDEFINED_GROUPS.")
            
            self.people_to_include = group_emails
            print(f"📋 Using predefined group '{self.group_name}' with {len(group_emails)} members")
        
    async def fetch_real_data(self, team_id: int, days_back: int = 7) -> Dict[str, Any]:
        """Fetch real data from the Cursor Admin SDK."""
        print("🔄 Loading team data from Cursor Admin SDK...")
        
        # Load team member mapping
        await self.aggregator.load_email_mapping_from_team_spend(team_id)
        all_emails = self.aggregator.get_all_team_emails()
        
        if not all_emails:
            raise ValueError("No team members found. Check team_id and authentication.")
        
        # Apply filtering logic
        original_count = len(all_emails)
        
        # If people_to_include is provided, filter to only include those emails
        if self.people_to_include:
            all_emails = [email for email in all_emails if email in self.people_to_include]
            included_count = len(all_emails)
            print(f"📊 Found {original_count} team members")
            print(f"✅ Filtered to include only {included_count} specified emails: {', '.join(self.people_to_include)}")
            
            # Check if any specified emails were not found
            missing_emails = [email for email in self.people_to_include if email not in self.aggregator.get_all_team_emails()]
            if missing_emails:
                print(f"⚠️  Warning: The following emails were not found in the team: {', '.join(missing_emails)}")
        else:
            print(f"📊 Found {original_count} team members")
        
        # Then apply excluded emails filter
        if self.excluded_emails:
            emails_before_exclusion = len(all_emails)
            all_emails = [email for email in all_emails if email not in self.excluded_emails]
            excluded_count = emails_before_exclusion - len(all_emails)
            
            if excluded_count > 0:
                excluded_found = [email for email in self.excluded_emails if email in self.aggregator.get_all_team_emails()]
                print(f"🚫 Excluded {excluded_count} emails: {', '.join(excluded_found)}")
        
        print(f"📈 Processing {len(all_emails)} team members")
        
        if not all_emails:
            if self.people_to_include:
                raise ValueError(f"None of the specified emails in people_to_include were found in the team. Available emails: {', '.join(self.aggregator.get_all_team_emails())}")
            else:
                raise ValueError("No team members remaining after filtering. Check your excluded_emails list.")
        
        # Calculate date ranges for week-over-week comparison
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Previous week: 14 days ago to 7 days ago
        prev_week_end = end_date - timedelta(days=7)
        prev_week_start = end_date - timedelta(days=14)
        
        # 🐛 DEBUG: Print date ranges
        print(f"\n🗓️  DATE RANGE DEBUG:")
        print(f"   Current time: {datetime.now().isoformat()}")
        print(f"   End date: {end_date.isoformat()}")
        print(f"   Start date: {start_date.isoformat()}")
        print(f"   Previous week start: {prev_week_start.isoformat()}")
        print(f"   Previous week end: {prev_week_end.isoformat()}")
        print(f"   Days back: {days_back}")
        
        # Fetch real user data
        users_data = []
        # Expanded color palette for more users
        user_colors = [
            "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444",
            "#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00c49f", 
            "#ffbb28", "#ff8042", "#a4de6c", "#ffc0cb", "#87ceeb",
            "#dda0dd", "#98fb98", "#f0e68c", "#ff6347", "#40e0d0",
            "#ee82ee", "#90ee90", "#ffb6c1", "#ffd700", "#ff69b4"
        ]
        
        # Weekly data structure for charts
        weekly_data_by_user = []
        weekly_chats_by_user = []
        weekly_completions_by_user = []
        
        # 🐛 FIXED: Generate actual dates matching SDK date range exactly (days_back days ago to today inclusive)
        dates_and_days = []
        for i in range(days_back, -1, -1):  # Start from days_back and go to 0 (inclusive)
            date = end_date - timedelta(days=i)
            day_name = date.strftime('%a')  # Short day name (Mon, Tue, etc.)
            date_str = date.strftime('%m/%d')  # Month/Day format
            full_date = date.strftime('%Y-%m-%d')  # For matching with SDK data
            dates_and_days.append({
                'day': day_name,
                'date': date_str,
                'full_date': full_date,
                'display': f"{day_name}\n{date_str}"
            })
        
        print(f"🗓️  Generated dates: {[d['full_date'] for d in dates_and_days]}")
        
        # Initialize weekly data structures with actual dates
        for date_info in dates_and_days:
            day_data = {
                "day": date_info['day'],
                "date": date_info['date'], 
                "display": date_info['display'],
                "full_date": date_info['full_date']
            }
            weekly_data_by_user.append(day_data.copy())
            weekly_chats_by_user.append(day_data.copy())
            weekly_completions_by_user.append(day_data.copy())
        
        # Process each team member
        active_users = []
        total_lines = 0
        total_chats = 0
        total_completions = 0
        
        # Previous week totals for growth calculation
        prev_week_total_lines = 0
        prev_week_total_chats = 0
        prev_week_total_completions = 0
        
        # Store weekly data for growth calculation
        user_weekly_data = {}
        
        for i, email in enumerate(all_emails):
            try:
                team_id_resolved, user_id = self.aggregator.resolve_email_to_userid(email)
                
                # Fetch current week stats
                try:
                    user_stats = await self.aggregator.aggregate_requests_for_user(
                        team_id=team_id_resolved,
                        user_id=user_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                except Exception as stats_error:
                    print(f"❌ Error fetching current week stats for {email}: {stats_error}")
                    continue
                
                # Fetch previous week stats for growth calculation
                try:
                    prev_week_stats = await self.aggregator.aggregate_requests_for_user(
                        team_id=team_id_resolved,
                        user_id=user_id,
                        start_date=prev_week_start,
                        end_date=prev_week_end
                    )
                except Exception as prev_stats_error:
                    print(f"❌ Error fetching previous week stats for {email}: {prev_stats_error}")
                    # Continue with zero previous week stats
                    prev_week_stats = {
                        'lines_of_agent_edits': 0,
                        'total_requests': 0,
                        'total_tabs_accepted': 0
                    }
                
                # Skip inactive users (no activity in either week)
                if (user_stats['total_requests'] == 0 and user_stats['lines_of_agent_edits'] == 0 and
                    prev_week_stats['total_requests'] == 0 and prev_week_stats['lines_of_agent_edits'] == 0):
                    continue
                
                # Extract name from email
                name = email.split('@')[0].replace('.', ' ').title()
                
                # 🐛 FIXED: Use real tab completions data instead of artificial minimums
                tab_completions = user_stats['total_tabs_accepted']  # Real data, no artificial minimum
                
                # Calculate agent growth (week-over-week lines of agent growth)
                current_lines = user_stats['lines_of_agent_edits']
                previous_lines = prev_week_stats['lines_of_agent_edits']
                
                if previous_lines > 0:
                    agent_growth = round(((current_lines - previous_lines) / previous_lines) * 100, 1)
                else:
                    # If no previous week activity but current week activity, it's new growth
                    agent_growth = 100.0 if current_lines > 0 else 0.0
                
                # 🐛 DEBUG: Print user statistics
                print(f"\n👤 DEBUG - {name} ({email}):")
                print(f"   Lines of Agent: {current_lines} (prev: {previous_lines})")
                print(f"   Chat Interactions: {user_stats['total_requests']}")
                print(f"   Tab Completions: {tab_completions} (REAL DATA)")
                print(f"   Agent Growth: {agent_growth}%")
                print(f"   Daily breakdown entries: {len(user_stats.get('daily_breakdown', []))}")
                
                user_data = {
                    "id": i + 1,
                    "name": name,
                    "avatar": "",
                    "email": email,
                    "linesOfAgent": user_stats['lines_of_agent_edits'],
                    "chats": user_stats['total_requests'],
                    "tabCompletions": tab_completions,
                    "agentGrowth": agent_growth
                }
                
                active_users.append(user_data)
                
                # Store weekly data for growth calculation
                user_weekly_data[name] = {
                    'current_week': user_stats['lines_of_agent_edits'],
                    'previous_week': prev_week_stats['lines_of_agent_edits']
                }
                
                # Use real daily breakdown data from the SDK
                daily_breakdown = user_stats.get('daily_breakdown', [])
                
                # 🐛 DEBUG: Print daily breakdown sample
                print(f"   📅 Daily breakdown sample:")
                for i, day in enumerate(daily_breakdown[:3]):  # Show first 3 days
                    print(f"      Day {i+1}: {day}")
                if len(daily_breakdown) > 3:
                    print(f"      ... and {len(daily_breakdown) - 3} more days")
                
                # Create maps of full dates to their daily values
                user_daily_lines = {}
                user_daily_chats = {}
                user_daily_completions = {}
                
                for daily_data in daily_breakdown:
                    try:
                        date_key = daily_data['date']  # Should be in YYYY-MM-DD format
                        user_daily_lines[date_key] = daily_data['lines_of_agent_edits']
                        user_daily_chats[date_key] = daily_data.get('total_chats', 0)
                        user_daily_completions[date_key] = daily_data.get('total_tabs_accepted', 0)
                    except KeyError as e:
                        print(f"      ⚠️  KeyError in daily data: {e}")
                        continue
                
                # 🐛 DEBUG: Print date matching
                print(f"   🔍 Date matching debug:")
                for idx, day_data in enumerate(weekly_data_by_user):
                    full_date = day_data['full_date']
                    lines_value = user_daily_lines.get(full_date, 0)
                    print(f"      {full_date}: {lines_value} lines")
                
                # Add real data to weekly structures using full date matching
                for idx, day_data in enumerate(weekly_data_by_user):
                    full_date = day_data['full_date']
                    day_data[name] = user_daily_lines.get(full_date, 0)
                    weekly_chats_by_user[idx][name] = user_daily_chats.get(full_date, 0)
                    weekly_completions_by_user[idx][name] = user_daily_completions.get(full_date, 0)
                
                # Accumulate totals
                total_lines += user_stats['lines_of_agent_edits']
                total_chats += user_stats['total_requests']
                total_completions += tab_completions
                
                # Accumulate previous week totals
                prev_week_total_lines += prev_week_stats['lines_of_agent_edits']
                prev_week_total_chats += prev_week_stats['total_requests']
                # 🐛 FIXED: Use real previous week tab completions
                prev_week_tab_completions = prev_week_stats['total_tabs_accepted']
                prev_week_total_completions += prev_week_tab_completions
                
                print(f"✅ {name}: {user_stats['lines_of_agent_edits']} lines (prev week: {prev_week_stats['lines_of_agent_edits']}), {user_stats['total_requests']} chats")
                    
            except Exception as e:
                print(f"❌ Error processing {email}: {e}")
                continue
        
        if not active_users:
            raise ValueError("No active users found in the specified time period.")
        
        # Sort by performance
        active_users.sort(key=lambda x: x['linesOfAgent'], reverse=True)
        
        # Generate growth metrics with real week-over-week data
        growth_metrics = []
        for user in active_users:
            name = user['name']
            if name in user_weekly_data:
                current_week = user_weekly_data[name]['current_week']
                previous_week = user_weekly_data[name]['previous_week']
                
                # Calculate growth percentage
                if previous_week > 0:
                    growth = ((current_week - previous_week) / previous_week) * 100
                else:
                    # If no previous week activity but current week activity, it's new growth
                    growth = 100.0 if current_week > 0 else 0.0
                
                growth_metrics.append({
                    "name": user['name'],
                    "currentWeek": current_week,
                    "previousWeek": previous_week,
                    "growth": round(growth, 1),
                    "avatar": ""
                })
        
        # Sort by growth percentage (highest first)
        growth_metrics.sort(key=lambda x: x['growth'], reverse=True)
        
        # 🐛 FIXED: Create weekly aggregate data using REAL daily totals instead of estimates
        weekly_data = []
        for idx, day_data in enumerate(weekly_data_by_user):
            # Sum REAL daily values for all users for this day
            day_total_lines = sum(day_data.get(user['name'], 0) for user in active_users)
            day_total_chats = sum(weekly_chats_by_user[idx].get(user['name'], 0) for user in active_users)
            day_total_completions = sum(weekly_completions_by_user[idx].get(user['name'], 0) for user in active_users)
            
            print(f"📊 Day {day_data['display']}: {day_total_lines} lines, {day_total_chats} chats, {day_total_completions} completions (REAL DATA)")
            
            weekly_data.append({
                "day": day_data['display'],  # Use display format with dates
                "chats": day_total_chats,  # REAL aggregated chats
                "tabCompletions": day_total_completions  # REAL aggregated completions
            })
        
        # 🐛 DEBUG: Print final summary
        print(f"\n📊 FINAL SUMMARY DEBUG:")
        print(f"   Active users: {len(active_users)}")
        print(f"   Total lines: {total_lines} (prev week: {prev_week_total_lines})")
        print(f"   Total chats: {total_chats} (prev week: {prev_week_total_chats})")
        print(f"   Total completions: {total_completions} (prev week: {prev_week_total_completions})")
        
        # Calculate pie chart values
        grand_total = total_completions + total_chats + total_lines
        if grand_total > 0:
            tab_pct = round((total_completions / grand_total) * 100, 1)
            chat_pct = round((total_chats / grand_total) * 100, 1)
            lines_pct = round((total_lines / grand_total) * 100, 1)
        else:
            tab_pct = chat_pct = lines_pct = 0.0
            
        print(f"   Pie chart percentages: Tab={tab_pct}%, Chat={chat_pct}%, Lines={lines_pct}%")
        
        # Calculate Persistent Daily Usage Leaderboard
        print(f"\n🏆 CALCULATING PERSISTENT USAGE LEADERBOARD...")
        persistent_leaderboard = []
        
        for user in active_users:
            name = user['name']
            
            # Find user's daily breakdown from the stored data
            user_daily_data = {}
            
            # Get the user's actual daily breakdown from their processed stats
            for i, email in enumerate(all_emails):
                user_name_from_email = email.split('@')[0].replace('.', ' ').title()
                if user_name_from_email == name:
                    # Find this user's aggregated stats to get daily breakdown
                    try:
                        team_id_resolved, user_id = self.aggregator.resolve_email_to_userid(email)
                        
                        # Re-fetch their daily breakdown for consistency analysis
                        user_stats_for_consistency = await self.aggregator.aggregate_requests_for_user(
                            team_id=team_id_resolved,
                            user_id=user_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        daily_breakdown = user_stats_for_consistency.get('daily_breakdown', [])
                        
                        # Calculate consistency metrics
                        total_days = days_back + 1  # Include today
                        active_days = 0
                        total_activity = 0
                        max_daily_activity = 0
                        daily_activities = []
                        
                        for daily_data in daily_breakdown:
                            lines_edited = daily_data.get('lines_of_agent_edits', 0)
                            daily_activity = (
                                daily_data.get('total_chats', 0) +
                                daily_data.get('total_tabs_accepted', 0) +
                                (lines_edited / 100)  # Scale down lines for balance
                            )
                            
                            daily_activities.append(daily_activity)
                            total_activity += daily_activity
                            
                            # Apply 500-line threshold for active day definition
                            if lines_edited >= 500:
                                active_days += 1
                                
                            if daily_activity > max_daily_activity:
                                max_daily_activity = daily_activity
                        
                        # Calculate consistency metrics
                        activity_ratio = active_days / total_days if total_days > 0 else 0
                        avg_daily_activity = total_activity / total_days if total_days > 0 else 0
                        
                        # Calculate activity variance (lower is more consistent)
                        if len(daily_activities) > 1:
                            mean_activity = sum(daily_activities) / len(daily_activities)
                            variance = sum((x - mean_activity) ** 2 for x in daily_activities) / len(daily_activities)
                            consistency_score = 1 / (1 + variance) if variance > 0 else 1.0
                        else:
                            consistency_score = 1.0 if daily_activities and daily_activities[0] > 0 else 0.0
                        
                        # Combined persistence score (weighted combination)
                        persistence_score = (
                            activity_ratio * 0.4 +  # 40% weight on daily consistency
                            min(avg_daily_activity / 20, 1.0) * 0.3 +  # 30% weight on activity level (capped)
                            consistency_score * 0.3  # 30% weight on activity consistency
                        ) * 100
                        
                        persistent_leaderboard.append({
                            "name": name,
                            "email": email,
                            "activeDays": active_days,
                            "totalDays": total_days,
                            "activityRatio": round(activity_ratio * 100, 1),
                            "avgDailyActivity": round(avg_daily_activity, 1),
                            "maxDailyActivity": round(max_daily_activity, 1),
                            "persistenceScore": round(persistence_score, 1),
                            "consistencyScore": round(consistency_score * 100, 1),
                            "totalActivity": round(total_activity, 1)
                        })
                        
                        print(f"   📊 {name}: {active_days}/{total_days} days with 500+ lines ({activity_ratio*100:.1f}%), "
                              f"avg daily: {avg_daily_activity:.1f}, persistence: {persistence_score:.1f}")
                        
                        break
                        
                    except Exception as e:
                        print(f"   ❌ Error calculating persistence for {name}: {e}")
                        continue
        
        # Sort by persistence score and take top 5
        persistent_leaderboard.sort(key=lambda x: x['persistenceScore'], reverse=True)
        top_persistent_users = persistent_leaderboard[:5]
        
        print(f"\n🏆 TOP 5 PERSISTENT DAILY USERS:")
        for i, user in enumerate(top_persistent_users, 1):
            print(f"   {i}. {user['name']}: {user['persistenceScore']}% persistence score "
                  f"({user['activeDays']}/{user['totalDays']} days active)")
        
        print(f"   Total users analyzed for persistence: {len(persistent_leaderboard)}")
        
        # Return data in the exact format expected by the HTML
        return {
            "users": active_users,
            "weeklyDataByUser": weekly_data_by_user,
            "weeklyChatsByUser": weekly_chats_by_user,
            "weeklyCompletionsByUser": weekly_completions_by_user,
            "userColors": user_colors[:len(active_users)] if len(active_users) <= len(user_colors) else user_colors * ((len(active_users) // len(user_colors)) + 1),
            "userMetrics": active_users,
            "growthMetrics": growth_metrics,
            "pieData": [
                {"name": "Tab Completions", "value": tab_pct, "color": "#8b5cf6"},
                {"name": "Chat Interactions", "value": chat_pct, "color": "#06b6d4"},
                {"name": "Lines of Agent", "value": lines_pct, "color": "#10b981"}
            ],
            "weeklyData": weekly_data,
            "totals": {
                "linesOfAgent": total_lines,
                "chats": total_chats,
                "tabCompletions": total_completions,
                "activeUsers": len(active_users),
                "linesGrowth": round(((total_lines - prev_week_total_lines) / prev_week_total_lines * 100) if prev_week_total_lines > 0 else 0, 1),
                "chatsGrowth": round(((total_chats - prev_week_total_chats) / prev_week_total_chats * 100) if prev_week_total_chats > 0 else 0, 1),
                "completionsGrowth": round(((total_completions - prev_week_total_completions) / prev_week_total_completions * 100) if prev_week_total_completions > 0 else 0, 1)
            },
            "dateRange": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "days": days_back
            },
            "persistentLeaderboard": top_persistent_users
        }
    
    def generate_html_with_data(self, data: Dict[str, Any]) -> str:
        """Generate HTML dashboard with real data embedded."""
        
        # Use embedded template instead of reading from file
        html_content = self._generate_template_inline()
        
        # Replace the sample data with real data
        sample_data_start = html_content.find("const dashboardData = {")
        sample_data_end = html_content.find("};", sample_data_start) + 2
        
        if sample_data_start == -1:
            raise ValueError("Could not find dashboard data in template")
        
        # Create new data block
        real_data_json = json.dumps(data, indent=12)
        new_data_block = f"const dashboardData = {real_data_json};"
        
        # Replace the data
        new_html = (
            html_content[:sample_data_start] + 
            new_data_block + 
            html_content[sample_data_end:]
        )
        
        # Update the title to indicate real data
        new_html = new_html.replace(
            "<title>Cursor Analytics Dashboard</title>",
            f"<title>Cursor Analytics Dashboard - Live Data ({data['dateRange']['start']} to {data['dateRange']['end']})</title>"
        )
        
        # Add real data indicator in header
        new_html = new_html.replace(
            "<p class=\"text-sm text-muted-foreground\">Monitor your team's usage and productivity</p>",
            f"<p class=\"text-sm text-muted-foreground\">Live data from {data['dateRange']['start']} to {data['dateRange']['end']} • {data['totals']['activeUsers']} active users</p>"
        )
        
        return new_html
    
    def _generate_template_inline(self) -> str:
        """Embedded HTML template for self-contained dashboard generation."""
        return '''<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cursor Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --background: 0 0% 100%;
            --foreground: 0 0% 3.9%;
            --card: 0 0% 100%;
            --card-foreground: 0 0% 3.9%;
            --popover: 0 0% 100%;
            --popover-foreground: 0 0% 3.9%;
            --primary: 0 0% 9%;
            --primary-foreground: 0 0% 98%;
            --secondary: 0 0% 96.1%;
            --secondary-foreground: 0 0% 9%;
            --muted: 0 0% 96.1%;
            --muted-foreground: 0 0% 45.1%;
            --accent: 0 0% 96.1%;
            --accent-foreground: 0 0% 9%;
            --destructive: 0 84.2% 60.2%;
            --destructive-foreground: 0 0% 98%;
            --border: 0 0% 89.8%;
            --input: 0 0% 89.8%;
            --ring: 0 0% 3.9%;
            --radius: 0.5rem;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: hsl(var(--background));
            color: hsl(var(--foreground));
            min-height: 100vh;
        }
        
        /* Utility Classes */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }
        
        .flex {
            display: flex;
        }
        
        .items-center {
            align-items: center;
        }
        
        .justify-between {
            justify-content: space-between;
        }
        
        .gap-2 {
            gap: 0.5rem;
        }
        
        .gap-3 {
            gap: 0.75rem;
        }
        
        .gap-4 {
            gap: 1rem;
        }
        
        .gap-6 {
            gap: 1.5rem;
        }
        
        .text-sm {
            font-size: 0.875rem;
            line-height: 1.25rem;
        }
        
        .text-xs {
            font-size: 0.75rem;
            line-height: 1rem;
        }
        
        .text-lg {
            font-size: 1.125rem;
            line-height: 1.75rem;
        }
        
        .text-2xl {
            font-size: 1.5rem;
            line-height: 2rem;
        }
        
        .font-semibold {
            font-weight: 600;
        }
        
        .font-medium {
            font-weight: 500;
        }
        
        .font-bold {
            font-weight: 700;
        }
        
        .text-muted-foreground {
            color: hsl(var(--muted-foreground));
        }
        
        .text-green-600 {
            color: #059669;
        }
        
        .text-red-600 {
            color: #dc2626;
        }
        
        .text-green-500 {
            color: #10b981;
        }
        
        .text-yellow-500 {
            color: #f59e0b;
        }
        
        .text-green-700 {
            color: #047857;
        }
        
        /* Header */
        .header {
            border-bottom: 1px solid hsl(var(--border));
            background: hsl(var(--background) / 0.95);
            backdrop-filter: blur(8px);
        }
        
        .header-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 4rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            background: hsl(var(--primary));
            color: hsl(var(--primary-foreground));
            border-radius: var(--radius);
        }
        
        /* Grid System */
        .grid {
            display: grid;
            gap: 1rem;
        }
        
        .grid-cols-4 {
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        }
        
        .grid-cols-3 {
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        }
        
        .grid-cols-2 {
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        }
        
        .col-span-2 {
            grid-column: span 2;
        }
        
        /* Cards */
        .card {
            background: hsl(var(--card));
            border: 1px solid hsl(var(--border));
            border-radius: var(--radius);
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        }
        
        .card-header {
            padding: 1.5rem 1.5rem 0;
            display: flex;
            flex-direction: column;
            space-between: 0;
        }
        
        .card-content {
            padding: 1.5rem;
        }
        
        .card-title {
            font-weight: 600;
            line-height: 1;
            tracking-tight;
            margin: 0;
        }
        
        .card-description {
            color: hsl(var(--muted-foreground));
            margin: 0;
        }
        
        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius);
            font-size: 0.875rem;
            font-weight: 500;
            transition: colors 0.2s;
            cursor: pointer;
            border: 1px solid transparent;
            padding: 0.5rem 1rem;
        }
        
        .btn-outline {
            border: 1px solid hsl(var(--border));
            background: hsl(var(--background));
            color: hsl(var(--foreground));
        }
        
        .btn-outline:hover {
            background: hsl(var(--accent));
            color: hsl(var(--accent-foreground));
        }
        
        .btn-sm {
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
        }
        
        /* Tabs */
        .tabs {
            width: 100%;
        }
        
        .tabs-list {
            display: inline-flex;
            height: 2.5rem;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius);
            background: hsl(var(--muted));
            padding: 0.25rem;
            color: hsl(var(--muted-foreground));
        }
        
        .tabs-trigger {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
            border-radius: calc(var(--radius) - 2px);
            padding: 0.375rem 0.75rem;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
            background: transparent;
            color: inherit;
        }
        
        .tabs-trigger.active {
            background: hsl(var(--background));
            color: hsl(var(--foreground));
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        }
        
        .tabs-content {
            margin-top: 1rem;
            display: none;
        }
        
        .tabs-content.active {
            display: block;
        }
        
        /* Avatar */
        .avatar {
            position: relative;
            display: flex;
            height: 2rem;
            width: 2rem;
            flex-shrink: 0;
            overflow: hidden;
            border-radius: 50%;
        }
        
        .avatar-fallback {
            display: flex;
            height: 100%;
            width: 100%;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: hsl(var(--muted));
            color: hsl(var(--muted-foreground));
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        /* Badge */
        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: calc(var(--radius) - 2px);
            padding: 0.125rem 0.625rem;
            font-size: 0.75rem;
            font-weight: 600;
            line-height: 1;
            transition: colors 0.2s;
        }
        
        .badge-secondary {
            background: hsl(var(--secondary));
            color: hsl(var(--secondary-foreground));
        }
        
        .badge-outline {
            color: hsl(var(--foreground));
            border: 1px solid hsl(var(--border));
        }
        
        .badge-success {
            background: #dcfce7;
            color: #166534;
        }
        
        .badge-warning {
            background: #fef3c7;
            color: #92400e;
        }
        
        .badge-info {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .badge-muted {
            background: #f3f4f6;
            color: #6b7280;
        }
        
        .cursor-help {
            cursor: help;
        }
        
        /* Chart Container */
        .chart-container {
            position: relative;
            height: 300px;
            width: 100%;
        }
        
        .chart-container-small {
            position: relative;
            height: 200px;
            width: 100%;
        }
        
        /* Table */
        .table {
            width: 100%;
            caption-side: bottom;
            font-size: 0.875rem;
            border-collapse: collapse;
        }
        
        .table th {
            height: 3rem;
            padding: 0.75rem;
            text-align: left;
            vertical-align: middle;
            font-weight: 500;
            color: hsl(var(--muted-foreground));
            border-bottom: 1px solid hsl(var(--border));
        }
        
        .table td {
            padding: 0.75rem;
            vertical-align: middle;
            border-bottom: 1px solid hsl(var(--border));
        }
        
        .table .text-right {
            text-align: right;
        }
        
        .font-mono {
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
        }
        
        /* User Filter Checkboxes */
        .user-checkbox {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
        }
        
        .user-color {
            width: 0.75rem;
            height: 0.75rem;
            border-radius: 50%;
        }
        
        /* Leaderboard */
        .leaderboard-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 1rem 0;
            border-bottom: 1px solid hsl(var(--border));
        }
        
        .leaderboard-item:last-child {
            border-bottom: none;
        }
        
        .rank-badge {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            font-weight: 600;
            font-size: 0.875rem;
        }
        
        .rank-badge-muted {
            background: hsl(var(--muted));
            color: hsl(var(--muted-foreground));
        }
        
        .rank-badge-gradient {
            background: linear-gradient(135deg, #10b981, #34d399);
            color: white;
        }
        
        .rank-badge-orange {
            background: linear-gradient(135deg, #f59e0b, #fbbf24);
            color: white;
        }
        
        .user-info {
            flex: 1;
            min-width: 0;
        }
        
        .truncate {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        /* Utilities */
        .space-y-4 > * + * {
            margin-top: 1rem;
        }
        
        .space-y-6 > * + * {
            margin-top: 1.5rem;
        }
        
        .min-w-0 {
            min-width: 0;
        }
        
        .flex-1 {
            flex: 1 1 0%;
        }
        
        .flex-wrap {
            flex-wrap: wrap;
        }
        
        .overflow-x-auto {
            overflow-x: auto;
        }
        
        /* Icon placeholders */
        .icon {
            width: 1rem;
            height: 1rem;
        }
        
        .icon-lg {
            width: 1.25rem;
            height: 1.25rem;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .col-span-2 {
                grid-column: span 1;
            }
            
            .grid-cols-3 {
                grid-template-columns: 1fr;
            }
        }
        
        @media (max-width: 768px) {
            .grid-cols-4 {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }
            
            .grid-cols-2 {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div class="flex items-center gap-2">
                    <div class="logo">
                        <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M16 18L22 12L16 6L14.59 7.41L19.17 12L14.59 16.59L16 18ZM8 6L2 12L8 18L9.41 16.59L4.83 12L9.41 7.41L8 6Z"/>
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-lg font-semibold">Cursor Analytics Dashboard</h1>
                        <p class="text-sm text-muted-foreground">Monitor your team's usage and productivity</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button class="btn btn-outline btn-sm" onclick="exportData()">
                        Export Data
                    </button>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container" style="padding: 1.5rem 1rem;">
        <div class="space-y-6">
            <!-- Key Metrics -->
            <div class="grid grid-cols-4 gap-4">
                <div class="card">
                    <div class="card-header">
                        <div class="flex items-center justify-between">
                            <h3 class="card-title text-sm font-medium">Total Lines of Agent</h3>
                            <svg class="icon text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="16,18 22,12 16,6"></polyline>
                                <polyline points="8,6 2,12 8,18"></polyline>
                            </svg>
                        </div>
                    </div>
                    <div class="card-content" style="padding-top: 0;">
                        <div class="text-2xl font-bold" id="total-lines">34,600</div>
                        <p class="text-xs text-muted-foreground">
                            <span id="lines-growth" class="font-medium">+0.0%</span> from last week
                        </p>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <div class="flex items-center justify-between">
                            <h3 class="card-title text-sm font-medium">Chat Interactions</h3>
                            <svg class="icon text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15A2 2 0 0 1 19 17H7L4 20V6A2 2 0 0 1 6 4H19A2 2 0 0 1 21 6Z"></path>
                            </svg>
                        </div>
                    </div>
                    <div class="card-content" style="padding-top: 0;">
                        <div class="text-2xl font-bold" id="total-chats">925</div>
                        <p class="text-xs text-muted-foreground">
                            <span id="chats-growth" class="font-medium">+0.0%</span> from last week
                        </p>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <div class="flex items-center justify-between">
                            <h3 class="card-title text-sm font-medium">Tab Completions</h3>
                            <svg class="icon text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"></polyline>
                            </svg>
                        </div>
                    </div>
                    <div class="card-content" style="padding-top: 0;">
                        <div class="text-2xl font-bold" id="total-completions">7,520</div>
                        <p class="text-xs text-muted-foreground">
                            <span id="completions-growth" class="font-medium">+0.0%</span> from last week
                        </p>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <div class="flex items-center justify-between">
                            <h3 class="card-title text-sm font-medium">Active Users</h3>
                            <svg class="icon text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M17 21V19A4 4 0 0 0 13 15H5A4 4 0 0 0 1 19V21"></path>
                                <circle cx="9" cy="7" r="4"></circle>
                                <path d="M23 21V19A4 4 0 0 0 16.5 15.5L16 15.5"></path>
                                <path d="M16 3.13A4 4 0 0 1 16 11"></path>
                            </svg>
                        </div>
                    </div>
                    <div class="card-content" style="padding-top: 0;">
                        <div class="text-2xl font-bold" id="active-users">5</div>
                        <p class="text-xs text-muted-foreground">All users active this week</p>
                    </div>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="grid grid-cols-3 gap-6">
                <!-- Weekly Trends -->
                <div class="card col-span-2">
                    <div class="card-header">
                        <h3 class="card-title">Weekly Activity Trends</h3>
                        <p class="card-description">Track your team's productivity across different metrics</p>
                    </div>
                    <div class="card-content">
                        <div class="tabs">
                            <div class="tabs-list">
                                <button class="tabs-trigger active" onclick="switchTab('lines')">Lines of Agent</button>
                                <button class="tabs-trigger" onclick="switchTab('chats')">Chat Interactions</button>
                                <button class="tabs-trigger" onclick="switchTab('completions')">Tab Completions</button>
                            </div>
                            
                            <div id="tab-lines" class="tabs-content active">
                                <div class="space-y-4">
                                    <div class="flex items-center gap-2">
                                        <button class="btn btn-outline btn-sm" onclick="selectAllUsers()">Select All</button>
                                        <button class="btn btn-outline btn-sm" onclick="deselectAllUsers()">Deselect All</button>
                                        <span class="text-sm text-muted-foreground">
                                            <span id="selected-count">5</span> of <span id="total-users">5</span> users selected
                                        </span>
                                    </div>
                                    <div class="flex flex-wrap gap-2" id="user-checkboxes">
                                        <!-- User checkboxes will be populated by JavaScript -->
                                    </div>
                                </div>
                                <div class="chart-container">
                                    <canvas id="linesChart"></canvas>
                                </div>
                            </div>
                            
                            <div id="tab-chats" class="tabs-content">
                                <div class="space-y-4">
                                    <div class="flex items-center gap-2">
                                        <button class="btn btn-outline btn-sm" onclick="selectAllUsers()">Select All</button>
                                        <button class="btn btn-outline btn-sm" onclick="deselectAllUsers()">Deselect All</button>
                                        <span class="text-sm text-muted-foreground">
                                            <span id="selected-count-chats">5</span> of <span id="total-users-chats">5</span> users selected
                                        </span>
                                    </div>
                                    <div class="flex flex-wrap gap-2" id="user-checkboxes-chats">
                                        <!-- User checkboxes will be populated by JavaScript -->
                                    </div>
                                </div>
                                <div class="chart-container">
                                    <canvas id="chatsChart"></canvas>
                                </div>
                            </div>
                            
                            <div id="tab-completions" class="tabs-content">
                                <div class="space-y-4">
                                    <div class="flex items-center gap-2">
                                        <button class="btn btn-outline btn-sm" onclick="selectAllUsers()">Select All</button>
                                        <button class="btn btn-outline btn-sm" onclick="deselectAllUsers()">Deselect All</button>
                                        <span class="text-sm text-muted-foreground">
                                            <span id="selected-count-completions">5</span> of <span id="total-users-completions">5</span> users selected
                                        </span>
                                    </div>
                                    <div class="flex flex-wrap gap-2" id="user-checkboxes-completions">
                                        <!-- User checkboxes will be populated by JavaScript -->
                                    </div>
                                </div>
                                <div class="chart-container">
                                    <canvas id="completionsChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Top Performers -->
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title flex items-center gap-2">
                            <svg class="icon-lg text-yellow-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path>
                                <path d="M14 9h1.5a2.5 2.5 0 0 1 0 5H14"></path>
                                <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"></path>
                                <path d="M6 2h12"></path>
                            </svg>
                            Top Performers
                        </h3>
                        <p class="card-description">Ranked by lines of agent code generated</p>
                    </div>
                    <div class="card-content">
                        <div class="space-y-4" id="top-performers">
                            <!-- Top performers will be populated by JavaScript -->
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-6">
                <!-- Persistent Usage Leaderboard -->
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">
                            Persistent Usage Champions
                        </h3>
                        <p class="card-description">Top 5 most consistent daily Cursor users (500+ lines/day required)</p>
                    </div>
                    <div class="card-content">
                        <div class="space-y-4" id="persistent-leaderboard">
                            <!-- Persistent leaderboard will be populated by JavaScript -->
                        </div>
                    </div>
                </div>

                <!-- Growth Leaderboard -->
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title flex items-center gap-2">
                            <svg class="icon-lg text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 3L21 21"></path>
                                <path d="M14 4L20 10"></path>
                                <path d="M17 7L17 13 11 13"></path>
                            </svg>
                            Growth Leaderboard
                        </h3>
                        <p class="card-description">Most distinguished growth from previous week</p>
                    </div>
                    <div class="card-content">
                        <div class="space-y-4" id="growth-leaderboard">
                            <!-- Growth leaderboard will be populated by JavaScript -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Usage Distribution (Stretched Horizontally) -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Usage Distribution</h3>
                    <p class="card-description">How your team uses Cursor features</p>
                </div>
                <div class="card-content">
                    <div class="chart-container">
                        <canvas id="usageChart"></canvas>
                    </div>
                    <div style="margin-top: 1rem;" id="usage-legend">
                        <!-- Legend will be populated by JavaScript -->
                    </div>
                </div>
            </div>

            <!-- Detailed User Metrics -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">User Performance Details</h3>
                    <p class="card-description">Comprehensive view of each team member's activity</p>
                </div>
                <div class="card-content">
                    <div class="overflow-x-auto">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th class="text-right">Lines of Agent</th>
                                    <th class="text-right">Chat Interactions</th>
                                    <th class="text-right">Tab Completions</th>
                                    <th class="text-right">Agent Accepted Lines Growth</th>
                                </tr>
                            </thead>
                            <tbody id="user-table">
                                <!-- Table rows will be populated by JavaScript -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        // Dashboard data matching the reference design exactly
        const dashboardData = {
            users: [
                { id: 1, name: "Alex Chen", avatar: "", email: "alex@company.com" },
                { id: 2, name: "Sarah Johnson", avatar: "", email: "sarah@company.com" },
                { id: 3, name: "Mike Rodriguez", avatar: "", email: "mike@company.com" },
                { id: 4, name: "Emily Davis", avatar: "", email: "emily@company.com" },
                { id: 5, name: "David Kim", avatar: "", email: "david@company.com" },
            ],
            weeklyDataByUser: [
                { day: "Mon", display: "Mon\\n06/28", "Alex Chen": 280, "Sarah Johnson": 240, "Mike Rodriguez": 220, "Emily Davis": 200, "David Kim": 260 },
                { day: "Tue", display: "Tue\\n06/29", "Alex Chen": 420, "Sarah Johnson": 380, "Mike Rodriguez": 340, "Emily Davis": 320, "David Kim": 340 },
                { day: "Wed", display: "Wed\\n06/30", "Alex Chen": 380, "Sarah Johnson": 320, "Mike Rodriguez": 300, "Emily Davis": 280, "David Kim": 320 },
                { day: "Thu", display: "Thu\\n07/01", "Alex Chen": 520, "Sarah Johnson": 460, "Mike Rodriguez": 420, "Emily Davis": 380, "David Kim": 440 },
                { day: "Fri", display: "Fri\\n07/02", "Alex Chen": 450, "Sarah Johnson": 400, "Mike Rodriguez": 360, "Emily Davis": 340, "David Kim": 350 },
                { day: "Sat", display: "Sat\\n07/03", "Alex Chen": 180, "Sarah Johnson": 160, "Mike Rodriguez": 140, "Emily Davis": 120, "David Kim": 200 },
                { day: "Sun", display: "Sun\\n07/04", "Alex Chen": 140, "Sarah Johnson": 120, "Mike Rodriguez": 100, "Emily Davis": 80, "David Kim": 160 }
            ],
            weeklyChatsByUser: [
                { day: "Mon", display: "Mon\\n06/28", "Alex Chen": 12, "Sarah Johnson": 8, "Mike Rodriguez": 15, "Emily Davis": 10, "David Kim": 18 },
                { day: "Tue", display: "Tue\\n06/29", "Alex Chen": 15, "Sarah Johnson": 10, "Mike Rodriguez": 12, "Emily Davis": 8, "David Kim": 20 },
                { day: "Wed", display: "Wed\\n06/30", "Alex Chen": 18, "Sarah Johnson": 14, "Mike Rodriguez": 16, "Emily Davis": 12, "David Kim": 22 },
                { day: "Thu", display: "Thu\\n07/01", "Alex Chen": 14, "Sarah Johnson": 16, "Mike Rodriguez": 18, "Emily Davis": 15, "David Kim": 19 },
                { day: "Fri", display: "Fri\\n07/02", "Alex Chen": 20, "Sarah Johnson": 12, "Mike Rodriguez": 14, "Emily Davis": 18, "David Kim": 25 },
                { day: "Sat", display: "Sat\\n07/03", "Alex Chen": 8, "Sarah Johnson": 6, "Mike Rodriguez": 10, "Emily Davis": 5, "David Kim": 12 },
                { day: "Sun", display: "Sun\\n07/04", "Alex Chen": 10, "Sarah Johnson": 8, "Mike Rodriguez": 12, "Emily Davis": 7, "David Kim": 14 }
            ],
            weeklyCompletionsByUser: [
                { day: "Mon", display: "Mon\\n06/28", "Alex Chen": 450, "Sarah Johnson": 380, "Mike Rodriguez": 420, "Emily Davis": 350, "David Kim": 480 },
                { day: "Tue", display: "Tue\\n06/29", "Alex Chen": 480, "Sarah Johnson": 400, "Mike Rodriguez": 440, "Emily Davis": 380, "David Kim": 500 },
                { day: "Wed", display: "Wed\\n06/30", "Alex Chen": 520, "Sarah Johnson": 420, "Mike Rodriguez": 460, "Emily Davis": 400, "David Kim": 540 },
                { day: "Thu", display: "Thu\\n07/01", "Alex Chen": 460, "Sarah Johnson": 440, "Mike Rodriguez": 480, "Emily Davis": 420, "David Kim": 520 },
                { day: "Fri", display: "Fri\\n07/02", "Alex Chen": 550, "Sarah Johnson": 400, "Mike Rodriguez": 450, "Emily Davis": 480, "David Kim": 580 },
                { day: "Sat", display: "Sat\\n07/03", "Alex Chen": 200, "Sarah Johnson": 180, "Mike Rodriguez": 220, "Emily Davis": 150, "David Kim": 250 },
                { day: "Sun", display: "Sun\\n07/04", "Alex Chen": 250, "Sarah Johnson": 200, "Mike Rodriguez": 280, "Emily Davis": 180, "David Kim": 300 }
            ],
            userColors: ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"],
            userMetrics: [
                { name: "Alex Chen", linesOfAgent: 8500, chats: 234, tabCompletions: 1850, agentGrowth: 15.2 },
                { name: "Sarah Johnson", linesOfAgent: 7200, chats: 198, tabCompletions: 1620, agentGrowth: -5.1 },
                { name: "Mike Rodriguez", linesOfAgent: 6800, chats: 176, tabCompletions: 1480, agentGrowth: 22.3 },
                { name: "Emily Davis", linesOfAgent: 6200, chats: 165, tabCompletions: 1320, agentGrowth: 8.7 },
                { name: "David Kim", linesOfAgent: 5900, chats: 152, tabCompletions: 1250, agentGrowth: -12.4 },
            ],
            growthMetrics: [
                { name: "Emily Davis", currentWeek: 6200, previousWeek: 4800, growth: 29.2 },
                { name: "David Kim", currentWeek: 5900, previousWeek: 4700, growth: 25.5 },
                { name: "Mike Rodriguez", currentWeek: 6800, previousWeek: 5600, growth: 21.4 },
                { name: "Sarah Johnson", currentWeek: 7200, previousWeek: 6100, growth: 18.0 },
                { name: "Alex Chen", currentWeek: 8500, previousWeek: 7800, growth: 9.0 },
            ],
            pieData: [
                { name: "Tab Completions", value: 65, color: "#8b5cf6" },
                { name: "Chat Interactions", value: 25, color: "#06b6d4" },
                { name: "Manual Coding", value: 10, color: "#10b981" },
            ],
            weeklyData: [
                { day: "Mon", chats: 280, tabCompletions: 240 },
                { day: "Tue", chats: 420, tabCompletions: 380 },
                { day: "Wed", chats: 380, tabCompletions: 320 },
                { day: "Thu", chats: 520, tabCompletions: 460 },
                { day: "Fri", chats: 450, tabCompletions: 400 },
                { day: "Sat", chats: 180, tabCompletions: 160 },
                { day: "Sun", chats: 140, tabCompletions: 120 },
            ],
            totals: {
                linesOfAgent: 34600,
                chats: 925,
                tabCompletions: 7520,
                activeUsers: 5
            },
            persistentLeaderboard: [
                { name: "Alex Chen", email: "alex@company.com", activeDays: 6, totalDays: 7, activityRatio: 85.7, avgDailyActivity: 45.8, persistenceScore: 85.2, consistencyScore: 87.3 },
                { name: "Sarah Johnson", email: "sarah@company.com", activeDays: 5, totalDays: 7, activityRatio: 71.4, avgDailyActivity: 38.2, persistenceScore: 72.1, consistencyScore: 78.9 },
                { name: "Mike Rodriguez", email: "mike@company.com", activeDays: 5, totalDays: 7, activityRatio: 71.4, avgDailyActivity: 35.6, persistenceScore: 69.4, consistencyScore: 72.1 },
                { name: "Emily Davis", email: "emily@company.com", activeDays: 4, totalDays: 7, activityRatio: 57.1, avgDailyActivity: 32.1, persistenceScore: 58.8, consistencyScore: 65.2 },
                { name: "David Kim", email: "david@company.com", activeDays: 3, totalDays: 7, activityRatio: 42.9, avgDailyActivity: 28.7, persistenceScore: 45.3, consistencyScore: 58.1 }
            ]
        };
        
        let selectedUsers = [];
        let linesChart = null;
        let chatsChart = null;
        let completionsChart = null;
        
        // Initialize dashboard
        function initDashboard() {
            selectedUsers = dashboardData.userMetrics.map(user => user.name);
            updateMetrics();
            populateUserFilters();
            createCharts();
            populateLeaderboards();
            populateUserTable();
        }
        
        function updateMetrics() {
            document.getElementById('total-lines').textContent = dashboardData.totals.linesOfAgent.toLocaleString();
            document.getElementById('total-chats').textContent = dashboardData.totals.chats.toLocaleString();
            document.getElementById('total-completions').textContent = dashboardData.totals.tabCompletions.toLocaleString();
            document.getElementById('active-users').textContent = dashboardData.totals.activeUsers.toString();
            
            // Update growth percentages
            if (dashboardData.totals.linesGrowth !== undefined) {
                const linesGrowthEl = document.getElementById('lines-growth');
                if (linesGrowthEl) {
                    const growth = dashboardData.totals.linesGrowth;
                    linesGrowthEl.textContent = (growth >= 0 ? '+' : '') + growth + '%';
                    linesGrowthEl.className = 'font-medium ' + (growth >= 0 ? 'text-green-600' : 'text-red-600');
                }
            }
            
            if (dashboardData.totals.chatsGrowth !== undefined) {
                const chatsGrowthEl = document.getElementById('chats-growth');
                if (chatsGrowthEl) {
                    const growth = dashboardData.totals.chatsGrowth;
                    chatsGrowthEl.textContent = (growth >= 0 ? '+' : '') + growth + '%';
                    chatsGrowthEl.className = 'font-medium ' + (growth >= 0 ? 'text-green-600' : 'text-red-600');
                }
            }
            
            if (dashboardData.totals.completionsGrowth !== undefined) {
                const completionsGrowthEl = document.getElementById('completions-growth');
                if (completionsGrowthEl) {
                    const growth = dashboardData.totals.completionsGrowth;
                    completionsGrowthEl.textContent = (growth >= 0 ? '+' : '') + growth + '%';
                    completionsGrowthEl.className = 'font-medium ' + (growth >= 0 ? 'text-green-600' : 'text-red-600');
                }
            }
        }
        
        function populateUserFilters() {
            // Populate checkboxes for all three tabs
            const containers = [
                'user-checkboxes',
                'user-checkboxes-chats', 
                'user-checkboxes-completions'
            ];
            
            containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                if (container) {
                    container.innerHTML = ''; // Clear existing content
                    
                    dashboardData.userMetrics.forEach((user, index) => {
                        const label = document.createElement('label');
                        label.className = 'user-checkbox';
                        label.innerHTML = `
                            <input type="checkbox" checked onchange="toggleUser('${user.name}')">
                            <div class="flex items-center gap-2">
                                <div class="user-color" style="background-color: ${dashboardData.userColors[index]}"></div>
                                <span class="text-sm">${user.name}</span>
                            </div>
                        `;
                        container.appendChild(label);
                    });
                }
            });
            
            updateSelectedCount();
        }
        
        function toggleUser(userName) {
            const index = selectedUsers.indexOf(userName);
            if (index > -1) {
                selectedUsers.splice(index, 1);
            } else {
                selectedUsers.push(userName);
            }
            updateSelectedCount();
            updateLinesChart();
            updateChatsChart();
            updateCompletionsChart();
        }
        
        function selectAllUsers() {
            selectedUsers = dashboardData.userMetrics.map(user => user.name);
            updateCheckboxes();
            updateSelectedCount();
            updateLinesChart();
            updateChatsChart();
            updateCompletionsChart();
        }
        
        function deselectAllUsers() {
            selectedUsers = [];
            updateCheckboxes();
            updateSelectedCount();
            updateLinesChart();
            updateChatsChart();
            updateCompletionsChart();
        }
        
        function updateCheckboxes() {
            // Update checkboxes in all three containers
            const containers = [
                'user-checkboxes',
                'user-checkboxes-chats', 
                'user-checkboxes-completions'
            ];
            
            containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                if (container) {
                    const checkboxes = container.querySelectorAll('.user-checkbox input');
                    checkboxes.forEach((checkbox, index) => {
                        if (index < dashboardData.userMetrics.length) {
                            const userName = dashboardData.userMetrics[index].name;
                            checkbox.checked = selectedUsers.includes(userName);
                        }
                    });
                }
            });
        }
        
        function updateSelectedCount() {
            const selectedCount = selectedUsers.length;
            const totalCount = dashboardData.userMetrics.length;
            
            // Update counts for all tabs
            const countIds = [
                'selected-count',
                'selected-count-chats',
                'selected-count-completions'
            ];
            
            const totalIds = [
                'total-users',
                'total-users-chats',
                'total-users-completions'
            ];
            
            countIds.forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = selectedCount;
            });
            
            totalIds.forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = totalCount;
            });
        }
        
        function createCharts() {
            createLinesChart();
            createChatsChart();
            createCompletionsChart();
            createUsageChart();
        }
        
        function createLinesChart() {
            const ctx = document.getElementById('linesChart').getContext('2d');
            
            const datasets = dashboardData.userMetrics.map((user, index) => ({
                label: user.name,
                data: dashboardData.weeklyDataByUser.map(day => day[user.name] || 0),
                borderColor: dashboardData.userColors[index],
                backgroundColor: dashboardData.userColors[index] + '20',
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                hidden: !selectedUsers.includes(user.name)
            }));
            
            linesChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dashboardData.weeklyDataByUser.map(day => day.display),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }
        
        function updateLinesChart() {
            if (linesChart) {
                linesChart.data.datasets.forEach((dataset, index) => {
                    const userName = dashboardData.userMetrics[index].name;
                    dataset.hidden = !selectedUsers.includes(userName);
                });
                linesChart.update();
            }
        }
        
        function updateChatsChart() {
            if (chatsChart) {
                chatsChart.data.datasets.forEach((dataset, index) => {
                    const userName = dashboardData.userMetrics[index].name;
                    dataset.hidden = !selectedUsers.includes(userName);
                });
                chatsChart.update();
            }
        }
        
        function updateCompletionsChart() {
            if (completionsChart) {
                completionsChart.data.datasets.forEach((dataset, index) => {
                    const userName = dashboardData.userMetrics[index].name;
                    dataset.hidden = !selectedUsers.includes(userName);
                });
                completionsChart.update();
            }
        }
        
        function createChatsChart() {
            const ctx = document.getElementById('chatsChart').getContext('2d');
            
            const datasets = dashboardData.userMetrics.map((user, index) => ({
                label: user.name,
                data: dashboardData.weeklyChatsByUser.map(day => day[user.name] || 0),
                borderColor: dashboardData.userColors[index],
                backgroundColor: dashboardData.userColors[index] + '20',
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                hidden: !selectedUsers.includes(user.name)
            }));
            
            chatsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dashboardData.weeklyChatsByUser.map(day => day.display),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }
        
        function createCompletionsChart() {
            const ctx = document.getElementById('completionsChart').getContext('2d');
            
            const datasets = dashboardData.userMetrics.map((user, index) => ({
                label: user.name,
                data: dashboardData.weeklyCompletionsByUser.map(day => day[user.name] || 0),
                borderColor: dashboardData.userColors[index],
                backgroundColor: dashboardData.userColors[index] + '20',
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                hidden: !selectedUsers.includes(user.name)
            }));
            
            completionsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dashboardData.weeklyCompletionsByUser.map(day => day.display),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }
        
        function createUsageChart() {
            const ctx = document.getElementById('usageChart').getContext('2d');
            
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: dashboardData.pieData.map(item => item.name),
                    datasets: [{
                        data: dashboardData.pieData.map(item => item.value),
                        backgroundColor: dashboardData.pieData.map(item => item.color),
                        borderWidth: 0,
                        cutout: '60%'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
            
            // Create custom legend
            const legendContainer = document.getElementById('usage-legend');
            dashboardData.pieData.forEach(item => {
                const legendItem = document.createElement('div');
                legendItem.className = 'flex items-center justify-between';
                legendItem.style.marginBottom = '0.5rem';
                legendItem.innerHTML = `
                    <div class="flex items-center gap-2">
                        <div class="user-color" style="background-color: ${item.color}"></div>
                        <span class="text-sm">${item.name}</span>
                    </div>
                    <span class="text-sm font-medium">${item.value}%</span>
                `;
                legendContainer.appendChild(legendItem);
            });
        }
        
        function populateLeaderboards() {
            populateTopPerformers();
            populateGrowthLeaderboard();
            populatePersistentLeaderboard();
        }
        
        function populateTopPerformers() {
            const container = document.getElementById('top-performers');
            // Only show top 5 performers
            const topUsers = dashboardData.userMetrics.slice(0, 5);
            
            topUsers.forEach((user, index) => {
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                
                const tooltipContent = `Overall Performance Metrics:
Lines of Agent: ${user.linesOfAgent.toLocaleString()}
Chat Interactions: ${user.chats.toLocaleString()}
Tab Completions: ${user.tabCompletions.toLocaleString()}
Agent Growth: ${user.agentGrowth >= 0 ? '+' : ''}${user.agentGrowth}%

Ranked by total lines of agent-assisted code edited`;
                
                item.innerHTML = `
                    <div class="rank-badge rank-badge-muted" title="${tooltipContent}">${index + 1}</div>
                    <div class="avatar" title="${tooltipContent}">
                        <div class="avatar-fallback">
                            ${user.name.split(' ').map(n => n[0]).join('')}
                        </div>
                    </div>
                    <div class="user-info" title="${tooltipContent}">
                        <p class="text-sm font-medium truncate">${user.name}</p>
                        <p class="text-xs text-muted-foreground">${user.linesOfAgent.toLocaleString()} lines</p>
                    </div>
                `;
                container.appendChild(item);
            });
        }
        
        function populateGrowthLeaderboard() {
            const container = document.getElementById('growth-leaderboard');
            // Only show top 5 growth performers
            const topGrowthUsers = dashboardData.growthMetrics.slice(0, 5);
            
            topGrowthUsers.forEach((user, index) => {
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                
                const tooltipContent = `Week-over-Week Growth: +${user.growth.toFixed(1)}%
Previous Week: ${user.previousWeek.toLocaleString()} lines
Current Week: ${user.currentWeek.toLocaleString()} lines
Change: +${(user.currentWeek - user.previousWeek).toLocaleString()} lines

Growth is calculated as:
((Current Week - Previous Week) / Previous Week) × 100%`;
                
                item.innerHTML = `
                    <div class="rank-badge rank-badge-gradient">${index + 1}</div>
                    <div class="avatar">
                        <div class="avatar-fallback">
                            ${user.name.split(' ').map(n => n[0]).join('')}
                        </div>
                    </div>
                    <div class="user-info">
                        <p class="text-sm font-medium truncate">${user.name}</p>
                        <p class="text-xs text-muted-foreground">
                            ${user.previousWeek.toLocaleString()} → ${user.currentWeek.toLocaleString()} lines
                        </p>
                    </div>
                    <div class="flex items-center gap-1">
                        <svg class="icon-sm text-green-500 cursor-help" 
                             style="width: 0.75rem; height: 0.75rem;" 
                             viewBox="0 0 24 24" 
                             fill="none" 
                             stroke="currentColor" 
                             stroke-width="2"
                             title="${tooltipContent}">
                            <path d="M7 17L17 7"></path>
                            <path d="M7 7L17 7 17 17"></path>
                        </svg>
                        <div class="badge badge-success" title="${tooltipContent}">+${user.growth.toFixed(1)}%</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }
        
        function populatePersistentLeaderboard() {
            const container = document.getElementById('persistent-leaderboard');
            const persistentUsers = dashboardData.persistentLeaderboard || [];
            
            persistentUsers.forEach((user, index) => {
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                
                // Determine icon style based on persistence score
                let iconColor = 'text-gray-500';
                let statusIcon = 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'; // checkmark
                
                if (user.persistenceScore >= 80) {
                    iconColor = 'text-green-500';
                    statusIcon = 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'; // checkmark
                } else if (user.persistenceScore >= 60) {
                    iconColor = 'text-yellow-500';
                    statusIcon = 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'; // info
                } else if (user.persistenceScore >= 40) {
                    iconColor = 'text-blue-500';
                    statusIcon = 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'; // info
                } else {
                    iconColor = 'text-gray-500';
                    statusIcon = 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.081 16.5c-.77.833.192 2.5 1.732 2.5z'; // warning
                }
                
                // Create tooltip content explaining the grading system
                const tooltipContent = `Persistence Score: ${user.persistenceScore}%
• Activity Ratio: ${user.activityRatio}% (40% weight) - Days with 500+ lines
• Activity Level: ${user.avgDailyActivity.toFixed(1)} avg/day (30% weight) - Normalized activity
• Consistency: ${user.consistencyScore}% (30% weight) - Low variance in usage
                
Grading Scale:
🟢 80%+ = Excellent persistence
🟡 60-79% = Good persistence  
🔵 40-59% = Moderate persistence
⚪ <40% = Needs improvement`;
                
                item.innerHTML = `
                    <div class="rank-badge rank-badge-orange">${index + 1}</div>
                    <div class="avatar">
                        <div class="avatar-fallback">
                            ${user.name.split(' ').map(n => n[0]).join('')}
                        </div>
                    </div>
                    <div class="user-info">
                        <p class="text-sm font-medium truncate">${user.name}</p>
                        <p class="text-xs text-muted-foreground">
                            ${user.activeDays}/${user.totalDays} days with 500+ lines
                        </p>
                    </div>
                    <div class="flex items-center gap-2">
                        <svg class="icon-sm ${iconColor} cursor-help" 
                             style="width: 1rem; height: 1rem;" 
                             viewBox="0 0 24 24" 
                             fill="none" 
                             stroke="currentColor" 
                             stroke-width="2"
                             title="${tooltipContent}">
                            <path stroke-linecap="round" stroke-linejoin="round" d="${statusIcon}"></path>
                        </svg>
                    </div>
                `;
                container.appendChild(item);
            });
        }
        
        function populateUserTable() {
            const tbody = document.getElementById('user-table');
            
            dashboardData.userMetrics.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>
                        <div class="flex items-center gap-2">
                            <div class="avatar" style="width: 1.5rem; height: 1.5rem;">
                                <div class="avatar-fallback" style="font-size: 0.625rem;">
                                    ${user.name.split(' ').map(n => n[0]).join('')}
                                </div>
                            </div>
                            <span class="text-sm font-medium">${user.name}</span>
                        </div>
                    </td>
                    <td class="text-right font-mono text-sm">${user.linesOfAgent.toLocaleString()}</td>
                    <td class="text-right font-mono text-sm">${user.chats.toLocaleString()}</td>
                    <td class="text-right font-mono text-sm">${user.tabCompletions.toLocaleString()}</td>
                    <td class="text-right">
                        <span class="${user.agentGrowth >= 0 ? 'text-green-600' : 'text-red-600'} font-medium">${user.agentGrowth >= 0 ? '+' : ''}${user.agentGrowth}%</span>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }
        
        function switchTab(tabName) {
            // Update tab triggers
            document.querySelectorAll('.tabs-trigger').forEach(trigger => {
                trigger.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Update tab content
            document.querySelectorAll('.tabs-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            // Synchronize checkbox states across all tabs
            updateCheckboxes();
            updateSelectedCount();
        }
        
        function exportData() {
            const dataStr = JSON.stringify(dashboardData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `cursor-analytics-${new Date().toISOString().split('T')[0]}.json`;
            link.click();
            URL.revokeObjectURL(url);
        }
        
        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', initDashboard);
    </script>
</body>
</html>'''


async def main():
    """Generate the live dashboard."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate Cursor Analytics Dashboard')
    parser.add_argument('--group', '-g', type=str, help='Group name to run report on', 
                       choices=list(PREDEFINED_GROUPS.keys()) + [None])
    parser.add_argument('--days', '-d', type=int, default=7, help='Number of days to analyze (default: 7)')
    parser.add_argument('--list-groups', action='store_true', help='List all available groups and exit')
    parser.add_argument('--cookie', '-c', type=str, help='Cookie string from authenticated browser session (overrides CURSOR_COOKIE_STRING env var)')
    parser.add_argument('--team-id', '-t', type=int, help='Team ID from Cursor dashboard (overrides TEAM_ID env var)')
    
    args = parser.parse_args()
    
    # Handle list groups command
    if args.list_groups:
        show_available_groups()
        return
    
    # Configuration - get cookie string from arguments or environment
    cookie_string = args.cookie if args.cookie else os.getenv("CURSOR_COOKIE_STRING")
    if not cookie_string:
        print("❌ Error: Cookie string not provided!")
        print("\n🔧 Setup options:")
        print("1. Command line: --cookie 'your_cookie_here'")
        print("2. Environment variable: CURSOR_COOKIE_STRING='your_cookie_here'")
        print("3. Or add to .env file: CURSOR_COOKIE_STRING=\"your_cookie_here\"")
        print("\n📖 For detailed instructions, see README.md")
        sys.exit(1)
    
    # Get team ID from arguments or environment variable
    team_id = args.team_id if args.team_id else os.getenv("TEAM_ID")
    if not team_id:
        print("❌ Error: Team ID not provided!")
        print("\n🔧 Setup options:")
        print("1. Command line: --team-id 1234567")
        print("2. Environment variable: TEAM_ID=1234567")
        print("3. Or add to .env file: TEAM_ID=1234567")
        print("\n📖 For detailed instructions, see README.md")
        sys.exit(1)
    
    # Convert team_id to int if it's a string from environment variable
    if isinstance(team_id, str):
        try:
            team_id = int(team_id)
        except ValueError:
            print("❌ Error: TEAM_ID must be a valid integer!")
            print(f"Current value: {team_id}")
            sys.exit(1)
    days_back = args.days  # Number of days to analyze
    
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    # 🎯 SIMPLE GROUP SELECTION - Choose which group to run the report on
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    
    # Command line argument takes precedence, then fallback to manual setting
    group_name = args.group if args.group else None  # Examples: "engineering", "management", "qa", None
    
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    # 🔧 ADVANCED FILTERING OPTIONS (optional - most users won't need these)
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    
    # Emails to exclude from the dashboard (add more emails here as needed)
    excluded_emails = [
        # "example@example.com"
        # Add more emails here if needed, separated by commas
        # "user1@example.com",
        # "user2@example.com"
    ]
    
    # Manual email list (only use if you don't want to use predefined groups)
    # Leave empty to use group_name or all team members
    people_to_include = [
        # Add specific emails here if you want to run the report only on them
        # "john.doe@example.com",
        # "jane.smith@example.com"
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    # 📋 FILTERING LOGIC (for reference):
    # 1. If group_name is provided: use emails from that predefined group
    # 2. If people_to_include is provided: only include those specific emails  
    # 3. If neither is provided: include all team members
    # 4. Then apply excluded_emails filter as a secondary filter
    # ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    
    try:
        print("🚀 Generating Live Cursor Analytics Dashboard...")
        print(f"📅 Analyzing last {days_back} days for team {team_id}")
        
        # Show filtering configuration
        if group_name:
            print(f"🎯 Using predefined group: '{group_name}'")
            available_groups = list(PREDEFINED_GROUPS.keys())
            if group_name not in available_groups:
                print(f"❌ Error: Group '{group_name}' not found. Available groups: {available_groups}")
                return
        elif people_to_include:
            print(f"✅ Including only specified emails: {', '.join(people_to_include)}")
        else:
            print("📊 Processing all team members")
            print(f"💡 Tip: Use --group flag to run on specific groups (e.g., -g ai_champs)")
            
        if excluded_emails:
            print(f"🚫 Excluding emails: {', '.join(excluded_emails)}")
        
        generator = LiveDashboardGenerator(cookie_string, excluded_emails, people_to_include, group_name)
        
        # Fetch real data
        real_data = await generator.fetch_real_data(team_id, days_back)
        
        # Generate HTML with real data
        html_content = generator.generate_html_with_data(real_data)
        
        # Save to timestamped file in reports folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        group_suffix = f"_{group_name}" if group_name else ""
        filename = f"reports/cursor_analytics_live{group_suffix}_{timestamp}.html"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✅ Live dashboard created: {filename}")
        print(f"📊 Data summary:")
        print(f"   • Active users: {real_data['totals']['activeUsers']}")
        print(f"   • Total lines of agent: {real_data['totals']['linesOfAgent']:,} ({real_data['totals']['linesGrowth']:+.1f}% vs last week)")
        print(f"   • Total chat interactions: {real_data['totals']['chats']:,} ({real_data['totals']['chatsGrowth']:+.1f}% vs last week)")
        print(f"   • Total tab completions: {real_data['totals']['tabCompletions']:,} ({real_data['totals']['completionsGrowth']:+.1f}% vs last week)")
        print(f"   • Date range: {real_data['dateRange']['start']} to {real_data['dateRange']['end']}")
        
        # Show data quality improvements
        print(f"\n🔧 DATA QUALITY IMPROVEMENTS:")
        print(f"   ✅ Fixed artificial tab completions (now using real SDK data)")
        print(f"   ✅ Fixed extreme growth percentages (now legitimate week-over-week)")
        print(f"   ✅ Fixed pie chart percentages (now realistic: Lines={[p['value'] for p in real_data['pieData'] if p['name'] == 'Lines of Agent'][0]}%)")
        print(f"   ✅ Fixed weekly aggregation (now uses real daily totals)")
        print(f"   ✅ Fixed date matching (now includes all SDK dates)")
        print(f"   ✅ Added error handling for API validation issues")
        
        print(f"\n🌐 Open {filename} in your browser to view your live dashboard!")
        
        # Show helpful usage information
        if not group_name:
            print(f"\n💡 QUICK USAGE TIPS:")
            print(f"   • AI Champions report: uv run python generate_live_dashboard.py -g ai_champs")
            print(f"   • Engineering report: uv run python generate_live_dashboard.py -g engineering")
            print(f"   • List all groups: uv run python generate_live_dashboard.py --list-groups")
            print(f"   • Available groups: {', '.join(PREDEFINED_GROUPS.keys())}")
        
    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        
        # Show group-specific error help
        if "not found" in str(e).lower() and "group" in str(e).lower():
            print(f"\n💡 GROUP HELP:")
            print(f"   Available groups: {', '.join(PREDEFINED_GROUPS.keys())}")
            print(f"   List groups: uv run python generate_live_dashboard.py --list-groups")
        
        print("\n💡 To fix authentication issues:")
        print("1. Open cursor.com in your browser")
        print("2. Log in to your account")
        print("3. Open Developer Tools (F12)")
        print("4. Go to Network tab")
        print("5. Navigate to your team dashboard")
        print("6. Find any request to cursor.com")
        print("7. Copy the 'Cookie' header value")
        print("8. Set it as CURSOR_COOKIE_STRING environment variable")
        print("\nExample: export CURSOR_COOKIE_STRING='your_cookie_string_here'")


if __name__ == "__main__":
    asyncio.run(main())