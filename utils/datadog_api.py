"""
DataDog API wrapper utilities.

Provides a client for searching and retrieving logs from DataDog.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


class DataDogAPIError(Exception):
    """Base exception for DataDog API errors."""
    pass


class DataDogAuthError(DataDogAPIError):
    """Raised when authentication fails (401/403)."""
    pass


class DataDogRateLimitError(DataDogAPIError):
    """Raised when rate limit is exceeded and retry fails."""
    pass


class DataDogTimeoutError(DataDogAPIError):
    """Raised when API request times out."""
    pass


@dataclass
class LogEntry:
    """Represents a parsed log entry from DataDog.

    Attributes:
        id: Unique log entry ID
        message: Log message text
        service: Service name
        efilogid: Session identifier
        dd_version: Deployment version (commit_hash___build_number)
        logger_name: Full qualified class name
        timestamp: Log timestamp
        status: Log level (info, warn, error, etc.)
        raw_attributes: Full raw attributes for additional access
    """
    id: str
    message: str
    service: Optional[str] = None
    efilogid: Optional[str] = None
    dd_version: Optional[str] = None
    logger_name: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    raw_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Results from a DataDog log search.

    Attributes:
        logs: List of parsed log entries
        total_count: Total number of logs returned
        unique_services: Set of unique service names found
        unique_efilogids: Set of unique session IDs found
        raw_response: Full raw API response
    """
    logs: List[LogEntry]
    total_count: int
    unique_services: set
    unique_efilogids: set
    raw_response: Optional[Dict[str, Any]] = None


class DataDogAPI:
    """Wrapper for DataDog API calls.

    Handles authentication, rate limiting, and response parsing.
    """

    DEFAULT_TIMEOUT = 30  # seconds
    LOGS_SEARCH_ENDPOINT = "/api/v2/logs/events/search"

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize the DataDog API client.

        Args:
            api_key: DataDog API key
            app_key: DataDog application key
            site: DataDog site (default: datadoghq.com)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = f"https://api.{site}"
        self.timeout = timeout
        self.headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Rate limit tracking
        self._rate_limit_remaining = None
        self._rate_limit_reset = None

        logger.debug(f"DataDog API client initialized for site: {site}")

    def search_logs(
        self,
        query: str,
        from_time: str,
        to_time: str,
        limit: int = 200,
    ) -> SearchResult:
        """Search logs from DataDog.

        Args:
            query: Log search query (DataDog query syntax)
            from_time: Start time (relative like "now-4h" or ISO 8601)
            to_time: End time (relative like "now" or ISO 8601)
            limit: Maximum number of logs to return (default: 200, max: 1000)

        Returns:
            SearchResult object with parsed logs and metadata.

        Raises:
            DataDogAuthError: If authentication fails (401/403)
            DataDogRateLimitError: If rate limit exceeded after retry
            DataDogTimeoutError: If request times out
            DataDogAPIError: For other API errors
        """
        url = f"{self.base_url}{self.LOGS_SEARCH_ENDPOINT}"

        # Build request body
        request_body = {
            "filter": {
                "from": from_time,
                "to": to_time,
                "query": query,
            },
            "page": {
                "limit": min(limit, 1000),  # API max is 1000
            },
            "sort": "-timestamp",  # Most recent first
        }

        logger.info(f"Searching DataDog logs: query='{query}', from={from_time}, to={to_time}")
        logger.debug(f"Full request body: {request_body}")

        response = self._make_request("POST", url, json=request_body)
        return self._parse_search_response(response)

    def _make_request(
        self,
        method: str,
        url: str,
        retry_on_rate_limit: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Make an HTTP request to DataDog API with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            retry_on_rate_limit: Whether to retry on 429 (default: True)
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object

        Raises:
            DataDogAuthError: If authentication fails (401/403)
            DataDogRateLimitError: If rate limit exceeded after retry
            DataDogTimeoutError: If request times out
            DataDogAPIError: For other API errors
        """
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )

            # Update rate limit tracking from headers
            self._update_rate_limit_info(response)

            # Handle specific status codes
            if response.status_code == 401:
                logger.error("DataDog API authentication failed: Invalid API key")
                raise DataDogAuthError(
                    "Authentication failed. Check DD_API_KEY in .env file."
                )

            if response.status_code == 403:
                logger.error("DataDog API authorization failed: Invalid application key or insufficient permissions")
                raise DataDogAuthError(
                    "Authorization failed. Check DD_APPLICATION_KEY and permissions."
                )

            if response.status_code == 429:
                if retry_on_rate_limit:
                    return self._handle_rate_limit(method, url, **kwargs)
                else:
                    raise DataDogRateLimitError(
                        "Rate limit exceeded. Please wait and try again."
                    )

            # Raise for other HTTP errors
            response.raise_for_status()

            return response

        except requests.Timeout:
            logger.error(f"DataDog API request timed out after {self.timeout}s")
            raise DataDogTimeoutError(
                f"Request timed out after {self.timeout} seconds."
            )
        except requests.RequestException as e:
            logger.error(f"DataDog API request failed: {e}")
            raise DataDogAPIError(f"API request failed: {e}")

    def _update_rate_limit_info(self, response: requests.Response) -> None:
        """Update rate limit tracking from response headers.

        Args:
            response: HTTP response object
        """
        headers = response.headers

        if "X-RateLimit-Remaining" in headers:
            self._rate_limit_remaining = int(headers["X-RateLimit-Remaining"])
            logger.debug(f"Rate limit remaining: {self._rate_limit_remaining}")

        if "X-RateLimit-Reset" in headers:
            self._rate_limit_reset = int(headers["X-RateLimit-Reset"])
            logger.debug(f"Rate limit reset at: {self._rate_limit_reset}")

        # Warn if approaching limit
        if self._rate_limit_remaining is not None and self._rate_limit_remaining < 10:
            logger.warning(
                f"Approaching rate limit: {self._rate_limit_remaining} requests remaining"
            )

    def _handle_rate_limit(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """Handle rate limiting by waiting and retrying.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Original request arguments

        Returns:
            Response from retry attempt

        Raises:
            DataDogRateLimitError: If retry also hits rate limit
        """
        if self._rate_limit_reset is None:
            # No reset time available, use default wait
            wait_time = 60
            logger.warning(
                f"Rate limit exceeded, no reset time available. Waiting {wait_time}s"
            )
        else:
            # Calculate wait time from reset timestamp
            current_time = int(time.time())
            wait_time = max(self._rate_limit_reset - current_time, 1)
            reset_dt = datetime.fromtimestamp(self._rate_limit_reset)
            logger.warning(
                f"Rate limit exceeded. Waiting {wait_time}s until {reset_dt.isoformat()}"
            )

        # Wait until reset time
        time.sleep(wait_time)

        # Retry the request (without retry to avoid infinite loop)
        logger.info("Retrying request after rate limit wait")
        return self._make_request(method, url, retry_on_rate_limit=False, **kwargs)

    def _parse_search_response(self, response: requests.Response) -> SearchResult:
        """Parse the search API response into structured data.

        Args:
            response: HTTP response from search API

        Returns:
            SearchResult object with parsed logs
        """
        data = response.json()
        logs_data = data.get("data", [])

        logs = []
        unique_services = set()
        unique_efilogids = set()

        for log_item in logs_data:
            log_entry = self._extract_log_entry(log_item)
            logs.append(log_entry)

            if log_entry.service:
                unique_services.add(log_entry.service)
            if log_entry.efilogid:
                unique_efilogids.add(log_entry.efilogid)

        logger.info(
            f"Parsed {len(logs)} logs, {len(unique_services)} unique services, "
            f"{len(unique_efilogids)} unique efilogids"
        )

        return SearchResult(
            logs=logs,
            total_count=len(logs),
            unique_services=unique_services,
            unique_efilogids=unique_efilogids,
            raw_response=data,
        )

    def _extract_log_entry(self, log_item: Dict[str, Any]) -> LogEntry:
        """Extract a LogEntry from raw API log item.

        Args:
            log_item: Single log item from API response

        Returns:
            LogEntry object with extracted fields
        """
        log_id = log_item.get("id", "")
        attributes = log_item.get("attributes", {})
        nested_attrs = attributes.get("attributes", {})

        # Extract fields from various locations
        message = attributes.get("message", "")
        service = attributes.get("service") or nested_attrs.get("service")
        timestamp = attributes.get("timestamp")
        status = attributes.get("status")

        # Extract from nested attributes
        efilogid = nested_attrs.get("efilogid")
        logger_name = nested_attrs.get("logger_name")

        # Extract dd.version from nested dd object
        dd_info = nested_attrs.get("dd", {})
        dd_version = dd_info.get("version")

        # If not in dd object, try direct attribute
        if not dd_version:
            dd_version = nested_attrs.get("dd.version")

        return LogEntry(
            id=log_id,
            message=message,
            service=service,
            efilogid=efilogid,
            dd_version=dd_version,
            logger_name=logger_name,
            timestamp=timestamp,
            status=status,
            raw_attributes=attributes,
        )

    def extract_log_data(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured log data from raw API response.

        This is a convenience method for working with raw responses.

        Args:
            response: Raw API response dictionary

        Returns:
            List of dictionaries with extracted fields:
            - message, service, efilogid, dd_version, logger_name, timestamp
        """
        logs_data = response.get("data", [])
        extracted = []

        for log_item in logs_data:
            entry = self._extract_log_entry(log_item)
            extracted.append({
                "id": entry.id,
                "message": entry.message,
                "service": entry.service,
                "efilogid": entry.efilogid,
                "dd_version": entry.dd_version,
                "logger_name": entry.logger_name,
                "timestamp": entry.timestamp,
                "status": entry.status,
            })

        return extracted

    @property
    def rate_limit_remaining(self) -> Optional[int]:
        """Get the number of remaining rate-limited requests."""
        return self._rate_limit_remaining

    @property
    def rate_limit_reset_time(self) -> Optional[int]:
        """Get the Unix timestamp when rate limit resets."""
        return self._rate_limit_reset

    def build_log_message_query(self, log_message: str) -> str:
        """Build a DataDog query for searching by log message.

        Args:
            log_message: The log message text to search for

        Returns:
            Formatted query string for DataDog API
        """
        # Escape quotes in the message
        escaped_message = log_message.replace('"', '\\"')
        return f'env:prod AND pod_label_team:card AND "{escaped_message}"'

    def build_identifiers_query(self, identifiers: List[str]) -> str:
        """Build a DataDog query for searching by identifiers.

        Args:
            identifiers: List of identifiers (CID, card_account_id, paymentId, etc.)

        Returns:
            Formatted query string for DataDog API
        """
        # Join identifiers with OR
        id_query = " OR ".join(identifiers)
        return f"env:prod AND pod_label_team:card AND ({id_query})"

    def build_efilogid_query(self, efilogid: str) -> str:
        """Build a DataDog query for searching by efilogid.

        Args:
            efilogid: The session identifier

        Returns:
            Formatted query string for DataDog API
        """
        return f"@efilogid:{efilogid}"
