"""
Main orchestrator agent for coordinating issue investigation.

This is the main agent that:
- Interacts with the user to collect inputs
- Determines the input mode (log message vs identifiers)
- Coordinates sub-agents (DataDog, Deployment Checker, Code Checker)
- Aggregates findings and generates investigation reports
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from utils.config import Config, get_config, ConfigurationError
from utils.logger import get_logger, configure_logging
from utils.time_utils import parse_time, tel_aviv_to_utc

from agents.datadog_retriever import (
    DataDogRetriever,
    DataDogSearchResult,
    SearchMode,
)
from agents.deployment_checker import (
    DeploymentChecker,
    DeploymentCheckResult,
    DeploymentInfo,
)

logger = get_logger(__name__)


class InputMode(Enum):
    """User input mode for investigation."""
    LOG_MESSAGE = 1
    IDENTIFIERS = 2


@dataclass
class UserInput:
    """Collected user input for investigation.

    Attributes:
        mode: The input mode selected by user
        log_message: Log message text (for Mode 1)
        issue_description: Free text description (for Mode 2)
        identifiers: List of identifiers (for Mode 2)
        datetime_str: Optional datetime string provided by user
        parsed_datetime: Parsed datetime object (in Tel Aviv timezone)
    """
    mode: InputMode
    log_message: Optional[str] = None
    issue_description: Optional[str] = None
    identifiers: Optional[List[str]] = None
    datetime_str: Optional[str] = None
    parsed_datetime: Optional[datetime] = None


@dataclass
class ServiceInvestigationResult:
    """Result from investigating a single service.

    Attributes:
        service_name: Name of the service
        deployment_result: Result from Deployment Checker
        code_analysis: Code analysis result (Phase 4)
        error: Error message if investigation failed
    """
    service_name: str
    deployment_result: Optional[DeploymentCheckResult] = None
    code_analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MainAgent:
    """Main agent that orchestrates the investigation process.

    The main agent is responsible for:
    - Interacting with users to collect inputs
    - Coordinating sub-agents (DataDog, Deployment, Code)
    - Aggregating results and generating reports
    - Handling errors and asking follow-up questions

    Sub-agents cannot interact with users directly - all user
    interaction goes through this main agent.
    """

    # Mode selection prompt shown to users
    MODE_SELECTION_PROMPT = """
Please select how you want to investigate:

1. **Log Message** - You have a specific log message or error text from DataDog
2. **Identifiers** - You have customer/transaction identifiers (CID, card_account_id, paymentId)

Which option? (Enter 1 or 2): """

    # Mode 1 input prompt
    MODE1_INPUT_PROMPT = """
Please provide:
- Log message: The exact or partial log text from DataDog
- DateTime (optional): When did this occur? Format: any human-readable format (e.g., "2026-02-10 14:30", "today 2pm", "yesterday")

Enter log message: """

    # Mode 2 input prompt
    MODE2_INPUT_PROMPT = """
Please provide:
- Issue description: Describe the problem/error
- Identifiers: One or more identifiers (CID, card_account_id, paymentId) separated by commas
- DateTime (optional): When did this occur? Format: any human-readable format

Enter issue description: """

    def __init__(self, config: Optional[Config] = None):
        """Initialize the main agent.

        Args:
            config: Application configuration. If not provided, will load from environment.
        """
        if config is None:
            config = get_config()

        self.config = config
        self._datadog_retriever: Optional[DataDogRetriever] = None
        self._deployment_checker: Optional[DeploymentChecker] = None

        # Configure logging based on config
        configure_logging(log_level=config.log_level)

        logger.info("MainAgent initialized")

    @property
    def datadog_retriever(self) -> DataDogRetriever:
        """Get or create the DataDog retriever sub-agent.

        Lazily initializes the retriever on first access.
        """
        if self._datadog_retriever is None:
            self._datadog_retriever = DataDogRetriever.from_config(self.config)
        return self._datadog_retriever

    @property
    def deployment_checker(self) -> DeploymentChecker:
        """Get or create the Deployment Checker sub-agent.

        Lazily initializes the checker on first access.
        """
        if self._deployment_checker is None:
            self._deployment_checker = DeploymentChecker.from_config(self.config)
        return self._deployment_checker

    def collect_user_input(self) -> Optional[UserInput]:
        """Interactively collect input from the user.

        Prompts the user to select a mode and provide the required inputs.

        Returns:
            UserInput object with collected data, or None if user cancels
        """
        print(self.MODE_SELECTION_PROMPT, end="")

        try:
            mode_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if mode_input == "1":
            return self._collect_mode1_input()
        elif mode_input == "2":
            return self._collect_mode2_input()
        else:
            print("\nInvalid option. Please enter 1 or 2.")
            return self.collect_user_input()

    def _collect_mode1_input(self) -> Optional[UserInput]:
        """Collect Mode 1 (log message) input from user.

        Returns:
            UserInput for Mode 1, or None if user cancels
        """
        print(self.MODE1_INPUT_PROMPT, end="")

        try:
            log_message = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not log_message:
            print("Log message cannot be empty.")
            return self._collect_mode1_input()

        print("Enter datetime (optional, press Enter to skip): ", end="")
        try:
            datetime_str = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        parsed_datetime = None
        if datetime_str:
            try:
                parsed_datetime = parse_time(datetime_str)
                logger.debug(f"Parsed datetime: {parsed_datetime}")
            except Exception as e:
                print(f"Warning: Could not parse datetime '{datetime_str}': {e}")
                print("Continuing without datetime filter.")

        return UserInput(
            mode=InputMode.LOG_MESSAGE,
            log_message=log_message,
            datetime_str=datetime_str if datetime_str else None,
            parsed_datetime=parsed_datetime,
        )

    def _collect_mode2_input(self) -> Optional[UserInput]:
        """Collect Mode 2 (identifiers) input from user.

        Returns:
            UserInput for Mode 2, or None if user cancels
        """
        print(self.MODE2_INPUT_PROMPT, end="")

        try:
            issue_description = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        print("Enter identifiers (comma-separated): ", end="")
        try:
            identifiers_str = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not identifiers_str:
            print("At least one identifier is required.")
            return self._collect_mode2_input()

        # Parse identifiers (comma or space separated)
        identifiers = [
            id.strip()
            for id in identifiers_str.replace(",", " ").split()
            if id.strip()
        ]

        if not identifiers:
            print("At least one identifier is required.")
            return self._collect_mode2_input()

        print("Enter datetime (optional, press Enter to skip): ", end="")
        try:
            datetime_str = input().strip()
        except (EOFError, KeyboardInterrupt):
            return None

        parsed_datetime = None
        if datetime_str:
            try:
                parsed_datetime = parse_time(datetime_str)
                logger.debug(f"Parsed datetime: {parsed_datetime}")
            except Exception as e:
                print(f"Warning: Could not parse datetime '{datetime_str}': {e}")
                print("Continuing without datetime filter.")

        return UserInput(
            mode=InputMode.IDENTIFIERS,
            issue_description=issue_description,
            identifiers=identifiers,
            datetime_str=datetime_str if datetime_str else None,
            parsed_datetime=parsed_datetime,
        )

    def investigate(self, user_input: Optional[UserInput] = None) -> Dict[str, Any]:
        """Investigate a production issue.

        This is the main entry point for investigations. It:
        1. Collects user input if not provided
        2. Calls the DataDog sub-agent to search logs
        3. Extracts unique services
        4. Calls Deployment Checker for each service (in parallel)
        5. (Phase 4) Calls Code Checker for each service
        6. Generates investigation report

        Args:
            user_input: Pre-collected user input. If None, will prompt interactively.

        Returns:
            Investigation results as a dictionary
        """
        # Collect input if not provided
        if user_input is None:
            user_input = self.collect_user_input()
            if user_input is None:
                return {
                    "status": "cancelled",
                    "message": "Investigation cancelled by user",
                }

        logger.info(f"Starting investigation with mode: {user_input.mode.name}")

        # Execute DataDog search
        print("\nSearching DataDog logs...")

        try:
            if user_input.mode == InputMode.LOG_MESSAGE:
                dd_result = self.datadog_retriever.search_by_log_message(
                    log_message=user_input.log_message,
                    user_datetime=user_input.parsed_datetime,
                )
            else:
                dd_result = self.datadog_retriever.search_by_identifiers(
                    identifiers=user_input.identifiers,
                    user_datetime=user_input.parsed_datetime,
                )
        except Exception as e:
            logger.error(f"DataDog search failed: {e}")
            return {
                "status": "error",
                "message": f"DataDog search failed: {e}",
            }

        # Display DataDog results
        self._display_datadog_results(dd_result)

        # Build result dictionary
        result = {
            "status": "success" if dd_result.error is None else "partial",
            "input": {
                "mode": user_input.mode.name,
                "log_message": user_input.log_message,
                "identifiers": user_input.identifiers,
                "datetime": user_input.datetime_str,
            },
            "datadog_results": {
                "total_logs": len(dd_result.logs),
                "unique_services": list(dd_result.unique_services),
                "unique_efilogids": len(dd_result.unique_efilogids),
                "unique_versions": list(dd_result.unique_dd_versions),
                "search_attempts": len(dd_result.search_attempts),
                "efilogids_processed": dd_result.efilogids_processed,
                "error": dd_result.error,
            },
            "deployment_results": {},
            "service_investigations": [],
        }

        # If no logs found, provide helpful message and return
        if dd_result.error and "No logs found" in dd_result.error:
            print("\n" + "=" * 60)
            print("No logs found matching your search criteria.")
            print("=" * 60)
            print("\nSuggestions:")
            print("  - Try a different search term or identifier")
            print("  - Check if the datetime is correct")
            print("  - Verify the service/team is correct (searching pod_label_team:card)")
            print("  - Try expanding the time range")
            return result

        # If we have services, investigate deployments
        if dd_result.unique_services:
            print("\nChecking deployments for services...")

            # Get the search timestamp from the last search attempt
            log_search_timestamp = "now-4h"  # Default
            if dd_result.search_attempts:
                log_search_timestamp = dd_result.search_attempts[-1].from_time

            # Investigate services in parallel
            service_results = self._investigate_services_parallel(
                services=list(dd_result.unique_services),
                log_search_timestamp=log_search_timestamp,
                dd_versions=dd_result.unique_dd_versions,
            )

            # Display and aggregate deployment results
            self._display_deployment_results(service_results)

            # Add to result
            result["service_investigations"] = [
                {
                    "service_name": sr.service_name,
                    "deployments_found": len(sr.deployment_result.deployments) if sr.deployment_result else 0,
                    "deployment_status": sr.deployment_result.status if sr.deployment_result else "error",
                    "error": sr.error,
                }
                for sr in service_results
            ]

            # Flatten deployment results
            for sr in service_results:
                if sr.deployment_result:
                    result["deployment_results"][sr.service_name] = {
                        "status": sr.deployment_result.status,
                        "deployments": [
                            {
                                "timestamp": d.deployment_timestamp,
                                "kubernetes_commit": d.kubernetes_commit_sha[:8],
                                "app_commit": d.application_commit_hash[:8],
                                "build_number": d.build_number,
                                "dd_version": d.dd_version,
                                "pr_number": d.pr_number,
                                "changed_files_count": len(d.changed_files),
                            }
                            for d in sr.deployment_result.deployments
                        ],
                        "search_window": {
                            "start": sr.deployment_result.search_window_start,
                            "end": sr.deployment_result.search_window_end,
                        },
                        "error": sr.deployment_result.error,
                    }

        return result

    def _investigate_services_parallel(
        self,
        services: List[str],
        log_search_timestamp: str,
        dd_versions: Set[str],
    ) -> List[ServiceInvestigationResult]:
        """Investigate multiple services in parallel.

        Uses ThreadPoolExecutor to run deployment checks for all services
        concurrently.

        Args:
            services: List of service names to investigate
            log_search_timestamp: The 'from' time from log search
            dd_versions: Set of dd.version values from logs

        Returns:
            List of ServiceInvestigationResult, one per service
        """
        logger.info(f"Investigating {len(services)} services in parallel")

        results: List[ServiceInvestigationResult] = []

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=min(len(services), 5)) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self._investigate_single_service,
                    service_name=service,
                    log_search_timestamp=log_search_timestamp,
                    dd_versions=dd_versions,
                ): service
                for service in services
            }

            # Collect results as they complete
            for future in futures:
                service = futures[future]
                try:
                    result = future.result(timeout=120)  # 2 minute timeout per service
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error investigating service {service}: {e}")
                    results.append(ServiceInvestigationResult(
                        service_name=service,
                        error=str(e),
                    ))

        return results

    def _investigate_single_service(
        self,
        service_name: str,
        log_search_timestamp: str,
        dd_versions: Set[str],
    ) -> ServiceInvestigationResult:
        """Investigate a single service.

        Runs Deployment Checker and (in Phase 4) Code Checker for the service.
        Code Checker runs AFTER Deployment Checker completes (sequential per service).

        Args:
            service_name: Name of the service to investigate
            log_search_timestamp: The 'from' time from log search
            dd_versions: Set of dd.version values from logs

        Returns:
            ServiceInvestigationResult with deployment and code analysis
        """
        logger.info(f"Investigating service: {service_name}")

        result = ServiceInvestigationResult(service_name=service_name)

        # Find matching dd_version for this service
        matching_version = None
        for version in dd_versions:
            # The dd.version format is: {commit_hash}___{build_number}
            # We need to check if any kubernetes commit title matches
            # service_name-{version}
            # This is a simplified check - the full validation happens in DeploymentChecker
            if version:
                matching_version = version
                break

        # Step 1: Run Deployment Checker
        try:
            deployment_result = self.deployment_checker.check_service_deployments(
                service_name=service_name,
                log_search_timestamp=log_search_timestamp,
                dd_version=matching_version,
            )
            result.deployment_result = deployment_result
        except Exception as e:
            logger.error(f"Deployment check failed for {service_name}: {e}")
            # Retry once
            try:
                logger.info(f"Retrying deployment check for {service_name}")
                deployment_result = self.deployment_checker.check_service_deployments(
                    service_name=service_name,
                    log_search_timestamp=log_search_timestamp,
                    dd_version=matching_version,
                )
                result.deployment_result = deployment_result
            except Exception as retry_e:
                logger.error(f"Retry failed for {service_name}: {retry_e}")
                result.error = str(retry_e)

        # Step 2: Run Code Checker (Phase 4 - placeholder)
        # Code Checker needs deployment info, so it runs sequentially after Deployment Checker
        # This will be implemented in Phase 4
        # if result.deployment_result and result.deployment_result.deployments:
        #     result.code_analysis = self._run_code_checker(
        #         service_name=service_name,
        #         deployment_info=result.deployment_result.deployments[0],
        #     )

        return result

    def _display_datadog_results(self, result: DataDogSearchResult) -> None:
        """Display DataDog search results to the user.

        Args:
            result: DataDog search result to display
        """
        print("\n" + "=" * 60)
        print("DataDog Search Results")
        print("=" * 60)

        if result.error:
            print(f"\nStatus: {result.error}")
        else:
            print(f"\nTotal logs found: {result.total_logs_before_dedup}")
            print(f"After deduplication: {len(result.logs)}")

        # Display search attempts
        print(f"\nSearch attempts: {len(result.search_attempts)}")
        for i, attempt in enumerate(result.search_attempts):
            status = "SUCCESS" if attempt.success else "FAILED"
            expansion = ["Initial", "Expanded (24h)", "Expanded (7d)"][attempt.expansion_level]
            print(f"  {i+1}. {expansion}: {attempt.results_count} results ({status})")
            if attempt.error:
                print(f"      Error: {attempt.error}")

        # Display unique services
        if result.unique_services:
            print(f"\nUnique services found ({len(result.unique_services)}):")
            for service in sorted(result.unique_services):
                print(f"  - {service}")

        # Display unique efilogids info
        print(f"\nSession (efilogid) summary:")
        print(f"  - Unique sessions found: {result.efilogids_found}")
        print(f"  - Sessions processed: {result.efilogids_processed}")
        print(f"  - Final unique sessions: {len(result.unique_efilogids)}")

        # Display unique versions
        if result.unique_dd_versions:
            print(f"\nUnique versions (dd.version) found ({len(result.unique_dd_versions)}):")
            for version in sorted(result.unique_dd_versions):
                print(f"  - {version}")

        # Display sample logs
        if result.logs:
            print(f"\nSample logs (showing first 5 of {len(result.logs)}):")
            print("-" * 60)
            for log in result.logs[:5]:
                timestamp = log.timestamp[:19] if log.timestamp else "N/A"
                service = log.service or "unknown"
                status = log.status or "info"
                message = log.message[:100] + "..." if len(log.message) > 100 else log.message
                print(f"[{timestamp}] [{service}] [{status}] {message}")
            if len(result.logs) > 5:
                print(f"  ... and {len(result.logs) - 5} more logs")

        print("\n" + "=" * 60)

    def _display_deployment_results(
        self,
        service_results: List[ServiceInvestigationResult],
    ) -> None:
        """Display deployment check results to the user.

        Args:
            service_results: List of service investigation results
        """
        print("\n" + "=" * 60)
        print("Deployment Check Results")
        print("=" * 60)

        total_deployments = 0
        services_with_deployments = 0

        for sr in service_results:
            print(f"\n{sr.service_name}:")

            if sr.error:
                print(f"  Status: ERROR - {sr.error}")
                continue

            if not sr.deployment_result:
                print("  Status: No result")
                continue

            dr = sr.deployment_result
            deployment_count = len(dr.deployments)
            total_deployments += deployment_count

            if deployment_count > 0:
                services_with_deployments += 1
                print(f"  Status: {dr.status}")
                print(f"  Deployments found: {deployment_count}")
                print(f"  Search window: {dr.search_window_start} to {dr.search_window_end}")

                # Show deployment details
                for i, d in enumerate(dr.deployments[:3]):  # Show first 3
                    print(f"\n  Deployment {i+1}:")
                    print(f"    Timestamp: {d.deployment_timestamp}")
                    print(f"    App commit: {d.application_commit_hash[:8]}")
                    print(f"    Build: {d.build_number}")
                    print(f"    dd.version: {d.dd_version[:20]}...")
                    if d.pr_number:
                        print(f"    PR: #{d.pr_number}")
                    if d.changed_files:
                        print(f"    Changed files: {len(d.changed_files)}")
                        for f in d.changed_files[:3]:
                            print(f"      - {f.filename} ({f.status})")
                        if len(d.changed_files) > 3:
                            print(f"      ... and {len(d.changed_files) - 3} more files")

                if len(dr.deployments) > 3:
                    print(f"\n  ... and {len(dr.deployments) - 3} more deployments")
            else:
                print(f"  Status: {dr.status}")
                print("  No deployments found in the 72-hour window")

        # Summary
        print("\n" + "-" * 40)
        print("Summary:")
        print(f"  Services checked: {len(service_results)}")
        print(f"  Services with deployments: {services_with_deployments}")
        print(f"  Total deployments found: {total_deployments}")
        print("=" * 60)

    def run_interactive(self) -> None:
        """Run the agent in interactive mode.

        Continuously prompts for investigations until user exits.
        """
        print("\n" + "=" * 70)
        print("Production Issue Investigator")
        print("=" * 70)
        print("\nThis agent helps investigate production issues by:")
        print("  - Searching DataDog logs for errors and patterns")
        print("  - Correlating issues with recent deployments")
        print("  - Analyzing code changes between versions")
        print("\nType 'exit' or 'quit' at any time to end the session.")
        print("Press Ctrl+C to cancel the current operation.")
        print("=" * 70 + "\n")

        while True:
            try:
                result = self.investigate()

                if result.get("status") == "cancelled":
                    break

                print("\n" + "-" * 40)
                print("Investigation complete.")
                print("-" * 40)

                print("\nWould you like to investigate another issue? (y/n): ", end="")
                try:
                    again = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    break

                if again not in ("y", "yes"):
                    break

                print()  # Add spacing before next investigation

            except KeyboardInterrupt:
                print("\n\nOperation cancelled.")
                continue

        print("\nGoodbye!")
