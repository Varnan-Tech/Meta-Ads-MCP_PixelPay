"""
Main MCP server for Meta Ads management.
"""
import asyncio
import json
import sys
from typing import Dict, Any, Sequence, List

from mcp.server import FastMCP
from mcp.server.models import InitializationOptions

# Import our tools and modules
try:
    # Try absolute imports first (when run as part of package)
    from .tools import accounts, campaigns, insights, targeting, adsets, ads
    from .core.analyzer import analyze_campaigns
    from .core.validators import create_validation_wrapper, create_account_analysis
    from .auth.token_manager import token_manager
    from .config.settings import settings
    from .utils.logger import logger
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from tools import accounts, campaigns, insights, targeting, adsets, ads
    from core.analyzer import analyze_campaigns
    from core.validators import create_validation_wrapper
    from auth.token_manager import token_manager
    from config.settings import settings
    from utils.logger import logger


# Create FastMCP server instance
mcp = FastMCP("meta-ads-mcp")

@mcp.tool()
def get_ad_accounts() -> str:
    """List all accessible Meta ad accounts."""
    try:
        from .tools.accounts import get_ad_accounts
    except ImportError:
        from tools.accounts import get_ad_accounts

    # Wrap with validation
    validated_get_ad_accounts = create_validation_wrapper(get_ad_accounts, 'get_ad_accounts')
    result = validated_get_ad_accounts()
    return json.dumps(result, indent=2)

@mcp.tool()
def get_account_info(account_id: str) -> str:
    """Get detailed information about a specific ad account."""
    try:
        from .tools.accounts import get_account_info
    except ImportError:
        from tools.accounts import get_account_info

    validated_get_account_info = create_validation_wrapper(get_account_info, 'get_account_info')
    result = validated_get_account_info(account_id=account_id)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_campaigns(account_id: str, status: str = None, limit: int = 100) -> str:
    """List campaigns for an ad account."""
    try:
        from .tools.campaigns import get_campaigns
    except ImportError:
        from tools.campaigns import get_campaigns

    validated_get_campaigns = create_validation_wrapper(get_campaigns, 'get_campaigns')
    result = validated_get_campaigns(account_id=account_id, status=status, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_campaign_details(campaign_id: str) -> str:
    """Get detailed information about a specific campaign."""
    try:
        from .tools.campaigns import get_campaign_details
    except ImportError:
        from tools.campaigns import get_campaign_details

    validated_get_campaign_details = create_validation_wrapper(get_campaign_details, 'get_campaign_details')
    result = validated_get_campaign_details(campaign_id=campaign_id)
    return json.dumps(result, indent=2)

@mcp.tool()
def create_campaign(account_id: str, name: str, objective: str, daily_budget: int = None, lifetime_budget: int = None, status: str = "PAUSED") -> str:
    """Create a new ad campaign."""
    try:
        from .tools.campaigns import create_campaign
    except ImportError:
        from tools.campaigns import create_campaign

    validated_create_campaign = create_validation_wrapper(create_campaign, 'create_campaign')
    result = validated_create_campaign(account_id=account_id, name=name, objective=objective,
                                     daily_budget=daily_budget, lifetime_budget=lifetime_budget, status=status)
    return json.dumps(result, indent=2)

@mcp.tool()
def update_campaign(campaign_id: str, status: str = None, daily_budget: int = None, lifetime_budget: int = None, name: str = None) -> str:
    """Update campaign status, budget, or settings."""
    try:
        from .tools.campaigns import update_campaign
    except ImportError:
        from tools.campaigns import update_campaign

    validated_update_campaign = create_validation_wrapper(update_campaign, 'update_campaign')
    result = validated_update_campaign(campaign_id=campaign_id, status=status,
                                     daily_budget=daily_budget, lifetime_budget=lifetime_budget, name=name)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_insights(object_id: str, time_range: str = "last_7d", breakdown: str = None) -> str:
    """Get performance metrics and analytics."""
    try:
        from .tools.insights import get_insights
    except ImportError:
        from tools.insights import get_insights

    validated_get_insights = create_validation_wrapper(get_insights, 'get_insights')
    result = validated_get_insights(object_id=object_id, time_range=time_range, breakdown=breakdown)
    return json.dumps(result, indent=2)

@mcp.tool()
def search_interests(query: str, limit: int = 25) -> str:
    """Search for targeting interests by keyword."""
    try:
        from .tools.targeting import search_interests
    except ImportError:
        from tools.targeting import search_interests

    validated_search_interests = create_validation_wrapper(search_interests, 'search_interests')
    result = validated_search_interests(query=query, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def search_demographics(demographic_class: str, limit: int = 50) -> str:
    """Search for demographic targeting options."""
    try:
        from .tools.targeting import search_demographics
    except ImportError:
        from tools.targeting import search_demographics

    validated_search_demographics = create_validation_wrapper(search_demographics, 'search_demographics')
    result = validated_search_demographics(demographic_class=demographic_class, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def search_locations(query: str, location_types: list, limit: int = 25) -> str:
    """Search for geographic targeting locations."""
    try:
        from .tools.targeting import search_locations
    except ImportError:
        from tools.targeting import search_locations

    validated_search_locations = create_validation_wrapper(search_locations, 'search_locations')
    result = validated_search_locations(query=query, location_types=location_types, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_adsets(account_id: str, campaign_id: str = None, status: str = None, limit: int = 100) -> str:
    """List ad sets for an account or campaign."""
    try:
        from .tools.adsets import get_adsets
    except ImportError:
        from tools.adsets import get_adsets

    validated_get_adsets = create_validation_wrapper(get_adsets, 'get_adsets')
    result = validated_get_adsets(account_id=account_id, campaign_id=campaign_id, status=status, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_adset_details(adset_id: str) -> str:
    """Get detailed information about a specific ad set."""
    try:
        from .tools.adsets import get_adset_details
    except ImportError:
        from tools.adsets import get_adset_details

    validated_get_adset_details = create_validation_wrapper(get_adset_details, 'get_adset_details')
    result = validated_get_adset_details(adset_id=adset_id)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_ads(adset_id: str = None, account_id: str = None, campaign_id: str = None, status: str = None, limit: int = 100) -> str:
    """List ads from an ad set, account, or campaign."""
    try:
        from .tools.ads import get_ads
    except ImportError:
        from tools.ads import get_ads

    validated_get_ads = create_validation_wrapper(get_ads, 'get_ads')
    # Map 'status' to 'status_filter' for compatibility
    result = validated_get_ads(adset_id=adset_id, account_id=account_id, campaign_id=campaign_id, status_filter=status, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_ad_details(ad_id: str) -> str:
    """Get detailed information about a specific ad."""
    try:
        from .tools.ads import get_ad_details
    except ImportError:
        from tools.ads import get_ad_details

    validated_get_ad_details = create_validation_wrapper(get_ad_details, 'get_ad_details')
    result = validated_get_ad_details(ad_id=ad_id)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_ad_creatives(ad_id: str) -> str:
    """Get creative details for a specific ad."""
    try:
        from .tools.ads import get_ad_creatives
    except ImportError:
        from tools.ads import get_ad_creatives

    validated_get_ad_creatives = create_validation_wrapper(get_ad_creatives, 'get_ad_creatives')
    result = validated_get_ad_creatives(ad_id=ad_id)
    return json.dumps(result, indent=2)


# =======================
# Targeting Tools
# =======================

# Duplicate function removed - using the one above

@mcp.tool()
def get_interest_suggestions(interest_list: List[str], limit: int = 25) -> str:
    """Get interest suggestions based on existing interests."""
    try:
        from .tools.targeting import get_interest_suggestions
    except ImportError:
        from tools.targeting import get_interest_suggestions

    validated_get_interest_suggestions = create_validation_wrapper(get_interest_suggestions, 'get_interest_suggestions')
    result = validated_get_interest_suggestions(interest_list=interest_list, limit=limit)
    return json.dumps(result, indent=2)

@mcp.tool()
def validate_interests(interest_list: List[str] = None, interest_fbid_list: List[str] = None) -> str:
    """Validate interest names or IDs for targeting."""
    try:
        from .tools.targeting import validate_interests
    except ImportError:
        from tools.targeting import validate_interests

    validated_validate_interests = create_validation_wrapper(validate_interests, 'validate_interests')
    result = validated_validate_interests(interest_list=interest_list, interest_fbid_list=interest_fbid_list)
    return json.dumps(result, indent=2)

@mcp.tool()
def estimate_audience_size(account_id: str, targeting: Dict[str, Any], optimization_goal: str = "REACH") -> str:
    """Estimate audience size for targeting specifications."""
    try:
        from .tools.targeting import estimate_audience_size
    except ImportError:
        from tools.targeting import estimate_audience_size

    validated_estimate_audience_size = create_validation_wrapper(estimate_audience_size, 'estimate_audience_size')
    result = validated_estimate_audience_size(account_id=account_id, targeting=targeting, optimization_goal=optimization_goal)
    return json.dumps(result, indent=2)

@mcp.tool()
def search_behaviors(limit: int = 50) -> str:
    """Get all available behavior targeting options."""
    try:
        from .tools.targeting import search_behaviors
    except ImportError:
        from tools.targeting import search_behaviors

    validated_search_behaviors = create_validation_wrapper(search_behaviors, 'search_behaviors')
    result = validated_search_behaviors(limit=limit)
    return json.dumps(result, indent=2)

# Duplicate function removed - using the one above

@mcp.tool()
def search_geo_locations(query: str, location_types: List[str] = None, limit: int = 25) -> str:
    """Search for geographic targeting locations."""
    try:
        from .tools.targeting import search_geo_locations
    except ImportError:
        from tools.targeting import search_geo_locations

    validated_search_geo_locations = create_validation_wrapper(search_geo_locations, 'search_geo_locations')
    result = validated_search_geo_locations(query=query, location_types=location_types, limit=limit)
    return json.dumps(result, indent=2)


@mcp.tool()
def analyze_campaigns(account_id: str, time_range: str = "last_30d", focus: str = None) -> str:
    """AI-powered campaign analysis with recommendations."""
    try:
        from .core.analyzer import analyze_campaigns
    except ImportError:
        from core.analyzer import analyze_campaigns

    validated_analyze_campaigns = create_validation_wrapper(analyze_campaigns, 'analyze_campaigns')
    result = validated_analyze_campaigns(account_id=account_id, time_range=time_range, focus=focus)
    return json.dumps(result, indent=2)

def main():
    """Main entry point for the MCP server."""
    try:
        # For MCP servers, stdout must be reserved for JSON-RPC communication only
        # Configure logger to use stderr instead of stdout
        for handler in logger.handlers:
            if hasattr(handler, 'stream') and handler.stream == sys.stdout:
                handler.stream = sys.stderr

        # Log startup message to stderr
        print("Starting Meta Ads MCP Server...", file=sys.stderr)

        # Check if token is configured (log to stderr)
        if not settings.has_token:
            print("WARNING: No access token configured. Some tools will not work until token is provided.", file=sys.stderr)

        # Run the FastMCP server
        mcp.run()

    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    main()
