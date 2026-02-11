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
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from utils.config import Config, get_config, ConfigurationError
from utils.logger import get_logger, configure_logging
from utils.time_utils import parse_time, tel_aviv_to_utc, UTC_TZ
from utils.report_generator import ReportGenerator
from utils.stack_trace_parser import extract_file_paths, StackTraceParser, ParsedStackTrace

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
from agents.code_checker import (
    CodeChecker,
    CodeAnalysisResult,
    FileAnalysis,
    PotentialIssue,
)
from agents.exception_analyzer import (
    ExceptionAnalyzer,
    ExceptionAnalysis,
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
        code_analysis: Code analysis result from Code Checker
        logger_names: Logger names found for this service (from DataDog logs)
        stack_trace_files: File paths extracted from stack traces
        parsed_stack_traces: Parsed stack traces with exception info
        exception_analysis: Analysis result from ExceptionAnalyzer
        error: Error message if investigation failed
    """
    service_name: str
    deployment_result: Optional[DeploymentCheckResult] = None
    code_analysis: Optional[CodeAnalysisResult] = None
    logger_names: Optional[Set[str]] = None
    stack_trace_files: Optional[Set[str]] = None
    parsed_stack_traces: Optional[List[ParsedStackTrace]] = None
    exception_analysis: Optional[ExceptionAnalysis] = None
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
        self._code_checker: Optional[CodeChecker] = None
        self._report_generator: Optional[ReportGenerator] = None

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

    @property
    def code_checker(self) -> CodeChecker:
        """Get or create the Code Checker sub-agent.

        Lazily initializes the checker on first access.
        """
        if self._code_checker is None:
            self._code_checker = CodeChecker.from_config(self.config)
        return self._code_checker

    @property
    def report_generator(self) -> ReportGenerator:
        """Get or create the report generator.

        Lazily initializes the generator on first access.
        """
        if self._report_generator is None:
            self._report_generator = ReportGenerator()
        return self._report_generator

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

        # Check for exit commands
        if mode_input.lower() in ("exit", "quit", "q"):
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

        if log_message.lower() in ("exit", "quit", "q"):
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

        if issue_description.lower() in ("exit", "quit", "q"):
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

    def investigate(self, user_input: Optional[UserInput] = None) -> str:
        """Investigate a production issue and return a markdown report.

        This is the main entry point for investigations. It:
        1. Collects user input if not provided
        2. Calls the DataDog sub-agent to search logs
        3. Extracts unique services
        4. Calls Deployment Checker and Code Checker for each service (in parallel)
        5. Generates investigation report

        Args:
            user_input: Pre-collected user input. If None, will prompt interactively.

        Returns:
            Markdown-formatted investigation report string
        """
        # Collect input if not provided
        if user_input is None:
            user_input = self.collect_user_input()
            if user_input is None:
                return ""  # User cancelled

        logger.info(f"Starting investigation with mode: {user_input.mode.name}")
        search_timestamp = datetime.now(UTC_TZ)

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
            # Return a minimal report with the error
            return self._generate_error_report(user_input, str(e), search_timestamp)

        # Display DataDog results
        self._display_datadog_results(dd_result)

        # Initialize service results list
        service_results: List[ServiceInvestigationResult] = []

        # If no logs found, try to provide helpful guidance
        if dd_result.error and "No logs found" in dd_result.error:
            return self._handle_no_logs_found(user_input, dd_result, search_timestamp)

        # If we have services, investigate deployments and code changes
        if dd_result.unique_services:
            print("\nChecking deployments and analyzing code for services...")

            # Get the search timestamp from the last search attempt
            log_search_timestamp = "now-4h"  # Default
            if dd_result.search_attempts:
                log_search_timestamp = dd_result.search_attempts[-1].from_time

            # Extract logger_names per service from the logs
            service_logger_names = self._extract_logger_names_per_service(dd_result)

            # Extract stack trace files per service
            service_stack_trace_files = self._extract_stack_trace_files_per_service(dd_result)

            # Investigate services in parallel
            service_results = self._investigate_services_parallel(
                services=list(dd_result.unique_services),
                log_search_timestamp=log_search_timestamp,
                dd_versions=dd_result.unique_dd_versions,
                service_logger_names=service_logger_names,
                service_stack_trace_files=service_stack_trace_files,
            )

            # Display deployment results
            self._display_deployment_results(service_results)

            # Display code analysis results
            self._display_code_analysis_results(service_results)

        # Build investigation result for report generation
        investigation_result = self._build_investigation_result(
            user_input=user_input,
            dd_result=dd_result,
            service_results=service_results,
            search_timestamp=search_timestamp,
        )

        # Generate the report
        print("\nGenerating investigation report...")
        report = self.report_generator.generate_report(investigation_result)

        return report

    def _build_investigation_result(
        self,
        user_input: UserInput,
        dd_result: DataDogSearchResult,
        service_results: List[ServiceInvestigationResult],
        search_timestamp: datetime,
    ) -> Dict[str, Any]:
        """Build the investigation result dictionary for report generation.

        Args:
            user_input: User input data
            dd_result: DataDog search result
            service_results: List of service investigation results
            search_timestamp: When investigation was performed

        Returns:
            Dictionary suitable for ReportGenerator.generate_report()
        """
        # Convert user input to dict
        user_input_dict = {
            "mode": user_input.mode.name,
            "log_message": user_input.log_message,
            "issue_description": user_input.issue_description,
            "identifiers": user_input.identifiers,
            "datetime": user_input.datetime_str,
        }

        # Convert DataDog result to dict
        datadog_dict = {
            "total_logs": len(dd_result.logs),
            "unique_services": list(dd_result.unique_services),
            "unique_efilogids": list(dd_result.unique_efilogids),
            "unique_dd_versions": list(dd_result.unique_dd_versions),
            "efilogids_found": dd_result.efilogids_found,
            "efilogids_processed": dd_result.efilogids_processed,
            "search_attempts": [
                {
                    "query": sa.query,
                    "from_time": sa.from_time,
                    "to_time": sa.to_time,
                    "expansion_level": sa.expansion_level,
                    "results_count": sa.results_count,
                    "success": sa.success,
                    "error": sa.error,
                }
                for sa in dd_result.search_attempts
            ],
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp,
                    "service": log.service,
                    "status": log.status,
                    "message": log.message,
                    "logger_name": log.logger_name,
                    "efilogid": log.efilogid,
                    "dd_version": log.dd_version,
                }
                for log in dd_result.logs
            ],
            "error": dd_result.error,
        }

        # Convert service results to dict
        service_results_dict = []
        for sr in service_results:
            sr_dict = {
                "service_name": sr.service_name,
                "logger_names": list(sr.logger_names) if sr.logger_names else [],
                "stack_trace_files": list(sr.stack_trace_files) if sr.stack_trace_files else [],
                "error": sr.error,
            }

            # Convert deployment result
            if sr.deployment_result:
                dr = sr.deployment_result
                sr_dict["deployment_result"] = {
                    "status": dr.status,
                    "search_window_start": dr.search_window_start,
                    "search_window_end": dr.search_window_end,
                    "error": dr.error,
                    "deployments": [
                        {
                            "deployment_timestamp": d.deployment_timestamp,
                            "kubernetes_commit_sha": d.kubernetes_commit_sha,
                            "application_commit_hash": d.application_commit_hash,
                            "build_number": d.build_number,
                            "dd_version": d.dd_version,
                            "pr_number": d.pr_number,
                            "changed_files": [
                                {"filename": f.filename, "status": f.status}
                                for f in d.changed_files
                            ],
                        }
                        for d in dr.deployments
                    ],
                }

            # Convert code analysis result
            if sr.code_analysis:
                ca = sr.code_analysis
                sr_dict["code_analysis"] = {
                    "status": ca.status,
                    "repository": ca.repository,
                    "dd_version": ca.dd_version,
                    "deployed_commit": ca.deployed_commit,
                    "parent_commit": ca.parent_commit,
                    "files_analyzed": ca.files_analyzed,
                    "total_issues_found": ca.total_issues_found,
                    "error": ca.error,
                    "file_analyses": [
                        {
                            "file_path": fa.file_path,
                            "previous_commit": fa.previous_commit,
                            "current_commit": fa.current_commit,
                            "diff": fa.diff,
                            "analysis_summary": fa.analysis_summary,
                            "error": fa.error,
                            "potential_issues": [
                                {
                                    "issue_type": pi.issue_type,
                                    "description": pi.description,
                                    "severity": pi.severity,
                                    "line_numbers": pi.line_numbers,
                                    "code_snippet": pi.code_snippet,
                                }
                                for pi in fa.potential_issues
                            ],
                        }
                        for fa in ca.file_analyses
                    ],
                }

            service_results_dict.append(sr_dict)

        return {
            "user_input": user_input_dict,
            "datadog_result": datadog_dict,
            "service_results": service_results_dict,
            "search_timestamp": search_timestamp,
        }

    def _generate_error_report(
        self,
        user_input: UserInput,
        error_message: str,
        search_timestamp: datetime,
    ) -> str:
        """Generate a minimal error report when investigation fails early.

        Args:
            user_input: User input data
            error_message: The error that occurred
            search_timestamp: When investigation was attempted

        Returns:
            Markdown error report
        """
        mode = user_input.mode.name
        if mode == "LOG_MESSAGE":
            issue_desc = user_input.log_message or "N/A"
        else:
            issue_desc = f"{user_input.issue_description} (IDs: {', '.join(user_input.identifiers or [])})"

        return f"""# Investigation Report: Error During Investigation

**Issue**: {issue_desc}
**Investigated**: {search_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}
**Status**: ERROR

---

## Error Details

The investigation could not be completed due to an error:

```
{error_message}
```

## Recommended Actions

1. Verify your API credentials are correct (DataDog API key, GitHub token)
2. Check network connectivity to DataDog and GitHub
3. Review the error message for specific guidance
4. Try again with a different search query or time window

---

*Generated by Production Issue Investigator Agent*
"""

    def _handle_no_logs_found(
        self,
        user_input: UserInput,
        dd_result: DataDogSearchResult,
        search_timestamp: datetime,
    ) -> str:
        """Handle the case when no logs are found.

        Provides helpful suggestions and generates a minimal report.

        Args:
            user_input: User input data
            dd_result: DataDog search result (empty)
            search_timestamp: When investigation was performed

        Returns:
            Markdown report with suggestions
        """
        print("\n" + "=" * 60)
        print("No logs found matching your search criteria.")
        print("=" * 60)
        print("\nSuggestions:")
        print("  - Try a different search term or identifier")
        print("  - Check if the datetime is correct")
        print("  - Verify the service/team is correct (searching pod_label_team:card)")
        print("  - Try expanding the time range")

        # Ask if user wants to try again with different input
        print("\nWould you like to provide more context? (y/n): ", end="")
        try:
            response = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            response = "n"

        if response in ("y", "yes"):
            print("\nPlease describe the issue in more detail or provide additional identifiers.")
            print("Additional context: ", end="")
            try:
                additional_context = input().strip()
            except (EOFError, KeyboardInterrupt):
                additional_context = ""

            if additional_context:
                # Log the additional context for the report
                logger.info(f"User provided additional context: {additional_context}")

        # Generate a minimal report
        investigation_result = self._build_investigation_result(
            user_input=user_input,
            dd_result=dd_result,
            service_results=[],
            search_timestamp=search_timestamp,
        )

        return self.report_generator.generate_report(investigation_result)

    def _investigate_services_parallel(
        self,
        services: List[str],
        log_search_timestamp: str,
        dd_versions: Set[str],
        service_logger_names: Dict[str, Set[str]],
        service_stack_trace_files: Optional[Dict[str, Set[str]]] = None,
    ) -> List[ServiceInvestigationResult]:
        """Investigate multiple services in parallel.

        Uses ThreadPoolExecutor to run deployment and code checks for all
        services concurrently. Per service, deployment check runs first,
        then code check runs (sequential within each service).

        Args:
            services: List of service names to investigate
            log_search_timestamp: The 'from' time from log search
            dd_versions: Set of dd.version values from logs
            service_logger_names: Map of service name to logger names from logs
            service_stack_trace_files: Map of service name to file paths from stack traces

        Returns:
            List of ServiceInvestigationResult, one per service
        """
        logger.info(f"Investigating {len(services)} services in parallel")

        if service_stack_trace_files is None:
            service_stack_trace_files = {}

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
                    logger_names=service_logger_names.get(service, set()),
                    stack_trace_files=service_stack_trace_files.get(service, set()),
                ): service
                for service in services
            }

            # Collect results as they complete
            for future in futures:
                service = futures[future]
                try:
                    result = future.result(timeout=180)  # 3 minute timeout per service
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
        logger_names: Set[str],
        stack_trace_files: Optional[Set[str]] = None,
    ) -> ServiceInvestigationResult:
        """Investigate a single service.

        Runs Deployment Checker and then Code Checker for the service.
        Code Checker runs AFTER Deployment Checker completes (sequential per service).
        Also analyzes files from stack traces if available.

        Args:
            service_name: Name of the service to investigate
            log_search_timestamp: The 'from' time from log search
            dd_versions: Set of dd.version values from logs
            logger_names: Set of logger names from DataDog logs for this service
            stack_trace_files: Set of file paths extracted from stack traces

        Returns:
            ServiceInvestigationResult with deployment and code analysis
        """
        logger.info(f"Investigating service: {service_name}")

        result = ServiceInvestigationResult(
            service_name=service_name,
            logger_names=logger_names,
            stack_trace_files=stack_trace_files,
        )

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

        # Step 2: Run Code Checker
        # Code Checker needs the dd_version to get the deployed commit
        # It runs sequentially after Deployment Checker
        if matching_version and logger_names:
            try:
                code_result = self.code_checker.analyze_service(
                    service_name=service_name,
                    dd_version=matching_version,
                    logger_names=logger_names,
                )
                result.code_analysis = code_result
            except Exception as e:
                logger.error(f"Code analysis failed for {service_name}: {e}")
                # Retry once
                try:
                    logger.info(f"Retrying code analysis for {service_name}")
                    code_result = self.code_checker.analyze_service(
                        service_name=service_name,
                        dd_version=matching_version,
                        logger_names=logger_names,
                    )
                    result.code_analysis = code_result
                except Exception as retry_e:
                    logger.error(f"Code analysis retry failed for {service_name}: {retry_e}")
                    # Continue without code analysis - partial result is OK
        else:
            logger.info(
                f"Skipping code analysis for {service_name}: "
                f"no dd_version={bool(matching_version)}, no logger_names={bool(logger_names)}"
            )

        # Step 3: Analyze stack trace files (if any, and not already analyzed)
        if matching_version and stack_trace_files and result.code_analysis:
            self._analyze_stack_trace_files(
                result=result,
                service_name=service_name,
                matching_version=matching_version,
                stack_trace_files=stack_trace_files,
            )

        return result

    def _analyze_stack_trace_files(
        self,
        result: ServiceInvestigationResult,
        service_name: str,
        matching_version: str,
        stack_trace_files: Set[str],
    ) -> None:
        """Analyze additional files from stack traces.

        Deduplicates against files already analyzed via logger_names,
        then calls code_checker.analyze_files_directly() for remaining files.

        Args:
            result: ServiceInvestigationResult to update
            service_name: Name of the service
            matching_version: The dd.version value
            stack_trace_files: File paths from stack traces
        """
        if not result.code_analysis:
            return

        # Get files already analyzed
        already_analyzed = set()
        for fa in result.code_analysis.file_analyses:
            already_analyzed.add(fa.file_path)

        # Find additional files to analyze
        additional_files = stack_trace_files - already_analyzed

        if not additional_files:
            logger.debug(f"No additional files to analyze from stack traces for {service_name}")
            return

        logger.info(f"Analyzing {len(additional_files)} additional files from stack traces for {service_name}")

        # Get repository and commit info from existing code analysis
        repository = result.code_analysis.repository
        if not repository:
            return

        owner, repo = repository.split("/")
        deployed_commit = result.code_analysis.deployed_commit
        parent_commit = result.code_analysis.parent_commit

        if not deployed_commit or not parent_commit:
            return

        # Analyze additional files
        try:
            additional_analyses = self.code_checker.analyze_files_directly(
                owner=owner,
                repo=repo,
                file_paths=list(additional_files),
                previous_commit=parent_commit,
                current_commit=deployed_commit,
            )

            # Merge results
            for analysis in additional_analyses:
                result.code_analysis.file_analyses.append(analysis)
                if not analysis.error:
                    result.code_analysis.files_analyzed += 1
                    result.code_analysis.total_issues_found += len(analysis.potential_issues)

        except Exception as e:
            logger.error(f"Error analyzing stack trace files for {service_name}: {e}")

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

    def _extract_logger_names_per_service(
        self,
        dd_result: DataDogSearchResult,
    ) -> Dict[str, Set[str]]:
        """Extract logger names grouped by service from DataDog logs.

        Args:
            dd_result: DataDog search result containing logs

        Returns:
            Dictionary mapping service name to set of logger names
        """
        service_logger_names: Dict[str, Set[str]] = {}

        for log in dd_result.logs:
            if log.service and log.logger_name:
                if log.service not in service_logger_names:
                    service_logger_names[log.service] = set()
                service_logger_names[log.service].add(log.logger_name)

        # Log what we found
        for service, loggers in service_logger_names.items():
            logger.debug(f"Service {service}: {len(loggers)} unique logger names")

        return service_logger_names

    def _extract_stack_trace_files_per_service(
        self,
        dd_result: DataDogSearchResult,
    ) -> Dict[str, Set[str]]:
        """Extract file paths from stack traces grouped by service.

        Only processes error/warn logs, as stack traces are most relevant
        for error cases. Parses both the dedicated stack_trace field and
        embedded stack traces in the message field.

        Args:
            dd_result: DataDog search result containing logs

        Returns:
            Dictionary mapping service name to set of file paths
        """
        # Use the new method and extract just file_paths for backwards compatibility
        data_result = self._extract_stack_trace_data_per_service(dd_result)
        return {
            service: data["file_paths"]
            for service, data in data_result.items()
        }

    def _extract_stack_trace_data_per_service(
        self,
        dd_result: DataDogSearchResult,
    ) -> Dict[str, Dict[str, Any]]:
        """Extract file paths and parsed traces from stack traces grouped by service.

        Only processes error/warn logs, as stack traces are most relevant
        for error cases. Parses both the dedicated stack_trace field and
        embedded stack traces in the message field.

        Args:
            dd_result: DataDog search result containing logs

        Returns:
            Dictionary mapping service name to dict with:
                - file_paths: Set of unique file paths
                - parsed_traces: List of ParsedStackTrace objects
        """
        service_stack_data: Dict[str, Dict[str, Any]] = {}
        parser = StackTraceParser()

        for log in dd_result.logs:
            # Only process error/warn logs for stack traces
            if log.status not in ("error", "warn", "ERROR", "WARN"):
                continue

            if not log.service:
                continue

            # Initialize service data if needed
            if log.service not in service_stack_data:
                service_stack_data[log.service] = {
                    "file_paths": set(),
                    "parsed_traces": [],
                }

            # Parse stack trace from dedicated field
            if log.stack_trace:
                parsed = parser.parse(log.stack_trace)
                if parsed.frames:
                    service_stack_data[log.service]["parsed_traces"].append(parsed)
                    service_stack_data[log.service]["file_paths"].update(parsed.unique_file_paths)

            # Also check for embedded stack trace in message
            if log.message:
                parsed = parser.parse(log.message)
                if parsed.frames:
                    service_stack_data[log.service]["parsed_traces"].append(parsed)
                    service_stack_data[log.service]["file_paths"].update(parsed.unique_file_paths)

        # Log what we found
        for service, data in service_stack_data.items():
            logger.debug(
                f"Service {service}: {len(data['file_paths'])} unique files, "
                f"{len(data['parsed_traces'])} parsed traces from stack traces"
            )

        return service_stack_data

    def _display_code_analysis_results(
        self,
        service_results: List[ServiceInvestigationResult],
    ) -> None:
        """Display code analysis results to the user.

        Args:
            service_results: List of service investigation results
        """
        # Check if any service has code analysis results
        has_code_analysis = any(sr.code_analysis for sr in service_results)
        if not has_code_analysis:
            return

        print("\n" + "=" * 60)
        print("Code Analysis Results")
        print("=" * 60)

        total_issues = 0
        services_analyzed = 0

        for sr in service_results:
            print(f"\n{sr.service_name}:")

            if not sr.code_analysis:
                print("  Status: Code analysis not performed")
                if not sr.logger_names:
                    print("  Reason: No logger names found in logs")
                continue

            ca = sr.code_analysis

            if ca.error:
                print(f"  Status: ERROR - {ca.error}")
                continue

            if ca.status == "no_changes":
                print("  Status: No code changes to analyze")
                continue

            services_analyzed += 1
            print(f"  Status: {ca.status}")
            print(f"  Repository: {ca.repository}")

            if ca.deployed_commit and ca.parent_commit:
                print(f"  Comparing: {ca.parent_commit[:8]} -> {ca.deployed_commit[:8]}")

            print(f"  Files analyzed: {ca.files_analyzed}")
            print(f"  Total issues found: {ca.total_issues_found}")
            total_issues += ca.total_issues_found

            # Show file analysis details
            if ca.file_analyses:
                for fa in ca.file_analyses:
                    if fa.error:
                        print(f"\n  File: {fa.file_path}")
                        print(f"    Error: {fa.error}")
                        continue

                    if fa.analysis_summary:
                        print(f"\n  File: {fa.file_path}")
                        print(f"    Summary: {fa.analysis_summary}")

                        # Show potential issues
                        if fa.potential_issues:
                            print("    Potential issues:")
                            for issue in fa.potential_issues[:5]:  # Show first 5
                                severity_marker = {
                                    "HIGH": "[!]",
                                    "MEDIUM": "[~]",
                                    "LOW": "[-]",
                                }.get(issue.severity, "[ ]")
                                print(f"      {severity_marker} {issue.description}")
                                if issue.code_snippet:
                                    # Show first 3 lines of snippet
                                    snippet_lines = issue.code_snippet.split("\n")[:3]
                                    for line in snippet_lines:
                                        print(f"          {line[:70]}")

                            if len(fa.potential_issues) > 5:
                                print(f"      ... and {len(fa.potential_issues) - 5} more issues")

        # Summary
        print("\n" + "-" * 40)
        print("Code Analysis Summary:")
        print(f"  Services analyzed: {services_analyzed}")
        print(f"  Total potential issues: {total_issues}")

        if total_issues > 0:
            # Count by severity
            high_count = 0
            medium_count = 0
            low_count = 0
            for sr in service_results:
                if sr.code_analysis:
                    for fa in sr.code_analysis.file_analyses:
                        for issue in fa.potential_issues:
                            if issue.severity == "HIGH":
                                high_count += 1
                            elif issue.severity == "MEDIUM":
                                medium_count += 1
                            else:
                                low_count += 1
            print(f"    HIGH: {high_count}, MEDIUM: {medium_count}, LOW: {low_count}")

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
        print("  - Generating comprehensive investigation reports")
        print("\nType 'exit' or 'quit' at any time to end the session.")
        print("Press Ctrl+C to cancel the current operation.")
        print("=" * 70 + "\n")

        while True:
            try:
                report = self.investigate()

                if not report:
                    # User cancelled
                    break

                # Display the report
                print("\n" + "=" * 70)
                print("INVESTIGATION REPORT")
                print("=" * 70)
                print(report)
                print("=" * 70 + "\n")

                print("-" * 40)
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
