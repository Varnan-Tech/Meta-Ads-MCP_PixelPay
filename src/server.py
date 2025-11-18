"""
Main MCP server for Meta Ads management.
"""
import asyncio
import json
import sys
from typing import Dict, Any, Sequence, List

from fastmcp import FastMCP
from starlette.routing import Mount

# Import our tools and modules
try:
    # Try absolute imports first (when run as part of package)
    from .tools import accounts, campaigns, insights, targeting, adsets, ads
    from .core.analyzer import analyze_campaigns
    from .core.validators import create_validation_wrapper, create_account_analysis
    from .auth.token_manager import token_manager
    from .config.settings import settings
    from .utils.logger import logger
    from .auth.oauth_service import oauth_service
    from .auth.database import get_db_session, FacebookToken
    from .auth.oauth_service import oauth_service
    from .auth.web_server import app as oauth_web_app
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
    from auth.oauth_service import oauth_service
    from auth.database import get_db_session, FacebookToken
    from auth.oauth_service import oauth_service
    from auth.web_server import app as oauth_web_app


# Create FastMCP server instance
mcp = FastMCP("meta-ads-mcp")

# Mount the OAuth FastAPI web server so OAuth callbacks and admin routes work in cloud deployments
try:
    mcp._additional_http_routes.append(Mount("/", oauth_web_app))
    logger.info("OAuth web server mounted at root path for HTTP transport")
except Exception as mount_error:
    logger.warning(f"Failed to mount OAuth web server: {mount_error}")

# Initialize database on module import (needed for OAuth token storage)
# This runs immediately when the module is loaded
try:
    from .auth.database import init_database
except ImportError:
    from auth.database import init_database

try:
    init_database()
except Exception as e:
    import sys
    print(f"Warning: Could not initialize database: {e}", file=sys.stderr)

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


@mcp.tool()
def open_facebook_connect(user_id: str | None = None) -> str:
    """Generate the Facebook Connect URL and attempt to open it in the default browser.

    Returns a JSON payload with the URL and whether a browser was opened.
    """
    try:
        state = oauth_service.generate_state(user_id=user_id)
        url = oauth_service.get_authorization_url(state)

        # Attempt to open browser; log to stderr only
        opened = False
        try:
            import webbrowser
            opened = webbrowser.open_new_tab(url)
        except Exception as e:
            print(f"Failed to open browser automatically: {e}", file=sys.stderr)

        return json.dumps({"success": True, "url": url, "opened": opened}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool()
def token_status() -> str:
    """Report which token source will be used by the MCP server (OAuth vs env), and show connection info."""
    try:
        status: dict = {"success": True}

        # Add debug info about database
        status["database"] = {
            "url": settings.database_url
        }

        # Force database initialization if needed
        try:
            from .auth.database import init_database as init_db_func
        except ImportError:
            from auth.database import init_database as init_db_func

        init_db_func()  # Ensure DB is initialized

        # Check OAuth DB for an active token
        db = get_db_session()
        try:
            # Debug: count total tokens
            total_tokens = db.query(FacebookToken).count()
            status["database"]["total_tokens"] = total_tokens

            # Check for active (non-revoked) tokens
            token = db.query(FacebookToken).filter(FacebookToken.revoked == False).order_by(FacebookToken.created_at.desc()).first()
            if token:
                # Check expiration
                from datetime import datetime, timezone
                expires_at = token.expires_at
                if expires_at and expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                is_expired = expires_at and expires_at < datetime.now(timezone.utc) if expires_at else False

                status["oauth"] = {
                    "present": True,
                    "fb_user_id": token.fb_user_id,
                    "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    "is_expired": is_expired,
                    "accounts_count": len(token.accounts) if token.accounts else 0,
                    "permissions": token.permissions if hasattr(token, 'permissions') else []
                }
            else:
                status["oauth"] = {"present": False}
                # Debug: check if there are any tokens at all
                any_token = db.query(FacebookToken).first()
                if any_token:
                    status["oauth"]["debug"] = f"Found {total_tokens} total token(s) but all are revoked"
                else:
                    status["oauth"]["debug"] = "No tokens found in database at all"
        except Exception as db_error:
            status["oauth"] = {"present": False, "error": str(db_error)}
        finally:
            db.close()

        # Check env token
        import os
        env_token = os.getenv("META_ACCESS_TOKEN")
        status["env_token_present"] = bool(env_token)

        # Which will be used according to client resolution order
        status["resolution_order"] = [
            "explicit_argument_if_provided",
            "oauth_managed_token_if_present",
            "META_ACCESS_TOKEN_as_fallback"
        ]
        status["will_use"] = "oauth_managed_token" if status["oauth"].get("present") else ("env_token" if status["env_token_present"] else "none")

        return json.dumps(status, indent=2)
    except Exception as e:
        import traceback
        return json.dumps({"success": False, "error": str(e), "traceback": traceback.format_exc()}, indent=2)


@mcp.tool()
def db_config() -> str:
    """Show the DATABASE_URL the MCP server is using and resolved SQLite path (if applicable)."""
    try:
        from .config.settings import settings as s_abs
    except Exception:
        from config.settings import settings as s_abs

    info = {"success": True, "DATABASE_URL": s_abs.database_url}
    try:
        if s_abs.database_url.startswith("sqlite"):
            # Extract file path for convenience
            path = s_abs.database_url.replace("sqlite:///", "")
            info["sqlite_path"] = path
    except Exception:
        pass
    return json.dumps(info, indent=2)


@mcp.tool()
def clear_database() -> str:
    """Clear all OAuth tokens from the database. WARNING: This deletes all stored tokens!"""
    try:
        from .auth.database import clear_oauth_tokens
    except ImportError:
        from auth.database import clear_oauth_tokens
    
    try:
        count = clear_oauth_tokens()
        return json.dumps({
            "success": True,
            "message": f"Cleared {count} OAuth token(s) from database",
            "tokens_deleted": count
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


@mcp.tool()
def reset_database() -> str:
    """Reset the entire database (drops and recreates all tables). WARNING: This deletes ALL data!"""
    try:
        from .auth.database import reset_database
    except ImportError:
        from auth.database import reset_database
    
    try:
        success = reset_database()
        return json.dumps({
            "success": success,
            "message": "Database reset successfully" if success else "Database reset failed"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


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

        # Initialize database (for OAuth token storage)
        try:
            from .auth.database import init_database
        except ImportError:
            from auth.database import init_database
        init_database()
        print("Database initialized", file=sys.stderr)

        # Check if token is configured (log to stderr)
        # Check both OAuth token and environment token
        has_oauth_token = False
        try:
            token = oauth_service.get_token()
            if token:
                has_oauth_token = True
                print(f"OAuth token found in database", file=sys.stderr)
        except Exception as e:
            logger.debug(f"Could not check OAuth token: {e}")

        if not has_oauth_token and not settings.has_token:
            print("WARNING: No access token configured. Some tools will not work until token is provided.", file=sys.stderr)
            print("Use 'open_facebook_connect' tool to authenticate via OAuth, or set META_ACCESS_TOKEN environment variable.", file=sys.stderr)

        # Run the FastMCP server
        mcp.run()

    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    main()
