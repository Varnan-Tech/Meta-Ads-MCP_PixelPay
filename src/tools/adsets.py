"""
Ad sets management tools for Meta Ads MCP server.
"""
from typing import Dict, Any, Optional

try:
    # Try absolute imports first (when run as part of package)
    from ..api.client import api_client, MetaAPIClient
    from ..auth.token_manager import token_manager
    from ..core.formatters import format_adsets_response, format_adset_response
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
    from core.formatters import format_adsets_response, format_adset_response
    from config.settings import settings
    from utils.logger import logger


def get_adsets(
    account_id: str,
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ad sets for an account or campaign.

    Args:
        account_id: Meta ad account ID (e.g., 'act_123456789')
        campaign_id: Optional campaign ID to filter ad sets
        status: Optional status filter ('ACTIVE', 'PAUSED', etc.)
        limit: Maximum number of ad sets to return

    Returns:
        Dictionary with ad sets data
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

        # Get ad sets
        if campaign_id:
            # Get ad sets for specific campaign
            response = client.get_adsets_by_campaign(campaign_id, status, limit)
        else:
            # Get ad sets for account
            response = client.get_adsets_by_account(account_id, status, limit)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ad sets: {response.error}"
            }

        # Format response
        return format_adsets_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_adsets for account {account_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_adset_details(adset_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific ad set.

    Args:
        adset_id: Meta ad set ID

    Returns:
        Dictionary with ad set details
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

        # Get ad set details
        response = client.get_adset_details(adset_id)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ad set details: {response.error}"
            }

        # Format response
        return format_adset_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_adset_details for {adset_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_adsets_by_account(
    account_id: str,
    status: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ad sets for a specific account.

    Args:
        account_id: Meta ad account ID
        status: Optional status filter
        limit: Maximum number of ad sets to return

    Returns:
        Dictionary with ad sets data
    """
    return get_adsets(account_id, None, status, limit)


def get_adsets_by_campaign(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ad sets for a specific campaign.

    Args:
        campaign_id: Meta campaign ID
        status: Optional status filter
        limit: Maximum number of ad sets to return

    Returns:
        Dictionary with ad sets data
    """
    # Extract account ID from campaign ID for token management
    # Campaign IDs are typically like 1202xxxxxxxxx
    # We need to find the account that owns this campaign
    try:
        access_token = token_manager.get_token() or settings.meta_access_token
        if not access_token:
            return {
                "success": False,
                "error": "No access token available. Please configure your Meta access token."
            }

        client = MetaAPIClient(access_token)
        # Get campaign details to find account ID
        campaign_response = client.get_campaign_details(campaign_id)
        if not campaign_response.success:
            return {
                "success": False,
                "error": f"Cannot access campaign {campaign_id}: {campaign_response.error}"
            }

        account_id = campaign_response.data.get('account_id')
        if not account_id:
            return {
                "success": False,
                "error": "Cannot determine account ID for campaign"
            }

        return get_adsets(account_id, campaign_id, status, limit)

    except Exception as e:
        logger.error(f"Error in get_adsets_by_campaign for {campaign_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
