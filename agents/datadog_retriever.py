"""
DataDog sub-agent for retrieving logs and metrics.

This sub-agent handles:
- Mode 1 searches (log message based)
- Mode 2 searches (identifier based)
- Session-based retrieval using efilogids
- Time window calculation and retry logic
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Set

from utils.config import Config
from utils.logger import get_logger
from utils.time_utils import (
    calculate_time_window,
    expand_time_window,
    format_time_range_for_display,
)
from utils.datadog_api import (
    DataDogAPI,
    LogEntry,
    SearchResult,
    DataDogAPIError,
)

logger = get_logger(__name__)


class SearchMode(Enum):
    """Search mode for DataDog queries."""
    LOG_MESSAGE = "log_message"
    IDENTIFIERS = "identifiers"


@dataclass
class DataDogSearchInput:
    """Input parameters for DataDog search.

    Attributes:
        mode: Search mode (LOG_MESSAGE or IDENTIFIERS)
        log_message: Log message text (for Mode 1)
        identifiers: List of identifiers (for Mode 2)
        user_datetime: Optional datetime provided by user
    """
    mode: SearchMode
    log_message: Optional[str] = None
    identifiers: Optional[List[str]] = None
    user_datetime: Optional[datetime] = None


@dataclass
class SearchAttempt:
    """Metadata about a search attempt.

    Attributes:
        query: The query string used
        from_time: Start time of search window
        to_time: End time of search window
        expansion_level: 0 = initial, 1 = first expansion, 2 = second expansion
        results_count: Number of results returned
        success: Whether the search succeeded
        error: Error message if search failed
    """
    query: str
    from_time: str
    to_time: str
    expansion_level: int
    results_count: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class DataDogSearchResult:
    """Complete result from DataDog search operations.

    Attributes:
        logs: Combined list of all log entries (deduplicated)
        unique_services: Set of unique service names found
        unique_efilogids: Set of unique session IDs found
        unique_dd_versions: Set of unique dd.version values found
        search_attempts: List of search attempts made
        efilogids_processed: Number of efilogids searched in Step 2
        efilogids_found: Total number of unique efilogids in Step 1
        total_logs_before_dedup: Total logs before deduplication
        error: Error message if search failed entirely
    """
    logs: List[LogEntry] = field(default_factory=list)
    unique_services: Set[str] = field(default_factory=set)
    unique_efilogids: Set[str] = field(default_factory=set)
    unique_dd_versions: Set[str] = field(default_factory=set)
    search_attempts: List[SearchAttempt] = field(default_factory=list)
    efilogids_processed: int = 0
    efilogids_found: int = 0
    total_logs_before_dedup: int = 0
    error: Optional[str] = None


class DataDogRetriever:
    """Sub-agent for retrieving logs from DataDog.

    This is a non-interactive sub-agent that performs DataDog searches
    based on the input parameters. It handles:
    - Building appropriate queries for both search modes
    - Time window calculation and expansion
    - Session-based retrieval (Step 2)
    - Retry logic with window expansion
    - Result aggregation and deduplication

    The sub-agent cannot interact with users directly - all inputs
    must be provided by the main agent.
    """

    # Maximum number of efilogids to search in Step 2
    MAX_EFILOGIDS_TO_PROCESS = 30

    # Default limit for search results
    DEFAULT_LIMIT = 200

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
    ):
        """Initialize the DataDog retriever.

        Args:
            api_key: DataDog API key
            app_key: DataDog application key
            site: DataDog site (default: datadoghq.com)
        """
        self.api = DataDogAPI(api_key=api_key, app_key=app_key, site=site)
        logger.info(f"DataDogRetriever initialized for site: {site}")

    @classmethod
    def from_config(cls, config: Config) -> "DataDogRetriever":
        """Create a DataDogRetriever from a Config object.

        Args:
            config: Application configuration

        Returns:
            Configured DataDogRetriever instance
        """
        return cls(
            api_key=config.datadog_api_key,
            app_key=config.datadog_app_key,
            site=config.datadog_site,
        )

    def search(self, search_input: DataDogSearchInput) -> DataDogSearchResult:
        """Execute a DataDog search based on the input parameters.

        This is the main entry point for the sub-agent. It:
        1. Builds the appropriate query based on search mode
        2. Executes Step 1 (initial search)
        3. If results found, executes Step 2 (session retrieval)
        4. Handles retries with expanded time windows
        5. Returns aggregated, deduplicated results

        Args:
            search_input: Search parameters including mode, query data, and datetime

        Returns:
            DataDogSearchResult with all logs and metadata
        """
        logger.info(f"Starting DataDog search, mode={search_input.mode.value}")

        result = DataDogSearchResult()

        # Build query based on mode
        if search_input.mode == SearchMode.LOG_MESSAGE:
            if not search_input.log_message:
                result.error = "Log message is required for Mode 1 search"
                logger.error(result.error)
                return result
            query = self.api.build_log_message_query(search_input.log_message)
            logger.info(f"Mode 1 search with log message: {search_input.log_message[:100]}...")
        else:  # SearchMode.IDENTIFIERS
            if not search_input.identifiers or len(search_input.identifiers) == 0:
                result.error = "At least one identifier is required for Mode 2 search"
                logger.error(result.error)
                return result
            query = self.api.build_identifiers_query(search_input.identifiers)
            logger.info(f"Mode 2 search with identifiers: {search_input.identifiers}")

        # Execute Step 1 with retry logic
        step1_result = self._execute_step1_with_retry(
            query=query,
            user_datetime=search_input.user_datetime,
            result=result,
        )

        if not step1_result or step1_result.total_count == 0:
            logger.warning("No logs found after all retry attempts")
            result.error = "No logs found matching the search criteria"
            return result

        # Store unique values from Step 1
        result.unique_services.update(step1_result.unique_services)
        result.unique_efilogids.update(step1_result.unique_efilogids)
        result.efilogids_found = len(step1_result.unique_efilogids)

        # Extract unique dd.versions
        for log in step1_result.logs:
            if log.dd_version:
                result.unique_dd_versions.add(log.dd_version)

        logger.info(
            f"Step 1 complete: {step1_result.total_count} logs, "
            f"{len(result.unique_services)} services, "
            f"{result.efilogids_found} unique efilogids"
        )

        # Execute Step 2 (session-based retrieval) if we have efilogids
        if result.efilogids_found > 0:
            # Get the time window from the last successful search attempt
            last_attempt = result.search_attempts[-1]
            from_time = last_attempt.from_time
            to_time = last_attempt.to_time

            step2_logs = self._execute_step2_session_retrieval(
                efilogids=list(step1_result.unique_efilogids),
                from_time=from_time,
                to_time=to_time,
                result=result,
            )

            # Combine Step 1 and Step 2 results
            all_logs = step1_result.logs + step2_logs
        else:
            all_logs = step1_result.logs

        # Deduplicate and finalize
        result.total_logs_before_dedup = len(all_logs)
        result.logs = self._deduplicate_logs(all_logs)

        # Update unique values from combined results
        for log in result.logs:
            if log.service:
                result.unique_services.add(log.service)
            if log.efilogid:
                result.unique_efilogids.add(log.efilogid)
            if log.dd_version:
                result.unique_dd_versions.add(log.dd_version)

        logger.info(
            f"Search complete: {len(result.logs)} logs (after dedup), "
            f"{len(result.unique_services)} services, "
            f"{len(result.unique_efilogids)} efilogids"
        )

        return result

    def _execute_step1_with_retry(
        self,
        query: str,
        user_datetime: Optional[datetime],
        result: DataDogSearchResult,
    ) -> Optional[SearchResult]:
        """Execute Step 1 search with time window expansion retry logic.

        Args:
            query: DataDog search query
            user_datetime: Optional user-provided datetime
            result: Result object to update with search attempts

        Returns:
            SearchResult if logs found, None if all retries exhausted
        """
        # Calculate initial time window
        from_time, to_time = calculate_time_window(user_datetime)

        # Attempt 0: Initial search
        search_result = self._execute_search(
            query=query,
            from_time=from_time,
            to_time=to_time,
            expansion_level=0,
            result=result,
        )

        if search_result and search_result.total_count > 0:
            return search_result

        # Attempt 1: Expand to level 1 (24h or +/- 12h)
        logger.info("No results found, expanding time window (level 1)")
        from_time, to_time = expand_time_window(
            original_from=from_time,
            original_to=to_time,
            expansion_level=1,
            user_datetime=user_datetime,
        )

        search_result = self._execute_search(
            query=query,
            from_time=from_time,
            to_time=to_time,
            expansion_level=1,
            result=result,
        )

        if search_result and search_result.total_count > 0:
            return search_result

        # Attempt 2: Expand to level 2 (7d or +/- 3.5d)
        logger.info("No results found, expanding time window (level 2)")
        from_time, to_time = expand_time_window(
            original_from=from_time,
            original_to=to_time,
            expansion_level=2,
            user_datetime=user_datetime,
        )

        search_result = self._execute_search(
            query=query,
            from_time=from_time,
            to_time=to_time,
            expansion_level=2,
            result=result,
        )

        return search_result if search_result and search_result.total_count > 0 else None

    def _execute_search(
        self,
        query: str,
        from_time: str,
        to_time: str,
        expansion_level: int,
        result: DataDogSearchResult,
    ) -> Optional[SearchResult]:
        """Execute a single search and record the attempt.

        Args:
            query: DataDog search query
            from_time: Start time for search
            to_time: End time for search
            expansion_level: Current expansion level (0, 1, or 2)
            result: Result object to update with search attempt

        Returns:
            SearchResult if successful, None if error
        """
        attempt = SearchAttempt(
            query=query,
            from_time=from_time,
            to_time=to_time,
            expansion_level=expansion_level,
        )

        time_range_display = format_time_range_for_display(from_time, to_time)
        logger.info(f"Executing search (level {expansion_level}): {time_range_display}")
        logger.debug(f"Query: {query}")

        try:
            search_result = self.api.search_logs(
                query=query,
                from_time=from_time,
                to_time=to_time,
                limit=self.DEFAULT_LIMIT,
            )

            attempt.results_count = search_result.total_count
            attempt.success = True

            logger.info(f"Search returned {search_result.total_count} results")

        except DataDogAPIError as e:
            attempt.success = False
            attempt.error = str(e)
            logger.error(f"DataDog API error: {e}")
            search_result = None

        result.search_attempts.append(attempt)
        return search_result

    def _execute_step2_session_retrieval(
        self,
        efilogids: List[str],
        from_time: str,
        to_time: str,
        result: DataDogSearchResult,
    ) -> List[LogEntry]:
        """Execute Step 2: Session-based retrieval for all unique efilogids.

        Args:
            efilogids: List of unique efilogids from Step 1
            from_time: Start time for searches
            to_time: End time for searches
            result: Result object to update with metadata

        Returns:
            List of log entries from session searches
        """
        # Prioritize and limit efilogids
        prioritized_efilogids = self._prioritize_efilogids(efilogids, result)

        result.efilogids_processed = len(prioritized_efilogids)

        logger.info(
            f"Step 2: Processing {result.efilogids_processed} of "
            f"{len(efilogids)} unique efilogids"
        )

        all_logs: List[LogEntry] = []

        for i, efilogid in enumerate(prioritized_efilogids):
            logger.debug(f"Searching efilogid {i+1}/{result.efilogids_processed}: {efilogid}")

            try:
                query = self.api.build_efilogid_query(efilogid)
                search_result = self.api.search_logs(
                    query=query,
                    from_time=from_time,
                    to_time=to_time,
                    limit=self.DEFAULT_LIMIT,
                )

                all_logs.extend(search_result.logs)

                logger.debug(f"  Found {search_result.total_count} logs for efilogid {efilogid}")

            except DataDogAPIError as e:
                logger.warning(f"Failed to search efilogid {efilogid}: {e}")
                continue

        logger.info(f"Step 2 complete: Retrieved {len(all_logs)} logs from session searches")

        return all_logs

    def _prioritize_efilogids(
        self,
        efilogids: List[str],
        result: DataDogSearchResult,
    ) -> List[str]:
        """Prioritize efilogids for Step 2 processing.

        Priority order:
        1. Sessions with ERROR-level logs (would need Step 1 logs to determine)
        2. Most recent sessions (by timestamp)
        3. Sessions with most log entries in Step 1

        For simplicity in this implementation, we take the first N efilogids
        since they come from a timestamp-sorted search (most recent first).

        Args:
            efilogids: List of all unique efilogids
            result: Result object with Step 1 data

        Returns:
            Prioritized list limited to MAX_EFILOGIDS_TO_PROCESS
        """
        if len(efilogids) <= self.MAX_EFILOGIDS_TO_PROCESS:
            return efilogids

        # Take first N since results are sorted by timestamp (most recent first)
        # This effectively prioritizes the most recent sessions
        logger.info(
            f"Limiting efilogids from {len(efilogids)} to {self.MAX_EFILOGIDS_TO_PROCESS}"
        )

        return efilogids[:self.MAX_EFILOGIDS_TO_PROCESS]

    def _deduplicate_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        """Deduplicate logs by their ID.

        Args:
            logs: List of log entries (may contain duplicates)

        Returns:
            Deduplicated list preserving order of first occurrence
        """
        seen_ids: Set[str] = set()
        unique_logs: List[LogEntry] = []

        for log in logs:
            if log.id not in seen_ids:
                seen_ids.add(log.id)
                unique_logs.append(log)

        dedup_count = len(logs) - len(unique_logs)
        if dedup_count > 0:
            logger.debug(f"Deduplicated {dedup_count} logs")

        return unique_logs

    def retrieve_logs(self, query: str, time_range: str) -> list:
        """Legacy method for backward compatibility.

        DEPRECATED: Use search() method instead.

        Args:
            query: Log search query
            time_range: Time range for the search (not used, for compatibility)

        Returns:
            List of log entries (empty list, use search() for full functionality)
        """
        logger.warning("retrieve_logs() is deprecated, use search() instead")
        return []

    def search_by_log_message(
        self,
        log_message: str,
        user_datetime: Optional[datetime] = None,
    ) -> DataDogSearchResult:
        """Convenience method for Mode 1 (log message) search.

        Args:
            log_message: The log message to search for
            user_datetime: Optional datetime when the issue occurred

        Returns:
            DataDogSearchResult with all logs and metadata
        """
        search_input = DataDogSearchInput(
            mode=SearchMode.LOG_MESSAGE,
            log_message=log_message,
            user_datetime=user_datetime,
        )
        return self.search(search_input)

    def search_by_identifiers(
        self,
        identifiers: List[str],
        user_datetime: Optional[datetime] = None,
    ) -> DataDogSearchResult:
        """Convenience method for Mode 2 (identifiers) search.

        Args:
            identifiers: List of identifiers (CID, card_account_id, paymentId)
            user_datetime: Optional datetime when the issue occurred

        Returns:
            DataDogSearchResult with all logs and metadata
        """
        search_input = DataDogSearchInput(
            mode=SearchMode.IDENTIFIERS,
            identifiers=identifiers,
            user_datetime=user_datetime,
        )
        return self.search(search_input)
