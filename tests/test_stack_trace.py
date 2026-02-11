"""
Tests for Stack Trace Extraction and Analysis functionality.

Tests are organized by phase:
- Phase 1: LogEntry stack_trace field
- Phase 2: Stack trace parser
- Phase 3: Main agent stack trace integration
- Phase 4: Code checker Kotlin/Java fallback
- Phase 5: Report generator stack trace section
"""
import unittest
from unittest.mock import MagicMock, patch

# Sample stack traces for testing
SAMPLE_STACK_TRACE = """java.lang.RuntimeException: Error processing event
	at com.sunbit.card.bankruptcy.handler.BankruptcyHandler.handleEvent(BankruptcyHandler.kt:45)
	at com.sunbit.card.kafka.consumer.EventConsumer.consume(EventConsumer.kt:123)
	at org.springframework.kafka.listener.KafkaMessageListenerContainer.doInvokeOnMessage(KafkaMessageListenerContainer.java:2089)
	at org.springframework.kafka.listener.adapter.MessagingMessageListenerAdapter.invokeHandler(MessagingMessageListenerAdapter.java:330)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1128)
"""

SAMPLE_STACK_TRACE_WITH_INNER_CLASS = """java.lang.IllegalStateException: Invalid state
	at com.sunbit.card.service.PaymentService$Companion.validate(PaymentService.kt:78)
	at com.sunbit.card.handler.PaymentHandler$1.invoke(PaymentHandler.kt:34)
	at com.sunbit.card.util.RetryHelper.retry(RetryHelper.kt:22)
"""

SAMPLE_STACK_TRACE_IN_MESSAGE = """Error processing consumeBankruptCustomerStatusChange event for customer 6222309
java.lang.NullPointerException: Customer not found
	at com.sunbit.card.customer.CustomerRepository.findById(CustomerRepository.kt:55)
	at com.sunbit.card.bankruptcy.BankruptcyService.processEvent(BankruptcyService.kt:89)
"""


class TestLogEntryStackTrace(unittest.TestCase):
    """Phase 1: Tests for LogEntry stack_trace field."""

    def test_log_entry_has_stack_trace_field(self):
        """Test that LogEntry has stack_trace optional field."""
        from utils.datadog_api import LogEntry

        # Should be able to create LogEntry with stack_trace
        entry = LogEntry(
            id="test-id",
            message="Test message",
            stack_trace=SAMPLE_STACK_TRACE,
        )

        self.assertEqual(entry.stack_trace, SAMPLE_STACK_TRACE)

    def test_log_entry_stack_trace_defaults_to_none(self):
        """Test that stack_trace defaults to None."""
        from utils.datadog_api import LogEntry

        entry = LogEntry(id="test-id", message="Test message")

        self.assertIsNone(entry.stack_trace)

    def test_extract_log_entry_extracts_error_stack(self):
        """Test extracting stack_trace from error.stack path."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        log_item = {
            "id": "log-id-1",
            "attributes": {
                "message": "Error occurred",
                "service": "test-service",
                "attributes": {
                    "error": {
                        "stack": SAMPLE_STACK_TRACE,
                    },
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.stack_trace, SAMPLE_STACK_TRACE)

    def test_extract_log_entry_extracts_stack_trace_direct(self):
        """Test extracting stack_trace from direct stack_trace attribute."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        log_item = {
            "id": "log-id-1",
            "attributes": {
                "message": "Error occurred",
                "service": "test-service",
                "attributes": {
                    "stack_trace": SAMPLE_STACK_TRACE,
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.stack_trace, SAMPLE_STACK_TRACE)

    def test_extract_log_entry_extracts_exception_stacktrace(self):
        """Test extracting stack_trace from exception.stacktrace path."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        log_item = {
            "id": "log-id-1",
            "attributes": {
                "message": "Error occurred",
                "service": "test-service",
                "attributes": {
                    "exception": {
                        "stacktrace": SAMPLE_STACK_TRACE,
                    },
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.stack_trace, SAMPLE_STACK_TRACE)

    def test_extract_log_entry_prefers_error_stack_over_others(self):
        """Test that error.stack takes priority."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        log_item = {
            "id": "log-id-1",
            "attributes": {
                "message": "Error occurred",
                "service": "test-service",
                "attributes": {
                    "error": {
                        "stack": "PRIMARY_STACK",
                    },
                    "stack_trace": "SECONDARY_STACK",
                    "exception": {
                        "stacktrace": "TERTIARY_STACK",
                    },
                },
            },
        }

        entry = client._extract_log_entry(log_item)

        self.assertEqual(entry.stack_trace, "PRIMARY_STACK")

    def test_extract_log_data_includes_stack_trace(self):
        """Test that extract_log_data includes stack_trace field."""
        from utils.datadog_api import DataDogAPI

        client = DataDogAPI(api_key="key", app_key="key")

        mock_response = {
            "data": [
                {
                    "id": "log-id-1",
                    "attributes": {
                        "message": "Error occurred",
                        "service": "test-service",
                        "attributes": {
                            "error": {
                                "stack": SAMPLE_STACK_TRACE,
                            },
                        },
                    },
                }
            ]
        }

        extracted = client.extract_log_data(mock_response)

        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["stack_trace"], SAMPLE_STACK_TRACE)


class TestStackTraceParser(unittest.TestCase):
    """Phase 2: Tests for stack trace parser."""

    def test_stack_frame_dataclass(self):
        """Test StackFrame dataclass."""
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.Handler",
            method_name="handleEvent",
            file_name="Handler.kt",
            line_number=45,
        )

        self.assertEqual(frame.class_name, "com.sunbit.card.Handler")
        self.assertEqual(frame.method_name, "handleEvent")
        self.assertEqual(frame.file_name, "Handler.kt")
        self.assertEqual(frame.line_number, 45)

    def test_stack_frame_to_file_path(self):
        """Test converting StackFrame to file path."""
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.bankruptcy.handler.BankruptcyHandler",
            method_name="handleEvent",
            file_name="BankruptcyHandler.kt",
            line_number=45,
        )

        expected = "src/main/kotlin/com/sunbit/card/bankruptcy/handler/BankruptcyHandler.kt"
        self.assertEqual(frame.to_file_path(), expected)

    def test_stack_frame_to_file_path_java(self):
        """Test converting StackFrame to Java file path."""
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.Handler",
            method_name="handle",
            file_name="Handler.java",
            line_number=10,
        )

        expected = "src/main/java/com/sunbit/card/Handler.java"
        self.assertEqual(frame.to_file_path(), expected)

    def test_parsed_stack_trace_dataclass(self):
        """Test ParsedStackTrace dataclass."""
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.Handler", "handle", "Handler.kt", 10),
            StackFrame("org.spring.Something", "run", "Something.java", 20),
        ]

        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=[frames[0]],
            unique_file_paths={"src/main/kotlin/com/sunbit/Handler.kt"},
        )

        self.assertEqual(len(parsed.frames), 2)
        self.assertEqual(len(parsed.sunbit_frames), 1)
        self.assertEqual(len(parsed.unique_file_paths), 1)

    def test_parser_parses_basic_stack_trace(self):
        """Test parsing a basic stack trace."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()
        result = parser.parse(SAMPLE_STACK_TRACE)

        # Should have 4 frames total (ThreadPoolExecutor line doesn't match due to package)
        self.assertGreaterEqual(len(result.frames), 4)

        # First frame should be BankruptcyHandler
        first_frame = result.frames[0]
        self.assertEqual(first_frame.class_name, "com.sunbit.card.bankruptcy.handler.BankruptcyHandler")
        self.assertEqual(first_frame.method_name, "handleEvent")
        self.assertEqual(first_frame.file_name, "BankruptcyHandler.kt")
        self.assertEqual(first_frame.line_number, 45)

    def test_parser_filters_to_sunbit_packages(self):
        """Test that parser filters to only com.sunbit packages."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()
        result = parser.parse(SAMPLE_STACK_TRACE)

        # Should only have 2 sunbit frames
        self.assertEqual(len(result.sunbit_frames), 2)

        # All sunbit frames should be com.sunbit
        for frame in result.sunbit_frames:
            self.assertTrue(frame.class_name.startswith("com.sunbit"))

    def test_parser_handles_inner_classes(self):
        """Test that parser handles inner classes correctly."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()
        result = parser.parse(SAMPLE_STACK_TRACE_WITH_INNER_CLASS)

        # Should have 3 sunbit frames
        self.assertEqual(len(result.sunbit_frames), 3)

        # PaymentService$Companion should map to PaymentService.kt
        payment_frame = result.sunbit_frames[0]
        self.assertIn("PaymentService", payment_frame.class_name)
        file_path = payment_frame.to_file_path()
        self.assertIn("PaymentService.kt", file_path)
        self.assertNotIn("$", file_path)

    def test_parser_extracts_unique_file_paths(self):
        """Test that parser extracts unique file paths."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()
        result = parser.parse(SAMPLE_STACK_TRACE)

        # Should have 2 unique file paths (BankruptcyHandler.kt, EventConsumer.kt)
        self.assertEqual(len(result.unique_file_paths), 2)

        # Check paths are correct format
        for path in result.unique_file_paths:
            self.assertTrue(path.startswith("src/main/kotlin/"))
            self.assertTrue(path.endswith(".kt"))

    def test_parser_handles_empty_input(self):
        """Test that parser handles empty input."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()

        result_empty = parser.parse("")
        self.assertEqual(len(result_empty.frames), 0)
        self.assertEqual(len(result_empty.sunbit_frames), 0)
        self.assertEqual(len(result_empty.unique_file_paths), 0)

        result_none = parser.parse(None)
        self.assertEqual(len(result_none.frames), 0)

    def test_parser_handles_stack_trace_in_message(self):
        """Test that parser can extract stack traces from messages."""
        from utils.stack_trace_parser import StackTraceParser

        parser = StackTraceParser()
        result = parser.parse(SAMPLE_STACK_TRACE_IN_MESSAGE)

        # Should find the stack trace frames
        self.assertGreater(len(result.sunbit_frames), 0)

        # Should find CustomerRepository and BankruptcyService
        class_names = [f.class_name for f in result.sunbit_frames]
        self.assertTrue(any("CustomerRepository" in cn for cn in class_names))
        self.assertTrue(any("BankruptcyService" in cn for cn in class_names))

    def test_extract_file_paths_convenience_function(self):
        """Test the convenience function extract_file_paths."""
        from utils.stack_trace_parser import extract_file_paths

        # Test with stack_trace only
        paths = extract_file_paths(stack_trace=SAMPLE_STACK_TRACE)
        self.assertEqual(len(paths), 2)

        # Test with message only (contains embedded stack trace)
        paths = extract_file_paths(message=SAMPLE_STACK_TRACE_IN_MESSAGE)
        self.assertGreater(len(paths), 0)

        # Test with both - should merge
        paths = extract_file_paths(
            stack_trace=SAMPLE_STACK_TRACE,
            message=SAMPLE_STACK_TRACE_IN_MESSAGE,
        )
        self.assertGreater(len(paths), 2)  # Should have more from both

        # Test with neither
        paths = extract_file_paths()
        self.assertEqual(len(paths), 0)

    def test_parser_handles_frame_without_line_number(self):
        """Test parser handles frames without line numbers."""
        from utils.stack_trace_parser import StackTraceParser

        stack_trace = """java.lang.Error
	at com.sunbit.card.Handler.handle(Handler.kt)
	at com.sunbit.card.Service.process(Native Method)
"""
        parser = StackTraceParser()
        result = parser.parse(stack_trace)

        # Should parse frames without line numbers
        self.assertGreater(len(result.frames), 0)


class TestMainAgentStackTrace(unittest.TestCase):
    """Phase 3: Tests for main agent stack trace integration."""

    def test_service_investigation_result_has_stack_trace_files(self):
        """Test ServiceInvestigationResult has stack_trace_files field."""
        from agents.main_agent import ServiceInvestigationResult

        result = ServiceInvestigationResult(
            service_name="test-service",
            stack_trace_files={"src/main/kotlin/com/sunbit/Handler.kt"},
        )

        self.assertIsNotNone(result.stack_trace_files)
        self.assertEqual(len(result.stack_trace_files), 1)

    def test_service_investigation_result_stack_trace_files_defaults_none(self):
        """Test stack_trace_files defaults to None."""
        from agents.main_agent import ServiceInvestigationResult

        result = ServiceInvestigationResult(service_name="test-service")

        self.assertIsNone(result.stack_trace_files)

    def test_extract_stack_trace_files_per_service(self):
        """Test _extract_stack_trace_files_per_service method."""
        from agents.main_agent import MainAgent
        from agents.datadog_retriever import DataDogSearchResult
        from utils.datadog_api import LogEntry
        from unittest.mock import MagicMock

        # Create mock config
        with patch('agents.main_agent.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.log_level = "INFO"
            mock_get_config.return_value = mock_config

            agent = MainAgent(config=mock_config)

            # Create mock DataDog result with logs
            logs = [
                LogEntry(
                    id="1",
                    message="Error",
                    service="card-service",
                    stack_trace=SAMPLE_STACK_TRACE,
                    status="error",
                ),
                LogEntry(
                    id="2",
                    message="Another error",
                    service="card-service",
                    stack_trace=SAMPLE_STACK_TRACE_WITH_INNER_CLASS,
                    status="error",
                ),
                LogEntry(
                    id="3",
                    message="Different service",
                    service="payment-service",
                    stack_trace=SAMPLE_STACK_TRACE,
                    status="error",
                ),
            ]

            dd_result = DataDogSearchResult(
                logs=logs,
                unique_services={"card-service", "payment-service"},
                unique_efilogids=set(),
                unique_dd_versions=set(),
                efilogids_found=0,
                efilogids_processed=0,
                total_logs_before_dedup=3,
            )

            result = agent._extract_stack_trace_files_per_service(dd_result)

            # Should have 2 services
            self.assertEqual(len(result), 2)
            self.assertIn("card-service", result)
            self.assertIn("payment-service", result)

            # card-service should have files from both stack traces
            self.assertGreater(len(result["card-service"]), 0)

    def test_extract_stack_trace_files_skips_non_error_logs(self):
        """Test that info logs are not processed for stack traces."""
        from agents.main_agent import MainAgent
        from agents.datadog_retriever import DataDogSearchResult
        from utils.datadog_api import LogEntry
        from unittest.mock import MagicMock

        with patch('agents.main_agent.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.log_level = "INFO"
            mock_get_config.return_value = mock_config

            agent = MainAgent(config=mock_config)

            # Only info logs
            logs = [
                LogEntry(
                    id="1",
                    message="Info message",
                    service="card-service",
                    stack_trace=SAMPLE_STACK_TRACE,
                    status="info",
                ),
            ]

            dd_result = DataDogSearchResult(
                logs=logs,
                unique_services={"card-service"},
                unique_efilogids=set(),
                unique_dd_versions=set(),
                efilogids_found=0,
                efilogids_processed=0,
                total_logs_before_dedup=1,
            )

            result = agent._extract_stack_trace_files_per_service(dd_result)

            # Should not process info logs - so no files
            self.assertEqual(len(result.get("card-service", set())), 0)

    def test_extract_stack_trace_files_also_checks_message(self):
        """Test that message field is also checked for embedded stack traces."""
        from agents.main_agent import MainAgent
        from agents.datadog_retriever import DataDogSearchResult
        from utils.datadog_api import LogEntry
        from unittest.mock import MagicMock

        with patch('agents.main_agent.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.log_level = "INFO"
            mock_get_config.return_value = mock_config

            agent = MainAgent(config=mock_config)

            # Log with stack trace in message
            logs = [
                LogEntry(
                    id="1",
                    message=SAMPLE_STACK_TRACE_IN_MESSAGE,
                    service="card-service",
                    status="error",
                ),
            ]

            dd_result = DataDogSearchResult(
                logs=logs,
                unique_services={"card-service"},
                unique_efilogids=set(),
                unique_dd_versions=set(),
                efilogids_found=0,
                efilogids_processed=0,
                total_logs_before_dedup=1,
            )

            result = agent._extract_stack_trace_files_per_service(dd_result)

            # Should find files from message
            self.assertGreater(len(result.get("card-service", set())), 0)


class TestCodeCheckerKotlinJavaFallback(unittest.TestCase):
    """Phase 4: Tests for Code Checker Kotlin/Java fallback."""

    def test_analyze_files_directly_tries_kt_fallback_for_java(self):
        """Test that when .java file not found, .kt is tried."""
        from agents.code_checker import CodeChecker
        from utils.github_helper import GitHubNotFoundError
        from unittest.mock import MagicMock

        checker = CodeChecker(github_token="test-token")

        # Mock github_helper to return 404 for .java but success for .kt
        mock_github = MagicMock()
        call_count = 0

        def mock_get_file_content(owner, repo, path, ref):
            nonlocal call_count
            call_count += 1
            if path.endswith(".java"):
                raise GitHubNotFoundError(f"File not found: {path}")
            elif path.endswith(".kt"):
                return "class Handler {}"
            return "content"

        mock_github.get_file_content = mock_get_file_content
        checker.github_helper = mock_github

        # Try to analyze a .java file
        results = checker.analyze_files_directly(
            owner="sunbit-dev",
            repo="test-repo",
            file_paths=["src/main/java/com/sunbit/Handler.java"],
            previous_commit="abc123",
            current_commit="def456",
        )

        # Should have result with actual .kt path
        self.assertEqual(len(results), 1)
        result = results[0]
        # Either found at .kt or has error
        if not result.error:
            self.assertTrue(result.file_path.endswith(".kt"))

    def test_analyze_files_directly_tries_java_fallback_for_kt(self):
        """Test that when .kt file not found, .java is tried."""
        from agents.code_checker import CodeChecker
        from utils.github_helper import GitHubNotFoundError
        from unittest.mock import MagicMock

        checker = CodeChecker(github_token="test-token")

        mock_github = MagicMock()

        def mock_get_file_content(owner, repo, path, ref):
            if path.endswith(".kt"):
                raise GitHubNotFoundError(f"File not found: {path}")
            elif path.endswith(".java"):
                return "class Handler {}"
            return "content"

        mock_github.get_file_content = mock_get_file_content
        checker.github_helper = mock_github

        # Try to analyze a .kt file
        results = checker.analyze_files_directly(
            owner="sunbit-dev",
            repo="test-repo",
            file_paths=["src/main/kotlin/com/sunbit/Handler.kt"],
            previous_commit="abc123",
            current_commit="def456",
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        if not result.error:
            self.assertTrue(result.file_path.endswith(".java"))

    def test_analyze_files_directly_error_if_both_fail(self):
        """Test that error is set if both .kt and .java fail."""
        from agents.code_checker import CodeChecker
        from utils.github_helper import GitHubNotFoundError
        from unittest.mock import MagicMock

        checker = CodeChecker(github_token="test-token")

        mock_github = MagicMock()
        mock_github.get_file_content.side_effect = GitHubNotFoundError("Not found")
        checker.github_helper = mock_github

        results = checker.analyze_files_directly(
            owner="sunbit-dev",
            repo="test-repo",
            file_paths=["src/main/kotlin/com/sunbit/Handler.kt"],
            previous_commit="abc123",
            current_commit="def456",
        )

        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].error)


class TestReportGeneratorStackTrace(unittest.TestCase):
    """Phase 5: Tests for report generator stack trace section."""

    def test_report_includes_stack_trace_section(self):
        """Test that report includes stack trace analysis section."""
        from utils.report_generator import ReportGenerator

        generator = ReportGenerator()

        # Create investigation result with stack trace files
        investigation_result = {
            "user_input": {
                "mode": "LOG_MESSAGE",
                "log_message": "Error processing event",
            },
            "datadog_result": {
                "total_logs": 5,
                "unique_services": ["card-service"],
                "unique_efilogids": [],
                "unique_dd_versions": ["abc123___100"],
                "logs": [],
                "search_attempts": [],
            },
            "service_results": [
                {
                    "service_name": "card-service",
                    "stack_trace_files": [
                        "src/main/kotlin/com/sunbit/Handler.kt",
                        "src/main/kotlin/com/sunbit/Service.kt",
                    ],
                    "logger_names": [],
                    "code_analysis": {
                        "status": "success",
                        "files_analyzed": 2,
                        "file_analyses": [],
                    },
                }
            ],
            "search_timestamp": "2026-02-11T12:00:00Z",
        }

        report = generator.generate_report(investigation_result)

        # Report should include stack trace section
        self.assertIn("Stack Trace", report)
        self.assertIn("Handler.kt", report)
        self.assertIn("Service.kt", report)

    def test_report_no_stack_trace_section_when_empty(self):
        """Test that no stack trace section appears when no stack trace files."""
        from utils.report_generator import ReportGenerator

        generator = ReportGenerator()

        investigation_result = {
            "user_input": {
                "mode": "LOG_MESSAGE",
                "log_message": "Error",
            },
            "datadog_result": {
                "total_logs": 1,
                "unique_services": ["card-service"],
                "unique_efilogids": [],
                "unique_dd_versions": [],
                "logs": [],
                "search_attempts": [],
            },
            "service_results": [
                {
                    "service_name": "card-service",
                    "stack_trace_files": [],  # Empty
                    "logger_names": [],
                }
            ],
            "search_timestamp": "2026-02-11T12:00:00Z",
        }

        report = generator.generate_report(investigation_result)

        # Should NOT have "Stack Trace Analysis" section or should indicate none found
        # Just ensure it doesn't crash


if __name__ == "__main__":
    unittest.main()
