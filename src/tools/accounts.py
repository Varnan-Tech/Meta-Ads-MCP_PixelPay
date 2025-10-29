"""
Account management tools for Meta Ads MCP server.
"""
import asyncio
from typing import Dict, Any, Optional

try:
    # Try absolute imports first (when run as part of package)
    from ..api.client import api_client, MetaAPIClient
    from ..auth.token_manager import token_manager
    from ..core.formatters import format_accounts_response, format_account_info_response
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
    from core.formatters import format_accounts_response, format_account_info_response
    from config.settings import settings
    from utils.logger import logger


def get_ad_accounts() -> Dict[str, Any]:
    """
    List all accessible Meta ad accounts.

    Returns:
        Dictionary with accounts data and count
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

        # Get accounts
        response = client.get_ad_accounts()

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve ad accounts: {response.error}"
            }

        # Format response
        return format_accounts_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_ad_accounts: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_account_info(account_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific ad account.

    Args:
        account_id: Meta ad account ID (format: act_XXXXX)

    Returns:
        Dictionary with account details
    """
    try:
        # Validate account ID format - accept both act_ prefixed and numeric formats
        if not (account_id.startswith('act_') or (account_id.isdigit() and len(account_id) >= 10)):
            return {
                "success": False,
                "error": "Invalid account ID format. Expected format: act_XXXXX or numeric ID (10+ digits)"
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

        # Get account info
        response = client.get_account_info(account_id)

        if not response.success:
            return {
                "success": False,
                "error": f"Failed to retrieve account info: {response.error}"
            }

        # Format response
        return format_account_info_response(response.data)

    except Exception as e:
        logger.error(f"Error in get_account_info for {account_id}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


