"""
Targeting search and validation tools for Meta Ads API.

This module provides comprehensive targeting capabilities including:
- Interest search and suggestions
- Audience size estimation
- Behavior and demographic targeting
- Geographic location search
"""

import json
from typing import Optional, List, Dict, Any
import os

try:
    from ..utils.logger import logger
    from ..api.client import APIResponse
except ImportError:
    from utils.logger import logger
    from api.client import APIResponse


def search_interests(
    query: str,
    limit: int = 25
) -> Dict[str, Any]:
    """
    Search for interest targeting options by keyword.

    Args:
        query: Search term for interests (e.g., "baseball", "cooking", "travel")
        limit: Maximum number of results to return (default: 25)

    Returns:
        Dictionary with interest data including id, name, audience_size, and path fields

    Example:
        response = search_interests("basketball", limit=10)
        # Returns interests related to basketball with audience sizes
    """
    try:
        from ..utils.meta_http import meta_api_get, get_access_token
        from ..core.formatters import format_interests_response
    except ImportError:
        from utils.meta_http import meta_api_get, get_access_token
        from core.formatters import format_interests_response

    if not query:
        return {
            "success": False,
            "error": "No search query provided. Please provide a search term."
        }

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return {
            "success": False,
            "error": "No access token available. Please authenticate first."
        }

    endpoint = "search"
    params = {
        "type": "adinterest",
        "q": query,
        "limit": limit,
        "access_token": access_token
    }

    logger.info(f"Searching interests for query: {query}")
    status_code, data = meta_api_get(endpoint, params)

    if status_code == 200:
        logger.info(f"Found {len(data.get('data', []))} interests")
        # Format the response data
        formatted_data = {"interests": data.get("data", []), "query": query}
        return format_interests_response(formatted_data)
    else:
        logger.error(f"Interest search failed: {data}")
        return {
            "success": False,
            "error": f"Failed to search interests: {data}"
        }


def get_interest_suggestions(
    interest_list: List[str],
    limit: int = 25
) -> APIResponse:
    """
    Get interest suggestions based on existing interests.
    
    Args:
        interest_list: List of interest names to get suggestions for (e.g., ["Basketball", "Soccer"])
        limit: Maximum number of suggestions to return (default: 25)

    Returns:
        APIResponse with suggested interests including id, name, audience_size, and description

    Example:
        response = get_interest_suggestions(["Basketball", "Soccer"], limit=10)
        # Returns related sports interests
    """
    try:
        from ..utils.meta_http import meta_api_get, get_access_token
    except ImportError:
        from utils.meta_http import meta_api_get, get_access_token

    if not interest_list:
        return APIResponse(
            success=False,
            data=None,
            error="No interest list provided. Please provide at least one interest."
        )

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return APIResponse(
            success=False,
            data=None,
            error="No access token available. Please authenticate first."
        )

    endpoint = "search"
    params = {
        "type": "adinterestsuggestion",
        "interest_list": json.dumps(interest_list),
        "limit": limit,
        "access_token": access_token
    }
    
    logger.info(f"Getting suggestions for interests: {interest_list}")
    status_code, data = meta_api_get(endpoint, params)
    
    if status_code == 200:
        logger.info(f"Found {len(data.get('data', []))} interest suggestions")
        return APIResponse(success=True, data=data)
    else:
        logger.error(f"Interest suggestions failed: {data}")
        return APIResponse(success=False, data=None, error=f"Failed to get interest suggestions: {data}")


def validate_interests(
    interest_list: Optional[List[str]] = None,
    interest_fbid_list: Optional[List[str]] = None
) -> APIResponse:
    """
    Validate interest names or IDs for targeting.

    Args:
        interest_list: List of interest names to validate (e.g., ["Japan", "Basketball"])
        interest_fbid_list: List of interest IDs to validate (e.g., ["6003700426513"])

    Returns:
        APIResponse with validation results showing valid status and audience_size for each interest

    Example:
        response = validate_interests(
            interest_list=["Basketball"],
            interest_fbid_list=["6003700426513"]
        )
    """
    try:
        from ..utils.meta_http import meta_api_get, get_access_token
    except ImportError:
        from utils.meta_http import meta_api_get, get_access_token

    if not interest_list and not interest_fbid_list:
        return APIResponse(
            success=False,
            data=None,
            error="No interest list or FBID list provided. Please provide at least one."
        )

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return APIResponse(
            success=False,
            data=None,
            error="No access token available. Please authenticate first."
        )

    endpoint = "search"
    params = {
        "type": "adinterestvalid",
        "access_token": access_token
    }
    
    if interest_list:
        params["interest_list"] = json.dumps(interest_list)
    
    if interest_fbid_list:
        params["interest_fbid_list"] = json.dumps(interest_fbid_list)
    
    logger.info(f"Validating interests: {interest_list or interest_fbid_list}")
    status_code, data = meta_api_get(endpoint, params)
    
    if status_code == 200:
        return APIResponse(success=True, data=data)
    else:
        logger.error(f"Interest validation failed: {data}")
        return APIResponse(success=False, data=None, error=f"Failed to validate interests: {data}")


def estimate_audience_size(
    account_id: str,
    targeting: Dict[str, Any],
    optimization_goal: str = "REACH"
) -> APIResponse:
    """
    Estimate audience size for targeting specifications using Meta's reachestimate API.
    
    This provides comprehensive audience estimation for complex targeting combinations
    including demographics, geography, interests, and behaviors.

    Args:
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        targeting: Complete targeting specification including demographics, geography, interests, etc.
                  Example: {
                      "age_min": 25,
                      "age_max": 65,
                      "geo_locations": {"countries": ["PL"]},
                      "flexible_spec": [
                          {"interests": [{"id": "6003371567474"}]},
                          {"interests": [{"id": "6003462346642"}]}
                      ]
                  }
        optimization_goal: Optimization goal for estimation (default: "REACH"). 
                          Options: "REACH", "LINK_CLICKS", "IMPRESSIONS", "CONVERSIONS", etc.

    Returns:
        APIResponse with audience estimation results including estimated_audience_size,
        reach_estimate, and targeting validation
    
    Example:
        targeting = {
            "age_min": 25,
            "age_max": 45,
            "geo_locations": {"countries": ["US"]},
            "flexible_spec": [{"interests": [{"id": "6003139266461"}]}]
        }
        response = estimate_audience_size("act_123456", targeting)
    """
    try:
        from ..utils.meta_http import meta_api_get, normalize_ad_account, get_access_token
    except ImportError:
        from utils.meta_http import meta_api_get, normalize_ad_account, get_access_token
    
    if not account_id:
        return APIResponse(
            success=False,
            data=None,
            error="account_id is required for comprehensive audience estimation"
        )
    
    if not targeting:
        return APIResponse(
            success=False,
            data=None,
            error={
                "message": "targeting specification is required for comprehensive audience estimation",
                "example": {
                    "age_min": 25,
                    "age_max": 65,
                    "geo_locations": {"countries": ["US"]},
                    "flexible_spec": [
                        {"interests": [{"id": "6003371567474"}]}
                    ]
                }
            }
        )
    
    # Validate that targeting has location or custom audience
    def _has_location_or_custom_audience(t: Dict[str, Any]) -> bool:
        if not isinstance(t, dict):
            return False
        geo = t.get("geo_locations") or {}
        if isinstance(geo, dict):
            for key in ["countries", "regions", "cities", "zips", "geo_markets", "country_groups"]:
                val = geo.get(key)
                if isinstance(val, list) and len(val) > 0:
                    return True
        ca = t.get("custom_audiences")
        if isinstance(ca, list) and len(ca) > 0:
            return True
        return False

    if not _has_location_or_custom_audience(targeting):
        return APIResponse(
            success=False,
            data=None,
            error={
                "message": "Missing target audience location",
                "details": "Select at least one location in targeting.geo_locations or include a custom audience.",
                "action_required": "Add geo_locations with countries/regions/cities/zips or include custom_audiences.",
                "example": {
                    "geo_locations": {"countries": ["US"]},
                    "age_min": 25,
                    "age_max": 65
                }
            }
        )

    # Validate optimization_goal parameter
    VALID_OPTIMIZATION_GOALS = [
        'REACH', 'LINK_CLICKS', 'IMPRESSIONS', 'CONVERSIONS',
        'APP_INSTALLS', 'OFFSITE_CONVERSIONS', 'LEAD_GENERATION',
        'POST_ENGAGEMENT', 'PAGE_LIKES', 'EVENT_RESPONSES',
        'MESSAGES', 'VIDEO_VIEWS', 'THRUPLAY', 'LANDING_PAGE_VIEWS'
    ]

    if optimization_goal and optimization_goal not in VALID_OPTIMIZATION_GOALS:
        return APIResponse(
            success=False,
            data=None,
            error={
                "message": f"Invalid optimization_goal: '{optimization_goal}'",
                "valid_options": VALID_OPTIMIZATION_GOALS,
                "details": "Please use one of the valid optimization goals listed above."
            }
        )

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return APIResponse(
            success=False,
            data=None,
            error="No access token available. Please authenticate first."
        )

    # Normalize account ID
    account_id = normalize_ad_account(account_id)

    # Build reach estimate request
    endpoint = f"{account_id}/reachestimate"
    params = {
        "targeting_spec": json.dumps(targeting),
        "optimization_goal": optimization_goal,
        "access_token": access_token
    }
    
    logger.info(f"Estimating audience size for account: {account_id}")
    status_code, data = meta_api_get(endpoint, params)
    
    if status_code == 200:
        # Format the response for easier consumption
        if "data" in data:
            response_data = data["data"]
            if isinstance(response_data, dict):
                lower = response_data.get("users_lower_bound", response_data.get("estimate_mau_lower_bound"))
                upper = response_data.get("users_upper_bound", response_data.get("estimate_mau_upper_bound"))
                estimate_ready = response_data.get("estimate_ready")
                midpoint = None
                try:
                    if isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
                        midpoint = int((lower + upper) / 2)
                except Exception:
                    midpoint = None
                    
                formatted_response = {
            "success": True,
                    "account_id": account_id,
                    "targeting": targeting,
                    "optimization_goal": optimization_goal,
                    "estimated_audience_size": midpoint if midpoint is not None else 0,
                    "estimate_details": {
                        "users_lower_bound": lower,
                        "users_upper_bound": upper,
                        "estimate_ready": estimate_ready
                    },
                    "raw_response": data
                }
                return APIResponse(success=True, data=formatted_response)
        
        return APIResponse(success=True, data=data)
    else:
        logger.error(f"Audience estimation failed: {data}")
        return APIResponse(success=False, data=None, error=f"Failed to estimate audience size: {data}")


def search_behaviors(
    behavior_class: str = "behaviors",
    limit: int = 50
) -> APIResponse:
    """
    Get behavior targeting options by class.

    Args:
        behavior_class: Type of behaviors to retrieve. Options: 'behaviors', 'industries',
                       'family_statuses', 'life_events' (default: 'behaviors')
        limit: Maximum number of results to return (default: 50)

    Returns:
        APIResponse with behavior targeting options including id, name, audience_size bounds,
        path, and description

    Example:
        response = search_behaviors(behavior_class="behaviors", limit=20)
        # Returns behavior targeting options like "Small business owners", "Frequent travelers", etc.

        response = search_behaviors(behavior_class="industries", limit=10)
        # Returns industry targeting options like "Technology", "Healthcare", etc.
    """
    try:
        from ..utils.meta_http import meta_api_get, get_access_token
    except ImportError:
        from utils.meta_http import meta_api_get, get_access_token

    # Validate behavior_class parameter
    valid_classes = ["behaviors", "industries", "family_statuses", "life_events"]
    if behavior_class not in valid_classes:
        return APIResponse(
            success=False,
            data=None,
            error=f"Invalid behavior_class: '{behavior_class}'. Valid options: {', '.join(valid_classes)}"
        )

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return APIResponse(
            success=False,
            data=None,
            error="No access token available. Please authenticate first."
        )

    endpoint = "search"
    params = {
        "type": "adTargetingCategory",
        "class": behavior_class,
        "limit": limit,
        "access_token": access_token
    }

    logger.info(f"Searching '{behavior_class}' targeting options")
    status_code, data = meta_api_get(endpoint, params)

    if status_code == 200:
        logger.info(f"Found {len(data.get('data', []))} {behavior_class} targeting options")
        return APIResponse(success=True, data=data)
    else:
        logger.error(f"{behavior_class.capitalize()} search failed: {data}")
        return APIResponse(success=False, data=None, error=f"Failed to search {behavior_class}: {data}")


def search_demographics(
    demographic_class: str = "demographics",
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get demographic targeting options.

    Args:
        demographic_class: Type of demographics to retrieve. Options: 'demographics', 'life_events',
                          'industries', 'income', 'family_statuses', 'user_device', 'user_os'
                          (default: 'demographics')
        limit: Maximum number of results to return (default: 50)

    Returns:
        Dictionary with demographic targeting options including id, name, audience_size bounds,
        path, and description

    Example:
        response = search_demographics(demographic_class="life_events")
        # Returns life events like "Recently moved", "New job", "Anniversary", etc.
    """
    try:
        from ..api.client import MetaAPIClient
        from ..core.formatters import format_demographics_response
        from ..utils.meta_http import get_access_token
    except ImportError:
        from api.client import MetaAPIClient
        from core.formatters import format_demographics_response
        from utils.meta_http import get_access_token

    valid_classes = ["demographics", "life_events", "industries", "income",
                    "family_statuses", "user_device", "user_os"]

    if demographic_class not in valid_classes:
        return {
            "success": False,
            "error": {
                "message": f"Invalid demographic_class: {demographic_class}",
                "valid_options": valid_classes
            }
        }

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return {
            "success": False,
            "error": "No access token available. Please authenticate first."
        }

    try:
        logger.info(f"Searching demographic targeting options for class: {demographic_class}")

        # Create Meta API client instance
        client = MetaAPIClient(access_token)

        # Try the standard adTargetingCategory approach first
        response = client.search_demographics(demographic_class, limit)

        if response.success:
            logger.info(f"Found {len(response.data.get('demographics', []))} demographic targeting options")
            # Format the response data
            formatted_data = {
                "demographics": response.data.get("demographics", []),
                "demographic_class": demographic_class
            }
            return format_demographics_response(formatted_data)
        else:
            # If adTargetingCategory fails, try alternative approaches
            logger.warning(f"Standard demographics search failed: {response.error}")
            logger.info("Attempting alternative demographics retrieval methods...")

            # Try getting targeting suggestions from account
            # Some accounts may have demographics available through targeting specs
            try:
                # Get a sample account to check targeting options
                accounts_response = client.get_ad_accounts()
                if accounts_response.success and accounts_response.data.get('accounts'):
                    account_id = accounts_response.data['accounts'][0]['id']
                    logger.info(f"Trying to get demographics from account {account_id}")

                    # Try to get account targeting specs (this might provide demographics)
                    # This is an experimental approach - the API might have changed
                    demo_response = client._make_request(
                        "GET",
                        endpoint=f"act_{account_id.replace('act_', '')}/targetingsuggestions",
                        params={"type": demographic_class, "limit": limit}
                    )

                    if demo_response.success and demo_response.data.get('data'):
                        logger.info(f"Alternative method found {len(demo_response.data.get('data', []))} demographic options")
                        formatted_data = {
                            "demographics": demo_response.data.get("data", []),
                            "demographic_class": demographic_class
                        }
                        return format_demographics_response(formatted_data)

            except Exception as alt_e:
                logger.warning(f"Alternative demographics method also failed: {alt_e}")

            # If all methods fail, return a helpful error message
            return {
                "success": False,
                "error": f"Demographics search not supported for this account. This may be due to account type, permissions, or regional restrictions. Error: {response.error}",
                "note": "Demographics targeting may not be available for all account types or regions. Try using interests or location targeting instead."
            }

    except Exception as e:
        logger.error(f"Demographics search failed with exception: {e}")
        return {
            "success": False,
            "error": f"Failed to search demographics: {str(e)}"
        }


def search_geo_locations(
    query: str,
    location_types: Optional[List[str]] = None,
    limit: int = 25
) -> APIResponse:
    """
    Search for geographic targeting locations.
    
    Args:
        query: Search term for locations (e.g., "New York", "California", "Japan")
        location_types: Types of locations to search. Options: ['country', 'region', 'city', 'zip',
                       'geo_market', 'electoral_district']. If not specified, searches all types.
        limit: Maximum number of results to return (default: 25)
    
    Returns:
        APIResponse with location data including key, name, type, and geographic hierarchy information
    
    Example:
        response = search_geo_locations(
            "New York",
            location_types=["city", "region"]
        )
        # Returns cities and regions matching "New York"
    """
    try:
        from ..utils.meta_http import meta_api_get, get_access_token
    except ImportError:
        from utils.meta_http import meta_api_get, get_access_token

    if not query:
        return APIResponse(
            success=False,
            data=None,
            error="No search query provided. Please provide a location search term."
        )

    # Get access token internally
    access_token = get_access_token()
    if not access_token:
        return APIResponse(
            success=False,
            data=None,
            error="No access token available. Please authenticate first."
        )

    endpoint = "search"
    params = {
        "type": "adgeolocation",
        "q": query,
        "limit": limit,
        "access_token": access_token
    }
    
    if location_types:
        valid_types = ["country", "region", "city", "zip", "geo_market", "electoral_district"]
        invalid_types = [t for t in location_types if t not in valid_types]
        if invalid_types:
            return APIResponse(
                success=False,
                data=None,
                error={
                    "message": f"Invalid location types: {invalid_types}",
                    "valid_options": valid_types
                }
            )
        params["location_types"] = json.dumps(location_types)
    
    logger.info(f"Searching geo locations for query: {query}")
    status_code, data = meta_api_get(endpoint, params)
    
    if status_code == 200:
        logger.info(f"Found {len(data.get('data', []))} geographic locations")
        return APIResponse(success=True, data=data)
    else:
        logger.error(f"Geo location search failed: {data}")
        return APIResponse(success=False, data=None, error=f"Failed to search geo locations: {data}")
