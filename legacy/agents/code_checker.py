"""
Code Checker sub-agent for analyzing code changes between versions.

This sub-agent is responsible for:
- Mapping logger names to file paths
- Fetching file content at specific commits
- Generating diffs between versions
- Analyzing code changes for potential issues
"""
import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any

from utils.config import Config
from utils.logger import get_logger
from utils.github_helper import (
    GitHubHelper,
    GitHubError,
    GitHubNotFoundError,
)

logger = get_logger(__name__)


# Constants
DEFAULT_ORG = "sunbit-dev"


@dataclass
class PotentialIssue:
    """A potential issue identified in code changes.

    Attributes:
        issue_type: Category of the issue (e.g., "error_handling_removed")
        description: Human-readable description of the issue
        severity: Severity level (HIGH, MEDIUM, LOW)
        line_numbers: Relevant line numbers in the diff
        code_snippet: Relevant code snippet
    """
    issue_type: str
    description: str
    severity: str = "MEDIUM"
    line_numbers: Optional[List[int]] = None
    code_snippet: Optional[str] = None


@dataclass
class FileAnalysis:
    """Analysis result for a single file.

    Attributes:
        file_path: Path to the file in the repository
        previous_commit: Commit SHA of the previous version
        current_commit: Commit SHA of the current (deployed) version
        diff: The generated diff between versions
        previous_content: Content at previous commit (for reference)
        current_content: Content at current commit (for reference)
        potential_issues: List of potential issues identified
        analysis_summary: Brief summary of the analysis
        error: Error message if analysis failed for this file
    """
    file_path: str
    previous_commit: str
    current_commit: str
    diff: Optional[str] = None
    previous_content: Optional[str] = None
    current_content: Optional[str] = None
    potential_issues: List[PotentialIssue] = field(default_factory=list)
    analysis_summary: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CodeAnalysisResult:
    """Complete result from code analysis for a service.

    Attributes:
        service_name: Name of the service analyzed
        repository: GitHub repository name (org/repo)
        dd_version: The dd.version value from logs
        deployed_commit: Commit hash of deployed version
        parent_commit: Commit hash of previous version
        file_analyses: List of file analysis results
        status: Overall status (success, partial, error, no_changes)
        error: Error message if analysis failed
        files_analyzed: Count of files successfully analyzed
        total_issues_found: Total count of potential issues found
    """
    service_name: str
    repository: Optional[str] = None
    dd_version: Optional[str] = None
    deployed_commit: Optional[str] = None
    parent_commit: Optional[str] = None
    file_analyses: List[FileAnalysis] = field(default_factory=list)
    status: str = "success"
    error: Optional[str] = None
    files_analyzed: int = 0
    total_issues_found: int = 0


class CodeChecker:
    """Sub-agent for analyzing code changes between versions.

    This is a non-interactive sub-agent that analyzes code changes
    between the deployed version and its parent commit to identify
    potential issues that may have caused production errors.

    The sub-agent:
    - Cannot interact with users directly
    - Logs all actions (inputs, outputs, tasks performed)
    - Handles errors gracefully (partial results OK)
    - Maps logger names to file paths
    - Generates diffs and analyzes for common issues
    """

    # Issue type constants
    ISSUE_ERROR_HANDLING_REMOVED = "error_handling_removed"
    ISSUE_BUSINESS_LOGIC_CHANGED = "business_logic_changed"
    ISSUE_NEW_EXCEPTION = "new_exception"
    ISSUE_SQL_QUERY_MODIFIED = "sql_query_modified"
    ISSUE_EXTERNAL_API_CHANGED = "external_api_changed"
    ISSUE_TIMING_ASYNC_MODIFIED = "timing_async_modified"
    ISSUE_SECURITY_CONCERN = "security_concern"

    def __init__(self, github_token: str):
        """Initialize the code checker.

        Args:
            github_token: GitHub API token
        """
        self.github_token = github_token
        self.github_helper = GitHubHelper(token=github_token)

        logger.info("CodeChecker initialized")

    @classmethod
    def from_config(cls, config: Config) -> "CodeChecker":
        """Create a CodeChecker from a Config object.

        Args:
            config: Application configuration

        Returns:
            Configured CodeChecker instance
        """
        return cls(github_token=config.github_token)

    def analyze_service(
        self,
        service_name: str,
        dd_version: str,
        logger_names: Set[str],
    ) -> CodeAnalysisResult:
        """Analyze code changes for a service.

        This is the main entry point for code analysis. It:
        1. Extracts commit hash from dd_version
        2. Finds the repository for the service
        3. Gets the parent commit
        4. For each logger_name, fetches files and generates diffs
        5. Analyzes diffs for potential issues

        Args:
            service_name: Name of the service to analyze
            dd_version: The dd.version from DataDog logs (format: {commit}___{build})
            logger_names: Set of logger names from DataDog logs

        Returns:
            CodeAnalysisResult with analysis details
        """
        logger.info(f"Starting code analysis for service: {service_name}")
        logger.debug(f"dd_version: {dd_version}")
        logger.debug(f"logger_names: {logger_names}")

        result = CodeAnalysisResult(
            service_name=service_name,
            dd_version=dd_version,
        )

        # Step 1: Extract commit hash from dd_version
        deployed_commit = self._extract_commit_hash(dd_version)
        if not deployed_commit:
            result.error = f"Could not extract commit hash from dd_version: {dd_version}"
            result.status = "error"
            logger.error(result.error)
            return result

        result.deployed_commit = deployed_commit
        logger.info(f"Deployed commit: {deployed_commit[:8]}")

        # Step 2: Find repository for service
        repository = self._get_repository_for_service(service_name)
        if not repository:
            result.error = f"Repository not found for service: {service_name}"
            result.status = "error"
            logger.error(result.error)
            return result

        result.repository = repository
        logger.info(f"Using repository: {repository}")

        # Step 3: Get parent commit
        owner, repo = repository.split("/")
        try:
            parent_commit = self.github_helper.get_parent_commit(
                owner=owner,
                repo=repo,
                commit_sha=deployed_commit,
            )
        except GitHubError as e:
            result.error = f"Failed to get parent commit: {e}"
            result.status = "error"
            logger.error(result.error)
            return result

        if not parent_commit:
            result.error = "No parent commit found (this may be the initial commit)"
            result.status = "no_changes"
            logger.warning(result.error)
            return result

        result.parent_commit = parent_commit
        logger.info(f"Parent commit: {parent_commit[:8]}")

        # Step 4: Analyze files from logger names
        if not logger_names:
            logger.warning("No logger names provided, skipping file analysis")
            result.status = "no_changes"
            return result

        for logger_name in logger_names:
            file_analysis = self._analyze_file_from_logger(
                owner=owner,
                repo=repo,
                logger_name=logger_name,
                previous_commit=parent_commit,
                current_commit=deployed_commit,
            )
            if file_analysis:
                result.file_analyses.append(file_analysis)
                if not file_analysis.error:
                    result.files_analyzed += 1
                    result.total_issues_found += len(file_analysis.potential_issues)

        # Determine final status
        if result.files_analyzed == 0:
            if len(result.file_analyses) > 0:
                result.status = "error"
                result.error = "All file analyses failed"
            else:
                result.status = "no_changes"
        elif result.files_analyzed < len(logger_names):
            result.status = "partial"
        else:
            result.status = "success"

        logger.info(
            f"Code analysis complete for {service_name}: "
            f"{result.files_analyzed} files analyzed, "
            f"{result.total_issues_found} potential issues found"
        )

        return result

    def _extract_commit_hash(self, dd_version: str) -> Optional[str]:
        """Extract commit hash from dd_version.

        The dd_version format is: {commit_hash}___{build_number}

        Args:
            dd_version: The dd.version value

        Returns:
            Commit hash if found, None otherwise
        """
        if not dd_version:
            return None

        # Pattern: 40-character hex hash followed by ___ and digits
        pattern = r"^([a-f0-9]{40})___\d+$"
        match = re.match(pattern, dd_version)

        if match:
            return match.group(1)

        # Fallback: try to extract anything that looks like a commit hash
        hash_pattern = r"([a-f0-9]{40})"
        hash_match = re.search(hash_pattern, dd_version)
        if hash_match:
            logger.warning(f"Using fallback pattern to extract commit hash from: {dd_version}")
            return hash_match.group(1)

        return None

    def _get_repository_for_service(self, service_name: str) -> Optional[str]:
        """Get the GitHub repository name for a service.

        Implements the fallback logic for "-jobs" services:
        1. Try sunbit-dev/{service-name}
        2. If 404 and name contains "jobs", try without "-jobs"

        Args:
            service_name: Name of the service

        Returns:
            Full repository name (org/repo) if found, None otherwise
        """
        # Primary: direct mapping
        if self.github_helper.check_repo_exists(DEFAULT_ORG, service_name):
            return f"{DEFAULT_ORG}/{service_name}"

        # Fallback: if service name contains "-jobs", try without it
        if "-jobs" in service_name:
            # Remove "-jobs" from the service name
            # e.g., "card-jobs-service" -> "card-service"
            alt_service_name = service_name.replace("-jobs", "")

            logger.debug(f"Primary repo not found, trying fallback: {DEFAULT_ORG}/{alt_service_name}")

            if self.github_helper.check_repo_exists(DEFAULT_ORG, alt_service_name):
                logger.info(f"Found fallback repository: {DEFAULT_ORG}/{alt_service_name}")
                return f"{DEFAULT_ORG}/{alt_service_name}"

        logger.warning(f"Repository not found for service: {service_name}")
        return None

    def _analyze_file_from_logger(
        self,
        owner: str,
        repo: str,
        logger_name: str,
        previous_commit: str,
        current_commit: str,
    ) -> Optional[FileAnalysis]:
        """Analyze a file based on its logger name.

        Maps the logger name to a file path, fetches both versions,
        generates a diff, and analyzes for potential issues.

        Args:
            owner: Repository owner
            repo: Repository name
            logger_name: Full qualified class name from logs
            previous_commit: Parent commit SHA
            current_commit: Deployed commit SHA

        Returns:
            FileAnalysis result, or None if logger name is invalid
        """
        # Map logger name to file paths
        file_paths = self._logger_name_to_file_paths(logger_name)
        if not file_paths:
            logger.warning(f"Could not map logger name to file path: {logger_name}")
            return None

        logger.info(f"Analyzing file for logger: {logger_name}")

        file_analysis = FileAnalysis(
            file_path=file_paths[0],  # Will be updated if we find the actual file
            previous_commit=previous_commit,
            current_commit=current_commit,
        )

        # Try to fetch the file (try .kt first, then .java)
        previous_content = None
        current_content = None
        actual_path = None

        for file_path in file_paths:
            try:
                # Fetch previous version
                previous_content = self.github_helper.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    ref=previous_commit,
                )

                # Fetch current version
                current_content = self.github_helper.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    ref=current_commit,
                )

                actual_path = file_path
                logger.debug(f"Found file at: {file_path}")
                break

            except GitHubNotFoundError:
                logger.debug(f"File not found at path: {file_path}")
                continue
            except GitHubError as e:
                logger.warning(f"Error fetching file {file_path}: {e}")
                continue

        if actual_path is None:
            file_analysis.error = f"File not found at any expected path: {file_paths}"
            logger.warning(file_analysis.error)
            return file_analysis

        file_analysis.file_path = actual_path
        file_analysis.previous_content = previous_content
        file_analysis.current_content = current_content

        # Generate diff
        if previous_content is not None and current_content is not None:
            diff = self._generate_diff(
                previous_content=previous_content,
                current_content=current_content,
                file_path=actual_path,
            )
            file_analysis.diff = diff

            # Check if there are any actual changes
            if previous_content == current_content:
                file_analysis.analysis_summary = "No changes in this file between versions"
                logger.debug(f"No changes in file: {actual_path}")
            else:
                # Analyze the diff for potential issues
                issues = self._analyze_diff(diff, current_content)
                file_analysis.potential_issues = issues
                file_analysis.analysis_summary = self._generate_analysis_summary(issues, diff)
                logger.info(f"Found {len(issues)} potential issues in {actual_path}")
        else:
            file_analysis.error = "Could not fetch file content for comparison"

        return file_analysis

    def _logger_name_to_file_paths(self, logger_name: str) -> List[str]:
        """Convert a logger name to potential file paths.

        Maps a fully qualified class name to file paths:
        - com.sunbit.card.invitation.lead.application.EntitledCustomerService
        - -> src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt
        - -> src/main/java/com/sunbit/card/invitation/lead/application/EntitledCustomerService.java

        Args:
            logger_name: Fully qualified class name

        Returns:
            List of possible file paths (Kotlin first, then Java)
        """
        if not logger_name:
            return []

        # Replace dots with path separators
        path_part = logger_name.replace(".", "/")

        # Return both Kotlin and Java paths
        return [
            f"src/main/kotlin/{path_part}.kt",
            f"src/main/java/{path_part}.java",
        ]

    def _generate_diff(
        self,
        previous_content: str,
        current_content: str,
        file_path: str,
    ) -> str:
        """Generate a unified diff between two versions.

        Args:
            previous_content: Content of previous version
            current_content: Content of current version
            file_path: Path to the file (for header)

        Returns:
            Unified diff string
        """
        previous_lines = previous_content.splitlines(keepends=True)
        current_lines = current_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            previous_lines,
            current_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )

        return "".join(diff)

    def _analyze_diff(self, diff: str, current_content: str) -> List[PotentialIssue]:
        """Analyze a diff for potential issues.

        Checks for:
        - Removed error handling (try/catch blocks)
        - Changed business logic
        - New exceptions introduced
        - Modified SQL/database queries
        - Changed external API calls
        - Modified timing/async behavior
        - Security concerns

        Args:
            diff: The unified diff string
            current_content: Current file content for context

        Returns:
            List of potential issues found
        """
        issues: List[PotentialIssue] = []

        if not diff:
            return issues

        diff_lines = diff.split("\n")

        # Track removed and added lines
        removed_lines = []
        added_lines = []
        current_line_num = 0

        for line in diff_lines:
            if line.startswith("@@"):
                # Parse line numbers from diff header
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line_num = int(match.group(1))
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append((current_line_num, line[1:]))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append((current_line_num, line[1:]))
                current_line_num += 1
            elif not line.startswith("-"):
                current_line_num += 1

        # Check for removed error handling
        issues.extend(self._check_error_handling_removed(removed_lines, added_lines))

        # Check for new exceptions
        issues.extend(self._check_new_exceptions(added_lines))

        # Check for SQL/database changes
        issues.extend(self._check_sql_changes(removed_lines, added_lines))

        # Check for external API changes
        issues.extend(self._check_api_changes(removed_lines, added_lines))

        # Check for timing/async changes
        issues.extend(self._check_timing_changes(removed_lines, added_lines))

        # Check for security concerns
        issues.extend(self._check_security_concerns(added_lines))

        # Check for business logic changes
        issues.extend(self._check_business_logic_changes(removed_lines, added_lines))

        return issues

    def _check_error_handling_removed(
        self,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for removed error handling patterns."""
        issues = []

        # Patterns indicating error handling
        error_patterns = [
            r"\btry\s*\{",
            r"\bcatch\s*\(",
            r"\.catch\s*\{",
            r"\.catch\s*\(",
            r"\bfinally\s*\{",
            r"\.onErrorReturn",
            r"\.onErrorResume",
            r"runCatching",
            r"\.getOrElse",
            r"\.getOrNull",
        ]

        removed_error_handling = []
        for line_num, line in removed_lines:
            for pattern in error_patterns:
                if re.search(pattern, line):
                    removed_error_handling.append((line_num, line.strip()))
                    break

        if removed_error_handling:
            snippet = "\n".join([f"-{line}" for _, line in removed_error_handling[:5]])
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_ERROR_HANDLING_REMOVED,
                description="Error handling code was removed or modified",
                severity="HIGH",
                line_numbers=[ln for ln, _ in removed_error_handling],
                code_snippet=snippet,
            ))

        return issues

    def _check_new_exceptions(
        self,
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for new exception throwing."""
        issues = []

        exception_patterns = [
            r"\bthrow\s+",
            r"\.orElseThrow\s*\{",
            r"error\s*\(",
            r"IllegalArgumentException",
            r"IllegalStateException",
            r"RuntimeException",
            r"NoSuchElementException",
        ]

        new_exceptions = []
        for line_num, line in added_lines:
            for pattern in exception_patterns:
                if re.search(pattern, line):
                    new_exceptions.append((line_num, line.strip()))
                    break

        if new_exceptions:
            snippet = "\n".join([f"+{line}" for _, line in new_exceptions[:5]])
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_NEW_EXCEPTION,
                description="New exception throwing code was added",
                severity="MEDIUM",
                line_numbers=[ln for ln, _ in new_exceptions],
                code_snippet=snippet,
            ))

        return issues

    def _check_sql_changes(
        self,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for SQL/database query changes."""
        issues = []

        sql_patterns = [
            r"\bSELECT\b",
            r"\bINSERT\b",
            r"\bUPDATE\b",
            r"\bDELETE\b",
            r"\bJOIN\b",
            r"\bWHERE\b",
            r"@Query\s*\(",
            r"\.query\s*\(",
            r"\.execute\s*\(",
            r"jdbcTemplate",
            r"entityManager",
            r"\.findBy",
            r"\.save\s*\(",
            r"\.delete\s*\(",
        ]

        sql_changes_found = False
        changed_lines = []

        all_lines = [(ln, f"-{line}", "removed") for ln, line in removed_lines]
        all_lines.extend([(ln, f"+{line}", "added") for ln, line in added_lines])

        for line_num, line, _ in all_lines:
            for pattern in sql_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    sql_changes_found = True
                    changed_lines.append((line_num, line.strip()))
                    break

        if sql_changes_found:
            snippet = "\n".join([line for _, line in changed_lines[:5]])
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_SQL_QUERY_MODIFIED,
                description="Database query or persistence code was modified",
                severity="MEDIUM",
                line_numbers=[ln for ln, _ in changed_lines],
                code_snippet=snippet,
            ))

        return issues

    def _check_api_changes(
        self,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for external API call changes."""
        issues = []

        api_patterns = [
            r"\.get\s*\(",
            r"\.post\s*\(",
            r"\.put\s*\(",
            r"\.delete\s*\(",
            r"\.exchange\s*\(",
            r"RestTemplate",
            r"WebClient",
            r"\.retrieve\s*\(",
            r"\.bodyTo",
            r"HttpClient",
            r"\.send\s*\(",
            r"FeignClient",
            r"\.call\s*\(",
        ]

        api_changes_found = False
        changed_lines = []

        all_lines = [(ln, f"-{line}", "removed") for ln, line in removed_lines]
        all_lines.extend([(ln, f"+{line}", "added") for ln, line in added_lines])

        for line_num, line, _ in all_lines:
            for pattern in api_patterns:
                if re.search(pattern, line):
                    api_changes_found = True
                    changed_lines.append((line_num, line.strip()))
                    break

        if api_changes_found:
            snippet = "\n".join([line for _, line in changed_lines[:5]])
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_EXTERNAL_API_CHANGED,
                description="External API call code was modified",
                severity="MEDIUM",
                line_numbers=[ln for ln, _ in changed_lines],
                code_snippet=snippet,
            ))

        return issues

    def _check_timing_changes(
        self,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for timing/async behavior changes."""
        issues = []

        timing_patterns = [
            r"\basync\b",
            r"\bawait\b",
            r"\.await\s*\(",
            r"runBlocking",
            r"launch\s*\{",
            r"async\s*\{",
            r"\.delay\s*\(",
            r"\.timeout\s*\(",
            r"CompletableFuture",
            r"\.thenApply",
            r"\.thenCompose",
            r"Mono\.",
            r"Flux\.",
            r"\.subscribe\s*\(",
            r"\.block\s*\(",
            r"@Async",
            r"@Scheduled",
            r"Thread\.",
            r"ExecutorService",
        ]

        timing_changes_found = False
        changed_lines = []

        all_lines = [(ln, f"-{line}", "removed") for ln, line in removed_lines]
        all_lines.extend([(ln, f"+{line}", "added") for ln, line in added_lines])

        for line_num, line, _ in all_lines:
            for pattern in timing_patterns:
                if re.search(pattern, line):
                    timing_changes_found = True
                    changed_lines.append((line_num, line.strip()))
                    break

        if timing_changes_found:
            snippet = "\n".join([line for _, line in changed_lines[:5]])
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_TIMING_ASYNC_MODIFIED,
                description="Asynchronous or timing-related code was modified",
                severity="HIGH",
                line_numbers=[ln for ln, _ in changed_lines],
                code_snippet=snippet,
            ))

        return issues

    def _check_security_concerns(
        self,
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for potential security concerns in added code."""
        issues = []

        security_patterns = [
            (r"password\s*=\s*[\"']", "Hardcoded password detected"),
            (r"secret\s*=\s*[\"']", "Hardcoded secret detected"),
            (r"api[_-]?key\s*=\s*[\"']", "Hardcoded API key detected"),
            (r"token\s*=\s*[\"']", "Hardcoded token detected"),
            (r"\$\{.*\}.*\+.*SQL", "Potential SQL injection"),
            (r"\.format\s*\(.*\).*[Ss][Qq][Ll]", "Potential SQL injection via string formatting"),
            (r"exec\s*\(", "Dynamic code execution"),
            (r"eval\s*\(", "Dynamic code evaluation"),
        ]

        security_issues = []
        for line_num, line in added_lines:
            for pattern, description in security_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    security_issues.append((line_num, line.strip(), description))
                    break

        if security_issues:
            for line_num, line, description in security_issues:
                issues.append(PotentialIssue(
                    issue_type=self.ISSUE_SECURITY_CONCERN,
                    description=description,
                    severity="HIGH",
                    line_numbers=[line_num],
                    code_snippet=f"+{line}",
                ))

        return issues

    def _check_business_logic_changes(
        self,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for significant business logic changes."""
        issues = []

        # Patterns that often indicate business logic
        logic_patterns = [
            r"\bif\s*\(",
            r"\belse\s*\{",
            r"\bwhen\s*\(",
            r"\bswitch\s*\(",
            r"\breturn\b",
            r"&&|\|\|",
            r"[<>=!]=",
            r"\.filter\s*\{",
            r"\.map\s*\{",
            r"\.let\s*\{",
            r"\.also\s*\{",
        ]

        removed_count = 0
        added_count = 0

        for _, line in removed_lines:
            for pattern in logic_patterns:
                if re.search(pattern, line):
                    removed_count += 1
                    break

        for _, line in added_lines:
            for pattern in logic_patterns:
                if re.search(pattern, line):
                    added_count += 1
                    break

        # If significant changes in logic patterns
        if removed_count >= 3 or added_count >= 3:
            issues.append(PotentialIssue(
                issue_type=self.ISSUE_BUSINESS_LOGIC_CHANGED,
                description=f"Significant business logic changes detected ({removed_count} logic statements removed, {added_count} added)",
                severity="MEDIUM",
                line_numbers=None,
                code_snippet=None,
            ))

        return issues

    def _generate_analysis_summary(
        self,
        issues: List[PotentialIssue],
        diff: str,
    ) -> str:
        """Generate a summary of the analysis.

        Args:
            issues: List of potential issues found
            diff: The diff string

        Returns:
            Summary string
        """
        if not issues:
            # Count changes from diff
            additions = len([l for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++")])
            deletions = len([l for l in diff.split("\n") if l.startswith("-") and not l.startswith("---")])
            return f"File changed ({additions} additions, {deletions} deletions) but no obvious issues detected"

        high_severity = sum(1 for i in issues if i.severity == "HIGH")
        medium_severity = sum(1 for i in issues if i.severity == "MEDIUM")
        low_severity = sum(1 for i in issues if i.severity == "LOW")

        parts = []
        if high_severity:
            parts.append(f"{high_severity} HIGH severity")
        if medium_severity:
            parts.append(f"{medium_severity} MEDIUM severity")
        if low_severity:
            parts.append(f"{low_severity} LOW severity")

        issue_types = set(i.issue_type for i in issues)
        type_descriptions = {
            self.ISSUE_ERROR_HANDLING_REMOVED: "error handling changes",
            self.ISSUE_NEW_EXCEPTION: "new exceptions",
            self.ISSUE_SQL_QUERY_MODIFIED: "database changes",
            self.ISSUE_EXTERNAL_API_CHANGED: "API call changes",
            self.ISSUE_TIMING_ASYNC_MODIFIED: "async/timing changes",
            self.ISSUE_SECURITY_CONCERN: "security concerns",
            self.ISSUE_BUSINESS_LOGIC_CHANGED: "business logic changes",
        }

        type_parts = [type_descriptions.get(t, t) for t in issue_types]

        return f"Found {len(issues)} potential issues ({', '.join(parts)}): {', '.join(type_parts)}"

    def analyze_files_directly(
        self,
        owner: str,
        repo: str,
        file_paths: List[str],
        previous_commit: str,
        current_commit: str,
    ) -> List[FileAnalysis]:
        """Analyze specific files directly (without logger name mapping).

        Useful when file paths are already known.

        Args:
            owner: Repository owner
            repo: Repository name
            file_paths: List of file paths to analyze
            previous_commit: Parent commit SHA
            current_commit: Deployed commit SHA

        Returns:
            List of FileAnalysis results
        """
        results = []

        for file_path in file_paths:
            file_analysis = FileAnalysis(
                file_path=file_path,
                previous_commit=previous_commit,
                current_commit=current_commit,
            )

            try:
                # Fetch previous version
                previous_content = self.github_helper.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    ref=previous_commit,
                )

                # Fetch current version
                current_content = self.github_helper.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    ref=current_commit,
                )

                file_analysis.previous_content = previous_content
                file_analysis.current_content = current_content

                # Generate diff
                if previous_content != current_content:
                    diff = self._generate_diff(previous_content, current_content, file_path)
                    file_analysis.diff = diff

                    # Analyze
                    issues = self._analyze_diff(diff, current_content)
                    file_analysis.potential_issues = issues
                    file_analysis.analysis_summary = self._generate_analysis_summary(issues, diff)
                else:
                    file_analysis.analysis_summary = "No changes in this file"

            except GitHubNotFoundError:
                file_analysis.error = f"File not found: {file_path}"
            except GitHubError as e:
                file_analysis.error = f"Error fetching file: {e}"

            results.append(file_analysis)

        return results

    # Pattern to extract file paths and line numbers from diff
    DIFF_HEADER_PATTERN = re.compile(r'^\+\+\+ b/(.+)$', re.MULTILINE)
    DIFF_HUNK_PATTERN = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', re.MULTILINE)

    def get_changed_line_numbers(self, diff: str) -> Dict[str, List[int]]:
        """Extract changed line numbers from a unified diff.

        Args:
            diff: Unified diff string

        Returns:
            Dict mapping file path to list of changed line numbers
        """
        result: Dict[str, List[int]] = {}
        current_file = None
        current_line = 0

        for line in diff.split('\n'):
            # Check for file header
            header_match = self.DIFF_HEADER_PATTERN.match(line)
            if header_match:
                current_file = header_match.group(1)
                if current_file not in result:
                    result[current_file] = []
                continue

            # Check for hunk header
            hunk_match = self.DIFF_HUNK_PATTERN.match(line)
            if hunk_match:
                current_line = int(hunk_match.group(2))
                continue

            if current_file is None:
                continue

            # Added lines
            if line.startswith('+') and not line.startswith('+++'):
                result[current_file].append(current_line)
                current_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                # Removed lines don't increment line number
                pass
            else:
                # Context line
                current_line += 1

        return result

    def check_line_in_changes(
        self,
        line_number: int,
        diff: str,
        file_path: Optional[str] = None,
        proximity: int = 5,
    ) -> Dict[str, Any]:
        """Check if a line number is in or near changed lines.

        Args:
            line_number: Line number to check
            diff: Unified diff string
            file_path: Optional file path to match (if diff has multiple files)
            proximity: Number of lines to consider "near"

        Returns:
            Dict with:
                - is_changed: True if line is directly changed
                - is_near_changes: True if line is within proximity of changes
                - nearby_lines: List of nearby changed line numbers
        """
        changed_lines = self.get_changed_line_numbers(diff)

        # Get lines for specific file or all files
        all_changed = []
        if file_path and file_path in changed_lines:
            all_changed = changed_lines[file_path]
        else:
            for lines in changed_lines.values():
                all_changed.extend(lines)

        is_changed = line_number in all_changed
        nearby_lines = [
            l for l in all_changed
            if abs(l - line_number) <= proximity and l != line_number
        ]
        is_near_changes = len(nearby_lines) > 0

        return {
            "is_changed": is_changed,
            "is_near_changes": is_near_changes,
            "nearby_lines": nearby_lines,
        }

    def _check_exception_specific_issues(
        self,
        exception_type: str,
        removed_lines: List[tuple],
        added_lines: List[tuple],
    ) -> List[PotentialIssue]:
        """Check for exception-type-specific issues in code changes.

        Args:
            exception_type: Short exception type (e.g., NullPointerException)
            removed_lines: List of (line_num, line_content) for removed lines
            added_lines: List of (line_num, line_content) for added lines

        Returns:
            List of PotentialIssue specific to the exception type
        """
        issues = []

        if exception_type == "NullPointerException":
            # Check for removed null checks
            null_check_patterns = [
                r'if\s*\([^)]*==\s*null',
                r'if\s*\([^)]*!=\s*null',
                r'\?\.',  # Safe call operator
                r'\?\:',  # Elvis operator
                r'\.orElse\(',
                r'\.orElseGet\(',
                r'requireNotNull',
                r'checkNotNull',
            ]

            for line_num, line in removed_lines:
                for pattern in null_check_patterns:
                    if re.search(pattern, line):
                        issues.append(PotentialIssue(
                            issue_type="null_check_removed",
                            description="Null check or safe navigation was removed",
                            severity="HIGH",
                            line_numbers=[line_num],
                            code_snippet=f"-{line}",
                        ))
                        break

        elif exception_type == "IllegalStateException":
            # Check for removed state checks
            state_check_patterns = [
                r'check\s*\(',
                r'require\s*\(',
                r'state\s*==',
                r'\.isReady',
                r'\.isValid',
            ]

            for line_num, line in removed_lines:
                for pattern in state_check_patterns:
                    if re.search(pattern, line):
                        issues.append(PotentialIssue(
                            issue_type="state_check_removed",
                            description="State validation was removed",
                            severity="HIGH",
                            line_numbers=[line_num],
                            code_snippet=f"-{line}",
                        ))
                        break

        elif exception_type == "IllegalArgumentException":
            # Check for removed argument validation
            validation_patterns = [
                r'require\s*\(',
                r'check\s*\(',
                r'if\s*\([^)]*\.isEmpty',
                r'if\s*\([^)]*\.isBlank',
                r'\.validate\(',
            ]

            for line_num, line in removed_lines:
                for pattern in validation_patterns:
                    if re.search(pattern, line):
                        issues.append(PotentialIssue(
                            issue_type="validation_removed",
                            description="Input validation was removed",
                            severity="HIGH",
                            line_numbers=[line_num],
                            code_snippet=f"-{line}",
                        ))
                        break

        return issues

    def analyze_commit(self, repo: str, commit_sha: str) -> dict:
        """Analyze a specific commit (legacy method).

        DEPRECATED: Use analyze_service() instead.

        Args:
            repo: Repository name (owner/repo)
            commit_sha: Commit SHA to analyze

        Returns:
            Analysis results as a dictionary (empty for backward compatibility)
        """
        logger.warning("analyze_commit() is deprecated, use analyze_service() instead")
        return {}
