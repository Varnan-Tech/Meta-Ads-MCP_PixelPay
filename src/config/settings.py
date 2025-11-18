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

        # API Timeout Settings (in seconds)
        # Default 180s handles worst-case Meta Insights API queries (large accounts, 30+ day ranges)
        self.api_timeout_total: int = int(os.getenv("API_TIMEOUT_TOTAL", "180"))  # Total timeout
        self.api_timeout_connect: int = int(os.getenv("API_TIMEOUT_CONNECT", "15"))  # Connect timeout
        self.api_retry_count: int = int(os.getenv("API_RETRY_COUNT", "3"))  # Number of retries

        # Connection Pool Settings
        self.connection_pool_size: int = int(os.getenv("CONNECTION_POOL_SIZE", "100"))
        self.connection_pool_per_host: int = int(os.getenv("CONNECTION_POOL_PER_HOST", "30"))

        # Cache Settings
        self.cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))
        self.enable_cache: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"

        # Token Storage Path
        self.token_storage_path: str = os.getenv(
            "TOKEN_STORAGE_PATH",
            os.path.expanduser("~/.meta-ads-mcp/tokens.json")
        )

        # Facebook OAuth Configuration
        self.fb_app_id: Optional[str] = os.getenv("FB_APP_ID", "PLEASE_SET")
        self.fb_app_secret: Optional[str] = os.getenv("FB_APP_SECRET", "PLEASE_SET")
        self.fb_api_version: str = os.getenv("FB_API_VERSION", "v24.0")
        self.fb_redirect_uri: Optional[str] = os.getenv("FB_REDIRECT_URI")
        self.fb_deauth_callback: Optional[str] = os.getenv("FB_DEAUTH_CALLBACK")
        
        # OAuth Scopes (comma-separated)
        # Based on Pipeboard's working implementation:
        # business_management,public_profile,pages_show_list,pages_read_engagement
        # For Marketing API access:
        # - business_management (works for internal testing, no App Review needed if you're admin)
        # - pages_show_list, pages_read_engagement (for page access)
        # - ads_management (requires App Review for production)
        # Note: ads_read is deprecated - use business_management instead
        self.fb_oauth_scopes: str = os.getenv(
            "FB_OAUTH_SCOPES", 
            "business_management,public_profile,pages_show_list,pages_read_engagement"
        )
        
        # Token Encryption
        self.token_encryption_key: Optional[str] = os.getenv("TOKEN_ENCRYPTION_KEY")
        # If no KMS key provided, use a local key (for development only)
        if not self.token_encryption_key:
            # In production, this should be set to a KMS key reference
            self.token_encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY_LOCAL", "dev-key-change-in-production")
        
        # OAuth Settings
        self.token_refresh_window_days: int = int(os.getenv("TOKEN_REFRESH_WINDOW_DAYS", "10"))
        self.oauth_state_ttl_minutes: int = int(os.getenv("OAUTH_STATE_TTL_MINUTES", "10"))
        self.fb_oauth_enabled: bool = os.getenv("FB_OAUTH_ENABLED", "false").lower() == "true"
        
        # Database Configuration
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{Path.home()}/.meta-ads-mcp/oauth.db"
        )
        
        # Web Server Configuration
        self.web_server_host: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
        self.web_server_port: int = int(os.getenv("WEB_SERVER_PORT", "8000"))

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def has_token(self) -> bool:
        """Check if access token is configured."""
        return self.meta_access_token is not None and self.meta_access_token.strip() != ""
    
    @property
    def is_oauth_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return (
            self.fb_oauth_enabled
            and self.fb_app_id not in (None, "PLEASE_SET")
            and self.fb_app_secret not in (None, "PLEASE_SET")
            and self.fb_redirect_uri is not None
        )


# Global settings instance
settings = Settings()
