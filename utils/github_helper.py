"""
GitHub helper for repository operations.

Provides a wrapper that can use GitHub CLI or PyGithub library.
This helper is used by the Deployment Checker and Code Checker sub-agents.

Primary method: GitHub CLI (gh)
Fallback: PyGithub library
"""
import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from utils.logger import get_logger
from utils.time_utils import datetime_to_iso8601, UTC_TZ

logger = get_logger(__name__)


class GitHubError(Exception):
    """Base exception for GitHub operations."""
    pass


class GitHubAuthError(GitHubError):
    """Raised when authentication fails."""
    pass


class GitHubNotFoundError(GitHubError):
    """Raised when repository or resource is not found (404)."""
    pass


class GitHubRateLimitError(GitHubError):
    """Raised when rate limit is exceeded."""
    pass


@dataclass
class CommitInfo:
    """Information about a Git commit.

    Attributes:
        sha: Full commit SHA
        message: Commit message (first line)
        author: Author name
        date: Commit date (ISO 8601 string)
        url: URL to the commit
    """
    sha: str
    message: str
    author: str
    date: str
    url: Optional[str] = None


@dataclass
class PullRequestInfo:
    """Information about a Pull Request.

    Attributes:
        number: PR number
        title: PR title
        state: PR state (open, closed, merged)
        url: URL to the PR
        merged_at: When PR was merged (if applicable)
        base_branch: Base branch name
        head_branch: Head branch name
    """
    number: int
    title: str
    state: str
    url: Optional[str] = None
    merged_at: Optional[str] = None
    base_branch: Optional[str] = None
    head_branch: Optional[str] = None


@dataclass
class FileChange:
    """Information about a file changed in a PR or commit.

    Attributes:
        filename: Path to the file
        status: Change status (added, modified, removed, renamed)
        additions: Number of lines added
        deletions: Number of lines deleted
        patch: Diff patch (if available)
    """
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    patch: Optional[str] = None


class GitHubHelper:
    """Helper class for GitHub operations.

    This class provides methods for interacting with GitHub repositories.
    It primarily uses the GitHub CLI (gh) for operations, with PyGithub
    as a fallback.

    The helper is designed to support the Deployment Checker and Code Checker
    sub-agents by providing:
    - Commit listing and searching
    - PR retrieval and file change listing
    - File content retrieval at specific commits
    """

    # Default organization for sunbit repositories
    DEFAULT_ORG = "sunbit-dev"

    # Kubernetes repository name
    KUBERNETES_REPO = "kubernetes"

    def __init__(
        self,
        token: str,
        mcp_tools: Optional[Dict[str, Callable]] = None,
    ):
        """Initialize the GitHub helper.

        Args:
            token: GitHub personal access token
            mcp_tools: Optional dictionary of MCP tool functions.
                      If provided, will attempt to use MCP first, then fall back to CLI.
        """
        self.token = token
        self.mcp_tools = mcp_tools or {}
        self._cli_available: Optional[bool] = None

        logger.debug("GitHubHelper initialized")

    @classmethod
    def from_config(cls, config) -> "GitHubHelper":
        """Create a GitHubHelper from a Config object.

        Args:
            config: Application configuration with github_token

        Returns:
            Configured GitHubHelper instance
        """
        return cls(token=config.github_token)

    def _redact_sensitive_env(self, cmd: List[str]) -> List[str]:
        """Redact sensitive information from command for logging.

        Args:
            cmd: Command list

        Returns:
            Command list with no changes (env vars not shown in cmd)
        """
        # The token is passed via environment variable, not in the command itself
        # So we don't need to redact the command. This method is for consistency.
        return cmd

    def _truncate_output(self, output: str, max_length: int = 1000) -> str:
        """Truncate output for logging.

        Args:
            output: Output string
            max_length: Maximum length before truncation

        Returns:
            Truncated string
        """
        if not output:
            return ""

        if len(output) > max_length:
            return output[:max_length] + f"... (truncated, total: {len(output)} chars)"

        return output

    def _log_cli_request(self, cmd: List[str], endpoint: str) -> None:
        """Log GitHub CLI request details.

        Args:
            cmd: Command list
            endpoint: API endpoint
        """
        # DEBUG: Full command (token is in env, not in cmd)
        logger.debug(f"[GH_CLI_REQ] command={' '.join(cmd)} endpoint={endpoint}")

        # INFO: Summary
        logger.info(f"[GH_CLI_REQ] endpoint={endpoint}")

    def _log_cli_response(self, result: subprocess.CompletedProcess, elapsed_ms: int) -> None:
        """Log GitHub CLI response details.

        Args:
            result: Completed process result
            elapsed_ms: Elapsed time in milliseconds
        """
        stdout_size = len(result.stdout) if result.stdout else 0
        stderr_size = len(result.stderr) if result.stderr else 0

        stdout_content = self._truncate_output(result.stdout)
        stderr_content = self._truncate_output(result.stderr)

        # DEBUG: Full output
        logger.debug(
            f"[GH_CLI_RESP] returncode={result.returncode} "
            f"stdout={stdout_content} stderr={stderr_content}"
        )

        # INFO: Summary
        logger.info(
            f"[GH_CLI_RESP] status={result.returncode} "
            f"timing={elapsed_ms}ms stdout_size={stdout_size}B stderr_size={stderr_size}B"
        )

    def _check_cli_available(self) -> bool:
        """Check if the GitHub CLI is available and authenticated.

        Returns:
            True if gh CLI is available and authenticated
        """
        if self._cli_available is not None:
            return self._cli_available

        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._cli_available = result.returncode == 0
            if self._cli_available:
                logger.debug("GitHub CLI is available and authenticated")
            else:
                logger.warning("GitHub CLI is not authenticated")
        except (subprocess.SubprocessError, FileNotFoundError):
            self._cli_available = False
            logger.warning("GitHub CLI is not available")

        return self._cli_available

    def _run_gh_api(
        self,
        endpoint: str,
        method: str = "GET",
        jq_filter: Optional[str] = None,
        data: Optional[Dict] = None,
    ) -> Any:
        """Run a gh api command.

        Args:
            endpoint: API endpoint (e.g., "repos/owner/repo/commits")
            method: HTTP method (GET, POST, etc.)
            jq_filter: Optional jq filter for response processing
            data: Optional data for POST/PATCH requests

        Returns:
            Parsed JSON response

        Raises:
            GitHubError: If the API call fails
        """
        cmd = ["gh", "api", endpoint, "-X", method]

        if jq_filter:
            cmd.extend(["--jq", jq_filter])

        if data:
            cmd.extend(["-f", json.dumps(data)])

        # Log CLI request
        self._log_cli_request(cmd, endpoint)

        # Set up environment with token (redacted in logs)
        env = os.environ.copy()
        if self.token:
            env["GITHUB_TOKEN"] = self.token

        import time
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )

            # Calculate elapsed time
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Log CLI response
            self._log_cli_response(result, elapsed_ms)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"gh api failed: {error_msg}")

                if "404" in error_msg or "Not Found" in error_msg:
                    raise GitHubNotFoundError(f"Resource not found: {endpoint}")
                if "401" in error_msg or "Unauthorized" in error_msg:
                    raise GitHubAuthError("GitHub authentication failed")
                if "403" in error_msg and "rate limit" in error_msg.lower():
                    raise GitHubRateLimitError("GitHub rate limit exceeded")

                raise GitHubError(f"GitHub API error: {error_msg}")

            # Parse JSON response
            if result.stdout.strip():
                return json.loads(result.stdout)
            return None

        except subprocess.TimeoutExpired:
            raise GitHubError("GitHub API request timed out")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh api response: {e}")
            # Return raw output if JSON parsing fails
            return result.stdout.strip() if result.stdout else None

    def list_commits(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 100,
        sha: Optional[str] = None,
    ) -> List[CommitInfo]:
        """List commits from a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            since: Only commits after this date (optional)
            until: Only commits before this date (optional)
            per_page: Number of commits per page (max 100)
            sha: SHA or branch to start listing commits from

        Returns:
            List of CommitInfo objects sorted by date (newest first)

        Raises:
            GitHubNotFoundError: If repository not found
            GitHubError: If API call fails
        """
        logger.info(f"Listing commits from {owner}/{repo}")

        # Build query parameters
        params = []
        if since:
            since_str = datetime_to_iso8601(since)
            params.append(f"since={since_str}")
        if until:
            until_str = datetime_to_iso8601(until)
            params.append(f"until={until_str}")
        if sha:
            params.append(f"sha={sha}")
        params.append(f"per_page={min(per_page, 100)}")

        endpoint = f"repos/{owner}/{repo}/commits"
        if params:
            endpoint += "?" + "&".join(params)

        logger.debug(f"Fetching commits with params: {params}")

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                logger.info("No commits found")
                return []

            commits = []
            for item in response:
                commit_data = item.get("commit", {})
                author_data = commit_data.get("author", {})

                commits.append(CommitInfo(
                    sha=item.get("sha", ""),
                    message=commit_data.get("message", "").split("\n")[0],  # First line only
                    author=author_data.get("name", ""),
                    date=author_data.get("date", ""),
                    url=item.get("html_url"),
                ))

            logger.info(f"Found {len(commits)} commits")
            return commits

        except GitHubNotFoundError:
            logger.warning(f"Repository not found: {owner}/{repo}")
            raise
        except Exception as e:
            logger.error(f"Failed to list commits: {e}")
            raise GitHubError(f"Failed to list commits: {e}")

    def get_commits_for_service(
        self,
        service_name: str,
        since: datetime,
        until: datetime,
    ) -> List[CommitInfo]:
        """Search kubernetes repo for commits related to a service.

        Searches the sunbit-dev/kubernetes repository for commits with
        {service-name} in the commit title.

        Args:
            service_name: Name of the service to search for
            since: Start of time window
            until: End of time window

        Returns:
            List of CommitInfo objects matching the service name, sorted by date

        Raises:
            GitHubError: If search fails
        """
        logger.info(f"Searching kubernetes commits for service: {service_name}")

        # Get all commits in the time window from kubernetes repo
        all_commits = self.list_commits(
            owner=self.DEFAULT_ORG,
            repo=self.KUBERNETES_REPO,
            since=since,
            until=until,
            per_page=100,
        )

        # Filter commits that contain the service name in the message
        matching_commits = []
        for commit in all_commits:
            if service_name in commit.message:
                matching_commits.append(commit)
                logger.debug(f"Found matching commit: {commit.sha[:8]} - {commit.message[:50]}")

        logger.info(f"Found {len(matching_commits)} commits for service {service_name}")
        return matching_commits

    def get_commit_prs(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
    ) -> List[PullRequestInfo]:
        """Get pull requests associated with a commit.

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Full or short commit SHA

        Returns:
            List of PullRequestInfo objects associated with the commit

        Raises:
            GitHubError: If API call fails
        """
        logger.info(f"Getting PRs for commit {commit_sha[:8]} in {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}/commits/{commit_sha}/pulls"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                logger.info(f"No PRs found for commit {commit_sha[:8]}")
                return []

            prs = []
            for item in response:
                prs.append(PullRequestInfo(
                    number=item.get("number", 0),
                    title=item.get("title", ""),
                    state=item.get("state", ""),
                    url=item.get("html_url"),
                    merged_at=item.get("merged_at"),
                    base_branch=item.get("base", {}).get("ref"),
                    head_branch=item.get("head", {}).get("ref"),
                ))

            logger.info(f"Found {len(prs)} PRs for commit {commit_sha[:8]}")
            return prs

        except Exception as e:
            logger.error(f"Failed to get PRs for commit: {e}")
            raise GitHubError(f"Failed to get PRs: {e}")

    def get_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> List[FileChange]:
        """Get list of files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of FileChange objects describing changed files

        Raises:
            GitHubError: If API call fails
        """
        logger.info(f"Getting files for PR #{pr_number} in {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/files"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                logger.info(f"No files found in PR #{pr_number}")
                return []

            files = []
            for item in response:
                files.append(FileChange(
                    filename=item.get("filename", ""),
                    status=item.get("status", ""),
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    patch=item.get("patch"),
                ))

            logger.info(f"Found {len(files)} files in PR #{pr_number}")
            return files

        except Exception as e:
            logger.error(f"Failed to get PR files: {e}")
            raise GitHubError(f"Failed to get PR files: {e}")

    def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str:
        """Get file content at a specific commit.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to the file in the repository
            ref: Commit SHA, branch, or tag

        Returns:
            File content as a string

        Raises:
            GitHubNotFoundError: If file not found at the specified ref
            GitHubError: If API call fails
        """
        logger.info(f"Getting file content: {owner}/{repo}/{path}@{ref[:8]}")

        endpoint = f"repos/{owner}/{repo}/contents/{path}?ref={ref}"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                raise GitHubNotFoundError(f"File not found: {path}")

            # File content is base64 encoded
            content_b64 = response.get("content", "")
            if content_b64:
                # Remove newlines from base64 content
                content_b64 = content_b64.replace("\n", "")
                content = base64.b64decode(content_b64).decode("utf-8")
                logger.debug(f"Retrieved file content: {len(content)} bytes")
                return content

            raise GitHubNotFoundError(f"File content is empty: {path}")

        except GitHubNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            raise GitHubError(f"Failed to get file content: {e}")

    def get_commit(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
    ) -> CommitInfo:
        """Get details for a specific commit.

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Full or short commit SHA

        Returns:
            CommitInfo object with commit details

        Raises:
            GitHubNotFoundError: If commit not found
            GitHubError: If API call fails
        """
        logger.info(f"Getting commit {commit_sha[:8]} from {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}/commits/{commit_sha}"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                raise GitHubNotFoundError(f"Commit not found: {commit_sha}")

            commit_data = response.get("commit", {})
            author_data = commit_data.get("author", {})

            return CommitInfo(
                sha=response.get("sha", ""),
                message=commit_data.get("message", "").split("\n")[0],
                author=author_data.get("name", ""),
                date=author_data.get("date", ""),
                url=response.get("html_url"),
            )

        except GitHubNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get commit: {e}")
            raise GitHubError(f"Failed to get commit: {e}")

    def get_parent_commit(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
    ) -> Optional[str]:
        """Get the parent commit SHA for a given commit.

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Full or short commit SHA

        Returns:
            Parent commit SHA, or None if no parent (root commit)

        Raises:
            GitHubError: If API call fails
        """
        logger.info(f"Getting parent of commit {commit_sha[:8]} from {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}/commits/{commit_sha}"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                raise GitHubNotFoundError(f"Commit not found: {commit_sha}")

            parents = response.get("parents", [])
            if parents:
                parent_sha = parents[0].get("sha", "")
                logger.debug(f"Parent commit: {parent_sha[:8]}")
                return parent_sha

            logger.debug("No parent commit (root commit)")
            return None

        except Exception as e:
            logger.error(f"Failed to get parent commit: {e}")
            raise GitHubError(f"Failed to get parent commit: {e}")

    def check_repo_exists(
        self,
        owner: str,
        repo: str,
    ) -> bool:
        """Check if a repository exists and is accessible.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if repository exists and is accessible, False otherwise
        """
        logger.debug(f"Checking if repo exists: {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}"

        try:
            response = self._run_gh_api(endpoint)
            exists = response is not None
            logger.debug(f"Repo {owner}/{repo} exists: {exists}")
            return exists
        except GitHubNotFoundError:
            logger.debug(f"Repo not found: {owner}/{repo}")
            return False
        except GitHubError as e:
            logger.warning(f"Error checking repo: {e}")
            return False

    def get_compare(
        self,
        owner: str,
        repo: str,
        base: str,
        head: str,
    ) -> Dict[str, Any]:
        """Compare two commits and get the diff.

        Args:
            owner: Repository owner
            repo: Repository name
            base: Base commit SHA or branch
            head: Head commit SHA or branch

        Returns:
            Dictionary with comparison information including files changed

        Raises:
            GitHubError: If API call fails
        """
        logger.info(f"Comparing {base[:8]}..{head[:8]} in {owner}/{repo}")

        endpoint = f"repos/{owner}/{repo}/compare/{base}...{head}"

        try:
            response = self._run_gh_api(endpoint)

            if not response:
                raise GitHubError("Empty response from compare API")

            return response

        except Exception as e:
            logger.error(f"Failed to compare commits: {e}")
            raise GitHubError(f"Failed to compare commits: {e}")

    def parse_deployment_commit_title(self, title: str) -> Optional[Dict[str, str]]:
        """Parse a kubernetes deployment commit title.

        Deployment commits follow the pattern:
        {service-name}-{commit_hash}___{build_number}

        Args:
            title: Commit message/title to parse

        Returns:
            Dictionary with parsed components:
            - service_name: The service name
            - commit_hash: The application commit hash
            - build_number: The build number
            - dd_version: The dd.version value ({commit_hash}___{build_number})
            Returns None if title doesn't match the pattern
        """
        # Pattern: service-name-commithash___buildnumber
        # The commit hash is 40 characters hex
        # The build number is numeric
        pattern = r"^(.+)-([a-f0-9]{40})___(\d+)$"
        match = re.match(pattern, title.strip())

        if match:
            service_name = match.group(1)
            commit_hash = match.group(2)
            build_number = match.group(3)

            return {
                "service_name": service_name,
                "commit_hash": commit_hash,
                "build_number": build_number,
                "dd_version": f"{commit_hash}___{build_number}",
            }

        return None

    def get_recent_commits(
        self,
        repo_name: str,
        since: str,
        branch: str = "main",
    ) -> List[CommitInfo]:
        """Get recent commits from a repository.

        This is a convenience method that wraps list_commits for
        backward compatibility and simpler usage.

        Args:
            repo_name: Repository name in format "owner/repo"
            since: ISO 8601 formatted date string
            branch: Branch name (default: main)

        Returns:
            List of CommitInfo objects
        """
        parts = repo_name.split("/")
        if len(parts) != 2:
            logger.error(f"Invalid repo_name format: {repo_name}")
            return []

        owner, repo = parts

        try:
            from dateutil.parser import parse as parse_date
            since_dt = parse_date(since)
        except Exception as e:
            logger.error(f"Failed to parse since date: {e}")
            return []

        return self.list_commits(
            owner=owner,
            repo=repo,
            since=since_dt,
            sha=branch,
        )
