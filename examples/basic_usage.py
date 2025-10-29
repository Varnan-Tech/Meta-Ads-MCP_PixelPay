#!/usr/bin/env python3
"""
Basic usage examples for Meta Ads MCP server.
This script demonstrates how to use the MCP server tools programmatically.
"""
import os
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import the modules we want to test
# Note: These imports work at runtime due to sys.path manipulation above
from tools.accounts import get_ad_accounts, get_account_info  # type: ignore
from tools.campaigns import get_campaigns, create_campaign, update_campaign  # type: ignore
from tools.insights import get_insights  # type: ignore
from tools.targeting import search_interests, search_demographics, search_locations  # type: ignore
from core.analyzer import analyze_campaigns  # type: ignore
from config.settings import settings  # type: ignore


def main():
    """Demonstrate basic usage of Meta Ads MCP tools."""
    print("Meta Ads MCP Server - Usage Examples")
    print("=" * 50)

    # Check if token is configured
    if not settings.has_token:
        print("ERROR: No Meta access token configured!")
        print("Please set META_ACCESS_TOKEN in your .env file")
        return

    print("SUCCESS: Access token configured")

    # Example 1: Get ad accounts
    print("\nExample 1: Get Ad Accounts")
    print("-" * 30)

    try:
        accounts_result = get_ad_accounts()
        if accounts_result.get('success'):
            accounts = accounts_result.get('accounts', [])
            print(f"Found {len(accounts)} ad accounts:")
            for account in accounts[:3]:  # Show first 3
                print(f"  * {account['name']} ({account['id']}) - {account['currency']}")
        else:
            print(f"ERROR: Failed to get accounts: {accounts_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error getting accounts: {e}")

    # Example 2: Search interests
    print("\nExample 2: Search Interests")
    print("-" * 30)

    try:
        interests_result = search_interests("fitness", limit=5)
        if interests_result.get('success'):
            interests = interests_result.get('interests', [])
            print(f"Found {len(interests)} fitness-related interests:")
            for interest in interests:
                print(f"  * {interest['name']} (ID: {interest['id']})")
                print(f"    Audience: {interest['audience_size_lower']:,} - {interest['audience_size_upper']:,}")
        else:
            print(f"ERROR: Failed to search interests: {interests_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error searching interests: {e}")

    # Example 3: Search demographics
    print("\nExample 3: Search Demographics")
    print("-" * 30)

    try:
        demos_result = search_demographics("education", limit=5)
        if demos_result.get('success'):
            demos = demos_result.get('demographics', [])
            print(f"Found {len(demos)} education-related demographics:")
            for demo in demos:
                print(f"  * {demo['name']} (ID: {demo['id']})")
        else:
            print(f"ERROR: Failed to search demographics: {demos_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error searching demographics: {e}")

    # Example 4: Search locations
    print("\nExample 4: Search Locations")
    print("-" * 30)

    try:
        locations_result = search_locations("New York", ["city"], limit=5)
        if locations_result.get('success'):
            locations = locations_result.get('locations', [])
            print(f"Found {len(locations)} New York locations:")
            for location in locations:
                print(f"  * {location['name']} ({location['type']})")
        else:
            print(f"ERROR: Failed to search locations: {locations_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error searching locations: {e}")

    # Example 5: Campaign operations (requires account_id)
    print("\nExample 5: Campaign Operations")
    print("-" * 30)

    # For demo purposes, we'll use a placeholder account ID
    # In real usage, you'd get this from get_ad_accounts()
    demo_account_id = "act_123456789"  # Replace with real account ID

    try:
        # Get campaigns (this would fail without real account/token)
        campaigns_result = get_campaigns(demo_account_id, limit=3)
        if campaigns_result.get('success'):
            campaigns = campaigns_result.get('campaigns', [])
            print(f"Found {len(campaigns)} campaigns")
        else:
            print(f"EXPECTED ERROR (no real account): {campaigns_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error getting campaigns: {e}")

    # Example 6: Campaign analysis (requires real data)
    print("\nExample 6: Campaign Analysis")
    print("-" * 30)

    try:
        # This would require real campaign data
        analysis_result = analyze_campaigns(demo_account_id)
        if analysis_result.get('success'):
            analysis = analysis_result.get('analysis', {})
            print("Campaign analysis completed")
        else:
            print(f"EXPECTED ERROR (no real data): {analysis_result.get('error')}")
    except Exception as e:
        print(f"ERROR: Error analyzing campaigns: {e}")

    print("\n" + "=" * 50)
    print("SUCCESS: Examples completed!")
    print("\nTo use with real data:")
    print("1. Set your META_ACCESS_TOKEN in .env")
    print("2. Get a real account ID from get_ad_accounts()")
    print("3. Replace demo_account_id with real account ID")
    print("4. Run the examples again")


if __name__ == "__main__":
    main()
