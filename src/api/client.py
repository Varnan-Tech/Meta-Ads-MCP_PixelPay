"""
Meta Marketing API client wrapper for Meta Ads MCP server.
"""
import time
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
import requests
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.user import User
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError, FacebookBadObjectError

try:
    # Try absolute imports first (when run as part of package)
    from ..config.settings import settings
    from ..config.constants import META_API_BASE_URL
    from ..utils.logger import logger
    from ..utils.helpers import normalize_account_id, fetch_all_pages
    from ..auth.oauth_service import oauth_service
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from config.settings import settings
    from config.constants import META_API_BASE_URL
    from utils.logger import logger
    from utils.helpers import normalize_account_id, fetch_all_pages
    from auth.oauth_service import oauth_service


@dataclass
class APIResponse:
    """Standardized API response wrapper."""
    success: bool
    data: Any
    error: Optional[str] = None
    rate_limit_info: Optional[Dict[str, Any]] = None


class MetaAPIClient:
    """
    Wrapper for Meta Marketing API with rate limiting and error handling.

    Features:
    - Automatic token management
    - Rate limiting
    - Error recovery
    - Response caching (optional)
    - Pagination handling
    """

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize API client.

        Args:
            access_token: Meta API access token (uses settings if None)
        """
        # Resolve token with OAuth-managed preference
        resolved: Optional[str] = access_token
        if not resolved:
            try:
                resolved = oauth_service.get_token()
            except Exception:
                resolved = None
        if not resolved:
            resolved = settings.meta_access_token
        if not resolved:
            raise ValueError("Access token is required (no OAuth token found and no META_ACCESS_TOKEN set)")
        self.access_token = resolved
        if not self.access_token:
            raise ValueError("Access token is required")

        # Initialize Facebook SDK
        self.api = FacebookAdsApi.init(access_token=self.access_token)

        # Rate limiting
        self._request_count = 0
        self._last_request_time = time.time()
        self._rate_limit_window_start = time.time()
        self._rate_limit_window_size = 3600  # 1 hour

        # Session for HTTP requests
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is available."""
        if self._session is None:
            # Use configurable timeout for Meta's Insights API which can be slow
            timeout = aiohttp.ClientTimeout(
                total=settings.api_timeout_total,
                connect=settings.api_timeout_connect
            )
            # Configure connection pooling to prevent connection exhaustion
            connector = aiohttp.TCPConnector(
                limit=settings.connection_pool_size,  # Max total connections
                limit_per_host=settings.connection_pool_per_host,  # Max connections per host
                ttl_dns_cache=300,  # DNS cache for 5 minutes
                force_close=False,  # Keep connections alive
                enable_cleanup_closed=True
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )

    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting (synchronous version)."""
        current_time = time.time()

        # Reset window if needed
        if current_time - self._rate_limit_window_start > self._rate_limit_window_size:
            self._request_count = 0
            self._rate_limit_window_start = current_time

        # Check if we've exceeded the limit
        if self._request_count >= settings.max_requests_per_hour:
            sleep_time = self._rate_limit_window_size - (current_time - self._rate_limit_window_start)
            if sleep_time > 0:
                logger.warning(f"Rate limit exceeded, sleeping for {sleep_time:.0f} seconds")
                time.sleep(sleep_time)
                self._request_count = 0
                self._rate_limit_window_start = time.time()

        self._request_count += 1
        self._last_request_time = current_time

    async def _check_rate_limit_async(self) -> None:
        """Check and enforce rate limiting (async version - non-blocking)."""
        current_time = time.time()

        # Reset window if needed
        if current_time - self._rate_limit_window_start > self._rate_limit_window_size:
            self._request_count = 0
            self._rate_limit_window_start = current_time

        # Check if we've exceeded the limit
        if self._request_count >= settings.max_requests_per_hour:
            sleep_time = self._rate_limit_window_size - (current_time - self._rate_limit_window_start)
            if sleep_time > 0:
                logger.warning(f"Rate limit exceeded, sleeping for {sleep_time:.0f} seconds")
                # Use asyncio.sleep instead of time.sleep to avoid blocking the event loop
                await asyncio.sleep(sleep_time)
                self._request_count = 0
                self._rate_limit_window_start = time.time()

        self._request_count += 1
        self._last_request_time = current_time

    def _prepare_params(self, base_params: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Prepare parameters with proper encoding for Meta API.
        Based on reference server implementation.
        """
        import json
        params = base_params.copy()

        for key, value in kwargs.items():
            if value is not None:
                # Parameters that need JSON encoding
                if key in ['filtering', 'time_range', 'time_ranges', 'effective_status',
                           'special_ad_categories', 'objective', 'buyer_guarantee_agreement_status'] and isinstance(value, (list, dict)):
                    params[key] = json.dumps(value)
                elif key == 'fields' and isinstance(value, list):
                    params[key] = ','.join(value)
                elif key == 'action_attribution_windows' and isinstance(value, list):
                    params[key] = ','.join(value)
                elif key == 'action_breakdowns' and isinstance(value, list):
                    params[key] = ','.join(value)
                elif key == 'breakdowns' and isinstance(value, list):
                    params[key] = ','.join(value)
                else:
                    params[key] = value

        return params

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> APIResponse:
        """
        Make a synchronous API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Request parameters

        Returns:
            APIResponse with success/data or error
        """
        self._check_rate_limit()

        try:
            url = f"{META_API_BASE_URL}{endpoint}"

            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                },
                timeout=settings.api_timeout_total  # Use configurable timeout (default: 180s)
            )

            response.raise_for_status()
            data = response.json()

            return APIResponse(
                success=True,
                data=data,
                rate_limit_info=self._get_rate_limit_info(response.headers)
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return APIResponse(
                success=False,
                data=None,
                error=str(e)
            )
        except ValueError as e:
            logger.error(f"Failed to parse API response: {e}")
            return APIResponse(
                success=False,
                data=None,
                error=f"Invalid JSON response: {e}"
            )

    async def _make_async_request(self, method: str, endpoint: str, params: Optional[Dict] = None, retry_count: int = 3) -> APIResponse:
        """
        Make an asynchronous API request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Request parameters
            retry_count: Number of retries on failure

        Returns:
            APIResponse with success/data or error
        """
        await self._ensure_session()
        await self._check_rate_limit_async()  # Use async version to avoid blocking

        last_error = None
        for attempt in range(retry_count):
            try:
                url = f"{META_API_BASE_URL}{endpoint}"

                async with self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    }
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    return APIResponse(
                        success=True,
                        data=data,
                        rate_limit_info=self._get_rate_limit_info(response.headers)
                    )

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < retry_count - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(f"Async API request failed (attempt {attempt + 1}/{retry_count}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Async API request failed after {retry_count} attempts: {e}")
            except ValueError as e:
                logger.error(f"Failed to parse async API response: {e}")
                return APIResponse(
                    success=False,
                    data=None,
                    error=f"Invalid JSON response: {e}"
                )

        return APIResponse(
            success=False,
            data=None,
            error=f"Request failed after {retry_count} attempts: {str(last_error)}"
        )

    def _get_rate_limit_info(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extract rate limit information from response headers."""
        return {
            'remaining': headers.get('X-RateLimit-Remaining', 'unknown'),
            'limit': headers.get('X-RateLimit-Limit', 'unknown'),
            'reset_time': headers.get('X-RateLimit-Reset', 'unknown')
        }

    # User and Account Operations

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information.

        Returns:
            User data or None if failed
        """
        try:
            me = User(fbid='me')
            user_data = me.api_get(fields=['id', 'name', 'email'])
            return user_data
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None

    def get_ad_accounts(self) -> APIResponse:
        """
        Get all accessible ad accounts (handles pagination automatically).
        CRITICAL: This automatically fetches ALL pages using pagination.

        Returns:
            APIResponse with accounts data
        """
        try:
            me = User(fbid='me')

            # Get all accounts with automatic pagination handling
            all_accounts = []
            accounts_iter = me.get_ad_accounts(fields=[
                'id', 'name', 'account_id', 'currency', 'account_status', 'balance'
            ])

            # Iterate through all pages to get complete results
            # The Facebook SDK handles pagination automatically with the iterator
            for account in accounts_iter:
                all_accounts.append(account)

            logger.info(f"Retrieved {len(all_accounts)} ad accounts total across all pages")

            return APIResponse(success=True, data={'accounts': all_accounts})

        except Exception as e:
            logger.error(f"Failed to get ad accounts: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_account_info(self, account_id: str) -> APIResponse:
        """
        Get detailed information about a specific ad account.

        Args:
            account_id: Meta ad account ID (with or without 'act_' prefix)

        Returns:
            APIResponse with account data
        """
        try:
            # Normalize account ID to ensure act_ prefix
            account_id = normalize_account_id(account_id)
            
            account = AdAccount(account_id)
            account_data = account.api_get(fields=[
                'id', 'name', 'account_id', 'currency', 'account_status',
                'balance', 'spend_cap', 'timezone_name'
            ])
            return APIResponse(success=True, data=account_data)

        except Exception as e:
            logger.error(f"Failed to get account info for {account_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    # Campaign Operations

    def get_campaigns(self, account_id: str, status_filter: Optional[str] = None,
                     limit: int = 100) -> APIResponse:
        """
        Get campaigns for an ad account.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            account_id: Meta ad account ID (with or without 'act_' prefix)
            status_filter: Filter by status (ACTIVE, PAUSED, etc.)
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL campaigns data across all pages
        """
        try:
            # Normalize account ID
            account_id = normalize_account_id(account_id)
            
            account = AdAccount(account_id)
            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'objective', 'daily_budget',
                    'lifetime_budget', 'created_time', 'updated_time'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            campaigns_iter = account.get_campaigns(params=params)

            # Iterate through ALL pages automatically
            all_campaigns = []
            for campaign in campaigns_iter:
                all_campaigns.append(campaign)

            logger.info(f"Retrieved {len(all_campaigns)} campaigns total across all pages")

            return APIResponse(success=True, data={'campaigns': all_campaigns})

        except Exception as e:
            logger.error(f"Failed to get campaigns for {account_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_campaign_details(self, campaign_id: str) -> APIResponse:
        """
        Get detailed information about a specific campaign.

        Args:
            campaign_id: Meta campaign ID

        Returns:
            APIResponse with campaign data
        """
        try:
            from facebook_business.adobjects.campaign import Campaign
            campaign = Campaign(campaign_id)
            campaign_data = campaign.api_get(fields=[
                'id', 'name', 'status', 'objective', 'daily_budget',
                'lifetime_budget', 'created_time', 'updated_time',
                'source_campaign_id', 'special_ad_categories'
            ])
            return APIResponse(success=True, data=campaign_data)

        except Exception as e:
            logger.error(f"Failed to get campaign details for {campaign_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def create_campaign(self, account_id: str, campaign_data: Dict[str, Any]) -> APIResponse:
        """
        Create a new campaign.

        Args:
            account_id: Meta ad account ID (with or without 'act_' prefix)
            campaign_data: Campaign configuration data

        Returns:
            APIResponse with created campaign data
        """
        try:
            # Normalize account ID
            account_id = normalize_account_id(account_id)
            
            account = AdAccount(account_id)

            # Prepare campaign parameters
            params = {
                'name': campaign_data['name'],
                'objective': campaign_data['objective'],
                'status': campaign_data.get('status', 'PAUSED'),
            }

            # Add budget if specified
            if 'daily_budget' in campaign_data:
                params['daily_budget'] = str(campaign_data['daily_budget'])
            elif 'lifetime_budget' in campaign_data:
                params['lifetime_budget'] = str(campaign_data['lifetime_budget'])

            # Add special ad categories if specified
            if 'special_ad_categories' in campaign_data:
                params['special_ad_categories'] = campaign_data['special_ad_categories']

            campaign = account.create_campaign(params=params)
            return APIResponse(success=True, data=campaign)

        except Exception as e:
            logger.error(f"Failed to create campaign for {account_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def update_campaign(self, campaign_id: str, update_data: Dict[str, Any]) -> APIResponse:
        """
        Update an existing campaign.

        Args:
            campaign_id: Meta campaign ID
            update_data: Fields to update

        Returns:
            APIResponse with updated campaign data
        """
        try:
            from facebook_business.adobjects.campaign import Campaign
            campaign = Campaign(campaign_id)

            # Prepare update parameters
            params = {}
            if 'name' in update_data:
                params['name'] = update_data['name']
            if 'status' in update_data:
                params['status'] = update_data['status']
            if 'daily_budget' in update_data:
                params['daily_budget'] = str(update_data['daily_budget'])
            if 'lifetime_budget' in update_data:
                params['lifetime_budget'] = str(update_data['lifetime_budget'])

            campaign.api_update(params=params)
            updated_data = campaign.api_get(fields=[
                'id', 'name', 'status', 'daily_budget', 'lifetime_budget'
            ])

            return APIResponse(success=True, data=updated_data)

        except Exception as e:
            logger.error(f"Failed to update campaign {campaign_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    # Insights Operations

    def _convert_time_range_to_dates(self, time_range: str) -> dict:
        """
        Convert time range presets to actual date ranges.

        Args:
            time_range: Preset like 'last_7d', 'last_30d', etc.

        Returns:
            Dict with 'since' and 'until' dates in YYYY-MM-DD format
        """
        from datetime import datetime, timedelta

        today = datetime.now()

        if time_range == 'today':
            since = today.strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')
        elif time_range == 'yesterday':
            yesterday = today - timedelta(days=1)
            since = yesterday.strftime('%Y-%m-%d')
            until = yesterday.strftime('%Y-%m-%d')
        elif time_range == 'last_7d':
            since = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')
        elif time_range == 'last_14d':
            since = (today - timedelta(days=14)).strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')
        elif time_range == 'last_30d':
            since = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')
        elif time_range == 'this_month':
            since = today.replace(day=1).strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')
        elif time_range == 'last_month':
            first_of_this_month = today.replace(day=1)
            last_of_last_month = first_of_this_month - timedelta(days=1)
            first_of_last_month = last_of_last_month.replace(day=1)
            since = first_of_last_month.strftime('%Y-%m-%d')
            until = last_of_last_month.strftime('%Y-%m-%d')
        else:
            # Default to last 7 days
            since = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            until = today.strftime('%Y-%m-%d')

        return {'since': since, 'until': until}

    def get_insights(self, object_id: str, time_range: str = 'last_7d',
                    breakdown: Optional[str] = None) -> APIResponse:
        """
        Get performance insights for campaigns, ad sets, or ads.

        Args:
            object_id: ID of campaign, ad set, ad, or account
            time_range: Time range preset
            breakdown: Optional breakdown dimension

        Returns:
            APIResponse with insights data
        """
        try:
            # Build insights parameters with proper encoding (unified approach)
            params = {}

            # Handle time parameters (priority: time_range > date_preset)
            if time_range in ['today', 'yesterday', 'last_7d', 'last_14d', 'last_30d', 'this_month', 'last_month', 'lifetime']:
                # Use date_preset for standard ranges (most reliable)
                preset_map = {
                    'today': 'today',
                    'yesterday': 'yesterday',
                    'last_7d': 'last_7d',
                    'last_14d': 'last_14d',
                    'last_30d': 'last_30d',
                    'this_month': 'this_month',
                    'last_month': 'last_month',
                    'lifetime': 'lifetime'
                }
                params = self._prepare_params(params, date_preset=preset_map[time_range])
            else:
                # For custom ranges, convert to actual dates and use time_range
                date_range = self._convert_time_range_to_dates(time_range)
                params = self._prepare_params(params, time_range=date_range)

            # Add fields (use common fields that are more likely to be supported)
            fields = ['spend', 'impressions', 'clicks', 'ctr', 'cpc', 'cpm', 'reach']
            params = self._prepare_params(params, fields=fields)

            # Add breakdown if specified
            if breakdown:
                params = self._prepare_params(params, breakdowns=[breakdown])

            # Make API call (unified for all object types)
            endpoint = f'/{object_id}/insights'
            response = self._make_request('GET', endpoint, params)

            if not response.success:
                return response

            insights = response.data.get('data', [])

            # Handle empty results with fallback
            if not insights:
                from datetime import datetime
                today = datetime.now()
                insights = [{
                    "spend": "0.00",
                    "impressions": "0",
                    "clicks": "0",
                    "ctr": "0.00%",
                    "cpc": "0.00",
                    "cpm": "0.00",
                    "reach": "0",
                    "conversions": "0",
                    "cost_per_conversion": "0.00",
                    "conversion_value": "0.00",
                    "roas": "0.00x",
                    "date_start": today.strftime('%Y-%m-%d'),
                    "date_stop": today.strftime('%Y-%m-%d'),
                    "note": f"No insights data available for {time_range} on this object"
                }]

            return APIResponse(success=True, data={'insights': insights})

        except Exception as e:
            logger.error(f"Failed to get insights for {object_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def _get_object(self, object_id: str):
        """Get appropriate Facebook object based on ID prefix."""
        if object_id.startswith('act_'):
            return AdAccount(object_id)
        elif len(object_id) == 15 and object_id.isdigit():  # Meta object IDs are typically 15 digits
            # For insights, we can make direct API calls without needing object types
            return None  # Insights will handle this directly
        else:
            raise ValueError(f"Unknown object ID format: {object_id}")

    # Targeting Operations

    def search_interests(self, query: str, limit: int = 25) -> APIResponse:
        """
        Search for interest targeting options.

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            APIResponse with interests data
        """
        try:
            from facebook_business.adobjects.targetingsearch import TargetingSearch

            params = {
                'type': 'adinterest',
                'q': query,
                'limit': limit
            }

            interests = TargetingSearch.search(params=params)

            # Convert to list if needed
            if hasattr(interests, '__iter__') and not isinstance(interests, list):
                interests = list(interests)

            return APIResponse(success=True, data={'interests': interests, 'query': query})

        except Exception as e:
            logger.error(f"Failed to search interests for '{query}': {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def search_demographics(self, demographic_class: str, limit: int = 50) -> APIResponse:
        """
        Search for demographic targeting options.

        Args:
            demographic_class: Type of demographics (education, relationship_status, etc.)
            limit: Maximum results

        Returns:
            APIResponse with demographics data
        """
        try:
            from facebook_business.adobjects.targetingsearch import TargetingSearch

            params = {
                'type': 'adTargetingCategory',
                'class': demographic_class,
                'limit': limit
            }

            demographics = TargetingSearch.search(params=params)

            # Convert to list if needed
            if hasattr(demographics, '__iter__') and not isinstance(demographics, list):
                demographics = list(demographics)

            return APIResponse(success=True, data={'demographics': demographics})

        except Exception as e:
            logger.error(f"Failed to search demographics for '{demographic_class}': {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def search_locations(self, query: str, location_types: List[str],
                        limit: int = 25) -> APIResponse:
        """
        Search for geographic targeting locations.

        Args:
            query: Search term
            location_types: Types of locations to search
            limit: Maximum results

        Returns:
            APIResponse with locations data
        """
        try:
            from facebook_business.adobjects.targetingsearch import TargetingSearch

            params = {
                'type': 'adgeolocation',
                'q': query,
                'location_types': location_types,
                'limit': limit
            }

            locations = TargetingSearch.search(params=params)

            # Convert to list if needed
            if hasattr(locations, '__iter__') and not isinstance(locations, list):
                locations = list(locations)

            return APIResponse(success=True, data={'locations': locations, 'query': query})

        except Exception as e:
            logger.error(f"Failed to search locations for '{query}': {e}")
            return APIResponse(success=False, data=None, error=str(e))

    # Ad Set Operations

    def get_adsets_by_account(self, account_id: str, status_filter: Optional[str] = None,
                             limit: int = 100) -> APIResponse:
        """
        Get ad sets for an account.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            account_id: Meta ad account ID (with or without 'act_' prefix)
            status_filter: Optional status filter
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL ad sets data across all pages
        """
        try:
            # Normalize account ID
            account_id = normalize_account_id(account_id)
            
            account = AdAccount(account_id)
            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'campaign_id', 'account_id', 'targeting',
                    'daily_budget', 'lifetime_budget', 'created_time', 'updated_time',
                    'optimization_goal', 'billing_event', 'bid_amount'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            adsets_iter = account.get_ad_sets(params=params)
            
            # Iterate through ALL pages automatically
            all_adsets = []
            for adset in adsets_iter:
                all_adsets.append(adset)
                
            logger.info(f"Retrieved {len(all_adsets)} ad sets total across all pages")
            
            return APIResponse(success=True, data={'adsets': all_adsets})

        except Exception as e:
            logger.error(f"Failed to get ad sets for account {account_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_adsets_by_campaign(self, campaign_id: str, status_filter: Optional[str] = None,
                              limit: int = 100) -> APIResponse:
        """
        Get ad sets for a campaign.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            campaign_id: Meta campaign ID
            status_filter: Optional status filter
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL ad sets data across all pages
        """
        try:
            from facebook_business.adobjects.campaign import Campaign
            campaign = Campaign(campaign_id)

            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'campaign_id', 'account_id', 'targeting',
                    'daily_budget', 'lifetime_budget', 'created_time', 'updated_time',
                    'optimization_goal', 'billing_event', 'bid_amount'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            adsets_iter = campaign.get_ad_sets(params=params)
            
            # Iterate through ALL pages automatically
            all_adsets = []
            for adset in adsets_iter:
                all_adsets.append(adset)
                
            logger.info(f"Retrieved {len(all_adsets)} ad sets total across all pages for campaign {campaign_id}")
            
            return APIResponse(success=True, data={'adsets': all_adsets})

        except Exception as e:
            logger.error(f"Failed to get ad sets for campaign {campaign_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_adset_details(self, adset_id: str) -> APIResponse:
        """
        Get detailed information about a specific ad set.

        Args:
            adset_id: Meta ad set ID

        Returns:
            APIResponse with ad set data
        """
        try:
            from facebook_business.adobjects.adset import AdSet
            adset = AdSet(adset_id)
            adset_data = adset.api_get(fields=[
                'id', 'name', 'status', 'campaign_id', 'account_id', 'targeting',
                'daily_budget', 'lifetime_budget', 'created_time', 'updated_time',
                'optimization_goal', 'billing_event', 'bid_amount', 'promoted_object'
            ])
            return APIResponse(success=True, data=adset_data)

        except Exception as e:
            logger.error(f"Failed to get ad set details for {adset_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    # Ad Operations

    def get_ads_by_adset(self, adset_id: str, status_filter: Optional[str] = None,
                        limit: int = 100) -> APIResponse:
        """
        Get ads for an ad set.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            adset_id: Meta ad set ID
            status_filter: Optional status filter
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL ads data across all pages
        """
        try:
            from facebook_business.adobjects.adset import AdSet
            adset = AdSet(adset_id)

            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'adset_id', 'campaign_id', 'account_id',
                    'creative', 'created_time', 'updated_time', 'tracking_specs'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            ads_iter = adset.get_ads(params=params)
            
            # Iterate through ALL pages automatically
            all_ads = []
            for ad in ads_iter:
                all_ads.append(ad)
                
            logger.info(f"Retrieved {len(all_ads)} ads total across all pages for ad set {adset_id}")
            
            return APIResponse(success=True, data={'ads': all_ads})

        except Exception as e:
            logger.error(f"Failed to get ads for ad set {adset_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_ads_by_account(self, account_id: str, status_filter: Optional[str] = None,
                          limit: int = 100) -> APIResponse:
        """
        Get ads for an account.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            account_id: Meta ad account ID (with or without 'act_' prefix)
            status_filter: Optional status filter
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL ads data across all pages
        """
        try:
            # Normalize account ID
            account_id = normalize_account_id(account_id)
            
            account = AdAccount(account_id)

            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'adset_id', 'campaign_id', 'account_id',
                    'creative', 'created_time', 'updated_time', 'tracking_specs'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            ads_iter = account.get_ads(params=params)
            
            # Iterate through ALL pages automatically
            all_ads = []
            for ad in ads_iter:
                all_ads.append(ad)
                
            logger.info(f"Retrieved {len(all_ads)} ads total across all pages for account {account_id}")
            
            return APIResponse(success=True, data={'ads': all_ads})

        except Exception as e:
            logger.error(f"Failed to get ads for account {account_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_ads_by_campaign(self, campaign_id: str, status_filter: Optional[str] = None,
                           limit: int = 100) -> APIResponse:
        """
        Get ads for a campaign.
        CRITICAL: This automatically fetches ALL pages using pagination.

        Args:
            campaign_id: Meta campaign ID
            status_filter: Optional status filter
            limit: Limit per page (will fetch all pages automatically)

        Returns:
            APIResponse with ALL ads data across all pages
        """
        try:
            from facebook_business.adobjects.campaign import Campaign
            campaign = Campaign(campaign_id)

            params = {
                'limit': limit,
                'fields': [
                    'id', 'name', 'status', 'adset_id', 'campaign_id', 'account_id',
                    'creative', 'created_time', 'updated_time', 'tracking_specs'
                ]
            }

            if status_filter:
                params['filtering'] = [{'field': 'status', 'operator': 'EQUAL', 'value': status_filter}]

            ads_iter = campaign.get_ads(params=params)
            
            # Iterate through ALL pages automatically
            all_ads = []
            for ad in ads_iter:
                all_ads.append(ad)
                
            logger.info(f"Retrieved {len(all_ads)} ads total across all pages for campaign {campaign_id}")
            
            return APIResponse(success=True, data={'ads': all_ads})

        except Exception as e:
            logger.error(f"Failed to get ads for campaign {campaign_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_ad_details(self, ad_id: str) -> APIResponse:
        """
        Get detailed information about a specific ad.

        Args:
            ad_id: Meta ad ID

        Returns:
            APIResponse with ad data
        """
        try:
            from facebook_business.adobjects.ad import Ad
            ad = Ad(ad_id)
            ad_data = ad.api_get(fields=[
                'id', 'name', 'status', 'adset_id', 'campaign_id', 'account_id',
                'creative', 'created_time', 'updated_time', 'tracking_specs',
                'conversion_specs', 'recommendations'
            ])
            return APIResponse(success=True, data=ad_data)

        except Exception as e:
            logger.error(f"Failed to get ad details for {ad_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))

    def get_ad_creatives(self, ad_id: str) -> APIResponse:
        """
        Get creative details for a specific ad.

        Args:
            ad_id: Meta ad ID

        Returns:
            APIResponse with creative data
        """
        try:
            # Use direct API call to get creative
            endpoint = f'/{ad_id}/creatives'
            params = {
                'fields': 'id,name,title,body,image_url,video_id,link_url,call_to_action,object_story_spec,asset_feed_spec'
            }

            response = self._make_request('GET', endpoint, params)
            if response.success:
                creatives = response.data.get('data', [])
                return APIResponse(success=True, data={'creatives': creatives})
            else:
                return response

        except Exception as e:
            logger.error(f"Failed to get creatives for ad {ad_id}: {e}")
            return APIResponse(success=False, data=None, error=str(e))


# Global API client instance (will be initialized with token when available)
api_client: Optional[MetaAPIClient] = None


def initialize_api_client(access_token: Optional[str] = None) -> MetaAPIClient:
    """
    Initialize the global API client.

    Args:
        access_token: Meta API access token (optional)

    Returns:
        Initialized API client
    """
    global api_client
    api_client = MetaAPIClient(access_token)
    return api_client


def initialize_api_client_auto(
    access_token: Optional[str] = None,
    user_id: Optional[str] = None,
    fb_user_id: Optional[str] = None,
) -> MetaAPIClient:
    """
    Initialize API client with dual token sourcing:
    1) explicit access_token argument
    2) OAuth-managed token (by fb_user_id or user_id)
    3) META_ACCESS_TOKEN from environment/settings
    """
    resolved_token: Optional[str] = access_token

    if not resolved_token:
        try:
            # Prefer fb_user_id when provided; otherwise try user_id
            if fb_user_id:
                resolved_token = oauth_service.get_token(fb_user_id=fb_user_id)
            elif user_id:
                resolved_token = oauth_service.get_token(user_id=user_id)
        except Exception as e:
            logger.warning(f"OAuth token lookup failed: {e}")

    if not resolved_token:
        resolved_token = settings.meta_access_token

    return initialize_api_client(resolved_token)
