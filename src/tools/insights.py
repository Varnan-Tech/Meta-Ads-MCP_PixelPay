"""
Performance insights and analytics tools for Meta Ads MCP server.
"""
import asyncio
import json
from typing import Dict, Any, Optional

try:
    # Try absolute imports first (when run as part of package)
    from ..api.client import api_client, MetaAPIClient
    from ..auth.token_manager import token_manager
    from ..core.formatters import format_insights_response
    from ..config.constants import TIME_RANGES, ESSENTIAL_METRICS, CONVERSION_METRICS, ENGAGEMENT_METRICS
    from ..config.settings import settings
    from ..utils.logger import logger
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from api.client import api_client, MetaAPIClient
    from auth.token_manager import token_manager
    from core.formatters import format_insights_response
    from config.constants import TIME_RANGES, ESSENTIAL_METRICS, CONVERSION_METRICS, ENGAGEMENT_METRICS, VALID_BREAKDOWNS, ACCOUNT_ONLY_BREAKDOWNS
    from config.settings import settings
    from utils.logger import logger


def get_insights(
    object_id: str,
    time_range: str = 'last_7d',
    breakdown: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get performance metrics and analytics for campaigns, ad sets, ads, or accounts.

    Args:
        object_id: ID of campaign, ad set, ad, or account
        time_range: Time range preset (today, yesterday, last_7d, etc.)
        breakdown: Optional breakdown dimension (age, gender, country, etc.)

    Returns:
        Dictionary with insights data
    """
    try:
        # Import the robust HTTP helper
        try:
            from ..utils.meta_http import get_adaccount_insights, normalize_ad_account, build_time_range, meta_get
        except ImportError:
            from utils.meta_http import get_adaccount_insights, normalize_ad_account, build_time_range, meta_get

        # Validate breakdown parameter first
        if breakdown:
            if breakdown not in VALID_BREAKDOWNS:
                # Provide helpful suggestions for common mistakes
                suggestions = []
                if breakdown.lower() in ['day', 'date', 'daily']:
                    suggestions.append("Note: Meta API automatically breaks down data by date when requesting insights over a time range. You don't need a 'day' breakdown.")
                elif breakdown.lower() in ['hour', 'hourly']:
                    suggestions.append("Try 'hourly_stats_aggregated_by_audience_time_zone' or 'hourly_stats_aggregated_by_advertiser_time_zone' instead.")
                elif breakdown.lower() in ['week', 'weekly']:
                    suggestions.append("Weekly breakdowns are not available. Use date ranges or time_range parameters instead.")
                elif breakdown.lower() in ['month', 'monthly']:
                    suggestions.append("Monthly breakdowns are not available. Use date ranges or time_range parameters instead.")

                error_msg = f"Invalid breakdown '{breakdown}'. Valid options include: age, gender, country, region, placement, publisher_platform, device_platform"
                if suggestions:
                    error_msg += f"\n\nSuggestions: {' '.join(suggestions)}"

                return {
                    "success": False,
                    "error": error_msg,
                    "valid_breakdowns": ["age", "gender", "country", "region", "placement", "publisher_platform", "platform_position", "device_platform"]
                }

            # Check if account-only breakdowns are being used with non-account objects
            is_account = object_id.isdigit() and len(object_id) >= 15
            if not is_account and breakdown in ACCOUNT_ONLY_BREAKDOWNS:
                return {
                    "success": False,
                    "error": f"Breakdown '{breakdown}' can only be used with account-level insights, not campaigns or ads"
                }

        # Determine if this is an account-level request
        # Accounts are typically act_ prefixed OR very long numeric IDs (>16 digits)
        # Campaign/Ad IDs are typically 15-16 digits
        is_account = object_id.startswith('act_') or (object_id.isdigit() and len(object_id) > 16)
        if is_account:
            # Account-level insights
            try:
                if time_range in ['today', 'yesterday', 'last_7d', 'last_14d', 'last_30d', 'this_month', 'last_month', 'lifetime']:
                    time_params = build_time_range(preset=time_range)
                elif '_' in time_range and len(time_range.split('_')) == 2:
                    # Handle custom date range format: YYYY-MM-DD_YYYY-MM-DD
                    try:
                        since_date, until_date = time_range.split('_')
                        if len(since_date) == 10 and len(until_date) == 10:
                            time_params = build_time_range(since=since_date, until=until_date)
                        else:
                            time_params = build_time_range(preset='last_30d')  # fallback
                    except (ValueError, TypeError):
                        time_params = build_time_range(preset='last_30d')  # fallback
                else:
                    time_params = {}
                    if not time_params:
                        # Custom time range - convert natural language if needed
                        if time_range.endswith(' days ago'):
                            days = int(time_range.split()[0])
                            time_params = build_time_range(since=f"{days} days ago", until="today")
                        else:
                            time_params = build_time_range(preset='last_30d')  # fallback

                # Use basic fields that are always available
                fields = ['spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm']

                # Add conversion fields - these may not be available for all accounts
                # but we'll handle errors gracefully
                conversion_fields = ['conversions', 'cost_per_conversion', 'conversion_value', 'roas']
                fields.extend(conversion_fields)

                params = {}
                # When using breakdowns, we need to be careful about field combinations
                # Some breakdowns don't work with all fields
                if breakdown:
                    # Use basic fields that work with all breakdowns
                    basic_fields = ['spend', 'impressions', 'reach', 'clicks']
                    params['breakdowns'] = [breakdown]
                    fields = basic_fields
                
                status, data = get_adaccount_insights(
                    object_id,
                    fields=fields,
                    **time_params,
                    **params
                )

                if status == 200:
                    insights = data.get('data', [])
                    if not insights:
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
                            "date_start": "2025-01-01",
                            "date_stop": "2025-01-01",
                            "note": f"No insights data available for {time_range} on this account"
                        }]

                    return {
                        "success": True,
                        "insights": insights
                    }
                elif status == 400 and "not valid for fields param" in str(data):
                    # If conversion fields are not available, try again with basic fields only
                    logger.warning(f"Conversion fields not available for account {object_id}, retrying with basic fields")
                    basic_fields = ['spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm']

                    status2, data2 = get_adaccount_insights(
                        object_id,
                        fields=basic_fields,
                        **time_params,
                        **params
                    )

                    if status2 == 200:
                        insights = data2.get('data', [])
                        if not insights:
                            insights = [{
                                "spend": "0.00",
                                "impressions": "0",
                                "clicks": "0",
                                "ctr": "0.00%",
                                "cpc": "0.00",
                                "cpm": "0.00",
                                "reach": "0",
                                "conversions": "N/A",
                                "cost_per_conversion": "N/A",
                                "conversion_value": "N/A",
                                "roas": "N/A",
                                "date_start": "2025-01-01",
                                "date_stop": "2025-01-01",
                                "note": f"Basic insights only - conversion tracking not available for {time_range}"
                            }]

                        return {
                            "success": True,
                            "insights": insights,
                            "note": "Conversion metrics not available for this account"
                        }
                    else:
                        # Handle error response properly
                        error_msg = data2
                        if isinstance(data2, dict):
                            if 'error' in data2:
                                error_info = data2['error']
                                if isinstance(error_info, dict):
                                    error_msg = error_info.get('message', str(error_info))
                                else:
                                    error_msg = str(error_info)
                            else:
                                error_msg = str(data2)
                        return {
                            "success": False,
                            "error": f"Failed to retrieve insights: HTTP {status2} - {error_msg}"
                        }
                elif status == 403:
                    # Handle permission errors with helpful message
                    error_msg = "Access denied. This ad account may not have granted the required permissions (ads_management or ads_read) for the current access token."
                    if isinstance(data, dict) and 'error' in data:
                        error_info = data['error']
                        if isinstance(error_info, dict):
                            error_msg += f" Details: {error_info.get('message', str(error_info))}"
                    return {
                        "success": False,
                        "error": error_msg,
                        "suggestion": "Please ensure the access token has ads_management or ads_read permissions for this ad account."
                    }
                else:
                    # Handle error response properly
                    error_msg = data
                    if isinstance(data, dict):
                        if 'error' in data:
                            error_info = data['error']
                            if isinstance(error_info, dict):
                                error_msg = error_info.get('message', str(error_info))
                            else:
                                error_msg = str(error_info)
                        else:
                            error_msg = str(data)
                    return {
                        "success": False,
                        "error": f"Failed to retrieve insights: HTTP {status} - {error_msg}"
                    }

            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Time range error: {e}"
                }

        else:
            # Campaign/ad/adset-level insights - use direct API call
            normalized_id = normalize_ad_account(object_id) if object_id.startswith('act_') or object_id.isdigit() else object_id
            path = f"{normalized_id}/insights"

            # When using breakdowns, use basic fields to avoid conflicts
            if breakdown:
                # Use basic fields that work with all breakdowns
                all_fields = 'spend,impressions,reach,clicks'
            else:
                # Try with all fields first, fall back to basic fields if needed
                all_fields = 'spend,impressions,reach,clicks,ctr,cpc,cpm,conversions,cost_per_conversion,conversion_value,roas'
            
            params = {
                'fields': all_fields
            }

            # Add time parameters
            if time_range in ['today', 'yesterday', 'last_7d', 'last_14d', 'last_30d', 'this_month', 'last_month', 'lifetime']:
                params['date_preset'] = time_range
            elif '_' in time_range and len(time_range.split('_')) == 2:
                # Handle custom date range format: YYYY-MM-DD_YYYY-MM-DD
                try:
                    since_date, until_date = time_range.split('_')
                    # Validate date format
                    if len(since_date) == 10 and len(until_date) == 10:
                        time_params = build_time_range(since=since_date, until=until_date)
                        params.update(time_params)
                    else:
                        params['date_preset'] = 'last_30d'  # fallback
                except (ValueError, TypeError):
                    params['date_preset'] = 'last_30d'  # fallback
            else:
                # Try to build custom time range
                try:
                    time_params = build_time_range(preset=time_range) if time_range in ['today', 'yesterday', 'last_7d', 'last_14d', 'last_30d', 'this_month', 'last_month', 'lifetime'] else build_time_range(since=time_range, until="today")
                    params.update(time_params)
                except ValueError:
                    params['date_preset'] = 'last_30d'  # fallback

            if breakdown:
                # Don't JSON encode for regular API calls - use comma-separated string
                params['breakdowns'] = breakdown

            status, data = meta_get(path, params)

            if status == 200:
                insights = data.get('data', [])
                if not insights:
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
                        "date_start": "2025-01-01",
                        "date_stop": "2025-01-01",
                        "note": f"No insights data available for {time_range} on this object"
                    }]

                return {
                    "success": True,
                    "insights": insights
                }
            elif status == 400 and "not valid for fields param" in str(data):
                # If conversion fields are not available, try again with basic fields only
                logger.warning(f"Conversion fields not available for object {object_id}, retrying with basic fields")
                params['fields'] = 'spend,impressions,reach,clicks,ctr,cpc,cpm'

                status2, data2 = meta_get(path, params)

                if status2 == 200:
                    insights = data2.get('data', [])
                    if not insights:
                        insights = [{
                            "spend": "0.00",
                            "impressions": "0",
                            "clicks": "0",
                            "ctr": "0.00%",
                            "cpc": "0.00",
                            "cpm": "0.00",
                            "reach": "0",
                            "conversions": "N/A",
                            "cost_per_conversion": "N/A",
                            "conversion_value": "N/A",
                            "roas": "N/A",
                            "date_start": "2025-01-01",
                            "date_stop": "2025-01-01",
                            "note": f"Basic insights only - conversion tracking not available for {time_range}"
                        }]

                    return {
                        "success": True,
                        "insights": insights,
                        "note": "Conversion metrics not available for this object"
                    }
                else:
                    # Handle error response properly
                    error_msg = data2
                    if isinstance(data2, dict):
                        if 'error' in data2:
                            error_info = data2['error']
                            if isinstance(error_info, dict):
                                error_msg = error_info.get('message', str(error_info))
                            else:
                                error_msg = str(error_info)
                        else:
                            error_msg = str(data2)
                    return {
                        "success": False,
                        "error": f"Failed to retrieve insights: HTTP {status2} - {error_msg}"
                    }
            elif status == 403:
                # Handle permission errors with helpful message
                error_msg = "Access denied. This object may not be accessible with the current access token permissions (ads_management or ads_read)."
                if isinstance(data, dict) and 'error' in data:
                    error_info = data['error']
                    if isinstance(error_info, dict):
                        error_msg += f" Details: {error_info.get('message', str(error_info))}"
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Please ensure the access token has proper permissions for this ad object."
                }
            else:
                # Handle error response properly
                error_msg = data
                if isinstance(data, dict):
                    if 'error' in data:
                        error_info = data['error']
                        if isinstance(error_info, dict):
                            error_msg = error_info.get('message', str(error_info))
                        else:
                            error_msg = str(error_info)
                    else:
                        error_msg = str(data)
                return {
                    "success": False,
                    "error": f"Failed to retrieve insights: HTTP {status} - {error_msg}"
                }

    except Exception as e:
        logger.error(f"Error in get_insights for {object_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_campaign_insights(
    campaign_id: str,
    time_range: str = 'last_7d',
    breakdown: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get insights specifically for a campaign.

    Args:
        campaign_id: Meta campaign ID
        time_range: Time range preset
        breakdown: Optional breakdown dimension

    Returns:
        Dictionary with campaign insights
    """
    return get_insights(campaign_id, time_range, breakdown)


def get_account_insights(
    account_id: str,
    time_range: str = 'last_7d',
    breakdown: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get insights specifically for an account.

    Args:
        account_id: Meta ad account ID
        time_range: Time range preset
        breakdown: Optional breakdown dimension

    Returns:
        Dictionary with account insights
    """
    return get_insights(account_id, time_range, breakdown)


def calculate_roas(spend: float, conversion_value: float) -> float:
    """
    Calculate Return on Ad Spend (ROAS).

    Args:
        spend: Amount spent
        conversion_value: Revenue generated

    Returns:
        ROAS value (revenue / spend)
    """
    try:
        if spend == 0:
            return 0.0
        return conversion_value / spend
    except (TypeError, ZeroDivisionError):
        return 0.0


def calculate_ctr(clicks: int, impressions: int) -> float:
    """
    Calculate Click-Through Rate (CTR).

    Args:
        clicks: Number of clicks
        impressions: Number of impressions

    Returns:
        CTR as decimal (e.g., 0.025 for 2.5%)
    """
    try:
        if impressions == 0:
            return 0.0
        return clicks / impressions
    except (TypeError, ZeroDivisionError):
        return 0.0


def calculate_cpc(spend: float, clicks: int) -> float:
    """
    Calculate Cost Per Click (CPC).

    Args:
        spend: Amount spent
        clicks: Number of clicks

    Returns:
        CPC value
    """
    try:
        if clicks == 0:
            return 0.0
        return spend / clicks
    except (TypeError, ZeroDivisionError):
        return 0.0


def calculate_cpm(spend: float, impressions: int) -> float:
    """
    Calculate Cost Per Mille (CPM).

    Args:
        spend: Amount spent
        impressions: Number of impressions

    Returns:
        CPM value (cost per 1000 impressions)
    """
    try:
        if impressions == 0:
            return 0.0
        return (spend / impressions) * 1000
    except (TypeError, ZeroDivisionError):
        return 0.0


def format_time_range_display(time_range: str) -> str:
    """
    Format time range for display.

    Args:
        time_range: Time range preset

    Returns:
        Human-readable time range description
    """
    time_range_labels = {
        'today': 'Today',
        'yesterday': 'Yesterday',
        'last_7d': 'Last 7 days',
        'last_14d': 'Last 14 days',
        'last_30d': 'Last 30 days',
        'this_month': 'This month',
        'last_month': 'Last month',
        'lifetime': 'Lifetime'
    }

    return time_range_labels.get(time_range, time_range)


