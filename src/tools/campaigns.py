"""
Campaign management tools for Meta Ads MCP server.
"""
import asyncio
from typing import Dict, Any, Optional

try:
    # Try absolute imports first (when run as part of package)
    from ..api.client import api_client, MetaAPIClient
    from ..auth.token_manager import token_manager
    from ..core.formatters import (
        format_campaigns_response,
        format_campaign_details_response,
        format_campaign_create_response,
        format_campaign_update_response
    )
    from ..core.validators import validate_campaign_input
    from ..config.constants import VALID_OBJECTIVES, CAMPAIGN_STATUSES
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
    from core.formatters import (
        format_campaigns_response,
        format_campaign_details_response,
        format_campaign_create_response,
        format_campaign_update_response
    )
    from core.validators import validate_campaign_input
    from config.constants import VALID_OBJECTIVES, CAMPAIGN_STATUSES
    from config.settings import settings
    from utils.logger import logger


def get_campaigns(account_id: str, status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    List campaigns for an ad account.

    Args:
        account_id: Meta ad account ID (format: act_XXXXX)
        status: Filter by status (ACTIVE, PAUSED, etc.)
        limit: Maximum number of results

    Returns:
        Dictionary with campaigns data
    """
    try:
        # Import the robust HTTP helper with alias to avoid naming collision
        try:
            from ..utils.meta_http import get_campaigns as fetch_campaigns_http, normalize_ad_account
        except ImportError:
            from utils.meta_http import get_campaigns as fetch_campaigns_http, normalize_ad_account
        
        # Import logger if not already available
        try:
            from ..utils.logger import logger
        except (ImportError, NameError):
            pass

        # Use the robust HTTP helper which handles account normalization automatically
        fields = ['id', 'name', 'status', 'effective_status', 'objective', 'daily_budget',
                 'lifetime_budget', 'created_time', 'updated_time']

        filtering = None
        if status:
            filtering = [{'field': 'effective_status', 'operator': 'EQUAL', 'value': status}]

        status_code, data = fetch_campaigns_http(
            account_id,
            fields=fields,
            limit=limit,
            filtering=filtering
        )

        if status_code == 200:
            campaigns = data.get('data', [])
            return {
                "success": True,
                "campaigns": campaigns
            }
        else:
            # Handle error response properly with detailed information
            error_msg = "Unknown error"
            error_details = {}
            
            if isinstance(data, dict):
                if 'error' in data:
                    error_info = data['error']
                    if isinstance(error_info, dict):
                        error_msg = error_info.get('message', str(error_info))
                        error_details = {
                            "code": error_info.get('code'),
                            "subcode": error_info.get('error_subcode'),
                            "type": error_info.get('type'),
                            "fbtrace_id": error_info.get('fbtrace_id')
                        }
                    else:
                        error_msg = str(error_info)
                else:
                    error_msg = str(data)
            else:
                error_msg = str(data)
            
            logger.error(f"Campaign retrieval failed for {account_id}")
            logger.error(f"Status Code: {status_code}")
            logger.error(f"Error Message: {error_msg}")
            logger.error(f"Error Details: {error_details}")
            
            return {
                "success": False,
                "error": f"Failed to retrieve campaigns: HTTP {status_code} - {error_msg}",
                "error_details": error_details,
                "account_id": normalize_ad_account(account_id),
                "suggestion": "Run test_account_access.py to diagnose the issue"
            }

    except Exception as e:
        logger.error(f"Error in get_campaigns for {account_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_campaign_details(campaign_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific campaign.

    Args:
        campaign_id: Meta campaign ID

    Returns:
        Dictionary with campaign details
    """
    try:
        # Get token from token manager or settings
        access_token = token_manager.get_token() or settings.meta_access_token
        if not access_token:
            return {
                "success": False,
                "error": "No access token available. Please configure your Meta access token."
            }

        # Initialize API client
        client = MetaAPIClient(access_token)

        # Get campaign details
        response = client.get_campaign_details(campaign_id)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve campaign details: {response.error}"
            }

        # Format response
        return format_campaign_details_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_campaign_details for {campaign_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def create_campaign(
    account_id: str,
    name: str,
    objective: str,
    daily_budget: Optional[int] = None,
    lifetime_budget: Optional[int] = None,
    status: str = "PAUSED",
    special_ad_categories: Optional[list] = None
) -> Dict[str, Any]:
    """
    Create a new ad campaign.

    Args:
        account_id: Meta ad account ID (format: act_XXXXX or just the numeric ID)
        name: Campaign name
        objective: Campaign objective (OUTCOME_AWARENESS, OUTCOME_TRAFFIC, etc.)
        daily_budget: Daily budget in smallest currency unit
                     - For USD/EUR/INR (2 decimals): multiply by 100 (e.g., $4000 = 400000)
                     - For JPY/KRW (0 decimals): use actual amount (e.g., ¥4000 = 4000)
                     - For BHD/KWD (3 decimals): multiply by 1000
        lifetime_budget: Lifetime budget in smallest currency unit
        status: Campaign status (ACTIVE or PAUSED)
        special_ad_categories: Special ad categories (empty list [] if not applicable)
                               Options: CREDIT, EMPLOYMENT, HOUSING, ISSUES_ELECTIONS_POLITICS

    Returns:
        Dictionary with created campaign data

    Note: Meta API uses the account's currency automatically. The budget value
          represents the smallest unit of that currency (cents for USD, paise for INR, etc.)
    """
    try:
        # Normalize account ID (ensure act_ prefix)
        if not account_id.startswith('act_'):
            account_id = f"act_{account_id}"

        # Validate inputs
        validation = validate_campaign_input({
            'name': name,
            'objective': objective,
            'daily_budget': daily_budget,
            'lifetime_budget': lifetime_budget,
            'status': status
        })

        if not validation['valid']:
            return {
                "success": False,
                "error": f"Validation failed: {validation['errors']}"
            }

        # Get token from token manager or settings
        access_token = token_manager.get_token(account_id) or token_manager.get_token() or settings.meta_access_token
        if not access_token:
            return {
                "success": False,
                "error": "No access token available. Please configure your Meta access token."
            }

        # Initialize API client
        client = MetaAPIClient(access_token)

        # Get account info to check currency (for logging/validation)
        account_response = client.get_account_info(account_id)
        account_currency = None
        if account_response.success and account_response.data:
            account_currency = account_response.data.get('currency', 'UNKNOWN')
            logger.info(f"Creating campaign for account with currency: {account_currency}")

            # Currency-specific validation hints
            currency_multipliers = {
                'USD': 100, 'EUR': 100, 'GBP': 100, 'INR': 100, 'CAD': 100, 'AUD': 100,
                'JPY': 1, 'KRW': 1,  # No decimal places
                'BHD': 1000, 'KWD': 1000, 'OMR': 1000, 'TND': 1000  # 3 decimal places
            }

            if account_currency in currency_multipliers:
                multiplier = currency_multipliers[account_currency]
                if daily_budget:
                    logger.info(f"Daily budget: {daily_budget} (= {daily_budget/multiplier:.2f} {account_currency})")
                elif lifetime_budget:
                    logger.info(f"Lifetime budget: {lifetime_budget} (= {lifetime_budget/multiplier:.2f} {account_currency})")

        # Prepare campaign data
        campaign_data = {
            'name': name,
            'objective': objective,
            'status': status,
            # CRITICAL: Meta API requires special_ad_categories (empty list if not applicable)
            'special_ad_categories': special_ad_categories if special_ad_categories is not None else []
        }

        # Add budget (Meta API expects integer in smallest currency unit)
        if daily_budget:
            campaign_data['daily_budget'] = daily_budget
        elif lifetime_budget:
            campaign_data['lifetime_budget'] = lifetime_budget

        # Create campaign
        response = client.create_campaign(account_id, campaign_data)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to create campaign: {response.error}",
                "account_currency": account_currency
            }

        # Format response
        result = format_campaign_create_response(response.data)
        if account_currency:
            result['account_currency'] = account_currency
        return result

    except Exception as e:
        logger.error(f"Error in create_campaign for {account_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def update_campaign(
    campaign_id: str,
    status: Optional[str] = None,
    daily_budget: Optional[int] = None,
    lifetime_budget: Optional[int] = None,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing campaign.

    Args:
        campaign_id: Meta campaign ID
        status: New status (ACTIVE, PAUSED, DELETED)
        daily_budget: New daily budget in cents
        lifetime_budget: New lifetime budget in cents
        name: New campaign name

    Returns:
        Dictionary with updated campaign data
    """
    try:
        # Get token from token manager or settings
        access_token = token_manager.get_token() or settings.meta_access_token
        if not access_token:
            return {
                "success": False,
                "error": "No access token available. Please configure your Meta access token."
            }

        # Initialize API client
        client = MetaAPIClient(access_token)

        # Get current campaign data for comparison
        current_response = client.get_campaign_details(campaign_id)
        if not current_response.success:
            return {
                "success": False,
                "error": f"Failed to get current campaign data: {current_response.error}"
            }

        # Prepare update data
        update_data = {}
        if status is not None:
            if status not in CAMPAIGN_STATUSES:
                return {
                    "success": False,
                    "error": f"Invalid status. Must be one of: {CAMPAIGN_STATUSES}"
                }
            update_data['status'] = status

        if daily_budget is not None:
            if daily_budget < 100:  # Minimum $1.00
                return {
                    "success": False,
                    "error": "Daily budget must be at least $1.00 (100 cents)"
                }
            update_data['daily_budget'] = daily_budget

        if lifetime_budget is not None:
            if lifetime_budget < 100:  # Minimum $1.00
                return {
                    "success": False,
                    "error": "Lifetime budget must be at least $1.00 (100 cents)"
                }
            update_data['lifetime_budget'] = lifetime_budget

        if name is not None:
            if len(name.strip()) == 0:
                return {
                    "success": False,
                    "error": "Campaign name cannot be empty"
                }
            update_data['name'] = name.strip()

        if not update_data:
            return {
                "success": False,
                "error": "No valid updates provided"
            }

        # Update campaign
        response = client.update_campaign(campaign_id, update_data)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to update campaign: {response.error}"
            }

        # Format response with before/after comparison
        return format_campaign_update_response(current_response.data, update_data)

    except Exception as e:
        logger.error(f"Error in update_campaign for {campaign_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


