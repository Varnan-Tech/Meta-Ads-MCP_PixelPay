"""
Validation and prerequisites system for Meta Ads MCP server.
Ensures data integrity and prevents AI hallucination.
"""
from typing import Dict, Any, List, Optional, Callable, Tuple
import re

try:
    # Try absolute imports first (when run as part of package)
    from ..auth.token_manager import token_manager
    from ..config.settings import settings
    from ..utils.logger import logger
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from auth.token_manager import token_manager
    from config.settings import settings
    from utils.logger import logger


# Validation rules for different object types
VALIDATION_RULES = {
    'account_id': {
        'pattern': r'^(act_\d+|\d{15,18})$',
        'description': 'Account ID must be in format act_123456789 or 15-18 digits'
    },
    'campaign_id': {
        'pattern': r'^\d{15,18}$',
        'description': 'Campaign ID must be 15-18 digits'
    },
    'adset_id': {
        'pattern': r'^\d{15,18}$',
        'description': 'Ad set ID must be 15-18 digits'
    },
    'ad_id': {
        'pattern': r'^\d{15,18}$',
        'description': 'Ad ID must be 15-18 digits'
    }
}


def validate_object_id(object_id: str, object_type: str) -> Tuple[bool, str]:
    """
    Validate an object ID format.

    Args:
        object_id: The ID to validate
        object_type: Type of object ('account_id', 'campaign_id', etc.)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if object_type not in VALIDATION_RULES:
        return True, ""  # No validation rule, assume valid

    rule = VALIDATION_RULES[object_type]
    pattern = rule['pattern']

    if not re.match(pattern, object_id):
        return False, rule['description']

    return True, ""


def validate_api_access() -> Tuple[bool, str]:
    """
    Validate that API access is available.

    Returns:
        Tuple of (has_access, error_message)
    """
    try:
        token = token_manager.get_token() or settings.meta_access_token
        if not token:
            return False, "No Meta access token configured. Please set META_ACCESS_TOKEN environment variable."

        # Basic token format validation
        if not token.startswith('EAA') or len(token) < 50:
            return False, "Invalid Meta access token format."

        return True, ""
    except Exception as e:
        return False, f"API access validation failed: {str(e)}"


# Tool prerequisites mapping
TOOL_PREREQUISITES = {
    'get_account_info': ['validate_api_access'],
    'get_campaigns': ['validate_api_access', 'validate_account_id'],
    'get_campaign_details': ['validate_api_access', 'validate_campaign_id'],
    'create_campaign': ['validate_api_access', 'validate_account_id'],
    'update_campaign': ['validate_api_access', 'validate_campaign_id'],
    'get_adsets': ['validate_api_access', 'validate_account_id'],
    'get_adset_details': ['validate_api_access', 'validate_adset_id'],
    'get_ads': ['validate_api_access'],
    'get_ad_details': ['validate_api_access', 'validate_ad_id'],
    'get_ad_creatives': ['validate_api_access', 'validate_ad_id'],
    'get_insights': ['validate_api_access'],
    'search_interests': ['validate_api_access'],
    'search_demographics': ['validate_api_access'],
    'search_locations': ['validate_api_access'],
    'analyze_campaigns': ['validate_api_access', 'validate_account_id']
}


def validate_account_id(account_id: str) -> bool:
    """Validate account ID format."""
    is_valid, error = validate_object_id(account_id, 'account_id')
    if not is_valid:
        logger.warning(f"Invalid account ID '{account_id}': {error}")
    return is_valid


def validate_campaign_id(campaign_id: str) -> bool:
    """Validate campaign ID format."""
    is_valid, error = validate_object_id(campaign_id, 'campaign_id')
    if not is_valid:
        logger.warning(f"Invalid campaign ID '{campaign_id}': {error}")
    return is_valid


def validate_adset_id(adset_id: str) -> bool:
    """Validate ad set ID format."""
    is_valid, error = validate_object_id(adset_id, 'adset_id')
    if not is_valid:
        logger.warning(f"Invalid ad set ID '{adset_id}': {error}")
    return is_valid


def validate_ad_id(ad_id: str) -> bool:
    """Validate ad ID format."""
    is_valid, error = validate_object_id(ad_id, 'ad_id')
    if not is_valid:
        logger.warning(f"Invalid ad ID '{ad_id}': {error}")
    return is_valid


def validate_campaign_input(campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate campaign creation/update input data.

    Args:
        campaign_data: Campaign data to validate

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    errors = []
    result = {"valid": True, "errors": errors}

    # Validate name
    name = campaign_data.get('name', '').strip()
    if not name:
        errors.append("Campaign name is required")
        result["valid"] = False
    elif len(name) > 100:
        errors.append("Campaign name must be 100 characters or less")
        result["valid"] = False

    # Validate objective
    valid_objectives = [
        'OUTCOME_SALES', 'OUTCOME_LEADS', 'OUTCOME_TRAFFIC', 'OUTCOME_ENGAGEMENT',
        'OUTCOME_APP_PROMOTION', 'OUTCOME_AWARENESS', 'REACH', 'IMPRESSIONS',
        'LINK_CLICKS', 'CONVERSIONS', 'CATALOG_SALES', 'STORE_VISITS'
    ]
    objective = campaign_data.get('objective')
    if not objective:
        errors.append("Campaign objective is required")
        result["valid"] = False
    elif objective not in valid_objectives:
        errors.append(f"Invalid objective '{objective}'. Valid options: {', '.join(valid_objectives[:5])}...")
        result["valid"] = False

    # Validate budgets
    daily_budget = campaign_data.get('daily_budget')
    lifetime_budget = campaign_data.get('lifetime_budget')

    if daily_budget is not None and lifetime_budget is not None:
        errors.append("Cannot specify both daily_budget and lifetime_budget")
        result["valid"] = False
    elif daily_budget is not None:
        if not isinstance(daily_budget, (int, float)) or daily_budget <= 0:
            errors.append("Daily budget must be a positive number")
            result["valid"] = False
    elif lifetime_budget is not None:
        if not isinstance(lifetime_budget, (int, float)) or lifetime_budget <= 0:
            errors.append("Lifetime budget must be a positive number")
            result["valid"] = False

    # Validate status
    valid_statuses = ['ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED']
    status = campaign_data.get('status', 'PAUSED')
    if status not in valid_statuses:
        errors.append(f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}")
        result["valid"] = False

    result["errors"] = errors
    return result


def check_tool_prerequisites(tool_name: str, **kwargs) -> Tuple[bool, str]:
    """
    Check prerequisites for a tool before execution.

    Args:
        tool_name: Name of the tool
        **kwargs: Tool parameters

    Returns:
        Tuple of (can_proceed, error_message)
    """
    if tool_name not in TOOL_PREREQUISITES:
        return True, ""  # No prerequisites defined

    prerequisites = TOOL_PREREQUISITES[tool_name]

    for prereq in prerequisites:
        if prereq == 'validate_api_access':
            has_access, error = validate_api_access()
            if not has_access:
                return False, error

        elif prereq == 'validate_account_id' and 'account_id' in kwargs:
            if not validate_account_id(kwargs['account_id']):
                return False, f"Invalid account ID format: {kwargs['account_id']}"

        elif prereq == 'validate_campaign_id' and 'campaign_id' in kwargs:
            if not validate_campaign_id(kwargs['campaign_id']):
                return False, f"Invalid campaign ID format: {kwargs['campaign_id']}"

        elif prereq == 'validate_adset_id' and 'adset_id' in kwargs:
            if not validate_adset_id(kwargs['adset_id']):
                return False, f"Invalid ad set ID format: {kwargs['adset_id']}"

        elif prereq == 'validate_ad_id' and 'ad_id' in kwargs:
            if not validate_ad_id(kwargs['ad_id']):
                return False, f"Invalid ad ID format: {kwargs['ad_id']}"

    return True, ""


def validate_response_integrity(response: Dict[str, Any], expected_fields: List[str] = None) -> Tuple[bool, str]:
    """
    Validate response integrity to prevent data corruption.

    Args:
        response: API response to validate
        expected_fields: List of fields that should be present

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not isinstance(response, dict):
            return False, "Response is not a valid dictionary"

        if 'success' not in response:
            return False, "Response missing 'success' field"

        if not response.get('success'):
            # Check if there's a proper error message
            if 'error' not in response:
                return False, "Failed response missing error message"
            return True, ""  # Valid failed response

        # For successful responses, check expected fields
        if expected_fields:
            for field in expected_fields:
                if field not in response:
                    return False, f"Response missing expected field: {field}"

        return True, ""

    except Exception as e:
        return False, f"Response validation failed: {str(e)}"


def create_validation_wrapper(tool_function: Callable, tool_name: str) -> Callable:
    """
    Create a validation wrapper for a tool function.

    Args:
        tool_function: The original tool function
        tool_name: Name of the tool

    Returns:
        Wrapped function with validation
    """
    def wrapper(*args, **kwargs):
        try:
            # Check prerequisites
            can_proceed, error = check_tool_prerequisites(tool_name, **kwargs)
            if not can_proceed:
                logger.error(f"Tool {tool_name} prerequisite check failed: {error}")
                return {
                    "success": False,
                    "error": error,
                    "validation_error": True
                }

            # Execute the tool
            result = tool_function(*args, **kwargs)

            # Validate response integrity
            is_valid, validation_error = validate_response_integrity(result)
            if not is_valid:
                logger.error(f"Tool {tool_name} response validation failed: {validation_error}")
                return {
                    "success": False,
                    "error": f"Response validation failed: {validation_error}",
                    "validation_error": True
                }

            # Add validation metadata
            result['_validated'] = True
            result['_tool_name'] = tool_name

            return result

        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "validation_error": True
            }

    return wrapper


# Data integrity checks
def verify_ad_hierarchy(account_id: str, campaign_id: str = None, adset_id: str = None, ad_id: str = None) -> Tuple[bool, str]:
    """
    Verify that ad objects belong to the correct hierarchy.

    Args:
        account_id: Account ID
        campaign_id: Optional campaign ID
        adset_id: Optional ad set ID
        ad_id: Optional ad ID

    Returns:
        Tuple of (is_valid, error_message)
    """
    # This would require API calls to verify hierarchy
    # For now, just do basic format validation
    validations = []

    if account_id and not validate_account_id(account_id):
        validations.append(f"Invalid account ID: {account_id}")

    if campaign_id and not validate_campaign_id(campaign_id):
        validations.append(f"Invalid campaign ID: {campaign_id}")

    if adset_id and not validate_adset_id(adset_id):
        validations.append(f"Invalid ad set ID: {adset_id}")

    if ad_id and not validate_ad_id(ad_id):
        validations.append(f"Invalid ad ID: {ad_id}")

    if validations:
        return False, "; ".join(validations)

    return True, ""


def create_account_analysis(account_id: str, insights_data: list = None) -> Dict[str, Any]:
    """
    Create a comprehensive analysis for an ad account.

    Args:
        account_id: Meta ad account ID
        insights_data: Optional insights data from API

    Returns:
        Comprehensive analysis dictionary
    """
    try:
        # Try absolute imports first (when run as part of package)
        from ..tools.accounts import get_account_info
        from ..tools.campaigns import get_campaigns
    except ImportError:
        # Fall back to relative imports (when run as script)
        import sys
        import os
        current_dir = os.path.dirname(__file__)
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        try:
            from tools.accounts import get_account_info
            from tools.campaigns import get_campaigns
        except ImportError:
            # Last resort - try from parent directory
            parent_dir = os.path.dirname(current_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from src.tools.accounts import get_account_info
            from src.tools.campaigns import get_campaigns

        analysis = {
            "account_id": account_id,
            "analysis_timestamp": "2025-10-23T14:00:00Z",
            "data_sources": [],
            "insights": {},
            "recommendations": [],
            "risks": []
        }

        # Get account information
        account_result = get_account_info(account_id)
        if account_result.get('success'):
            account = account_result.get('account', {})
            analysis["account_info"] = {
                "name": account.get('name', 'Unknown'),
                "currency": account.get('currency', 'USD'),
                "status": account.get('account_status', 'Unknown'),
                "balance": account.get('balance', '0.00')
            }
            analysis["data_sources"].append("account_info")
        else:
            analysis["account_info"] = {"error": "Could not retrieve account information"}
            analysis["risks"].append("Unable to access account details")

        # Get campaign information
        campaigns_result = get_campaigns(account_id, limit=100)
        if campaigns_result.get('success'):
            campaigns = campaigns_result.get('campaigns', [])
            analysis["campaigns"] = {
                "total_count": len(campaigns),
                "active_count": len([c for c in campaigns if c.get('status') == 'ACTIVE']),
                "paused_count": len([c for c in campaigns if c.get('status') == 'PAUSED']),
                "sample_campaigns": campaigns[:5]  # First 5 for overview
            }
            analysis["data_sources"].append("campaigns")

            # Basic campaign analysis
            if campaigns:
                objectives = {}
                for campaign in campaigns:
                    obj = campaign.get('objective', 'Unknown')
                    objectives[obj] = objectives.get(obj, 0) + 1

                analysis["campaign_analysis"] = {
                    "primary_objectives": objectives,
                    "most_common_objective": max(objectives.items(), key=lambda x: x[1])[0] if objectives else "None"
                }
        else:
            analysis["campaigns"] = {"error": "Could not retrieve campaigns"}
            analysis["risks"].append("Unable to access campaign data")

        # Analyze insights data
        if insights_data and len(insights_data) > 0:
            analysis["insights"] = {
                "total_records": len(insights_data),
                "date_range": f"{insights_data[0].get('date_start', 'Unknown')} to {insights_data[-1].get('date_stop', 'Unknown')}",
                "total_spend": sum(float(i.get('spend', '0').replace('$', '').replace(',', '')) for i in insights_data),
                "total_impressions": sum(int(i.get('impressions', '0').replace(',', '')) for i in insights_data),
                "total_clicks": sum(int(i.get('clicks', '0').replace(',', '')) for i in insights_data)
            }

            # Calculate derived metrics
            total_spend = analysis["insights"]["total_spend"]
            total_impressions = analysis["insights"]["total_impressions"]
            total_clicks = analysis["insights"]["total_clicks"]

            analysis["insights"]["average_ctr"] = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            analysis["insights"]["average_cpm"] = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0
            analysis["insights"]["average_cpc"] = (total_spend / total_clicks) if total_clicks > 0 else 0

        else:
            analysis["insights"] = {
                "status": "No insights data available",
                "possible_reasons": [
                    "Account has no active campaigns",
                    "Campaigns have no recent activity",
                    "API permissions may limit insights access",
                    "Time range may not include active periods"
                ]
            }

        # Generate recommendations
        if analysis.get("campaigns", {}).get("total_count", 0) == 0:
            analysis["recommendations"].append("Create your first campaign to start collecting performance data")
        elif analysis.get("campaigns", {}).get("active_count", 0) == 0:
            analysis["recommendations"].append("Activate campaigns to start generating insights and results")

        if not insights_data or len(insights_data) == 0:
            analysis["recommendations"].append("Monitor campaign performance regularly to optimize ad spend")
            analysis["recommendations"].append("Ensure campaigns have sufficient budget and are properly targeted")

        # Determine account health
        active_campaigns = analysis.get("campaigns", {}).get("active_count", 0)
        total_campaigns = analysis.get("campaigns", {}).get("total_count", 0)

        if total_campaigns == 0:
            analysis["account_health"] = "Not Started"
            analysis["recommendations"].insert(0, "Set up your first advertising campaign")
        elif active_campaigns == 0:
            analysis["account_health"] = "Inactive"
            analysis["recommendations"].insert(0, "Activate existing campaigns to start advertising")
        elif active_campaigns / total_campaigns > 0.7:
            analysis["account_health"] = "Very Active"
        elif active_campaigns / total_campaigns > 0.3:
            analysis["account_health"] = "Active"
        else:
            analysis["account_health"] = "Moderately Active"

        return analysis

    except Exception as e:
        logger.error(f"Error creating account analysis for {account_id}: {e}")
        return {
            "account_id": account_id,
            "error": f"Analysis failed: {str(e)}",
            "account_health": "Error",
            "recommendations": ["Contact support if issues persist"]
        }


def log_validation_metrics(tool_name: str, success: bool, execution_time: float = None):
    """
    Log validation metrics for monitoring.

    Args:
        tool_name: Name of the tool
        success: Whether validation succeeded
        execution_time: Optional execution time
    """
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"Validation {status} for tool '{tool_name}'" +
               (f" in {execution_time:.2f}s" if execution_time else ""))