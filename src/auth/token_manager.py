"""
Token management for Meta Ads MCP server.
Handles secure storage and validation of Meta API access tokens.
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

try:
    # Try absolute imports first (when run as part of package)
    from ..config.settings import settings
    from ..utils.logger import logger
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from config.settings import settings
    from utils.logger import logger


class TokenManager:
    """
    Manages Meta API access tokens with secure storage and validation.

    Tokens are stored in JSON format with metadata:
    {
        "default": "EAABwz...",
        "account_123": "EAABwz...",
        "last_validated": "2025-10-21T10:00:00Z"
    }
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize token manager with storage path."""
        self.config_path = config_path or settings.token_storage_path
        self._ensure_storage_directory()
        self._tokens: Dict[str, Any] = {}
        self._load_tokens()

    def _ensure_storage_directory(self) -> None:
        """Ensure the token storage directory exists with proper permissions."""
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (read/write for owner only)
        if os.name != 'nt':  # Not Windows
            config_dir.chmod(0o700)

    def _load_tokens(self) -> None:
        """Load tokens from storage file."""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._tokens = json.load(f)
            else:
                self._tokens = {}
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load tokens: {e}")
            self._tokens = {}

    def _save_tokens(self) -> None:
        """Save tokens to storage file."""
        try:
            # Create backup before saving
            if Path(self.config_path).exists():
                backup_path = f"{self.config_path}.backup"
                Path(self.config_path).rename(backup_path)

            # Write new tokens file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._tokens, f, indent=2)

            # Set restrictive permissions
            if os.name != 'nt':  # Not Windows
                Path(self.config_path).chmod(0o600)

        except IOError as e:
            logger.error(f"Failed to save tokens: {e}")
            # Restore backup if it exists
            backup_path = f"{self.config_path}.backup"
            if Path(backup_path).exists():
                Path(backup_path).rename(self.config_path)

    def get_token(self, account_id: Optional[str] = None) -> Optional[str]:
        """
        Get access token for account.

        Args:
            account_id: Specific account ID, or None for default token

        Returns:
            Access token string or None if not found
        """
        if not account_id:
            account_id = "default"

        token = self._tokens.get(account_id)
        if token and isinstance(token, dict):
            return token.get("token")
        
        if token:
            return token

        # Fall back to environment variable for default account
        if account_id == "default":
            env_token = os.getenv("META_ACCESS_TOKEN")
            if env_token:
                logger.debug("Using META_ACCESS_TOKEN from environment variable")
                return env_token

        return None

    def set_token(self, token: str, account_id: Optional[str] = None) -> None:
        """
        Store access token for account.

        Args:
            token: Meta API access token
            account_id: Account ID or None for default
        """
        if not account_id:
            account_id = "default"

        # Validate token format (basic check)
        if not self._validate_token_format(token):
            raise ValueError("Invalid token format")

        # Store token with metadata
        self._tokens[account_id] = {
            "token": token,
            "stored_at": datetime.utcnow().isoformat(),
            "source": "manual"  # Could be 'oauth', 'manual', etc.
        }

        # Update last validated timestamp
        self._tokens["last_validated"] = datetime.utcnow().isoformat()

        self._save_tokens()
        logger.info(f"Token stored for account: {account_id}")

    def validate_token(self, token: Optional[str] = None, account_id: Optional[str] = None) -> bool:
        """
        Validate access token with Meta API.

        Args:
            token: Token to validate (uses stored token if None)
            account_id: Account ID for token lookup

        Returns:
            True if token is valid
        """
        if not token:
            token = self.get_token(account_id)

        if not token:
            logger.error("No token provided for validation")
            return False

        try:
            # Basic validation - try to make a simple API call
            from ..api.client import MetaAPIClient
            client = MetaAPIClient(token)

            # Try to get user info (simple validation)
            user = client.get_user_info()
            if user:
                # Update validation timestamp
                self._tokens["last_validated"] = datetime.utcnow().isoformat()
                self._save_tokens()
                logger.info("Token validation successful")
                return True

        except Exception as e:
            logger.error(f"Token validation failed: {e}")

        return False

    def refresh_token(self, token: str) -> Optional[str]:
        """
        Refresh an expired token (placeholder for future implementation).

        Args:
            token: Current token

        Returns:
            New token or None if refresh failed
        """
        # TODO: Implement token refresh logic when needed
        logger.warning("Token refresh not implemented yet")
        return None

    def delete_token(self, account_id: Optional[str] = None) -> bool:
        """
        Delete stored token.

        Args:
            account_id: Account ID or None for default

        Returns:
            True if token was deleted
        """
        if not account_id:
            account_id = "default"

        if account_id in self._tokens:
            del self._tokens[account_id]
            self._save_tokens()
            logger.info(f"Token deleted for account: {account_id}")
            return True

        return False

    def list_accounts(self) -> Dict[str, Any]:
        """List all stored account tokens with metadata."""
        accounts = {}
        for key, value in self._tokens.items():
            if key != "last_validated" and isinstance(value, dict):
                accounts[key] = {
                    "stored_at": value.get("stored_at"),
                    "source": value.get("source"),
                    "has_token": bool(value.get("token"))
                }
        return accounts

    def _validate_token_format(self, token: str) -> bool:
        """
        Basic validation of token format.

        Args:
            token: Token string to validate

        Returns:
            True if token format looks valid
        """
        if not token or not isinstance(token, str):
            return False

        # Meta access tokens typically start with "EAAB" or "EAAI" and are quite long
        if len(token) < 50:
            return False

        # Should contain only valid characters (alphanumeric, hyphens, underscores)
        import re
        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            return False

        return True

    def get_token_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed information about stored token.

        Args:
            account_id: Account ID or None for default

        Returns:
            Token information dictionary
        """
        if not account_id:
            account_id = "default"

        token_data = self._tokens.get(account_id)
        if not token_data:
            return {"exists": False}

        return {
            "exists": True,
            "stored_at": token_data.get("stored_at"),
            "source": token_data.get("source"),
            "last_validated": self._tokens.get("last_validated")
        }


# Global token manager instance
token_manager = TokenManager()
