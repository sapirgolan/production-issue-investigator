"""
Deployment Checker sub-agent for checking recent deployments.

This sub-agent is responsible for:
- Searching the sunbit-dev/kubernetes repository for deployment commits
- Correlating deployments with services found in DataDog logs
- Extracting application commit hashes from kubernetes commit titles
- Retrieving PR information and changed files
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Set

from utils.config import Config
from utils.logger import get_logger
from utils.time_utils import (
    parse_relative_time,
    get_deployment_window_start,
    UTC_TZ,
)
from utils.github_helper import (
    GitHubHelper,
    GitHubError,
    GitHubNotFoundError,
    CommitInfo,
    PullRequestInfo,
    FileChange,
)

logger = get_logger(__name__)


# Constants
DEPLOYMENT_WINDOW_HOURS = 72  # Search 72 hours before log search time
DEFAULT_ORG = "sunbit-dev"
KUBERNETES_REPO = "kubernetes"


@dataclass
class DeploymentInfo:
    """Information about a deployment.

    Attributes:
        service_name: Name of the service deployed
        deployment_timestamp: When the deployment was made
        kubernetes_commit_sha: Commit SHA in the kubernetes repo
        application_commit_hash: Commit hash in the application repo (from dd.version)
        build_number: Build number from the deployment
        dd_version: The full dd.version value ({commit_hash}___{build_number})
        pr_number: Associated PR number (if found)
        changed_files: List of files changed in the deployment PR
        kubernetes_commit_url: URL to the kubernetes commit
    """
    service_name: str
    deployment_timestamp: str
    kubernetes_commit_sha: str
    application_commit_hash: str
    build_number: str
    dd_version: str
    pr_number: Optional[int] = None
    changed_files: List[FileChange] = field(default_factory=list)
    kubernetes_commit_url: Optional[str] = None


@dataclass
class DeploymentCheckResult:
    """Result from deployment check for a service.

    Attributes:
        service_name: Name of the service checked
        deployments: List of deployments found
        search_window_start: Start of search window (ISO 8601)
        search_window_end: End of search window (ISO 8601)
        error: Error message if check failed
        status: Result status (success, no_deployments, error)
    """
    service_name: str
    deployments: List[DeploymentInfo] = field(default_factory=list)
    search_window_start: Optional[str] = None
    search_window_end: Optional[str] = None
    error: Optional[str] = None
    status: str = "success"


class DeploymentChecker:
    """Sub-agent for checking deployment history.

    This is a non-interactive sub-agent that checks the kubernetes
    repository for recent deployments of specified services.

    The sub-agent:
    - Cannot interact with users directly
    - Logs all actions (inputs, outputs, tasks performed)
    - Retries once on failure with same parameters
    - Returns partial results if retry fails
    """

    def __init__(self, github_token: str):
        """Initialize the deployment checker.

        Args:
            github_token: GitHub API token
        """
        self.github_token = github_token
        self.github_helper = GitHubHelper(token=github_token)

        logger.info("DeploymentChecker initialized")

    @classmethod
    def from_config(cls, config: Config) -> "DeploymentChecker":
        """Create a DeploymentChecker from a Config object.

        Args:
            config: Application configuration

        Returns:
            Configured DeploymentChecker instance
        """
        return cls(github_token=config.github_token)

    def check_service_deployments(
        self,
        service_name: str,
        log_search_timestamp: str,
        dd_version: Optional[str] = None,
    ) -> DeploymentCheckResult:
        """Check for deployments of a specific service.

        Searches the kubernetes repository for commits related to the
        service within 72 hours before the log search timestamp.

        Args:
            service_name: Name of the service to check
            log_search_timestamp: The 'from' time used for log search
                                 (relative like "now-4h" or ISO 8601)
            dd_version: Optional dd.version from logs for correlation

        Returns:
            DeploymentCheckResult with found deployments
        """
        logger.info(f"Checking deployments for service: {service_name}")

        result = DeploymentCheckResult(service_name=service_name)

        try:
            # Calculate the deployment search window
            # 72 hours BEFORE the log search timestamp
            log_search_from = parse_relative_time(log_search_timestamp)
            deployment_window_start = get_deployment_window_start(log_search_timestamp)
            deployment_window_end = log_search_from

            result.search_window_start = deployment_window_start.isoformat()
            result.search_window_end = deployment_window_end.isoformat()

            logger.info(
                f"Deployment search window: {result.search_window_start} to {result.search_window_end}"
            )

            # Get commits for the service from kubernetes repo
            commits = self._get_service_commits(
                service_name=service_name,
                since=deployment_window_start,
                until=deployment_window_end,
            )

            if not commits:
                logger.info(f"No deployment commits found for {service_name}")
                result.status = "no_deployments"
                return result

            # Process each commit to extract deployment info
            for commit in commits:
                deployment = self._process_deployment_commit(
                    commit=commit,
                    service_name=service_name,
                )
                if deployment:
                    result.deployments.append(deployment)

            logger.info(f"Found {len(result.deployments)} deployments for {service_name}")

            # If dd_version provided, check for correlation
            if dd_version and result.deployments:
                self._correlate_with_dd_version(result.deployments, dd_version)

            return result

        except GitHubError as e:
            logger.error(f"GitHub error checking deployments for {service_name}: {e}")
            result.error = str(e)
            result.status = "error"
            return result
        except Exception as e:
            logger.error(f"Unexpected error checking deployments for {service_name}: {e}")
            result.error = str(e)
            result.status = "error"
            return result

    def _get_service_commits(
        self,
        service_name: str,
        since: datetime,
        until: datetime,
    ) -> List[CommitInfo]:
        """Get commits for a service from the kubernetes repository.

        Args:
            service_name: Name of the service
            since: Start of search window
            until: End of search window

        Returns:
            List of commits containing the service name
        """
        logger.debug(f"Fetching kubernetes commits for {service_name}")

        try:
            commits = self.github_helper.get_commits_for_service(
                service_name=service_name,
                since=since,
                until=until,
            )
            return commits
        except GitHubNotFoundError:
            logger.warning(f"Kubernetes repository not found: {DEFAULT_ORG}/{KUBERNETES_REPO}")
            return []

    def _process_deployment_commit(
        self,
        commit: CommitInfo,
        service_name: str,
    ) -> Optional[DeploymentInfo]:
        """Process a deployment commit and extract deployment info.

        Args:
            commit: The commit to process
            service_name: Expected service name

        Returns:
            DeploymentInfo if commit is a valid deployment, None otherwise
        """
        logger.debug(f"Processing commit: {commit.sha[:8]} - {commit.message[:50]}")

        # Parse the commit title to extract deployment info
        parsed = self.github_helper.parse_deployment_commit_title(commit.message)

        if not parsed:
            logger.debug(f"Commit title doesn't match deployment pattern: {commit.message}")
            return None

        # Verify the service name matches
        if parsed["service_name"] != service_name:
            logger.debug(
                f"Service name mismatch: expected {service_name}, "
                f"got {parsed['service_name']}"
            )
            return None

        # Create deployment info
        deployment = DeploymentInfo(
            service_name=service_name,
            deployment_timestamp=commit.date,
            kubernetes_commit_sha=commit.sha,
            application_commit_hash=parsed["commit_hash"],
            build_number=parsed["build_number"],
            dd_version=parsed["dd_version"],
            kubernetes_commit_url=commit.url,
        )

        # Try to get PR info and changed files
        try:
            prs = self.github_helper.get_commit_prs(
                owner=DEFAULT_ORG,
                repo=KUBERNETES_REPO,
                commit_sha=commit.sha,
            )

            if prs:
                pr = prs[0]  # Take the first PR
                deployment.pr_number = pr.number

                # Get files changed in the PR
                files = self.github_helper.get_pr_files(
                    owner=DEFAULT_ORG,
                    repo=KUBERNETES_REPO,
                    pr_number=pr.number,
                )
                deployment.changed_files = files

                logger.debug(f"Found PR #{pr.number} with {len(files)} changed files")

        except GitHubError as e:
            logger.warning(f"Failed to get PR info for commit {commit.sha[:8]}: {e}")
            # Continue without PR info - partial result is OK

        return deployment

    def _correlate_with_dd_version(
        self,
        deployments: List[DeploymentInfo],
        dd_version: str,
    ) -> None:
        """Correlate deployments with a dd.version value.

        Logs which deployment matches the dd.version from logs.

        Args:
            deployments: List of deployments to check
            dd_version: The dd.version value from DataDog logs
        """
        for deployment in deployments:
            if deployment.dd_version == dd_version:
                logger.info(
                    f"Found deployment matching dd.version {dd_version}: "
                    f"commit {deployment.application_commit_hash[:8]}"
                )

    def check_multiple_services(
        self,
        service_names: List[str],
        log_search_timestamp: str,
        dd_versions: Optional[Set[str]] = None,
    ) -> List[DeploymentCheckResult]:
        """Check deployments for multiple services.

        This method checks each service sequentially. For parallel
        execution, use asyncio.gather in the calling code.

        Args:
            service_names: List of service names to check
            log_search_timestamp: The 'from' time used for log search
            dd_versions: Optional set of dd.version values for correlation

        Returns:
            List of DeploymentCheckResult, one for each service
        """
        logger.info(f"Checking deployments for {len(service_names)} services")

        results = []
        for service_name in service_names:
            # Find matching dd_version for this service (if available)
            matching_version = None
            if dd_versions:
                for version in dd_versions:
                    # Try to parse and match service name
                    parsed = self.github_helper.parse_deployment_commit_title(
                        f"{service_name}-{version}"
                    )
                    if parsed and parsed["service_name"] == service_name:
                        matching_version = version
                        break

            result = self.check_service_deployments(
                service_name=service_name,
                log_search_timestamp=log_search_timestamp,
                dd_version=matching_version,
            )
            results.append(result)

        return results

    def check_recent_deployments(
        self,
        repo: str,
        time_window: str,
    ) -> List[DeploymentInfo]:
        """Legacy method for backward compatibility.

        DEPRECATED: Use check_service_deployments() instead.

        Args:
            repo: Repository name (owner/repo) - ignored, always uses kubernetes
            time_window: Time window string (e.g., "72h")

        Returns:
            List of deployment info (empty - use new method)
        """
        logger.warning(
            "check_recent_deployments() is deprecated, "
            "use check_service_deployments() instead"
        )
        return []

    def get_deployment_by_dd_version(
        self,
        service_name: str,
        dd_version: str,
        log_search_timestamp: str,
    ) -> Optional[DeploymentInfo]:
        """Find a specific deployment by its dd.version.

        Args:
            service_name: Name of the service
            dd_version: The exact dd.version to find
            log_search_timestamp: The 'from' time for the search window

        Returns:
            DeploymentInfo if found, None otherwise
        """
        logger.info(f"Looking for deployment with dd.version: {dd_version}")

        result = self.check_service_deployments(
            service_name=service_name,
            log_search_timestamp=log_search_timestamp,
            dd_version=dd_version,
        )

        for deployment in result.deployments:
            if deployment.dd_version == dd_version:
                return deployment

        return None

    def get_repository_for_service(
        self,
        service_name: str,
    ) -> Optional[str]:
        """Get the GitHub repository name for a service.

        Implements the fallback logic for "-jobs" services:
        1. Try sunbit-dev/{service-name}
        2. If 404 and name contains "jobs", try without "-jobs"

        Args:
            service_name: Name of the service

        Returns:
            Repository name if found (e.g., "sunbit-dev/card-service"), None if not found
        """
        # Primary: direct mapping
        primary_repo = f"{DEFAULT_ORG}/{service_name}"

        if self.github_helper.check_repo_exists(DEFAULT_ORG, service_name):
            logger.debug(f"Found repository: {primary_repo}")
            return primary_repo

        # Fallback: if service name contains "jobs", try without it
        if "-jobs" in service_name:
            # Remove "-jobs" from the service name
            # e.g., "card-jobs-service" -> "card-service"
            alt_service_name = service_name.replace("-jobs", "")
            alt_repo = f"{DEFAULT_ORG}/{alt_service_name}"

            logger.debug(f"Primary repo not found, trying fallback: {alt_repo}")

            if self.github_helper.check_repo_exists(DEFAULT_ORG, alt_service_name):
                logger.info(f"Found fallback repository: {alt_repo}")
                return alt_repo

        logger.warning(f"Repository not found for service: {service_name}")
        return None
