"""
Response formatters for Meta Ads MCP server.
"""
from typing import Dict, Any, List, Union
import json

try:
    # Try absolute imports first (when run as part of package)
    from ..utils.helpers import format_currency, format_number, format_percentage, format_date
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from utils.helpers import format_currency, format_number, format_percentage, format_date


def format_accounts_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format accounts response for MCP.

    Args:
        data: Raw accounts data from API

    Returns:
        Formatted response
    """
    try:
        accounts = data.get('accounts', [])

        formatted_accounts = []
        for account in accounts:
            formatted_account = {
                "id": account.get('id'),
                "name": account.get('name', 'Unknown'),
                "account_id": account.get('account_id'),
                "currency": account.get('currency', 'USD'),
                "status": account.get('account_status', 'UNKNOWN'),
                "balance": format_currency(account.get('balance', 0), account.get('currency', 'USD'))
            }
            formatted_accounts.append(formatted_account)

        return {
            "success": True,
            "accounts": formatted_accounts,
            "count": len(formatted_accounts)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format accounts response: {str(e)}"
        }


def format_account_info_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format account info response for MCP.

    Args:
        data: Raw account data from API

    Returns:
        Formatted response
    """
    try:
        formatted_info = {
            "id": data.get('id'),
            "name": data.get('name', 'Unknown'),
            "account_id": data.get('account_id'),
            "currency": data.get('currency', 'USD'),
            "status": data.get('account_status', 'UNKNOWN'),
            "balance": format_currency(data.get('balance', 0), data.get('currency', 'USD')),
            "spend_cap": format_currency(data.get('spend_cap', 0), data.get('currency', 'USD')),
            "timezone": data.get('timezone_name', 'Unknown')
        }

        return {
            "success": True,
            "account": formatted_info
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format account info response: {str(e)}"
        }


def format_campaigns_response(data: Any) -> Dict[str, Any]:
    """
    Format campaigns response for MCP.

    Args:
        data: Raw campaigns data from API (may include Facebook SDK objects)

    Returns:
        Formatted response safe for JSON serialization
    """
    try:
        # Convert Facebook SDK objects to plain Python objects
        safe_data = convert_facebook_object(data)
        campaigns = safe_data.get('campaigns', [])

        formatted_campaigns = []
        for campaign in campaigns:
            # Format budget based on currency
            currency = 'USD'  # Default, could be extracted from account

            daily_budget = None
            if campaign.get('daily_budget'):
                daily_budget = format_currency(campaign.get('daily_budget'), currency)

            lifetime_budget = None
            if campaign.get('lifetime_budget'):
                lifetime_budget = format_currency(campaign.get('lifetime_budget'), currency)

            formatted_campaign = {
                "id": campaign.get('id'),
                "name": campaign.get('name', 'Unknown'),
                "status": campaign.get('status', 'UNKNOWN'),
                "effective_status": campaign.get('effective_status', 'UNKNOWN'),
                "objective": campaign.get('objective', 'Unknown'),
                "daily_budget": daily_budget,
                "lifetime_budget": lifetime_budget,
                "created_time": format_date(campaign.get('created_time', '')),
                "updated_time": format_date(campaign.get('updated_time', ''))
            }
            formatted_campaigns.append(formatted_campaign)

        return {
            "success": True,
            "campaigns": formatted_campaigns,
            "count": len(formatted_campaigns)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format campaigns response: {str(e)}"
        }


def format_campaign_details_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format campaign details response for MCP.

    Args:
        data: Raw campaign data from API

    Returns:
        Formatted response
    """
    try:
        # Format budget based on currency
        currency = 'USD'  # Default, could be extracted from account

        daily_budget = None
        if data.get('daily_budget'):
            daily_budget = format_currency(data.get('daily_budget'), currency)

        lifetime_budget = None
        if data.get('lifetime_budget'):
            lifetime_budget = format_currency(data.get('lifetime_budget'), currency)

        formatted_campaign = {
            "id": data.get('id'),
            "name": data.get('name', 'Unknown'),
            "status": data.get('status', 'UNKNOWN'),
            "effective_status": data.get('effective_status', 'UNKNOWN'),
            "objective": data.get('objective', 'Unknown'),
            "daily_budget": daily_budget,
            "lifetime_budget": lifetime_budget,
            "created_time": format_date(data.get('created_time', '')),
            "updated_time": format_date(data.get('updated_time', ''))
        }

        return {
            "success": True,
            "campaign": formatted_campaign
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format campaign details response: {str(e)}"
        }


def format_adsets_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format ad sets response for display.

    Args:
        data: Raw ad sets data from API

    Returns:
        Formatted ad sets response
    """
    try:
        if 'adsets' not in data:
            return {
                "success": False,
                "error": "No adsets data found"
            }

        adsets = data['adsets']
        formatted_adsets = []

        for adset in adsets:
            formatted_adset = {
                "id": adset.get('id', 'N/A'),
                "name": adset.get('name', 'Unnamed Ad Set'),
                "status": adset.get('status', 'UNKNOWN'),
                "campaign_id": adset.get('campaign_id', 'N/A'),
                "account_id": adset.get('account_id', 'N/A'),
                "optimization_goal": adset.get('optimization_goal', 'N/A'),
                "billing_event": adset.get('billing_event', 'N/A'),
                "daily_budget": format_currency(adset.get('daily_budget')),
                "lifetime_budget": format_currency(adset.get('lifetime_budget')),
                "bid_amount": format_currency(adset.get('bid_amount')),
                "created_time": format_date(adset.get('created_time')),
                "updated_time": format_date(adset.get('updated_time')),
                "targeting_summary": _summarize_targeting(adset.get('targeting', {}))
            }
            formatted_adsets.append(formatted_adset)

        return {
            "success": True,
            "adsets": formatted_adsets,
            "count": len(formatted_adsets)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format adsets response: {str(e)}"
        }


def format_adset_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format single ad set response for display.

    Args:
        data: Raw ad set data from API

    Returns:
        Formatted ad set response
    """
    try:
        formatted_adset = {
            "id": data.get('id', 'N/A'),
            "name": data.get('name', 'Unnamed Ad Set'),
            "status": data.get('status', 'UNKNOWN'),
            "campaign_id": data.get('campaign_id', 'N/A'),
            "account_id": data.get('account_id', 'N/A'),
            "optimization_goal": data.get('optimization_goal', 'N/A'),
            "billing_event": data.get('billing_event', 'N/A'),
            "daily_budget": format_currency(data.get('daily_budget')),
            "lifetime_budget": format_currency(data.get('lifetime_budget')),
            "bid_amount": format_currency(data.get('bid_amount')),
            "created_time": format_date(data.get('created_time')),
            "updated_time": format_date(data.get('updated_time')),
            "targeting": data.get('targeting', {}),
            "promoted_object": data.get('promoted_object', {})
        }

        return {
            "success": True,
            "adset": formatted_adset
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format adset response: {str(e)}"
        }


def format_ads_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format ads response for display.

    Args:
        data: Raw ads data from API

    Returns:
        Formatted ads response
    """
    try:
        if 'ads' not in data:
            return {
                "success": False,
                "error": "No ads data found"
            }

        ads = data['ads']
        formatted_ads = []

        for ad in ads:
            formatted_ad = {
                "id": ad.get('id', 'N/A'),
                "name": ad.get('name', 'Unnamed Ad'),
                "status": ad.get('status', 'UNKNOWN'),
                "adset_id": ad.get('adset_id', 'N/A'),
                "campaign_id": ad.get('campaign_id', 'N/A'),
                "account_id": ad.get('account_id', 'N/A'),
                "creative_id": ad.get('creative', {}).get('id') if ad.get('creative') else 'N/A',
                "created_time": format_date(ad.get('created_time')),
                "updated_time": format_date(ad.get('updated_time')),
                "tracking_specs": ad.get('tracking_specs', [])
            }
            formatted_ads.append(formatted_ad)

        return {
            "success": True,
            "ads": formatted_ads,
            "count": len(formatted_ads)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format ads response: {str(e)}"
        }


def format_ad_response(data: Any) -> Dict[str, Any]:
    """
    Format single ad response for display.

    Args:
        data: Raw ad data from API (may include Facebook SDK objects)

    Returns:
        Formatted ad response safe for JSON serialization
    """
    try:
        # Convert Facebook SDK objects to plain Python objects
        safe_data = convert_facebook_object(data)

        formatted_ad = {
            "id": safe_data.get('id', 'N/A'),
            "name": safe_data.get('name', 'Unnamed Ad'),
            "status": safe_data.get('status', 'UNKNOWN'),
            "adset_id": safe_data.get('adset_id', 'N/A'),
            "campaign_id": safe_data.get('campaign_id', 'N/A'),
            "account_id": safe_data.get('account_id', 'N/A'),
            "creative": safe_data.get('creative', {}),
            "created_time": format_date(safe_data.get('created_time')),
            "updated_time": format_date(safe_data.get('updated_time')),
            "tracking_specs": safe_data.get('tracking_specs', []),
            "conversion_specs": safe_data.get('conversion_specs', []),
            "recommendations": safe_data.get('recommendations', [])
        }

        return {
            "success": True,
            "ad": formatted_ad
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format ad response: {str(e)}"
        }


def format_creatives_response(data: Any) -> Dict[str, Any]:
    """
    Format creatives response for display.

    Args:
        data: Raw creatives data from API (may include Facebook SDK objects)

    Returns:
        Formatted creatives response safe for JSON serialization
    """
    try:
        # Convert Facebook SDK objects to plain Python objects
        safe_data = convert_facebook_object(data)

        if 'creatives' not in safe_data:
            return {
                "success": False,
                "error": "No creatives data found"
            }

        creatives = safe_data['creatives']
        formatted_creatives = []

        for creative in creatives:
            formatted_creative = {
                "id": creative.get('id', 'N/A'),
                "name": creative.get('name', 'Unnamed Creative'),
                "title": creative.get('title', ''),
                "body": creative.get('body', ''),
                "image_url": creative.get('image_url', ''),
                "video_id": creative.get('video_id', ''),
                "link_url": creative.get('link_url', ''),
                "call_to_action": creative.get('call_to_action', {}),
                "object_story_spec": creative.get('object_story_spec', {}),
                "asset_feed_spec": creative.get('asset_feed_spec', {})
            }
            formatted_creatives.append(formatted_creative)

        return {
            "success": True,
            "creatives": formatted_creatives,
            "count": len(formatted_creatives)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format creatives response: {str(e)}"
        }


def convert_facebook_object(obj: Any) -> Any:
    """
    Convert Facebook SDK objects to plain Python dictionaries for JSON serialization.

    Args:
        obj: Facebook SDK object or regular Python object

    Returns:
        Plain Python object safe for JSON serialization
    """
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {k: convert_facebook_object(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_facebook_object(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)):
        # Primitive types
        return obj
    elif hasattr(obj, '__dict__'):
        # Facebook SDK object - convert to dict
        result = {}
        try:
            # Try to get the raw data first
            if hasattr(obj, 'export_all_data'):
                return convert_facebook_object(obj.export_all_data())
            elif hasattr(obj, '_json'):
                return convert_facebook_object(obj._json)
            else:
                # Fallback: iterate through attributes
                for key in dir(obj):
                    if not key.startswith('_') and key not in ['export_all_data', '_json']:
                        try:
                            value = getattr(obj, key)
                            if not callable(value) and value is not None:
                                result[key] = convert_facebook_object(value)
                        except:
                            # Skip attributes that can't be accessed
                            continue
        except Exception:
            # If all conversion methods fail, return string representation
            return str(obj)
        return result
    else:
        # For any other type, try to convert to string safely
        try:
            return str(obj)
        except:
            return "<unserializable_object>"


def _summarize_targeting(targeting: Dict[str, Any]) -> str:
    """
    Create a human-readable summary of targeting options.

    Args:
        targeting: Targeting configuration

    Returns:
        Summary string
    """
    try:
        summary_parts = []

        # Age range
        if 'age_min' in targeting and 'age_max' in targeting:
            summary_parts.append(f"Ages {targeting['age_min']}-{targeting['age_max']}")

        # Gender
        if 'genders' in targeting:
            genders = targeting['genders']
            if genders == [1]:
                summary_parts.append("Men")
            elif genders == [2]:
                summary_parts.append("Women")
            else:
                summary_parts.append("All genders")

        # Locations
        if 'geo_locations' in targeting:
            geo = targeting['geo_locations']
            if 'countries' in geo:
                countries = geo['countries']
                if len(countries) == 1:
                    summary_parts.append(f"{countries[0]}")
                elif len(countries) <= 3:
                    summary_parts.append(f"{', '.join(countries)}")
                else:
                    summary_parts.append(f"{len(countries)} countries")

        # Interests
        if 'interests' in targeting:
            interests = targeting['interests']
            if len(interests) > 0:
                interest_names = [interest.get('name', '') for interest in interests[:2]]
                if len(interests) > 2:
                    summary_parts.append(f"Interests: {', '.join(interest_names)} +{len(interests)-2} more")
                else:
                    summary_parts.append(f"Interests: {', '.join(interest_names)}")

        if not summary_parts:
            return "Custom targeting"

        return "; ".join(summary_parts)

    except Exception:
        return "Complex targeting"


def format_insights_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format insights response for MCP.

    Args:
        data: Raw insights data from API

    Returns:
        Formatted response
    """
    try:
        insights = data.get('insights', [])

        formatted_insights = {}
        for insight in insights:
            # Format metrics
            formatted_insight = {}

            # Format currency values
            currency_fields = ['spend', 'cpc', 'cpm', 'cost_per_conversion', 'conversion_value']
            for field in currency_fields:
                if field in insight:
                    formatted_insight[field] = format_currency(insight[field])

            # Format numbers
            number_fields = ['impressions', 'reach', 'clicks', 'conversions']
            for field in number_fields:
                if field in insight:
                    formatted_insight[field] = format_number(insight[field])

            # Format percentages
            percentage_fields = ['ctr', 'roas']
            for field in percentage_fields:
                if field in insight:
                    formatted_insight[field] = format_percentage(insight[field])

            # Copy other fields as-is
            other_fields = ['date_start', 'date_stop', 'account_id', 'account_name']
            for field in other_fields:
                if field in insight:
                    formatted_insight[field] = insight[field]

            # Use date_start as key if available, otherwise use a counter
            key = insight.get('date_start', f'insight_{len(formatted_insights)}')
            formatted_insights[key] = formatted_insight

        return {
            "success": True,
            "insights": formatted_insights,
            "count": len(formatted_insights)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format insights response: {str(e)}"
        }


def format_interests_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format interests response for MCP.

    Args:
        data: Raw interests data from API

    Returns:
        Formatted response
    """
    try:
        interests = data.get('interests', [])

        formatted_interests = []
        for interest in interests:
            formatted_interest = {
                "id": interest.get('id'),
                "name": interest.get('name', 'Unknown'),
                "audience_size_lower": format_number(interest.get('audience_size_lower_bound', 0)),
                "audience_size_upper": format_number(interest.get('audience_size_upper_bound', 0)),
                "path": interest.get('path', []),
                "description": interest.get('description')
            }
            formatted_interests.append(formatted_interest)

        return {
            "success": True,
            "interests": formatted_interests,
            "count": len(formatted_interests),
            "query": data.get('query', '')
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format interests response: {str(e)}"
        }


def format_demographics_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format demographics response for MCP.

    Args:
        data: Raw demographics data from API

    Returns:
        Formatted response
    """
    try:
        demographics = data.get('demographics', [])

        formatted_demographics = []
        for demographic in demographics:
            formatted_demographic = {
                "id": demographic.get('id'),
                "name": demographic.get('name', 'Unknown'),
                "type": demographic.get('type'),
                "description": demographic.get('description')
            }
            formatted_demographics.append(formatted_demographic)

        return {
            "success": True,
            "demographics": formatted_demographics,
            "count": len(formatted_demographics),
            "demographic_class": data.get('demographic_class', '')
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format demographics response: {str(e)}"
        }


def format_campaign_create_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format campaign creation response for MCP.

    Args:
        data: Raw campaign data from API

    Returns:
        Formatted response
    """
    try:
        formatted_campaign = {
            "id": data.get('id'),
            "name": data.get('name', 'Unknown'),
            "status": data.get('status', 'UNKNOWN'),
            "objective": data.get('objective', 'Unknown'),
            "created_time": format_date(data.get('created_time', ''))
        }

        return {
            "success": True,
            "campaign": formatted_campaign,
            "message": "Campaign created successfully. Status is PAUSED - activate when ready."
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format campaign creation response: {str(e)}"
        }


def format_campaign_update_response(old_data: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format campaign update response for MCP.

    Args:
        old_data: Previous campaign data
        updates: Applied updates

    Returns:
        Formatted response
    """
    try:
        changes = {}
        for field, new_value in updates.items():
            old_value = old_data.get(field, 'Not set')
            changes[field] = {"from": old_value, "to": new_value}

        return {
            "success": True,
            "campaign_id": old_data.get('id'),
            "updated_fields": list(updates.keys()),
            "changes": changes,
            "message": "Campaign updated successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format campaign update response: {str(e)}"
        }


def format_analysis_response(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format campaign analysis response for MCP.

    Args:
        analysis: Analysis results

    Returns:
        Formatted response
    """
    try:
        return {
            "success": True,
            "analysis": analysis
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to format analysis response: {str(e)}"
        }
