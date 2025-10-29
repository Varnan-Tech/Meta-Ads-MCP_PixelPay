"""
Logging configuration for Meta Ads MCP server.
"""
import logging
import sys
from typing import Optional

def setup_logger(name: str = "meta-ads-mcp", level: Optional[str] = None) -> logging.Logger:
    """
    Set up logger with appropriate configuration.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    # Default level if settings import fails
    default_level = "INFO"

    try:
        # Try absolute imports first (when run as part of package)
        from ..config.settings import settings
        if level is None:
            level = settings.log_level
    except ImportError:
        try:
            # Fall back to relative imports (when run as script from src directory)
            import sys
            import os
            # Add current directory to path for relative imports
            sys.path.insert(0, os.path.dirname(__file__))
            from config.settings import settings
            if level is None:
                level = settings.log_level
        except ImportError:
            # If settings import fails completely, use default
            if level is None:
                level = default_level

    # Create logger
    logger = logging.getLogger(name)

    # Don't add handlers if already configured
    if logger.handlers:
        return logger

    # Set level
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger


# Global logger instance
logger = setup_logger()
