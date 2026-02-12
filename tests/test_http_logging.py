"""
Tests for HTTP and GitHub CLI logging functionality.

Tests the structured logging for:
- DataDog API HTTP requests/responses (utils/datadog_api.py)
- GitHub CLI commands (utils/github_helper.py)

Logging format:
- Prefixes: [HTTP_REQ], [HTTP_RESP], [GH_CLI_REQ], [GH_CLI_RESP]
- Two levels: DEBUG (full details) and INFO (summaries)
- Sensitive data redaction: API keys, tokens, authorization headers
"""
import json
import logging
import subprocess
import unittest
from typing import List
from unittest.mock import MagicMock, Mock, patch

import requests

from utils.datadog_api import DataDogAPI
from utils.github_helper import GitHubHelper


class LogCaptureHandler(logging.Handler):
    """Custom logging handler to capture log records during tests."""

    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Capture log record.

        Args:
            record: The log record to capture
        """
        self.records.append(record)

    def get_messages(self, level: int) -> List[str]:
        """Get log messages at a specific level.

        Args:
            level: Log level (logging.DEBUG, logging.INFO, etc.)

        Returns:
            List of log messages at that level
        """
        return [r.message for r in self.records if r.levelno == level]

    def get_debug_messages(self) -> List[str]:
        """Get DEBUG level messages."""
        return self.get_messages(logging.DEBUG)

    def get_info_messages(self) -> List[str]:
        """Get INFO level messages."""
        return self.get_messages(logging.INFO)

    def clear(self):
        """Clear captured records."""
        self.records.clear()


class TestDataDogHTTPLogging(unittest.TestCase):
    """Tests for DataDog API HTTP request/response logging."""

    def setUp(self):
        """Set up test fixtures."""
        self.log_capture = LogCaptureHandler()

        # Configure logger for datadog_api module
        self.logger = logging.getLogger("utils.datadog_api")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Add custom handler to capture logs
        self.log_capture.setLevel(logging.DEBUG)
        self.logger.addHandler(self.log_capture)

        # Create API client
        self.api = DataDogAPI(
            api_key="test_api_key_123",
            app_key="test_app_key_456",
            site="datadoghq.com",
        )

    def tearDown(self):
        """Clean up after tests."""
        self.logger.handlers.clear()
        self.log_capture.clear()

    @patch("requests.request")
    def test_http_request_logged_at_debug(self, mock_request):
        """Test that HTTP request is logged at DEBUG level with full details."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"data": []}'
        mock_request.return_value = mock_response

        # Make request
        request_body = {"filter": {"query": "test query"}}
        self.api._make_request("POST", "https://api.datadoghq.com/test", json=request_body)

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()

        # Find the HTTP_REQ debug message
        req_messages = [msg for msg in debug_messages if "[HTTP_REQ]" in msg]
        self.assertEqual(len(req_messages), 1, "Should have one HTTP_REQ debug message")

        req_msg = req_messages[0]

        # Verify structure
        self.assertIn("[HTTP_REQ]", req_msg)
        self.assertIn("method=POST", req_msg)
        self.assertIn("url=https://api.datadoghq.com/test", req_msg)
        self.assertIn("headers=", req_msg)
        self.assertIn("body=", req_msg)

        # Verify body content is logged
        self.assertIn("test query", req_msg)

    @patch("requests.request")
    def test_http_request_logged_at_info(self, mock_request):
        """Test that HTTP request is logged at INFO level with summary."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"data": []}'
        mock_request.return_value = mock_response

        # Make request
        request_body = {"filter": {"query": "test"}}
        self.api._make_request("POST", "https://api.datadoghq.com/test", json=request_body)

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()

        # Find the HTTP_REQ info message
        req_messages = [msg for msg in info_messages if "[HTTP_REQ]" in msg]
        self.assertEqual(len(req_messages), 1, "Should have one HTTP_REQ info message")

        req_msg = req_messages[0]

        # Verify structure: [HTTP_REQ] {method} {url} body_size={size}B
        self.assertIn("[HTTP_REQ]", req_msg)
        self.assertIn("POST", req_msg)
        self.assertIn("https://api.datadoghq.com/test", req_msg)
        self.assertIn("body_size=", req_msg)
        self.assertIn("B", req_msg)  # Bytes suffix

        # Should NOT contain full body at INFO level
        self.assertNotIn("test query", req_msg)

    @patch("requests.request")
    def test_http_response_logged_at_debug(self, mock_request):
        """Test that HTTP response is logged at DEBUG level with full details."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Type": "application/json",
            "X-RateLimit-Remaining": "100"
        }
        mock_response.content = b'{"data": [{"id": "123"}]}'
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("GET", "https://api.datadoghq.com/test")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()

        # Find the HTTP_RESP debug message
        resp_messages = [msg for msg in debug_messages if "[HTTP_RESP]" in msg]
        self.assertEqual(len(resp_messages), 1, "Should have one HTTP_RESP debug message")

        resp_msg = resp_messages[0]

        # Verify structure
        self.assertIn("[HTTP_RESP]", resp_msg)
        self.assertIn("status=200", resp_msg)
        self.assertIn("headers=", resp_msg)
        self.assertIn("body=", resp_msg)

        # Verify body content is logged
        self.assertIn("123", resp_msg)

    @patch("requests.request")
    def test_http_response_logged_at_info(self, mock_request):
        """Test that HTTP response is logged at INFO level with summary."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.content = b'{"success": true}'
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("POST", "https://api.datadoghq.com/test")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()

        # Find the HTTP_RESP info message
        resp_messages = [msg for msg in info_messages if "[HTTP_RESP]" in msg]
        self.assertEqual(len(resp_messages), 1, "Should have one HTTP_RESP info message")

        resp_msg = resp_messages[0]

        # Verify structure: [HTTP_RESP] status={code} timing={ms}ms body_size={size}B
        self.assertIn("[HTTP_RESP]", resp_msg)
        self.assertIn("status=201", resp_msg)
        self.assertIn("timing=", resp_msg)
        self.assertIn("ms", resp_msg)
        self.assertIn("body_size=", resp_msg)
        self.assertIn("B", resp_msg)

        # Should NOT contain full body at INFO level
        self.assertNotIn("success", resp_msg)

    @patch("requests.request")
    def test_sensitive_data_redaction_api_keys(self, mock_request):
        """Test that DD-API-KEY is redacted in logs."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("GET", "https://api.datadoghq.com/test")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        req_messages = [msg for msg in debug_messages if "[HTTP_REQ]" in msg]

        self.assertEqual(len(req_messages), 1)
        req_msg = req_messages[0]

        # API key should be redacted
        self.assertNotIn("test_api_key_123", req_msg)
        self.assertIn("***REDACTED***", req_msg)

    @patch("requests.request")
    def test_sensitive_data_redaction_app_keys(self, mock_request):
        """Test that DD-APPLICATION-KEY is redacted in logs."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("GET", "https://api.datadoghq.com/test")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        req_messages = [msg for msg in debug_messages if "[HTTP_REQ]" in msg]

        self.assertEqual(len(req_messages), 1)
        req_msg = req_messages[0]

        # App key should be redacted
        self.assertNotIn("test_app_key_456", req_msg)
        self.assertIn("***REDACTED***", req_msg)

    @patch("requests.request")
    def test_sensitive_data_redaction_authorization(self, mock_request):
        """Test that Authorization header is redacted in logs."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        # Add Authorization header
        original_headers = self.api.headers.copy()
        self.api.headers["Authorization"] = "Bearer secret_token_123"

        try:
            # Make request
            self.api._make_request("GET", "https://api.datadoghq.com/test")

            # Check DEBUG logs
            debug_messages = self.log_capture.get_debug_messages()
            req_messages = [msg for msg in debug_messages if "[HTTP_REQ]" in msg]

            self.assertEqual(len(req_messages), 1)
            req_msg = req_messages[0]

            # Authorization should be redacted
            self.assertNotIn("secret_token_123", req_msg)
            self.assertIn("***REDACTED***", req_msg)
        finally:
            # Restore headers
            self.api.headers = original_headers

    @patch("requests.request")
    def test_large_body_truncation(self, mock_request):
        """Test that large request bodies are truncated in logs."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        # Create a large body (>1000 chars)
        large_body = {"data": "x" * 2000}

        # Make request
        self.api._make_request("POST", "https://api.datadoghq.com/test", json=large_body)

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        req_messages = [msg for msg in debug_messages if "[HTTP_REQ]" in msg]

        self.assertEqual(len(req_messages), 1)
        req_msg = req_messages[0]

        # Should be truncated
        self.assertIn("truncated", req_msg)
        self.assertIn("total:", req_msg)

    @patch("requests.request")
    def test_large_response_truncation(self, mock_request):
        """Test that large response bodies are truncated in logs."""
        # Setup mock response with large body
        large_response_body = b'{"data": "' + b'y' * 2000 + b'"}'
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = large_response_body
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("GET", "https://api.datadoghq.com/test")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        resp_messages = [msg for msg in debug_messages if "[HTTP_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should be truncated
        self.assertIn("truncated", resp_msg)
        self.assertIn("total:", resp_msg)

    @patch("requests.request")
    def test_timing_in_response_log(self, mock_request):
        """Test that response timing is included in INFO logs."""
        # Setup mock response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        # Make request
        self.api._make_request("GET", "https://api.datadoghq.com/test")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()
        resp_messages = [msg for msg in info_messages if "[HTTP_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should have timing
        self.assertIn("timing=", resp_msg)
        self.assertIn("ms", resp_msg)

        # Extract timing value (should be >= 0)
        import re
        timing_match = re.search(r"timing=(\d+)ms", resp_msg)
        self.assertIsNotNone(timing_match)
        timing_value = int(timing_match.group(1))
        self.assertGreaterEqual(timing_value, 0)


class TestGitHubCLILogging(unittest.TestCase):
    """Tests for GitHub CLI command logging."""

    def setUp(self):
        """Set up test fixtures."""
        self.log_capture = LogCaptureHandler()

        # Configure logger for github_helper module
        self.logger = logging.getLogger("utils.github_helper")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Add custom handler to capture logs
        self.log_capture.setLevel(logging.DEBUG)
        self.logger.addHandler(self.log_capture)

        # Create helper
        self.helper = GitHubHelper(token="ghp_test_token_123456789")

    def tearDown(self):
        """Clean up after tests."""
        self.logger.handlers.clear()
        self.log_capture.clear()

    @patch("subprocess.run")
    def test_cli_request_logged_at_debug(self, mock_run):
        """Test that CLI request is logged at DEBUG level with full command."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{"sha": "abc123"}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()

        # Find the GH_CLI_REQ debug message
        req_messages = [msg for msg in debug_messages if "[GH_CLI_REQ]" in msg]
        self.assertEqual(len(req_messages), 1, "Should have one GH_CLI_REQ debug message")

        req_msg = req_messages[0]

        # Verify structure
        self.assertIn("[GH_CLI_REQ]", req_msg)
        self.assertIn("command=", req_msg)
        self.assertIn("gh api", req_msg)
        self.assertIn("endpoint=repos/owner/repo/commits", req_msg)

    @patch("subprocess.run")
    def test_cli_request_logged_at_info(self, mock_run):
        """Test that CLI request is logged at INFO level with endpoint summary."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{"sha": "abc123"}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/pulls/123")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()

        # Find the GH_CLI_REQ info message
        req_messages = [msg for msg in info_messages if "[GH_CLI_REQ]" in msg]
        self.assertEqual(len(req_messages), 1, "Should have one GH_CLI_REQ info message")

        req_msg = req_messages[0]

        # Verify structure: [GH_CLI_REQ] endpoint={endpoint}
        self.assertIn("[GH_CLI_REQ]", req_msg)
        self.assertIn("endpoint=repos/owner/repo/pulls/123", req_msg)

        # Should NOT contain full command at INFO level
        self.assertNotIn("command=", req_msg)

    @patch("subprocess.run")
    def test_cli_response_logged_at_debug(self, mock_run):
        """Test that CLI response is logged at DEBUG level with stdout/stderr."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "success"}'
        mock_result.stderr = "warning: something"
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()

        # Find the GH_CLI_RESP debug message
        resp_messages = [msg for msg in debug_messages if "[GH_CLI_RESP]" in msg]
        self.assertEqual(len(resp_messages), 1, "Should have one GH_CLI_RESP debug message")

        resp_msg = resp_messages[0]

        # Verify structure
        self.assertIn("[GH_CLI_RESP]", resp_msg)
        self.assertIn("returncode=0", resp_msg)
        self.assertIn("stdout=", resp_msg)
        self.assertIn("stderr=", resp_msg)

        # Verify content is logged
        self.assertIn("success", resp_msg)
        self.assertIn("warning", resp_msg)

    @patch("subprocess.run")
    def test_cli_response_logged_at_info(self, mock_run):
        """Test that CLI response is logged at INFO level with status and timing."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{"data": []}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()

        # Find the GH_CLI_RESP info message
        resp_messages = [msg for msg in info_messages if "[GH_CLI_RESP]" in msg]
        self.assertEqual(len(resp_messages), 1, "Should have one GH_CLI_RESP info message")

        resp_msg = resp_messages[0]

        # Verify structure: [GH_CLI_RESP] status={code} timing={ms}ms stdout_size={size}B stderr_size={size}B
        self.assertIn("[GH_CLI_RESP]", resp_msg)
        self.assertIn("status=0", resp_msg)
        self.assertIn("timing=", resp_msg)
        self.assertIn("ms", resp_msg)
        self.assertIn("stdout_size=", resp_msg)
        self.assertIn("stderr_size=", resp_msg)

        # Should NOT contain full output at INFO level
        self.assertNotIn("data", resp_msg)

    @patch("subprocess.run")
    def test_github_token_not_in_logs(self, mock_run):
        """Test that GITHUB_TOKEN is not logged in command output."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{"sha": "abc"}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check all logs
        all_messages = (
            self.log_capture.get_debug_messages() +
            self.log_capture.get_info_messages()
        )

        # Token should not appear anywhere
        for msg in all_messages:
            self.assertNotIn("ghp_test_token_123456789", msg)

    @patch("subprocess.run")
    def test_large_stdout_truncation(self, mock_run):
        """Test that large stdout is truncated in logs."""
        # Setup mock result with large stdout
        large_stdout = '{"data": "' + 'z' * 2000 + '"}'
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = large_stdout
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        resp_messages = [msg for msg in debug_messages if "[GH_CLI_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should be truncated
        self.assertIn("truncated", resp_msg)
        self.assertIn("total:", resp_msg)

    @patch("subprocess.run")
    def test_large_stderr_truncation(self, mock_run):
        """Test that large stderr is truncated in logs."""
        # Setup mock result with large stderr
        large_stderr = "error: " + "e" * 2000
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = large_stderr
        mock_run.return_value = mock_result

        # Run command (will fail but that's ok for this test)
        try:
            self.helper._run_gh_api("repos/owner/repo/commits")
        except Exception:
            pass  # Expected to fail

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        resp_messages = [msg for msg in debug_messages if "[GH_CLI_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should be truncated
        self.assertIn("truncated", resp_msg)
        self.assertIn("total:", resp_msg)

    @patch("subprocess.run")
    def test_timing_in_cli_response_log(self, mock_run):
        """Test that CLI response timing is included in INFO logs."""
        # Setup mock result
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = '{}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()
        resp_messages = [msg for msg in info_messages if "[GH_CLI_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should have timing
        self.assertIn("timing=", resp_msg)
        self.assertIn("ms", resp_msg)

        # Extract timing value (should be >= 0)
        import re
        timing_match = re.search(r"timing=(\d+)ms", resp_msg)
        self.assertIsNotNone(timing_match)
        timing_value = int(timing_match.group(1))
        self.assertGreaterEqual(timing_value, 0)

    @patch("subprocess.run")
    def test_error_returncode_logged(self, mock_run):
        """Test that non-zero return codes are logged correctly."""
        # Setup mock result with error
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: not found"
        mock_run.return_value = mock_result

        # Run command (will fail)
        try:
            self.helper._run_gh_api("repos/invalid/repo")
        except Exception:
            pass  # Expected to fail

        # Check DEBUG logs
        debug_messages = self.log_capture.get_debug_messages()
        resp_messages = [msg for msg in debug_messages if "[GH_CLI_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should log the error returncode
        self.assertIn("returncode=1", resp_msg)

    @patch("subprocess.run")
    def test_output_sizes_in_info_log(self, mock_run):
        """Test that stdout and stderr sizes are logged at INFO level."""
        # Setup mock result
        stdout_content = '{"data": [1, 2, 3]}'
        stderr_content = "warning message"
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = stdout_content
        mock_result.stderr = stderr_content
        mock_run.return_value = mock_result

        # Run command
        self.helper._run_gh_api("repos/owner/repo/commits")

        # Check INFO logs
        info_messages = self.log_capture.get_info_messages()
        resp_messages = [msg for msg in info_messages if "[GH_CLI_RESP]" in msg]

        self.assertEqual(len(resp_messages), 1)
        resp_msg = resp_messages[0]

        # Should have size information
        self.assertIn(f"stdout_size={len(stdout_content)}B", resp_msg)
        self.assertIn(f"stderr_size={len(stderr_content)}B", resp_msg)


class TestLoggingHelperMethods(unittest.TestCase):
    """Tests for logging helper methods."""

    def test_redact_sensitive_headers(self):
        """Test header redaction utility."""
        api = DataDogAPI(
            api_key="secret_key",
            app_key="secret_app",
        )

        headers = {
            "DD-API-KEY": "secret_key",
            "DD-APPLICATION-KEY": "secret_app",
            "Authorization": "Bearer token123",
            "Content-Type": "application/json",
        }

        redacted = api._redact_sensitive_headers(headers)

        # Sensitive headers should be redacted
        self.assertEqual(redacted["DD-API-KEY"], "***REDACTED***")
        self.assertEqual(redacted["DD-APPLICATION-KEY"], "***REDACTED***")
        self.assertEqual(redacted["Authorization"], "***REDACTED***")

        # Non-sensitive headers should remain
        self.assertEqual(redacted["Content-Type"], "application/json")

    def test_truncate_body_dict(self):
        """Test body truncation with dict input."""
        api = DataDogAPI(api_key="test", app_key="test")

        body = {"key": "value" * 500}
        truncated = api._truncate_body(body, max_length=100)

        self.assertIn("truncated", truncated)
        self.assertIn("total:", truncated)
        self.assertLess(len(truncated), len(str(body)))

    def test_truncate_body_string(self):
        """Test body truncation with string input."""
        api = DataDogAPI(api_key="test", app_key="test")

        body = "x" * 2000
        truncated = api._truncate_body(body, max_length=100)

        self.assertIn("truncated", truncated)
        self.assertEqual(len(truncated.split("...")[0]), 100)

    def test_truncate_body_none(self):
        """Test body truncation with None input."""
        api = DataDogAPI(api_key="test", app_key="test")

        truncated = api._truncate_body(None)
        self.assertEqual(truncated, "")

    def test_truncate_output(self):
        """Test CLI output truncation."""
        helper = GitHubHelper(token="test")

        output = "y" * 2000
        truncated = helper._truncate_output(output, max_length=100)

        self.assertIn("truncated", truncated)
        self.assertIn("total:", truncated)
        self.assertLess(len(truncated), len(output))

    def test_truncate_output_empty(self):
        """Test CLI output truncation with empty input."""
        helper = GitHubHelper(token="test")

        truncated = helper._truncate_output("")
        self.assertEqual(truncated, "")

        truncated = helper._truncate_output(None)
        self.assertEqual(truncated, "")


if __name__ == "__main__":
    unittest.main()
