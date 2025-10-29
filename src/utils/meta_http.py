"""
Robust HTTP helper for Meta Ads API calls.
Based on reference implementation with proper error handling and parameter normalization.
"""
import os
import sys
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system env vars only

# Import token manager for access token
try:
    from ..auth.token_manager import token_manager
except ImportError:
    try:
        from auth.token_manager import token_manager
    except ImportError:
        token_manager = None

# API Configuration
API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

def get_access_token() -> Optional[str]:
    """Get access token from token manager or environment variable."""
    # Try token manager first
    if token_manager:
        token = token_manager.get_token()
        if token:
            return token
    # Fall back to environment variable
    return os.getenv("META_ACCESS_TOKEN")

# Regex for ISO date validation
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_ad_account(account_id: str) -> str:
    """
    Normalize ad account ID to ensure proper act_ prefix.

    Args:
        account_id: Raw account ID (with or without act_ prefix)

    Returns:
        Normalized account ID with act_ prefix
    """
    account_id = str(account_id).strip()
    if account_id.startswith("act_"):
        return account_id
    # If the value looks like a numeric id, prefix it
    if account_id.isdigit():
        return f"act_{account_id}"
    return account_id  # leave as-is for other object ids


def build_time_range(since: Optional[str] = None, until: Optional[str] = None,
                    preset: Optional[str] = None) -> Dict[str, Any]:
    """
    Build proper time range parameters for Meta Ads API.

    Args:
        since: Start date (ISO format or "X days ago")
        until: End date (ISO format or "today")
        preset: Preset time range (last_7d, last_30d, etc.)

    Returns:
        Dict with either date_preset or time_range parameter

    Raises:
        ValueError: If dates are invalid or cannot be parsed
    """
    if preset:
        return {"date_preset": preset}

    today = datetime.utcnow().date()

    # Parse 'since' date
    if since and since.endswith(" days ago"):
        days = int(since.split()[0])
        since_date = (today - timedelta(days=days)).isoformat()
    elif since and ISO_DATE_RE.match(since):
        since_date = since
    else:
        since_date = None

    # Parse 'until' date
    if until == "today" or until is None:
        until_date = today.isoformat()
    elif until and ISO_DATE_RE.match(until):
        until_date = until
    else:
        until_date = None

    if not since_date or not until_date:
        raise ValueError("time_range requires either date_preset or valid ISO 'since' and 'until' dates (YYYY-MM-DD)")

    return {"time_range": json.dumps({"since": since_date, "until": until_date})}


def meta_get(path: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    """
    Make a robust GET request to Meta Graph API with proper error handling.

    Args:
        path: API path without base URL (e.g., "act_12345/insights")
        params: Query parameters dict

    Returns:
        Tuple of (status_code, parsed_json_or_text)
        - Success: (200, json_data)
        - Error: (status_code, error_json_or_text)
    """
    url = f"{BASE_URL}/{path}"

    # Get access token
    access_token = get_access_token()
    if not access_token:
        return 401, {
            "error": {
                "message": "No access token available. Please authenticate first.",
                "type": "AUTH_ERROR",
                "code": 401
            }
        }

    # Add access token to params
    request_params = params.copy()
    request_params["access_token"] = access_token

    try:
        resp = requests.get(url, params=request_params, timeout=30)

        # Log request URL for debugging (without exposing token)
        debug_url = resp.request.url
        if access_token and access_token in debug_url:
            debug_url = debug_url.replace(access_token, "TOKEN_REDACTED")
        print(f"DEBUG URL: {debug_url}", file=sys.stderr)
        print(f"DEBUG STATUS: {resp.status_code}", file=sys.stderr)

        # Handle non-success responses
        if resp.status_code >= 400:
            try:
                json_response = resp.json()
                print(f"ERROR RESPONSE: {json.dumps(json_response, indent=2)}", file=sys.stderr)

                # Check if this is an authentication/permission error
                if "error" in json_response:
                    error_info = json_response["error"]
                    if isinstance(error_info, dict):
                        error_code = error_info.get("code")
                        error_subcode = error_info.get("error_subcode")
                        error_msg = error_info.get("message", "Unknown error")

                        print(f"Meta API Error Code: {error_code}, Subcode: {error_subcode}", file=sys.stderr)
                        print(f"Meta API Error Message: {error_msg}", file=sys.stderr)
                        
                        # Specific error handling
                        if error_code == 100 and error_subcode == 33:
                            return resp.status_code, {
                                "error": {
                                    "message": "Invalid account ID or insufficient permissions",
                                    "details": error_msg,
                                    "code": error_code,
                                    "subcode": error_subcode,
                                    "suggestion": "Verify the account ID is correct and you have access to it"
                                }
                            }
                
                return resp.status_code, json_response
            except json.JSONDecodeError:
                # Return a structured error response
                print(f"ERROR TEXT: {resp.text}", file=sys.stderr)
                return resp.status_code, {
                    "error": {
                        "message": resp.text,
                        "type": "HTTP_ERROR",
                        "code": resp.status_code
                    }
                }

        # Success - try to parse JSON
        try:
            return resp.status_code, resp.json()
        except json.JSONDecodeError:
            return resp.status_code, resp.text

    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 0, str(e)  # 0 indicates network error


# Convenience functions for common endpoints
def get_adaccount_insights(account_id: str, fields: Optional[list] = None,
                          date_preset: str = "last_30d", **kwargs) -> Tuple[int, Any]:
    """
    Get ad account insights with proper parameter handling.
    """
    path = f"{normalize_ad_account(account_id)}/insights"

    params = {}
    if fields:
        params["fields"] = ",".join(fields)

    # Add time parameters
    if date_preset:
        params["date_preset"] = date_preset
    elif "time_range" in kwargs:
        params["time_range"] = json.dumps(kwargs["time_range"])

    # Add other optional parameters
    for key in ["level", "action_attribution_windows", "breakdowns", "filtering"]:
        if key in kwargs and kwargs[key] is not None:
            if isinstance(kwargs[key], (list, dict)):
                params[key] = json.dumps(kwargs[key])
            else:
                params[key] = kwargs[key]

    return meta_get(path, params)


def get_campaigns(account_id: str, fields: Optional[list] = None,
                 limit: int = 250, **kwargs) -> Tuple[int, Any]:
    """
    Get campaigns for an ad account.
    """
    path = f"{normalize_ad_account(account_id)}/campaigns"

    params = {"limit": limit}
    if fields:
        params["fields"] = ",".join(fields)

    # Add filtering if specified
    if "filtering" in kwargs and kwargs["filtering"]:
        params["filtering"] = json.dumps(kwargs["filtering"])

    return meta_get(path, params)


def meta_api_get(endpoint: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    """
    Alias for meta_get for consistency with targeting tools.
    
    Args:
        endpoint: API endpoint without base URL
        params: Query parameters
        
    Returns:
        Tuple of (status_code, response_data)
    """
    return meta_get(endpoint, params)


def test_token_access(account_id: Optional[str] = None) -> bool:
    """
    Test if the current token has access to ad accounts and optionally a specific account.

    Returns:
        True if access is working, False otherwise
    """
    # Test basic ad accounts access
    status, data = meta_get("me/adaccounts", {"limit": 5})
    if status != 200:
        print(f"Token test FAILED: Cannot access ad accounts (status {status})", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        return False

    print(f"Token test PASSED: Can access {len(data.get('data', []))} ad accounts", file=sys.stderr)

    # Test specific account if provided
    if account_id:
        status, data = meta_get(normalize_ad_account(account_id), {"fields": "id,name"})
        if status != 200:
            print(f"Account test FAILED: Cannot access account {account_id} (status {status})", file=sys.stderr)
            print(f"Response: {data}", file=sys.stderr)
            return False

        print(f"Account test PASSED: Can access {normalize_ad_account(account_id)}", file=sys.stderr)

    return True


# Example usage (for testing):
if __name__ == "__main__":
    # Test token access
    print("Testing token access...", file=sys.stderr)
    if test_token_access("614899713980355"):
        print("All token tests passed!", file=sys.stderr)

        # Test insights
        print("\nTesting insights...", file=sys.stderr)
        status, data = get_adaccount_insights(
            "614899713980355",
            fields=["spend", "impressions", "clicks"],
            date_preset="last_7d"
        )
        print(f"Insights result: {status}, {type(data)}", file=sys.stderr)

        # Test campaigns
        print("\nTesting campaigns...", file=sys.stderr)
        status, data = get_campaigns(
            "614899713980355",
            fields=["id", "name", "status", "effective_status"],
            limit=10
        )
        print(f"Campaigns result: {status}, {type(data)}", file=sys.stderr)
    else:
        print("Token access failed - check permissions and system user assignment", file=sys.stderr)
