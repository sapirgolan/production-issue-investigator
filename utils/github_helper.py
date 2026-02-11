"""
GitHub helper utilities for interacting with repositories.
"""
from github import Github


class GitHubHelper:
    """Helper class for GitHub operations."""

    def __init__(self, token: str):
        """Initialize the GitHub helper.

        Args:
            token: GitHub personal access token
        """
        self.client = Github(token) if token else None

    def get_recent_commits(self, repo_name: str, since: str, branch: str = "main") -> list:
        """Get recent commits from a repository.

        Args:
            repo_name: Repository name in format "owner/repo"
            since: ISO 8601 formatted date string
            branch: Branch name (default: main)

        Returns:
            List of recent commits
        """
        if not self.client:
            return []

        # TODO: Implement commit retrieval
        return []
