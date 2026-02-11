"""
Utility modules for the Production Issue Investigator.

This package provides:
- config: Environment configuration loading and validation
- logger: Logging infrastructure with file rotation
- time_utils: Timezone conversion and time window calculation
- datadog_api: DataDog API client for log search
- github_helper: GitHub API helper for repository operations
- report_generator: Investigation report generation
"""

from utils.config import Config, load_config, get_config, get_cached_config, ConfigurationError
from utils.logger import get_logger, configure_logging
from utils.time_utils import (
    parse_time,
    tel_aviv_to_utc,
    utc_to_tel_aviv,
    datetime_to_milliseconds,
    datetime_to_iso8601,
    calculate_time_window,
    expand_time_window,
    get_deployment_window_start,
)
from utils.datadog_api import (
    DataDogAPI,
    LogEntry,
    SearchResult,
    DataDogAPIError,
    DataDogAuthError,
    DataDogRateLimitError,
    DataDogTimeoutError,
)
from utils.github_helper import (
    GitHubHelper,
    GitHubError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    CommitInfo,
    PullRequestInfo,
    FileChange,
)

__all__ = [
    # Config
    "Config",
    "load_config",
    "get_config",
    "get_cached_config",
    "ConfigurationError",
    # Logger
    "get_logger",
    "configure_logging",
    # Time utils
    "parse_time",
    "tel_aviv_to_utc",
    "utc_to_tel_aviv",
    "datetime_to_milliseconds",
    "datetime_to_iso8601",
    "calculate_time_window",
    "expand_time_window",
    "get_deployment_window_start",
    # DataDog API
    "DataDogAPI",
    "LogEntry",
    "SearchResult",
    "DataDogAPIError",
    "DataDogAuthError",
    "DataDogRateLimitError",
    "DataDogTimeoutError",
    # GitHub Helper
    "GitHubHelper",
    "GitHubError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "CommitInfo",
    "PullRequestInfo",
    "FileChange",
]
