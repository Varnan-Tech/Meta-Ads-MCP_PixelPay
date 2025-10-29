"""
Ads management tools for Meta Ads MCP server.
"""
from typing import Dict, Any, Optional

try:
    # Try absolute imports first (when run as part of package)
    from ..api.client import api_client, MetaAPIClient
    from ..auth.token_manager import token_manager
    from ..core.formatters import format_ads_response, format_ad_response, format_creatives_response
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
    from core.formatters import format_ads_response, format_ad_response, format_creatives_response
    from config.settings import settings
    from utils.logger import logger


def get_ads(
    adset_id: Optional[str] = None,
    account_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ads from an ad set, account, or campaign.

    Args:
        adset_id: Meta ad set ID to get ads from
        account_id: Meta ad account ID (alternative to adset_id)
        campaign_id: Meta campaign ID (alternative to adset_id)
        status_filter: Optional status filter ('ACTIVE', 'PAUSED', etc.)
        limit: Maximum number of ads to return

    Returns:
        Dictionary with ads data
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

        # Determine which API call to make
        if adset_id:
            response = client.get_ads_by_adset(adset_id, status_filter, limit)
        elif account_id:
            response = client.get_ads_by_account(account_id, status_filter, limit)
        elif campaign_id:
            response = client.get_ads_by_campaign(campaign_id, status_filter, limit)
        else:
            return {
                "success": False,
                "error": "Must provide either adset_id, account_id, or campaign_id"
            }

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ads: {response.error}"
            }

        # Format response
        return format_ads_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_ads: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_ad_details(ad_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific ad.

    Args:
        ad_id: Meta ad ID

    Returns:
        Dictionary with ad details
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

        # Get ad details
        response = client.get_ad_details(ad_id)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ad details: {response.error}"
            }

        # Format response
        return format_ad_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_ad_details for {ad_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_ad_creatives(ad_id: str) -> Dict[str, Any]:
    """
    Get creative details for a specific ad.

    Args:
        ad_id: Meta ad ID

    Returns:
        Dictionary with creative details
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

        # Get ad creatives
        response = client.get_ad_creatives(ad_id)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ad creatives: {response.error}"
            }

        # Format response
        return format_creatives_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_ad_creatives for {ad_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_ads_by_adset(
    adset_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ads for a specific ad set.

    Args:
        adset_id: Meta ad set ID
        status_filter: Optional status filter
        limit: Maximum number of ads to return

    Returns:
        Dictionary with ads data
    """
    return get_ads(adset_id=adset_id, status_filter=status_filter, limit=limit)


def get_ads_by_account(
    account_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ads for a specific account.

    Args:
        account_id: Meta ad account ID
        status_filter: Optional status filter
        limit: Maximum number of ads to return

    Returns:
        Dictionary with ads data
    """
    return get_ads(account_id=account_id, status_filter=status_filter, limit=limit)


def get_ads_by_campaign(
    campaign_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get ads for a specific campaign.

    Args:
        campaign_id: Meta campaign ID
        status_filter: Optional status filter
        limit: Maximum number of ads to return

    Returns:
        Dictionary with ads data
    """
    return get_ads(campaign_id=campaign_id, status_filter=status_filter, limit=limit)
