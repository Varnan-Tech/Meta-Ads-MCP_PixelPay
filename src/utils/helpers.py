"""
Helper utilities for Meta Ads MCP server.
"""
from typing import Union, Dict, List, Any, Optional
import requests
import json


def format_currency(amount: Union[str, int, float], currency: str = "USD") -> str:
    """
    Format amount as currency string.

    Args:
        amount: Amount in cents (for USD) or currency units
        currency: Currency code

    Returns:
        Formatted currency string (e.g., "$50.00")
    """
    try:
        if currency.upper() == "USD":
            # Assume amount is in cents for USD
            amount_float = float(amount) / 100
        else:
            amount_float = float(amount)

        return f"${amount_float:,.2f}"
    except (ValueError, TypeError):
        return str(amount)


def format_number(value: Union[str, int, float]) -> str:
    """
    Format number with thousands separator.

    Args:
        value: Number to format

    Returns:
        Formatted number string (e.g., "1,234")
    """
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: Union[str, int, float], decimals: int = 2) -> str:
    """
    Format value as percentage.

    Args:
        value: Value to format (e.g., 0.025 for 2.5%)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string (e.g., "2.50%")
    """
    try:
        percentage = float(value) * 100
        return f"{percentage:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


def format_date(date_string: str) -> str:
    """
    Format date string to readable format.

    Args:
        date_string: ISO date string

    Returns:
        Formatted date string (e.g., "Oct 21, 2025")
    """
    try:
        from datetime import datetime
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return date_string


def normalize_account_id(account_id: str) -> str:
    """
    Normalize account ID to ensure proper format with 'act_' prefix.
    
    Args:
        account_id: Account ID with or without 'act_' prefix
        
    Returns:
        Account ID with 'act_' prefix
    """
    if not account_id:
        raise ValueError("Account ID cannot be empty")
    
    account_id = str(account_id).strip()
    
    # If it already has the prefix, return as-is
    if account_id.startswith('act_'):
        return account_id
    
    # Otherwise, add the prefix
    return f'act_{account_id}'


def fetch_all_pages(initial_response: Dict[str, Any], access_token: str) -> List[Dict[str, Any]]:
    """
    Automatically fetch all pages of results from Meta API pagination.
    
    This handles the pagination by following 'paging.next' URLs until no more pages exist.
    Based on the reference server implementation that MUST fetch all pages automatically.
    
    Args:
        initial_response: The first page response from Meta API
        access_token: Meta access token for subsequent requests
        
    Returns:
        List of all data items across all pages
    """
    all_data = []
    
    # Add first page data
    if 'data' in initial_response:
        all_data.extend(initial_response['data'])
    
    # Check for pagination
    current_response = initial_response
    page_count = 1
    max_pages = 1000  # Safety limit to prevent infinite loops
    
    while 'paging' in current_response and 'next' in current_response['paging']:
        if page_count >= max_pages:
            from .logger import logger
            logger.warning(f"Reached maximum page limit of {max_pages}, stopping pagination")
            break
            
        next_url = current_response['paging']['next']
        
        try:
            # Fetch next page
            response = requests.get(next_url, timeout=30)
            response.raise_for_status()
            current_response = response.json()
            
            # Add data from this page
            if 'data' in current_response:
                all_data.extend(current_response['data'])
                page_count += 1
            else:
                break
                
        except Exception as e:
            from .logger import logger
            logger.error(f"Error fetching page {page_count + 1}: {e}")
            break
    
    return all_data


def make_paginated_request(url: str, params: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    """
    Make a Meta API request and automatically fetch all pages.
    
    Args:
        url: API endpoint URL
        params: Request parameters
        access_token: Meta access token
        
    Returns:
        Dictionary with 'data' containing all items across all pages
    """
    try:
        # Make initial request
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        initial_response = response.json()
        
        # Fetch all pages
        all_data = fetch_all_pages(initial_response, access_token)
        
        return {
            'data': all_data,
            'total_count': len(all_data)
        }
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {e}")
