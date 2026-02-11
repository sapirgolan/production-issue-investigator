"""
Additional tests for DataDog API to reach 80% coverage.

Tests cover:
- search_logs method with mocks
- _make_request with various HTTP responses
- Rate limit handling
- Error scenarios
"""
import time
import unittest
from unittest.mock import MagicMock, patch, Mock
import requests

from utils.datadog_api import (
    DataDogAPI,
    DataDogAPIError,
    DataDogAuthError,
    DataDogRateLimitError,
    DataDogTimeoutError,
    LogEntry,
    SearchResult,
)


class TestDataDogAPISearchLogs(unittest.TestCase):
    """Tests for search_logs method."""

    @patch('utils.datadog_api.requests.request')
    def test_search_logs_success(self, mock_request):
        """Test successful log search."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "log-1",
                    "attributes": {
                        "message": "Test error message",
                        "service": "card-service",
                        "timestamp": "2024-01-15T10:00:00Z",
                        "status": "error",
                        "attributes": {
                            "efilogid": "session-123",
                            "logger_name": "com.sunbit.Handler",
                            "dd": {"version": "abc123___100"},
                        },
                    },
                }
            ]
        }
        mock_response.headers = {"X-RateLimit-Remaining": "100"}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        result = client.search_logs(
            query="env:prod",
            from_time="now-1h",
            to_time="now",
            limit=100,
        )

        self.assertIsInstance(result, SearchResult)
        self.assertEqual(len(result.logs), 1)
        self.assertEqual(result.logs[0].message, "Test error message")
        self.assertEqual(result.logs[0].service, "card-service")
        self.assertEqual(result.logs[0].efilogid, "session-123")
        self.assertIn("card-service", result.unique_services)

    @patch('utils.datadog_api.requests.request')
    def test_search_logs_empty_results(self, mock_request):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        result = client.search_logs(
            query="env:prod",
            from_time="now-1h",
            to_time="now",
        )

        self.assertEqual(len(result.logs), 0)
        self.assertEqual(result.total_count, 0)

    @patch('utils.datadog_api.requests.request')
    def test_search_logs_limit_capped_at_1000(self, mock_request):
        """Test that limit is capped at 1000."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        client.search_logs(
            query="env:prod",
            from_time="now-1h",
            to_time="now",
            limit=5000,  # Exceeds max
        )

        # Verify request was made with capped limit
        call_args = mock_request.call_args
        request_body = call_args.kwargs.get("json", {})
        self.assertEqual(request_body["page"]["limit"], 1000)


class TestDataDogAPIMakeRequest(unittest.TestCase):
    """Tests for _make_request method."""

    @patch('utils.datadog_api.requests.request')
    def test_make_request_401_raises_auth_error(self, mock_request):
        """Test 401 response raises DataDogAuthError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="bad-key", app_key="test-app")

        with self.assertRaises(DataDogAuthError) as ctx:
            client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertIn("DD_API_KEY", str(ctx.exception))

    @patch('utils.datadog_api.requests.request')
    def test_make_request_403_raises_auth_error(self, mock_request):
        """Test 403 response raises DataDogAuthError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="bad-app")

        with self.assertRaises(DataDogAuthError) as ctx:
            client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertIn("APPLICATION_KEY", str(ctx.exception))

    @patch('utils.datadog_api.requests.request')
    def test_make_request_429_with_retry_success(self, mock_request):
        """Test 429 response triggers retry and succeeds."""
        # First call returns 429, second call succeeds
        mock_429_response = Mock()
        mock_429_response.status_code = 429
        mock_429_response.headers = {"X-RateLimit-Reset": str(int(time.time()) + 1)}

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": []}
        mock_success_response.headers = {}

        mock_request.side_effect = [mock_429_response, mock_success_response]

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        client._rate_limit_reset = int(time.time()) + 1

        with patch('utils.datadog_api.time.sleep'):
            response = client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertEqual(response.status_code, 200)

    @patch('utils.datadog_api.requests.request')
    def test_make_request_429_without_retry(self, mock_request):
        """Test 429 response without retry raises error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")

        with self.assertRaises(DataDogRateLimitError):
            client._make_request(
                "POST",
                "https://api.datadoghq.com/test",
                retry_on_rate_limit=False,
            )

    @patch('utils.datadog_api.requests.request')
    def test_make_request_timeout_raises_error(self, mock_request):
        """Test timeout raises DataDogTimeoutError."""
        mock_request.side_effect = requests.Timeout("Connection timed out")

        client = DataDogAPI(api_key="test-key", app_key="test-app")

        with self.assertRaises(DataDogTimeoutError) as ctx:
            client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertIn("timed out", str(ctx.exception))

    @patch('utils.datadog_api.requests.request')
    def test_make_request_generic_error_raises_api_error(self, mock_request):
        """Test generic request error raises DataDogAPIError."""
        mock_request.side_effect = requests.RequestException("Network error")

        client = DataDogAPI(api_key="test-key", app_key="test-app")

        with self.assertRaises(DataDogAPIError) as ctx:
            client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertIn("Network error", str(ctx.exception))

    @patch('utils.datadog_api.requests.request')
    def test_make_request_http_error_raises_for_status(self, mock_request):
        """Test HTTP errors raise via raise_for_status and wrapped in DataDogAPIError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_request.return_value = mock_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")

        # HTTPError is caught and re-raised as DataDogAPIError
        with self.assertRaises(DataDogAPIError) as ctx:
            client._make_request("POST", "https://api.datadoghq.com/test")

        self.assertIn("Server Error", str(ctx.exception))


class TestDataDogAPIRateLimiting(unittest.TestCase):
    """Tests for rate limit handling."""

    def test_update_rate_limit_info_from_headers(self):
        """Test rate limit info extracted from headers."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        mock_response = Mock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": "1705320000",
        }

        client._update_rate_limit_info(mock_response)

        self.assertEqual(client._rate_limit_remaining, 50)
        self.assertEqual(client._rate_limit_reset, 1705320000)

    def test_update_rate_limit_info_warns_when_low(self):
        """Test warning when rate limit is low."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        mock_response = Mock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "5",  # Below threshold of 10
        }

        # Should not raise, but logs a warning
        client._update_rate_limit_info(mock_response)
        self.assertEqual(client._rate_limit_remaining, 5)

    @patch('utils.datadog_api.time.sleep')
    @patch('utils.datadog_api.requests.request')
    def test_handle_rate_limit_with_reset_time(self, mock_request, mock_sleep):
        """Test rate limit handling uses reset time."""
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.headers = {}
        mock_request.return_value = mock_success_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        client._rate_limit_reset = int(time.time()) + 5  # 5 seconds from now

        response = client._handle_rate_limit("POST", "https://api.datadoghq.com/test")

        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        self.assertGreater(sleep_time, 0)
        self.assertEqual(response.status_code, 200)

    @patch('utils.datadog_api.time.sleep')
    @patch('utils.datadog_api.requests.request')
    def test_handle_rate_limit_without_reset_time(self, mock_request, mock_sleep):
        """Test rate limit handling uses default when no reset time."""
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.headers = {}
        mock_request.return_value = mock_success_response

        client = DataDogAPI(api_key="test-key", app_key="test-app")
        client._rate_limit_reset = None  # No reset time

        response = client._handle_rate_limit("POST", "https://api.datadoghq.com/test")

        mock_sleep.assert_called_once_with(60)  # Default wait
        self.assertEqual(response.status_code, 200)


class TestDataDogAPIParseSearchResponse(unittest.TestCase):
    """Tests for _parse_search_response method."""

    def test_parse_search_response_multiple_logs(self):
        """Test parsing response with multiple logs."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "log-1",
                    "attributes": {
                        "message": "Error 1",
                        "service": "service-a",
                        "timestamp": "2024-01-15T10:00:00Z",
                        "attributes": {"efilogid": "session-1"},
                    },
                },
                {
                    "id": "log-2",
                    "attributes": {
                        "message": "Error 2",
                        "service": "service-b",
                        "timestamp": "2024-01-15T10:01:00Z",
                        "attributes": {"efilogid": "session-2"},
                    },
                },
                {
                    "id": "log-3",
                    "attributes": {
                        "message": "Error 3",
                        "service": "service-a",
                        "timestamp": "2024-01-15T10:02:00Z",
                        "attributes": {"efilogid": "session-1"},
                    },
                },
            ]
        }

        result = client._parse_search_response(mock_response)

        self.assertEqual(len(result.logs), 3)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.unique_services), 2)
        self.assertIn("service-a", result.unique_services)
        self.assertIn("service-b", result.unique_services)
        self.assertEqual(len(result.unique_efilogids), 2)

    def test_parse_search_response_logs_without_service(self):
        """Test parsing logs that may be missing service."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "log-1",
                    "attributes": {
                        "message": "Error without service",
                        "attributes": {},
                    },
                },
            ]
        }

        result = client._parse_search_response(mock_response)

        self.assertEqual(len(result.logs), 1)
        self.assertIsNone(result.logs[0].service)
        self.assertEqual(len(result.unique_services), 0)


class TestDataDogAPIProperties(unittest.TestCase):
    """Tests for API properties."""

    def test_rate_limit_remaining_property(self):
        """Test rate_limit_remaining property."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        self.assertIsNone(client.rate_limit_remaining)

        client._rate_limit_remaining = 42
        self.assertEqual(client.rate_limit_remaining, 42)

    def test_rate_limit_reset_time_property(self):
        """Test rate_limit_reset_time property."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        self.assertIsNone(client.rate_limit_reset_time)

        client._rate_limit_reset = 1705320000
        self.assertEqual(client.rate_limit_reset_time, 1705320000)


class TestDataDogAPIExtractLogEntry(unittest.TestCase):
    """Tests for _extract_log_entry with various data structures."""

    def test_extract_log_entry_dd_version_from_nested_dd(self):
        """Test dd_version extraction from nested dd object."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        log_item = {
            "id": "test-id",
            "attributes": {
                "message": "Test",
                "attributes": {
                    "dd": {"version": "abc123___100"},
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.dd_version, "abc123___100")

    def test_extract_log_entry_dd_version_from_direct_attribute(self):
        """Test dd_version extraction from direct attribute."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        log_item = {
            "id": "test-id",
            "attributes": {
                "message": "Test",
                "attributes": {
                    "dd.version": "def456___200",
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.dd_version, "def456___200")

    def test_extract_log_entry_service_from_nested_attrs(self):
        """Test service extraction from nested attributes."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        log_item = {
            "id": "test-id",
            "attributes": {
                "message": "Test",
                "attributes": {
                    "service": "nested-service",
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.service, "nested-service")


class TestDataDogAPIBuildEfilogidQuery(unittest.TestCase):
    """Tests for build_efilogid_query method."""

    def test_build_efilogid_query_escapes_value(self):
        """Test that efilogid value is wrapped in escaped quotes."""
        client = DataDogAPI(api_key="test-key", app_key="test-app")

        efilogid = "-1-abc123"
        query = client.build_efilogid_query(efilogid)

        # Verify query starts with @efilogid:
        self.assertTrue(query.startswith("@efilogid:"))

        # Verify the efilogid value is wrapped in escaped quotes
        # Expected format: @efilogid:\"-1-abc123\"
        expected_query = f'@efilogid:\\"{efilogid}\\"'
        self.assertEqual(query, expected_query)


if __name__ == "__main__":
    unittest.main()
