"""
Configuration management for the Production Issue Investigator.

Loads and validates environment variables from .env file.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    Attributes:
        anthropic_api_key: Anthropic API key for Claude SDK
        datadog_api_key: DataDog API key
        datadog_app_key: DataDog application key
        github_token: GitHub personal access token
        datadog_site: DataDog site (default: datadoghq.com)
        log_level: Logging level (default: INFO)
        timezone: User timezone (default: Asia/Tel_Aviv)
    """
    anthropic_api_key: str
    datadog_api_key: str
    datadog_app_key: str
    github_token: str
    datadog_site: str = "datadoghq.com"
    log_level: str = "INFO"
    timezone: str = "Asia/Tel_Aviv"


def load_config(env_path: Optional[Path] = None) -> Config:
    """Load configuration from environment variables.

    Args:
        env_path: Optional path to .env file. If not provided,
                 searches for .env in the project root.

    Returns:
        Config object with loaded values.

    Raises:
        ConfigurationError: If required environment variables are missing.
    """
    # Load .env file
    if env_path:
        load_dotenv(env_path)
    else:
        # Try to find .env in project root
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # Fall back to default behavior
            load_dotenv()

    # Required variables
    required_vars = [
        "ANTHROPIC_API_KEY",
        "DATADOG_API_KEY",
        "DATADOG_APP_KEY",
        "GITHUB_TOKEN",
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_"):
            missing_vars.append(var)

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            f"Please set them in .env file or environment."
        )

    # Build config with required and optional values
    return Config(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        datadog_api_key=os.getenv("DATADOG_API_KEY"),
        datadog_app_key=os.getenv("DATADOG_APP_KEY"),
        github_token=os.getenv("GITHUB_TOKEN"),
        datadog_site=os.getenv("DATADOG_SITE", "datadoghq.com"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        timezone=os.getenv("TIMEZONE", "Asia/Tel_Aviv"),
    )


def get_config() -> Config:
    """Get the application configuration.

    This is a convenience function that loads and returns the config.
    For repeated access, consider caching the result.

    Returns:
        Config object with loaded values.

    Raises:
        ConfigurationError: If required environment variables are missing.
    """
    return load_config()


# Singleton pattern for config
_config_instance: Optional[Config] = None


def get_cached_config() -> Config:
    """Get a cached configuration instance.

    Loads the configuration once and returns the cached instance
    on subsequent calls.

    Returns:
        Config object with loaded values.

    Raises:
        ConfigurationError: If required environment variables are missing.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance


def reset_config_cache() -> None:
    """Reset the cached configuration.

    Useful for testing or when environment variables change.
    """
    global _config_instance
    _config_instance = None
