"""
GitHub MCP Server for Production Issue Investigator.

Provides MCP tools that wrap the existing GitHub helper utilities.
Tools are designed to be used by the Deployment Analyzer and Code Reviewer subagents.

Tools:
- search_commits: Search commits in kubernetes or app repos
- get_file_content: Get file content at specific commit
- get_pr_files: Get changed files in a PR
- compare_commits: Get diff between two commits
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config import get_cached_config, ConfigurationError
from utils.github_helper import (
    GitHubHelper,
    GitHubError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    CommitInfo,
    FileChange,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Global instance - lazily initialized
_github_helper: Optional[GitHubHelper] = None

# Maximum commits to return
MAX_COMMITS_RETURNED = 50
# Maximum file content length before truncation
MAX_FILE_CONTENT_LENGTH = 50000


def get_github_helper() -> GitHubHelper:
    """Get or create the GitHub helper instance.

    Returns:
        Configured GitHubHelper instance

    Raises:
        ConfigurationError: If configuration is missing
    """
    global _github_helper
    if _github_helper is None:
        config = get_cached_config()
        _github_helper = GitHubHelper(token=config.github_token)
    return _github_helper


def _truncate_content(content: str, max_length: int = MAX_FILE_CONTENT_LENGTH) -> str:
    """Truncate content to the specified length.

    Args:
        content: Content to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated content with indicator if needed
    """
    if not content:
        return ""
    if len(content) <= max_length:
        return content
    return content[:max_length] + f"\n\n... (truncated, total: {len(content)} chars)"


def _format_commit_info(commit: CommitInfo) -> Dict[str, Any]:
    """Format a CommitInfo for MCP response.

    Args:
        commit: CommitInfo to format

    Returns:
        Dictionary with formatted commit fields
    """
    return {
        "sha": commit.sha,
        "message": commit.message,
        "author": commit.author,
        "date": commit.date,
        "url": commit.url,
    }


def _format_file_change(file_change: FileChange) -> Dict[str, Any]:
    """Format a FileChange for MCP response.

    Args:
        file_change: FileChange to format

    Returns:
        Dictionary with formatted file change fields
    """
    return {
        "filename": file_change.filename,
        "status": file_change.status,
        "additions": file_change.additions,
        "deletions": file_change.deletions,
        "patch": file_change.patch,
    }


def _create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a successful MCP tool response.

    Args:
        data: Response data to include

    Returns:
        MCP-compliant response dict
    """
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2),
            }
        ]
    }


def _create_error_response(error_message: str, error_type: str = "error") -> Dict[str, Any]:
    """Create an error MCP tool response.

    Args:
        error_message: Error message to include
        error_type: Type of error

    Returns:
        MCP-compliant error response dict
    """
    return {
        "is_error": True,
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "error": error_message,
                    "error_type": error_type,
                }),
            }
        ]
    }


async def search_commits_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search commits in kubernetes or app repos.

    MCP tool that wraps GitHubHelper.list_commits() with async support.

    Args:
        args: Dictionary with:
            - owner (str): Repository owner (e.g., "sunbit-dev")
            - repo (str): Repository name (e.g., "kubernetes")
            - since (str): Start time (ISO 8601 format)
            - until (str, optional): End time (ISO 8601 format)
            - author (str, optional): Filter by author

    Returns:
        MCP response with commit list or error
    """
    try:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        since_str = args.get("since", "")
        until_str = args.get("until")
        author = args.get("author")

        if not owner or not repo:
            return _create_error_response("owner and repo are required", "validation_error")

        if not since_str:
            return _create_error_response("since is required", "validation_error")

        logger.info(f"MCP search_commits: {owner}/{repo} since={since_str}")

        # Parse dates
        try:
            since_dt = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        except ValueError:
            return _create_error_response(f"Invalid since date format: {since_str}", "validation_error")

        until_dt = None
        if until_str:
            try:
                until_dt = datetime.fromisoformat(until_str.replace("Z", "+00:00"))
            except ValueError:
                return _create_error_response(f"Invalid until date format: {until_str}", "validation_error")

        # Call the sync API in a thread
        github_helper = get_github_helper()
        commits: List[CommitInfo] = await asyncio.to_thread(
            github_helper.list_commits,
            owner=owner,
            repo=repo,
            since=since_dt,
            until=until_dt,
            per_page=100,
        )

        # Filter by author if specified
        if author:
            commits = [c for c in commits if c.author == author]

        # Truncate to max
        commits_to_return = commits[:MAX_COMMITS_RETURNED]
        formatted_commits = [_format_commit_info(c) for c in commits_to_return]

        response_data = {
            "success": True,
            "owner": owner,
            "repo": repo,
            "total_commits": len(commits),
            "returned_commits": len(formatted_commits),
            "commits": formatted_commits,
        }

        logger.info(f"MCP search_commits: found {len(commits)} commits")
        return _create_success_response(response_data)

    except GitHubNotFoundError as e:
        logger.warning(f"MCP search_commits: Not found - {e}")
        return _create_error_response(f"Repository not found: {e}", "not_found_error")

    except GitHubAuthError as e:
        logger.error(f"MCP search_commits: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except GitHubRateLimitError as e:
        logger.warning(f"MCP search_commits: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except GitHubError as e:
        logger.error(f"MCP search_commits: GitHub error - {e}")
        return _create_error_response(f"GitHub error: {e}", "github_error")

    except Exception as e:
        logger.exception(f"MCP search_commits: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


async def get_file_content_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get file content at specific commit.

    MCP tool that wraps GitHubHelper.get_file_content() with async support.

    Args:
        args: Dictionary with:
            - owner (str): Repository owner
            - repo (str): Repository name
            - file_path (str): Path to the file in the repository
            - commit_sha (str): Commit SHA, branch, or tag

    Returns:
        MCP response with file content or error
    """
    try:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        file_path = args.get("file_path", "")
        commit_sha = args.get("commit_sha", "")

        if not owner or not repo or not file_path or not commit_sha:
            return _create_error_response(
                "owner, repo, file_path, and commit_sha are required",
                "validation_error"
            )

        logger.info(f"MCP get_file_content: {owner}/{repo}/{file_path}@{commit_sha[:8]}")

        # Call the sync API in a thread
        github_helper = get_github_helper()
        content: str = await asyncio.to_thread(
            github_helper.get_file_content,
            owner=owner,
            repo=repo,
            path=file_path,
            ref=commit_sha,
        )

        # Truncate content if too long
        truncated_content = _truncate_content(content)

        response_data = {
            "success": True,
            "owner": owner,
            "repo": repo,
            "file_path": file_path,
            "commit_sha": commit_sha,
            "content_length": len(content),
            "truncated": len(truncated_content) < len(content),
            "content": truncated_content,
        }

        logger.info(f"MCP get_file_content: retrieved {len(content)} bytes")
        return _create_success_response(response_data)

    except GitHubNotFoundError as e:
        logger.warning(f"MCP get_file_content: File not found - {e}")
        return _create_error_response(f"File not found: {file_path}", "not_found_error")

    except GitHubAuthError as e:
        logger.error(f"MCP get_file_content: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except GitHubRateLimitError as e:
        logger.warning(f"MCP get_file_content: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except GitHubError as e:
        logger.error(f"MCP get_file_content: GitHub error - {e}")
        return _create_error_response(f"GitHub error: {e}", "github_error")

    except Exception as e:
        logger.exception(f"MCP get_file_content: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


async def get_pr_files_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get changed files in a PR.

    MCP tool that wraps GitHubHelper.get_pr_files() with async support.

    Args:
        args: Dictionary with:
            - owner (str): Repository owner
            - repo (str): Repository name
            - pr_number (int): Pull request number

    Returns:
        MCP response with file changes or error
    """
    try:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        pr_number = args.get("pr_number")

        if not owner or not repo or pr_number is None:
            return _create_error_response(
                "owner, repo, and pr_number are required",
                "validation_error"
            )

        logger.info(f"MCP get_pr_files: {owner}/{repo}#{pr_number}")

        # Call the sync API in a thread
        github_helper = get_github_helper()
        files: List[FileChange] = await asyncio.to_thread(
            github_helper.get_pr_files,
            owner=owner,
            repo=repo,
            pr_number=int(pr_number),
        )

        formatted_files = [_format_file_change(f) for f in files]

        # Calculate summary stats
        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)

        response_data = {
            "success": True,
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "file_count": len(files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "files": formatted_files,
        }

        logger.info(f"MCP get_pr_files: found {len(files)} files")
        return _create_success_response(response_data)

    except GitHubNotFoundError as e:
        logger.warning(f"MCP get_pr_files: PR not found - {e}")
        return _create_error_response(f"PR not found: #{pr_number}", "not_found_error")

    except GitHubAuthError as e:
        logger.error(f"MCP get_pr_files: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except GitHubRateLimitError as e:
        logger.warning(f"MCP get_pr_files: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except GitHubError as e:
        logger.error(f"MCP get_pr_files: GitHub error - {e}")
        return _create_error_response(f"GitHub error: {e}", "github_error")

    except Exception as e:
        logger.exception(f"MCP get_pr_files: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


async def compare_commits_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get diff between two commits.

    MCP tool that wraps GitHubHelper.get_compare() with async support.

    Args:
        args: Dictionary with:
            - owner (str): Repository owner
            - repo (str): Repository name
            - base (str): Base commit SHA or branch
            - head (str): Head commit SHA or branch
            - file_path (str, optional): Filter to specific file

    Returns:
        MCP response with comparison info or error
    """
    try:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        base = args.get("base", "")
        head = args.get("head", "")
        file_path = args.get("file_path")

        if not owner or not repo or not base or not head:
            return _create_error_response(
                "owner, repo, base, and head are required",
                "validation_error"
            )

        logger.info(f"MCP compare_commits: {owner}/{repo} {base[:8]}..{head[:8]}")

        # Call the sync API in a thread
        github_helper = get_github_helper()
        comparison: Dict[str, Any] = await asyncio.to_thread(
            github_helper.get_compare,
            owner=owner,
            repo=repo,
            base=base,
            head=head,
        )

        # Extract files from comparison
        files = comparison.get("files", [])

        # Filter by file path if specified
        if file_path:
            files = [f for f in files if f.get("filename") == file_path]

        # Format files for response
        formatted_files = []
        for file_data in files:
            formatted_files.append({
                "filename": file_data.get("filename", ""),
                "status": file_data.get("status", ""),
                "additions": file_data.get("additions", 0),
                "deletions": file_data.get("deletions", 0),
                "patch": file_data.get("patch", ""),
            })

        response_data = {
            "success": True,
            "owner": owner,
            "repo": repo,
            "base": base,
            "head": head,
            "status": comparison.get("status", ""),
            "ahead_by": comparison.get("ahead_by", 0),
            "behind_by": comparison.get("behind_by", 0),
            "total_commits": comparison.get("total_commits", 0),
            "file_count": len(formatted_files),
            "files": formatted_files,
        }

        # If filtering by file path, include the filtered file's diff
        if file_path and formatted_files:
            response_data["file_diff"] = formatted_files[0].get("patch", "")

        logger.info(f"MCP compare_commits: found {len(formatted_files)} files changed")
        return _create_success_response(response_data)

    except GitHubNotFoundError as e:
        logger.warning(f"MCP compare_commits: Not found - {e}")
        return _create_error_response(f"Commit not found: {e}", "not_found_error")

    except GitHubAuthError as e:
        logger.error(f"MCP compare_commits: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except GitHubRateLimitError as e:
        logger.warning(f"MCP compare_commits: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except GitHubError as e:
        logger.error(f"MCP compare_commits: GitHub error - {e}")
        return _create_error_response(f"GitHub error: {e}", "github_error")

    except Exception as e:
        logger.exception(f"MCP compare_commits: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


# Reset function for testing
def reset_github_helper():
    """Reset the cached GitHub helper instance (for testing)."""
    global _github_helper
    _github_helper = None


def set_github_helper(helper: GitHubHelper):
    """Set the GitHub helper instance (for testing).

    Args:
        helper: GitHubHelper instance to use
    """
    global _github_helper
    _github_helper = helper
