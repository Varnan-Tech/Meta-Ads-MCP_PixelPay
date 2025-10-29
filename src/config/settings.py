"""
Configuration settings for Meta Ads MCP server.
"""
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# This searches for .env in current directory and parent directories
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Meta API Configuration
        self.meta_access_token: Optional[str] = os.getenv("META_ACCESS_TOKEN")
        self.meta_app_id: Optional[str] = os.getenv("META_APP_ID")
        self.meta_app_secret: Optional[str] = os.getenv("META_APP_SECRET")

        # Default Ad Account
        self.default_ad_account: Optional[str] = os.getenv("DEFAULT_AD_ACCOUNT")

        # Environment
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Rate Limiting
        self.max_requests_per_hour: int = int(os.getenv("MAX_REQUESTS_PER_HOUR", "200"))

        # Cache Settings
        self.cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))
        self.enable_cache: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"

        # Token Storage Path
        self.token_storage_path: str = os.getenv(
            "TOKEN_STORAGE_PATH",
            os.path.expanduser("~/.meta-ads-mcp/tokens.json")
        )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def has_token(self) -> bool:
        """Check if access token is configured."""
        return self.meta_access_token is not None and self.meta_access_token.strip() != ""


# Global settings instance
settings = Settings()
