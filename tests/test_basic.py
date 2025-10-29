"""
Basic tests for Meta Ads MCP server.
"""
import pytest
from unittest.mock import patch, MagicMock

# Import the modules we want to test
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from config.settings import Settings  # type: ignore
from config.constants import VALID_OBJECTIVES, CAMPAIGN_STATUSES  # type: ignore
from core.validators import validate_account_id, validate_campaign_input  # type: ignore
from utils.logger import setup_logger  # type: ignore


def test_settings_initialization():
    """Test that settings can be initialized."""
    settings = Settings()
    assert settings is not None
    assert hasattr(settings, 'meta_access_token')
    assert hasattr(settings, 'environment')


def test_constants():
    """Test that constants are properly defined."""
    assert 'OUTCOME_AWARENESS' in VALID_OBJECTIVES
    assert 'OUTCOME_TRAFFIC' in VALID_OBJECTIVES
    assert 'ACTIVE' in CAMPAIGN_STATUSES
    assert 'PAUSED' in CAMPAIGN_STATUSES


def test_validators():
    """Test input validation functions."""
    # Test account ID validation
    valid_result = validate_account_id('act_123456789')
    assert valid_result['valid'] is True

    invalid_result = validate_account_id('invalid_id')
    assert invalid_result['valid'] is False

    # Test campaign input validation
    valid_campaign = {
        'name': 'Test Campaign',
        'objective': 'OUTCOME_TRAFFIC',
        'daily_budget': 1000,
        'status': 'PAUSED'
    }
    valid_result = validate_campaign_input(valid_campaign)
    assert valid_result['valid'] is True

    invalid_campaign = {
        'name': '',  # Empty name
        'objective': 'INVALID_OBJECTIVE'
    }
    invalid_result = validate_campaign_input(invalid_campaign)
    assert invalid_result['valid'] is False


def test_logger():
    """Test that logger can be set up."""
    logger = setup_logger('test_logger')
    assert logger is not None
    assert logger.name == 'test_logger'


@patch('tools.accounts.settings')
def test_accounts_tool_no_token(mock_settings):
    """Test accounts tool when no token is configured."""
    from tools.accounts import get_ad_accounts  # type: ignore

    # Mock settings to have no token
    mock_settings.has_token = False
    mock_settings.meta_access_token = None

    result = get_ad_accounts()
    assert result['success'] is False
    assert 'No access token' in result['error']


@patch('tools.targeting.settings')
def test_targeting_tool_no_token(mock_settings):
    """Test targeting tool when no token is configured."""
    from tools.targeting import search_interests  # type: ignore

    # Mock settings to have no token
    mock_settings.has_token = False
    mock_settings.meta_access_token = None

    result = search_interests('fitness')
    assert result['success'] is False
    assert 'No access token' in result['error']


def test_formatters():
    """Test formatter functions."""
    from core.formatters import format_currency, format_number, format_percentage  # type: ignore

    assert format_currency(1000) == "$10.00"
    assert format_number(1234567) == "1,234,567"
    assert format_percentage(0.1234) == "12.34%"


if __name__ == "__main__":
    # Run basic tests
    test_settings_initialization()
    test_constants()
    test_validators()
    test_logger()
    test_formatters()

    print("✅ All basic tests passed!")
