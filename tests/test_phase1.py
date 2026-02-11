"""
Phase 1 Tests for Production Issue Investigator.

Tests for:
- Configuration loading (utils/config.py)
- Logging infrastructure (utils/logger.py)
- Time utilities (utils/time_utils.py)
- DataDog API client initialization (utils/datadog_api.py)
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytz


class TestConfig(unittest.TestCase):
    """Tests for configuration loading and validation."""

    def setUp(self):
        """Reset config cache before each test."""
        from utils.config import reset_config_cache
        reset_config_cache()

    def test_config_loads_from_env(self):
        """Test that config loads environment variables correctly."""
        test_env = {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "DATADOG_API_KEY": "test-dd-api-key",
            "DATADOG_APP_KEY": "test-dd-app-key",
            "GITHUB_TOKEN": "test-github-token",
            "DATADOG_SITE": "datadoghq.eu",
            "LOG_LEVEL": "DEBUG",
            "TIMEZONE": "UTC",
        }

        with patch.dict(os.environ, test_env, clear=False):
            from utils.config import load_config
            config = load_config()

            self.assertEqual(config.anthropic_api_key, "test-anthropic-key")
            self.assertEqual(config.datadog_api_key, "test-dd-api-key")
            self.assertEqual(config.datadog_app_key, "test-dd-app-key")
            self.assertEqual(config.github_token, "test-github-token")
            self.assertEqual(config.datadog_site, "datadoghq.eu")
            self.assertEqual(config.log_level, "DEBUG")
            self.assertEqual(config.timezone, "UTC")

    def test_config_uses_defaults(self):
        """Test that config uses defaults for optional variables."""
        test_env = {
            "ANTHROPIC_API_KEY": "test-key",
            "DATADOG_API_KEY": "test-key",
            "DATADOG_APP_KEY": "test-key",
            "GITHUB_TOKEN": "test-key",
        }

        # Clear optional vars
        env_to_clear = ["DATADOG_SITE", "LOG_LEVEL", "TIMEZONE"]
        clean_env = {k: v for k, v in test_env.items()}
        for key in env_to_clear:
            clean_env[key] = ""

        with patch.dict(os.environ, clean_env, clear=False):
            # Remove the keys to test defaults
            with patch.dict(os.environ, {k: "" for k in env_to_clear}):
                os.environ.pop("DATADOG_SITE", None)
                os.environ.pop("LOG_LEVEL", None)
                os.environ.pop("TIMEZONE", None)

                from utils.config import load_config
                config = load_config()

                self.assertEqual(config.datadog_site, "datadoghq.com")
                self.assertEqual(config.log_level, "INFO")
                self.assertEqual(config.timezone, "Asia/Tel_Aviv")

    def test_config_raises_on_missing_required(self):
        """Test that config raises error for missing required variables."""
        from utils.config import load_config, ConfigurationError, reset_config_cache

        # Reset config cache first
        reset_config_cache()

        test_env = {
            "ANTHROPIC_API_KEY": "test-key",
            # Missing DATADOG_API_KEY - set to placeholder value
            "DATADOG_API_KEY": "your_datadog_api_key",  # Placeholder treated as missing
            "DATADOG_APP_KEY": "test-key",
            "GITHUB_TOKEN": "test-key",
        }

        with patch.dict(os.environ, test_env, clear=True):
            with self.assertRaises(ConfigurationError) as context:
                load_config()

            self.assertIn("DATADOG_API_KEY", str(context.exception))

    def test_config_cached_singleton(self):
        """Test that get_cached_config returns same instance."""
        test_env = {
            "ANTHROPIC_API_KEY": "test-key",
            "DATADOG_API_KEY": "test-key",
            "DATADOG_APP_KEY": "test-key",
            "GITHUB_TOKEN": "test-key",
        }

        with patch.dict(os.environ, test_env, clear=False):
            from utils.config import get_cached_config, reset_config_cache
            reset_config_cache()

            config1 = get_cached_config()
            config2 = get_cached_config()

            self.assertIs(config1, config2)


class TestLogger(unittest.TestCase):
    """Tests for logging infrastructure."""

    def setUp(self):
        """Reset logging before each test."""
        from utils.logger import reset_logging
        reset_logging()

    def tearDown(self):
        """Clean up after each test."""
        from utils.logger import reset_logging
        reset_logging()

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        from utils.logger import get_logger
        import logging

        logger = get_logger("test_module")

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_module")

    def test_logger_creates_log_file(self):
        """Test that logger creates log file in correct location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            from utils.logger import configure_logging, get_logger
            configure_logging(log_file=str(log_file))

            logger = get_logger("test")
            logger.info("Test message")

            self.assertTrue(log_file.exists())

    def test_logger_creates_directory(self):
        """Test that logger creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "test.log"

            from utils.logger import configure_logging, get_logger
            configure_logging(log_file=str(log_file))

            logger = get_logger("test")
            logger.info("Test message")

            self.assertTrue(log_file.parent.exists())

    def test_logger_respects_log_level(self):
        """Test that logger respects configured log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            from utils.logger import configure_logging, get_logger
            configure_logging(log_level="ERROR", log_file=str(log_file))

            logger = get_logger("test")
            logger.info("Info message - should not appear")
            logger.error("Error message - should appear")

            with open(log_file) as f:
                content = f.read()

            self.assertNotIn("Info message", content)
            self.assertIn("Error message", content)

    def test_logger_format(self):
        """Test that logger uses correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            from utils.logger import configure_logging, get_logger
            configure_logging(log_file=str(log_file))

            logger = get_logger("test_module")
            logger.info("Test message")

            with open(log_file) as f:
                content = f.read()

            # Check format: [timestamp] [name] [level] message
            self.assertIn("[test_module]", content)
            self.assertIn("[INFO]", content)
            self.assertIn("Test message", content)


class TestTimeUtils(unittest.TestCase):
    """Tests for time utility functions."""

    def test_parse_time_iso8601(self):
        """Test parsing ISO 8601 format."""
        from utils.time_utils import parse_time

        result = parse_time("2026-02-10T14:30:00")

        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 10)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)

    def test_parse_time_human_readable(self):
        """Test parsing human-readable format."""
        from utils.time_utils import parse_time

        result = parse_time("February 10, 2026 2:30 PM")

        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 10)
        self.assertEqual(result.hour, 14)

    def test_tel_aviv_to_utc_naive(self):
        """Test converting naive datetime (assumed Tel Aviv) to UTC."""
        from utils.time_utils import tel_aviv_to_utc

        # Tel Aviv is UTC+2 in winter, UTC+3 in summer
        # February is winter (UTC+2)
        tel_aviv_dt = datetime(2026, 2, 10, 14, 0, 0)  # 14:00 Tel Aviv
        utc_dt = tel_aviv_to_utc(tel_aviv_dt)

        self.assertEqual(utc_dt.hour, 12)  # Should be 12:00 UTC (winter)
        self.assertEqual(utc_dt.tzinfo, pytz.UTC)

    def test_tel_aviv_to_utc_aware(self):
        """Test converting aware datetime to UTC."""
        from utils.time_utils import tel_aviv_to_utc

        tel_aviv_tz = pytz.timezone("Asia/Tel_Aviv")
        tel_aviv_dt = tel_aviv_tz.localize(datetime(2026, 2, 10, 14, 0, 0))
        utc_dt = tel_aviv_to_utc(tel_aviv_dt)

        self.assertEqual(utc_dt.tzinfo, pytz.UTC)

    def test_utc_to_tel_aviv(self):
        """Test converting UTC to Tel Aviv."""
        from utils.time_utils import utc_to_tel_aviv

        utc_dt = pytz.UTC.localize(datetime(2026, 2, 10, 12, 0, 0))  # 12:00 UTC
        tel_aviv_dt = utc_to_tel_aviv(utc_dt)

        self.assertEqual(tel_aviv_dt.hour, 14)  # Should be 14:00 Tel Aviv (winter)

    def test_datetime_to_milliseconds(self):
        """Test converting datetime to Unix milliseconds."""
        from utils.time_utils import datetime_to_milliseconds

        dt = pytz.UTC.localize(datetime(2026, 2, 10, 12, 0, 0))
        ms = datetime_to_milliseconds(dt)

        # Convert back and verify
        from utils.time_utils import milliseconds_to_datetime
        result = milliseconds_to_datetime(ms)

        self.assertEqual(result.year, dt.year)
        self.assertEqual(result.month, dt.month)
        self.assertEqual(result.day, dt.day)
        self.assertEqual(result.hour, dt.hour)
        self.assertEqual(result.minute, dt.minute)

    def test_datetime_to_iso8601(self):
        """Test converting datetime to ISO 8601 string."""
        from utils.time_utils import datetime_to_iso8601

        dt = pytz.UTC.localize(datetime(2026, 2, 10, 14, 30, 0))
        result = datetime_to_iso8601(dt)

        self.assertEqual(result, "2026-02-10T14:30:00Z")

    def test_parse_relative_time_now(self):
        """Test parsing 'now' relative time."""
        from utils.time_utils import parse_relative_time

        before = datetime.now(pytz.UTC)
        result = parse_relative_time("now")
        after = datetime.now(pytz.UTC)

        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_parse_relative_time_hours_ago(self):
        """Test parsing 'now-Xh' relative time."""
        from utils.time_utils import parse_relative_time

        now = datetime.now(pytz.UTC)
        result = parse_relative_time("now-4h")

        expected = now - timedelta(hours=4)
        # Allow 1 second tolerance
        self.assertAlmostEqual(
            result.timestamp(),
            expected.timestamp(),
            delta=1,
        )

    def test_parse_relative_time_days_ago(self):
        """Test parsing 'now-Xd' relative time."""
        from utils.time_utils import parse_relative_time

        now = datetime.now(pytz.UTC)
        result = parse_relative_time("now-7d")

        expected = now - timedelta(days=7)
        self.assertAlmostEqual(
            result.timestamp(),
            expected.timestamp(),
            delta=1,
        )

    def test_calculate_time_window_no_datetime(self):
        """Test calculate_time_window with no datetime (default)."""
        from utils.time_utils import calculate_time_window

        from_time, to_time = calculate_time_window(None)

        self.assertEqual(from_time, "now-4h")
        self.assertEqual(to_time, "now")

    def test_calculate_time_window_with_datetime(self):
        """Test calculate_time_window with user datetime."""
        from utils.time_utils import calculate_time_window

        # Use a past time to avoid future cap
        user_dt = datetime(2026, 1, 10, 12, 0, 0)  # Naive, assumed Tel Aviv
        from_time, to_time = calculate_time_window(user_dt)

        # Should be ISO 8601 strings
        self.assertTrue(from_time.endswith("Z"))
        self.assertTrue(to_time.endswith("Z"))

        # Parse and verify window is +/- 2 hours
        from utils.time_utils import parse_relative_time
        from_dt = parse_relative_time(from_time)
        to_dt = parse_relative_time(to_time)

        window = to_dt - from_dt
        # Window should be at most 4 hours (could be less if capped at now)
        self.assertLessEqual(window.total_seconds(), 4 * 3600 + 1)

    def test_expand_time_window_level1_no_datetime(self):
        """Test expand_time_window level 1 without datetime."""
        from utils.time_utils import expand_time_window

        from_time, to_time = expand_time_window("now-4h", "now", 1, None)

        self.assertEqual(from_time, "now-24h")
        self.assertEqual(to_time, "now")

    def test_expand_time_window_level2_no_datetime(self):
        """Test expand_time_window level 2 without datetime."""
        from utils.time_utils import expand_time_window

        from_time, to_time = expand_time_window("now-24h", "now", 2, None)

        self.assertEqual(from_time, "now-7d")
        self.assertEqual(to_time, "now")

    def test_expand_time_window_invalid_level(self):
        """Test expand_time_window with invalid level raises error."""
        from utils.time_utils import expand_time_window

        with self.assertRaises(ValueError):
            expand_time_window("now-4h", "now", 3, None)

    def test_time_window_never_future(self):
        """Test that time windows are never expanded into the future."""
        from utils.time_utils import calculate_time_window, expand_time_window, parse_relative_time

        # Use current time as user datetime
        now = datetime.now(pytz.UTC)

        # Test calculate_time_window
        from_time, to_time = calculate_time_window(now.replace(tzinfo=None))
        to_dt = parse_relative_time(to_time)
        self.assertLessEqual(to_dt, datetime.now(pytz.UTC) + timedelta(seconds=5))

        # Test expand_time_window level 1
        from_time, to_time = expand_time_window(
            "now-4h", "now", 1, now.replace(tzinfo=None)
        )
        to_dt = parse_relative_time(to_time)
        self.assertLessEqual(to_dt, datetime.now(pytz.UTC) + timedelta(seconds=5))


class TestDataDogAPI(unittest.TestCase):
    """Tests for DataDog API client."""

    def test_client_initialization(self):
        """Test that DataDog client initializes correctly."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(
            api_key="test-api-key",
            app_key="test-app-key",
            site="datadoghq.eu",
        )

        self.assertEqual(client.api_key, "test-api-key")
        self.assertEqual(client.app_key, "test-app-key")
        self.assertEqual(client.base_url, "https://api.datadoghq.eu")

    def test_client_default_site(self):
        """Test that client uses default site."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(
            api_key="test-api-key",
            app_key="test-app-key",
        )

        self.assertEqual(client.base_url, "https://api.datadoghq.com")

    def test_client_headers(self):
        """Test that client sets correct headers."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(
            api_key="test-api-key",
            app_key="test-app-key",
        )

        self.assertEqual(client.headers["DD-API-KEY"], "test-api-key")
        self.assertEqual(client.headers["DD-APPLICATION-KEY"], "test-app-key")
        self.assertEqual(client.headers["Content-Type"], "application/json")
        self.assertEqual(client.headers["Accept"], "application/json")

    def test_build_log_message_query(self):
        """Test building query for log message search."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")
        query = client.build_log_message_query("Error processing request")

        self.assertIn("env:prod", query)
        self.assertIn("pod_label_team:card", query)
        self.assertIn('"Error processing request"', query)

    def test_build_identifiers_query(self):
        """Test building query for identifiers search."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")
        query = client.build_identifiers_query(["12345", "67890", "ABC123"])

        self.assertIn("env:prod", query)
        self.assertIn("pod_label_team:card", query)
        self.assertIn("12345", query)
        self.assertIn("67890", query)
        self.assertIn("ABC123", query)
        self.assertIn(" OR ", query)

    def test_build_efilogid_query(self):
        """Test building query for efilogid search."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")
        query = client.build_efilogid_query("test-session-id")

        self.assertEqual(query, '@efilogid:\\"test-session-id\\"')

    def test_extract_log_data(self):
        """Test extracting log data from API response."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        # Mock response structure (based on design doc)
        mock_response = {
            "data": [
                {
                    "id": "log-id-1",
                    "type": "log",
                    "attributes": {
                        "service": "card-invitation-service",
                        "message": "Test log message",
                        "status": "info",
                        "timestamp": "2026-02-10T19:03:43.990Z",
                        "attributes": {
                            "dd": {
                                "service": "card-invitation-service",
                                "env": "prod",
                                "version": "08b9cd7acf38ddf65e3e470bbb27137fe682323e___618",
                            },
                            "efilogid": "-1-OTQ1NWU2MzEtNGQwNC00ZTE4LWE1Y2ItM2M3OGNkMmE4OGUw",
                            "logger_name": "com.sunbit.card.invitation.lead.application.EntitledCustomerService",
                        },
                    },
                }
            ]
        }

        extracted = client.extract_log_data(mock_response)

        self.assertEqual(len(extracted), 1)
        log = extracted[0]
        self.assertEqual(log["id"], "log-id-1")
        self.assertEqual(log["service"], "card-invitation-service")
        self.assertEqual(log["message"], "Test log message")
        self.assertEqual(
            log["dd_version"],
            "08b9cd7acf38ddf65e3e470bbb27137fe682323e___618"
        )
        self.assertEqual(
            log["efilogid"],
            "-1-OTQ1NWU2MzEtNGQwNC00ZTE4LWE1Y2ItM2M3OGNkMmE4OGUw"
        )
        self.assertEqual(
            log["logger_name"],
            "com.sunbit.card.invitation.lead.application.EntitledCustomerService"
        )

    def test_log_entry_dataclass(self):
        """Test LogEntry dataclass structure."""
        from utils.datadog_api import LogEntry

        entry = LogEntry(
            id="test-id",
            message="Test message",
            service="test-service",
            efilogid="test-efi",
            dd_version="abc123___100",
            logger_name="com.example.Test",
            timestamp="2026-02-10T12:00:00Z",
            status="info",
        )

        self.assertEqual(entry.id, "test-id")
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.service, "test-service")

    def test_search_result_dataclass(self):
        """Test SearchResult dataclass structure."""
        from utils.datadog_api import SearchResult, LogEntry

        log = LogEntry(id="1", message="test")
        result = SearchResult(
            logs=[log],
            total_count=1,
            unique_services={"service1"},
            unique_efilogids={"efi1"},
        )

        self.assertEqual(result.total_count, 1)
        self.assertIn("service1", result.unique_services)
        self.assertIn("efi1", result.unique_efilogids)


class TestDataDogAPIErrors(unittest.TestCase):
    """Tests for DataDog API error handling."""

    def test_auth_error_exception(self):
        """Test that DataDogAuthError is properly defined."""
        from utils.datadog_api import DataDogAuthError, DataDogAPIError

        error = DataDogAuthError("Test auth error")
        self.assertIsInstance(error, DataDogAPIError)
        self.assertEqual(str(error), "Test auth error")

    def test_rate_limit_error_exception(self):
        """Test that DataDogRateLimitError is properly defined."""
        from utils.datadog_api import DataDogRateLimitError, DataDogAPIError

        error = DataDogRateLimitError("Rate limit exceeded")
        self.assertIsInstance(error, DataDogAPIError)

    def test_timeout_error_exception(self):
        """Test that DataDogTimeoutError is properly defined."""
        from utils.datadog_api import DataDogTimeoutError, DataDogAPIError

        error = DataDogTimeoutError("Request timed out")
        self.assertIsInstance(error, DataDogAPIError)


if __name__ == "__main__":
    unittest.main()
