"""
TDD Tests for MCP Tools.

Tests cover the MCP tool wrappers that will be implemented in Phase 2:
- DataDog tools: search_logs, get_logs_by_efilogid, parse_stack_trace
- GitHub tools: search_commits, get_file_content, get_pr_files, compare_commits

These tests are written BEFORE the implementation (TDD red phase).
They validate:
- Tool function signatures and return formats
- Error handling (is_error: true format)
- asyncio.to_thread() usage for sync utility calls
- Proper integration with utility classes
"""
import asyncio
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Import utility classes for mocking
from utils.datadog_api import (
    DataDogAPI,
    DataDogAPIError,
    DataDogAuthError,
    DataDogRateLimitError,
    DataDogTimeoutError,
    LogEntry,
    SearchResult,
)
from utils.github_helper import (
    CommitInfo,
    FileChange,
    GitHubError,
    GitHubHelper,
    GitHubNotFoundError,
    GitHubAuthError,
    GitHubRateLimitError,
    PullRequestInfo,
)
from utils.stack_trace_parser import ParsedStackTrace, StackFrame, StackTraceParser

# MCP tools will be in these modules once implemented
# These imports will fail initially (TDD red phase)
# Split imports to allow partial testing

# DataDog tools
try:
    from mcp_servers.datadog_server import (
        search_logs_tool,
        get_logs_by_efilogid_tool,
        parse_stack_trace_tool,
        set_datadog_api,
        set_stack_parser,
        reset_datadog_api,
        reset_stack_parser,
    )
    DATADOG_TOOLS_AVAILABLE = True
except ImportError:
    DATADOG_TOOLS_AVAILABLE = False

# GitHub tools
try:
    from mcp_servers.github_server import (
        search_commits_tool,
        get_file_content_tool,
        get_pr_files_tool,
        compare_commits_tool,
        set_github_helper,
        reset_github_helper,
    )
    GITHUB_TOOLS_AVAILABLE = True
except ImportError:
    GITHUB_TOOLS_AVAILABLE = False

MCP_TOOLS_AVAILABLE = DATADOG_TOOLS_AVAILABLE and GITHUB_TOOLS_AVAILABLE


def skip_if_no_datadog_tools(test_func):
    """Decorator to skip tests if DataDog MCP tools are not yet implemented."""
    def wrapper(*args, **kwargs):
        if not DATADOG_TOOLS_AVAILABLE:
            raise unittest.SkipTest("DataDog MCP tools not yet implemented")
        return test_func(*args, **kwargs)
    return wrapper


def skip_if_no_github_tools(test_func):
    """Decorator to skip tests if GitHub MCP tools are not yet implemented."""
    def wrapper(*args, **kwargs):
        if not GITHUB_TOOLS_AVAILABLE:
            raise unittest.SkipTest("GitHub MCP tools not yet implemented")
        return test_func(*args, **kwargs)
    return wrapper


def skip_if_no_mcp_tools(test_func):
    """Decorator to skip tests if MCP tools are not yet implemented."""
    def wrapper(*args, **kwargs):
        if not MCP_TOOLS_AVAILABLE:
            raise unittest.SkipTest("MCP tools not yet implemented (TDD red phase)")
        return test_func(*args, **kwargs)
    return wrapper


class TestSearchLogsToolSuccess(unittest.TestCase):
    """Tests for search_logs MCP tool - success scenarios."""

    def setUp(self):
        """Reset DataDog API before each test."""
        if DATADOG_TOOLS_AVAILABLE:
            reset_datadog_api()

    @skip_if_no_datadog_tools
    def test_search_logs_returns_valid_json(self):
        """Test that search_logs returns valid JSON with success flag."""
        async def run_test():
            # Create mock DataDog API
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[
                    LogEntry(
                        id="log-1",
                        message="Test error message",
                        service="card-service",
                        efilogid="session-123",
                        dd_version="abc123___100",
                        logger_name="com.sunbit.card.Handler",
                        timestamp="2024-01-15T10:00:00Z",
                        status="error",
                    )
                ],
                total_count=1,
                unique_services={"card-service"},
                unique_efilogids={"session-123"},
            )
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod NullPointerException",
                "from_time": "now-4h",
                "to_time": "now",
                "limit": 50,
            })

            # Validate MCP tool response format
            self.assertIn("content", result)
            self.assertIsInstance(result["content"], list)
            self.assertEqual(len(result["content"]), 1)
            self.assertEqual(result["content"][0]["type"], "text")

            # Parse JSON response
            response_data = json.loads(result["content"][0]["text"])
            self.assertTrue(response_data["success"])
            self.assertEqual(response_data["total_logs"], 1)
            self.assertEqual(len(response_data["logs"]), 1)
            self.assertEqual(response_data["logs"][0]["service"], "card-service")

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_truncates_long_messages(self):
        """Test that log messages over 200 chars are truncated."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            long_message = "A" * 500  # 500 character message
            mock_api.search_logs.return_value = SearchResult(
                logs=[
                    LogEntry(
                        id="log-1",
                        message=long_message,
                        service="card-service",
                    )
                ],
                total_count=1,
                unique_services={"card-service"},
                unique_efilogids=set(),
            )
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
            })

            response_data = json.loads(result["content"][0]["text"])
            message = response_data["logs"][0]["message"]

            # Should be truncated to 200 chars + "..."
            self.assertLessEqual(len(message), 203)  # 200 + "..."
            self.assertTrue(message.endswith("..."))

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_limits_results_to_50(self):
        """Test that search_logs limits returned logs to 50."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            # Create 100 logs
            logs = [
                LogEntry(
                    id=f"log-{i}",
                    message=f"Error {i}",
                    service="card-service",
                )
                for i in range(100)
            ]
            mock_api.search_logs.return_value = SearchResult(
                logs=logs,
                total_count=100,
                unique_services={"card-service"},
                unique_efilogids=set(),
            )
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
                "limit": 100,
            })

            response_data = json.loads(result["content"][0]["text"])

            # Should return max 50 logs
            self.assertEqual(response_data["total_logs"], 100)
            self.assertLessEqual(response_data["returned_logs"], 50)
            self.assertLessEqual(len(response_data["logs"]), 50)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_uses_asyncio_to_thread(self):
        """Test that search_logs wraps sync call with asyncio.to_thread."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[],
                total_count=0,
                unique_services=set(),
                unique_efilogids=set(),
            )
            set_datadog_api(mock_api)

            with patch('mcp_servers.datadog_server.asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_api.search_logs.return_value

                await search_logs_tool({
                    "query": "env:prod",
                    "from_time": "now-4h",
                    "to_time": "now",
                })

                # Verify asyncio.to_thread was called
                mock_to_thread.assert_called_once()

        asyncio.run(run_test())


class TestSearchLogsToolErrors(unittest.TestCase):
    """Tests for search_logs MCP tool - error handling."""

    def setUp(self):
        """Reset DataDog API before each test."""
        if DATADOG_TOOLS_AVAILABLE:
            reset_datadog_api()

    @skip_if_no_datadog_tools
    def test_search_logs_rate_limit_error_returns_is_error(self):
        """Test that rate limit error returns is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.side_effect = DataDogRateLimitError("Rate limit exceeded")
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("content", result)
            self.assertIn("Rate limit", result["content"][0]["text"])

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_auth_error_returns_is_error(self):
        """Test that auth error returns is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.side_effect = DataDogAuthError("Invalid API key")
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("content", result)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_timeout_error_returns_is_error(self):
        """Test that timeout error returns is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.side_effect = DataDogTimeoutError("Connection timed out")
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("content", result)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_search_logs_generic_exception_returns_is_error(self):
        """Test that generic exception returns is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.side_effect = Exception("Unexpected error")
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "env:prod",
                "from_time": "now-4h",
                "to_time": "now",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("content", result)
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestGetLogsByEfilogidTool(unittest.TestCase):
    """Tests for get_logs_by_efilogid MCP tool."""

    def setUp(self):
        """Reset DataDog API before each test."""
        if DATADOG_TOOLS_AVAILABLE:
            reset_datadog_api()

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_escapes_quotes(self):
        """Test that efilogid is properly quoted in query."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[],
                total_count=0,
                unique_services=set(),
                unique_efilogids=set(),
            )
            mock_api.build_efilogid_query.return_value = '@efilogid:"-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl"'
            set_datadog_api(mock_api)

            await get_logs_by_efilogid_tool({
                "efilogid": "-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl",
            })

            # Verify build_efilogid_query was called
            mock_api.build_efilogid_query.assert_called_once_with(
                "-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl"
            )

            # Verify query was called with quoted efilogid
            call_args = mock_api.search_logs.call_args
            query = call_args.kwargs.get("query", "")

            # Query should contain quoted efilogid: @efilogid:"-1-NGFm..."
            self.assertIn('@efilogid:"', query)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_uses_default_time_window(self):
        """Test that default time window is now-24h."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[],
                total_count=0,
                unique_services=set(),
                unique_efilogids=set(),
            )
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            set_datadog_api(mock_api)

            await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            call_args = mock_api.search_logs.call_args
            from_time = call_args.kwargs.get("from_time", "")

            self.assertEqual(from_time, "now-24h")

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_custom_time_window(self):
        """Test that custom time window is used."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[],
                total_count=0,
                unique_services=set(),
                unique_efilogids=set(),
            )
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            set_datadog_api(mock_api)

            await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
                "time_window": "now-7d",
            })

            call_args = mock_api.search_logs.call_args
            from_time = call_args.kwargs.get("from_time", "")

            self.assertEqual(from_time, "now-7d")

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_empty_results(self):
        """Test response when no logs found for efilogid."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[],
                total_count=0,
                unique_services=set(),
                unique_efilogids=set(),
            )
            mock_api.build_efilogid_query.return_value = '@efilogid:"nonexistent-session"'
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "nonexistent-session",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(response_data["log_count"], 0)
            self.assertEqual(len(response_data["logs"]), 0)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_error_returns_is_error(self):
        """Test that errors return is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            mock_api.search_logs.side_effect = DataDogAPIError("API error")
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            self.assertTrue(result.get("is_error", False))

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_rate_limit_error(self):
        """Test rate limit error handling in get_logs_by_efilogid."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            mock_api.search_logs.side_effect = DataDogRateLimitError("Rate limit exceeded")
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("rate limit", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_auth_error(self):
        """Test auth error handling in get_logs_by_efilogid."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            mock_api.search_logs.side_effect = DataDogAuthError("Invalid API key")
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("auth", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_timeout_error(self):
        """Test timeout error handling in get_logs_by_efilogid."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            mock_api.search_logs.side_effect = DataDogTimeoutError("Connection timed out")
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("timeout", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_generic_error(self):
        """Test generic error handling in get_logs_by_efilogid."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.build_efilogid_query.return_value = '@efilogid:"session-123"'
            mock_api.search_logs.side_effect = Exception("Unexpected error")
            set_datadog_api(mock_api)

            result = await get_logs_by_efilogid_tool({
                "efilogid": "session-123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestParseStackTraceTool(unittest.TestCase):
    """Tests for parse_stack_trace MCP tool."""

    def setUp(self):
        """Reset stack parser before each test."""
        if DATADOG_TOOLS_AVAILABLE:
            reset_stack_parser()

    @skip_if_no_datadog_tools
    def test_parse_kotlin_stack_trace(self):
        """Test parsing a Kotlin stack trace."""
        async def run_test():
            stack_trace = """java.lang.NullPointerException: Customer not found
    at com.sunbit.card.invitation.lead.application.EntitledCustomerService.findCustomer(EntitledCustomerService.kt:45)
    at com.sunbit.card.invitation.lead.application.EntitledCustomerService.processLead(EntitledCustomerService.kt:30)
    at org.springframework.aop.support.AopUtils.invokeJoinpointUsingReflection(AopUtils.java:344)"""

            result = await parse_stack_trace_tool({
                "stack_trace_text": stack_trace,
            })

            self.assertNotIn("is_error", result)
            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(response_data["exception_type"], "java.lang.NullPointerException")
            self.assertEqual(response_data["exception_message"], "Customer not found")
            self.assertGreater(len(response_data["file_paths"]), 0)

            # Check sunbit frames are extracted
            file_paths = response_data["file_paths"]
            self.assertTrue(any("com/sunbit" in path for path in file_paths))

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_parse_java_stack_trace(self):
        """Test parsing a Java stack trace."""
        async def run_test():
            stack_trace = """java.lang.IllegalStateException: Service unavailable
    at com.sunbit.payment.handler.PaymentHandler.processPayment(PaymentHandler.java:89)
    at com.sunbit.payment.handler.PaymentHandler.handleRequest(PaymentHandler.java:45)"""

            result = await parse_stack_trace_tool({
                "stack_trace_text": stack_trace,
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(response_data["exception_type"], "java.lang.IllegalStateException")

            # Verify Java files are mapped correctly
            file_paths = response_data["file_paths"]
            self.assertTrue(any(".java" in path for path in file_paths))

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_parse_stack_trace_extracts_frames(self):
        """Test that stack frames are extracted with correct info."""
        async def run_test():
            stack_trace = """java.lang.NullPointerException: null
    at com.sunbit.card.Handler.process(Handler.kt:50)"""

            result = await parse_stack_trace_tool({
                "stack_trace_text": stack_trace,
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertGreater(response_data["frame_count"], 0)
            self.assertIn("frames", response_data)

            if response_data["frames"]:
                frame = response_data["frames"][0]
                self.assertIn("file_path", frame)
                self.assertIn("line_number", frame)
                self.assertIn("method_name", frame)
                self.assertIn("class_name", frame)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_parse_stack_trace_limits_frames_to_10(self):
        """Test that frames are limited to first 10."""
        async def run_test():
            # Create stack trace with 20 frames
            frames = "\n".join([
                f"    at com.sunbit.service.Handler{i}.method(Handler{i}.kt:{i * 10})"
                for i in range(20)
            ])
            stack_trace = f"java.lang.Exception: Test\n{frames}"

            result = await parse_stack_trace_tool({
                "stack_trace_text": stack_trace,
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertLessEqual(len(response_data["frames"]), 10)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_parse_stack_trace_empty_input(self):
        """Test parsing empty stack trace."""
        async def run_test():
            result = await parse_stack_trace_tool({
                "stack_trace_text": "",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertIsNone(response_data.get("exception_type"))
            self.assertEqual(len(response_data.get("file_paths", [])), 0)

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_parse_stack_trace_error_returns_is_error(self):
        """Test that parsing errors return is_error: true."""
        async def run_test():
            mock_parser = Mock(spec=StackTraceParser)
            mock_parser.parse.side_effect = Exception("Parse error")
            set_stack_parser(mock_parser)

            result = await parse_stack_trace_tool({
                "stack_trace_text": "some text",
            })

            self.assertTrue(result.get("is_error", False))

        asyncio.run(run_test())


class TestSearchCommitsTool(unittest.TestCase):
    """Tests for search_commits MCP tool."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_with_time_range(self):
        """Test searching commits within a time range."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.return_value = [
                CommitInfo(
                    sha="abc123def456",
                    message="card-invitation-service-abc123def456___12345",
                    author="deploy-bot",
                    date="2024-01-15T10:00:00Z",
                    url="https://github.com/sunbit-dev/kubernetes/commit/abc123",
                )
            ]
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-14T00:00:00Z",
                "until": "2024-01-15T23:59:59Z",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertGreater(len(response_data["commits"]), 0)
            self.assertEqual(response_data["commits"][0]["sha"], "abc123def456")

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_with_author_filter(self):
        """Test filtering commits by author."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.return_value = [
                CommitInfo(
                    sha="abc123",
                    message="Deploy commit",
                    author="deploy-bot",
                    date="2024-01-15T10:00:00Z",
                )
            ]
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-14T00:00:00Z",
                "author": "deploy-bot",
            })

            # Verify author filter was passed
            mock_helper.list_commits.assert_called()
            response_data = json.loads(result["content"][0]["text"])
            self.assertTrue(response_data["success"])

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_empty_results(self):
        """Test response when no commits found."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.return_value = []
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-14T00:00:00Z",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(len(response_data["commits"]), 0)

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_error_returns_is_error(self):
        """Test that errors return is_error: true."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.side_effect = GitHubError("API error")
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-14T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))

        asyncio.run(run_test())


class TestGetFileContentTool(unittest.TestCase):
    """Tests for get_file_content MCP tool."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_get_file_content_at_specific_commit(self):
        """Test getting file content at a specific commit."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.return_value = """package com.sunbit.card

class Handler {
    fun process() {
        // implementation
    }
}"""
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "file_path": "src/main/kotlin/com/sunbit/card/Handler.kt",
                "commit_sha": "abc123def456",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertIn("content", response_data)
            self.assertIn("class Handler", response_data["content"])

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_not_found(self):
        """Test getting file that doesn't exist."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.side_effect = GitHubNotFoundError("File not found")
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "file_path": "src/main/kotlin/NonExistent.kt",
                "commit_sha": "abc123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("not found", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_uses_asyncio_to_thread(self):
        """Test that get_file_content wraps sync call with asyncio.to_thread."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.return_value = "file content"
            set_github_helper(mock_helper)

            with patch('mcp_servers.github_server.asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = "file content"

                await get_file_content_tool({
                    "owner": "sunbit-dev",
                    "repo": "test-repo",
                    "file_path": "test.kt",
                    "commit_sha": "abc123",
                })

                mock_to_thread.assert_called_once()

        asyncio.run(run_test())


class TestGetPRFilesTool(unittest.TestCase):
    """Tests for get_pr_files MCP tool."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_get_pr_files_returns_file_list(self):
        """Test getting files changed in a PR."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.return_value = [
                FileChange(
                    filename="src/main/kotlin/Handler.kt",
                    status="modified",
                    additions=10,
                    deletions=5,
                    patch="@@ -1,5 +1,10 @@\n+new line",
                ),
                FileChange(
                    filename="src/test/kotlin/HandlerTest.kt",
                    status="added",
                    additions=50,
                    deletions=0,
                ),
            ]
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "pr_number": 123,
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(len(response_data["files"]), 2)
            self.assertEqual(response_data["files"][0]["filename"], "src/main/kotlin/Handler.kt")
            self.assertEqual(response_data["files"][0]["status"], "modified")

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_pr_not_found(self):
        """Test getting files for non-existent PR."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.side_effect = GitHubNotFoundError("PR not found")
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "pr_number": 99999,
            })

            self.assertTrue(result.get("is_error", False))

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_empty_pr(self):
        """Test getting files for PR with no changes."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.return_value = []
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "pr_number": 123,
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(len(response_data["files"]), 0)

        asyncio.run(run_test())


class TestCompareCommitsTool(unittest.TestCase):
    """Tests for compare_commits MCP tool."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_compare_commits_generates_diff(self):
        """Test comparing two commits generates diff."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.return_value = {
                "status": "diverged",
                "ahead_by": 1,
                "behind_by": 0,
                "total_commits": 1,
                "files": [
                    {
                        "filename": "src/main/kotlin/Handler.kt",
                        "status": "modified",
                        "additions": 5,
                        "deletions": 3,
                        "patch": "@@ -10,3 +10,5 @@\n-old\n+new",
                    }
                ],
            }
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "base": "abc123",
                "head": "def456",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertIn("files", response_data)
            self.assertEqual(len(response_data["files"]), 1)
            self.assertIn("patch", response_data["files"][0])

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_with_file_filter(self):
        """Test comparing commits with file path filter."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.return_value = {
                "files": [
                    {"filename": "src/main/kotlin/Handler.kt", "patch": "diff1"},
                    {"filename": "src/main/kotlin/Service.kt", "patch": "diff2"},
                ],
            }
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "base": "abc123",
                "head": "def456",
                "file_path": "src/main/kotlin/Handler.kt",
            })

            response_data = json.loads(result["content"][0]["text"])

            # Should filter to only requested file
            self.assertTrue(response_data["success"])
            if "file_diff" in response_data:
                self.assertIn("Handler", str(response_data))

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_no_changes(self):
        """Test comparing identical commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.return_value = {
                "status": "identical",
                "ahead_by": 0,
                "behind_by": 0,
                "total_commits": 0,
                "files": [],
            }
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "base": "abc123",
                "head": "abc123",
            })

            response_data = json.loads(result["content"][0]["text"])

            self.assertTrue(response_data["success"])
            self.assertEqual(len(response_data.get("files", [])), 0)

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_error_returns_is_error(self):
        """Test that compare errors return is_error: true."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = GitHubError("API error")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "card-invitation-service",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))

        asyncio.run(run_test())


class TestValidationErrors(unittest.TestCase):
    """Tests for validation error handling."""

    def setUp(self):
        """Reset helpers before each test."""
        if DATADOG_TOOLS_AVAILABLE:
            reset_datadog_api()
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_datadog_tools
    def test_search_logs_empty_query_returns_error(self):
        """Test that empty query returns validation error."""
        async def run_test():
            result = await search_logs_tool({
                "query": "",
                "from_time": "now-4h",
                "to_time": "now",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_datadog_tools
    def test_get_logs_by_efilogid_empty_returns_error(self):
        """Test that empty efilogid returns validation error."""
        async def run_test():
            result = await get_logs_by_efilogid_tool({
                "efilogid": "",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_missing_owner_returns_error(self):
        """Test that missing owner returns validation error."""
        async def run_test():
            result = await search_commits_tool({
                "repo": "kubernetes",
                "since": "2024-01-01T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_missing_since_returns_error(self):
        """Test that missing since returns validation error."""
        async def run_test():
            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_search_commits_invalid_date_format_returns_error(self):
        """Test that invalid date format returns validation error."""
        async def run_test():
            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "not-a-date",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("invalid", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_missing_params_returns_error(self):
        """Test that missing parameters return validation error."""
        async def run_test():
            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                # Missing file_path and commit_sha
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_missing_pr_number_returns_error(self):
        """Test that missing pr_number returns validation error."""
        async def run_test():
            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "test",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_missing_base_returns_error(self):
        """Test that missing base returns validation error."""
        async def run_test():
            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("required", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestGitHubRateLimitErrors(unittest.TestCase):
    """Tests for GitHub rate limit error handling."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_rate_limit_error(self):
        """Test rate limit error handling in search_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.side_effect = GitHubRateLimitError("Rate limit exceeded")
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-01T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("rate limit", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_rate_limit_error(self):
        """Test rate limit error handling in get_file_content."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.side_effect = GitHubRateLimitError("Rate limit exceeded")
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "file_path": "test.kt",
                "commit_sha": "abc123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("rate limit", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_rate_limit_error(self):
        """Test rate limit error handling in get_pr_files."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.side_effect = GitHubRateLimitError("Rate limit exceeded")
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "pr_number": 123,
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("rate limit", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_rate_limit_error(self):
        """Test rate limit error handling in compare_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = GitHubRateLimitError("Rate limit exceeded")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("rate limit", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestGitHubAuthErrors(unittest.TestCase):
    """Tests for GitHub auth error handling."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_auth_error(self):
        """Test auth error handling in search_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.side_effect = GitHubAuthError("Invalid token")
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-01T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("auth", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_auth_error(self):
        """Test auth error handling in get_file_content."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.side_effect = GitHubAuthError("Invalid token")
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "file_path": "test.kt",
                "commit_sha": "abc123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("auth", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_auth_error(self):
        """Test auth error handling in get_pr_files."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.side_effect = GitHubAuthError("Invalid token")
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "pr_number": 123,
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("auth", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_auth_error(self):
        """Test auth error handling in compare_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = GitHubAuthError("Invalid token")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("auth", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestGitHubNotFoundErrors(unittest.TestCase):
    """Tests for GitHub not found error handling."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_not_found_error(self):
        """Test not found error handling in search_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.side_effect = GitHubNotFoundError("Repo not found")
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "nonexistent",
                "since": "2024-01-01T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("not found", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_not_found_error(self):
        """Test not found error handling in compare_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = GitHubNotFoundError("Commit not found")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("not found", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestDateParsing(unittest.TestCase):
    """Tests for date parsing in search_commits."""

    def setUp(self):
        """Reset GitHub helper before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_invalid_until_date(self):
        """Test that invalid until date returns validation error."""
        async def run_test():
            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-01T00:00:00Z",
                "until": "not-a-date",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("invalid", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestGenericErrors(unittest.TestCase):
    """Tests for generic error handling."""

    def setUp(self):
        """Reset helpers before each test."""
        if GITHUB_TOOLS_AVAILABLE:
            reset_github_helper()

    @skip_if_no_github_tools
    def test_search_commits_generic_error(self):
        """Test generic error handling in search_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.side_effect = Exception("Unexpected error")
            set_github_helper(mock_helper)

            result = await search_commits_tool({
                "owner": "sunbit-dev",
                "repo": "kubernetes",
                "since": "2024-01-01T00:00:00Z",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_github_error(self):
        """Test GitHubError handling in get_file_content."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.side_effect = GitHubError("GitHub API error")
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "file_path": "test.kt",
                "commit_sha": "abc123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("github", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_file_content_generic_error(self):
        """Test generic error handling in get_file_content."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_file_content.side_effect = Exception("Unexpected error")
            set_github_helper(mock_helper)

            result = await get_file_content_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "file_path": "test.kt",
                "commit_sha": "abc123",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_github_error(self):
        """Test GitHubError handling in get_pr_files."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.side_effect = GitHubError("GitHub API error")
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "pr_number": 123,
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("github", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_get_pr_files_generic_error(self):
        """Test generic error handling in get_pr_files."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_pr_files.side_effect = Exception("Unexpected error")
            set_github_helper(mock_helper)

            result = await get_pr_files_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "pr_number": 123,
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_github_error(self):
        """Test GitHubError handling in compare_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = GitHubError("GitHub API error")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("github", result["content"][0]["text"].lower())

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_compare_commits_generic_error(self):
        """Test generic error handling in compare_commits."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.get_compare.side_effect = Exception("Unexpected error")
            set_github_helper(mock_helper)

            result = await compare_commits_tool({
                "owner": "sunbit-dev",
                "repo": "test",
                "base": "abc123",
                "head": "def456",
            })

            self.assertTrue(result.get("is_error", False))
            self.assertIn("error", result["content"][0]["text"].lower())

        asyncio.run(run_test())


class TestMCPToolResponseFormat(unittest.TestCase):
    """Tests verifying MCP tool response format compliance."""

    @skip_if_no_mcp_tools
    def test_all_tools_return_content_array(self):
        """Test that all tools return content as array."""
        # This test is a format compliance check - verified in individual tool tests
        # Each tool test already verifies the content array format in assertions like:
        # self.assertIn("content", result)
        # self.assertIsInstance(result["content"], list)
        pass

    @skip_if_no_datadog_tools
    def test_error_responses_include_is_error_flag(self):
        """Test that error responses always include is_error: true."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.side_effect = Exception("Test error")
            set_datadog_api(mock_api)

            result = await search_logs_tool({
                "query": "test",
                "from_time": "now-1h",
                "to_time": "now",
            })

            self.assertIn("is_error", result)
            self.assertTrue(result["is_error"])
            self.assertIn("content", result)
            self.assertIsInstance(result["content"], list)

        asyncio.run(run_test())


class TestAsyncioToThreadIntegration(unittest.TestCase):
    """Tests verifying asyncio.to_thread usage for sync utilities."""

    @skip_if_no_datadog_tools
    def test_datadog_tools_use_asyncio_to_thread(self):
        """Test DataDog tools properly wrap sync calls."""
        async def run_test():
            mock_api = Mock(spec=DataDogAPI)
            mock_api.search_logs.return_value = SearchResult(
                logs=[], total_count=0, unique_services=set(), unique_efilogids=set()
            )
            set_datadog_api(mock_api)

            with patch('mcp_servers.datadog_server.asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_api.search_logs.return_value

                await search_logs_tool({
                    "query": "test",
                    "from_time": "now-1h",
                    "to_time": "now",
                })

                # Verify to_thread was called
                self.assertTrue(mock_to_thread.called)

        asyncio.run(run_test())

    @skip_if_no_github_tools
    def test_github_tools_use_asyncio_to_thread(self):
        """Test GitHub tools properly wrap sync calls."""
        async def run_test():
            mock_helper = Mock(spec=GitHubHelper)
            mock_helper.list_commits.return_value = []
            set_github_helper(mock_helper)

            with patch('mcp_servers.github_server.asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = []

                await search_commits_tool({
                    "owner": "test",
                    "repo": "test",
                    "since": "2024-01-01T00:00:00Z",
                })

                # Verify to_thread was called
                self.assertTrue(mock_to_thread.called)

        asyncio.run(run_test())


if __name__ == "__main__":
    # Run tests - all should fail initially (TDD red phase)
    unittest.main(verbosity=2)
