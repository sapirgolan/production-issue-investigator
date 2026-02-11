"""
Additional tests for Report Generator to reach 80% coverage.

Tests cover:
- _normalize_service_results (dict and list formats)
- _generate_issue_title (various modes)
- _generate_header (with different inputs)
- _generate_executive_summary (with various scenarios)
- _format_timeline (with events)
- _format_services_section (with services data)
- _determine_root_cause (high/medium issues, deployments)
- _format_root_cause_section (identified/not identified)
- _propose_fix (various fix types)
- _format_files_to_modify
- _format_investigation_details
- _format_notes
- generate_report convenience function
"""
import unittest
from datetime import datetime
from utils.report_generator import ReportGenerator, generate_report
from utils.time_utils import UTC_TZ


class TestNormalizeServiceResults(unittest.TestCase):
    """Tests for _normalize_service_results method."""

    def test_normalize_dict_format(self):
        """Test normalizing dict format to list."""
        generator = ReportGenerator()

        service_results_dict = {
            "card-service": {"deployment_result": {"deployments": []}},
            "payment-service": {"code_analysis": {"files_analyzed": 2}},
        }

        result = generator._normalize_service_results(service_results_dict)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        # Check service_name was added
        service_names = [r.get("service_name") for r in result]
        self.assertIn("card-service", service_names)
        self.assertIn("payment-service", service_names)

    def test_normalize_list_format_unchanged(self):
        """Test list format passes through unchanged."""
        generator = ReportGenerator()

        service_results_list = [
            {"service_name": "card-service", "deployment_result": {}},
            {"service_name": "payment-service", "code_analysis": {}},
        ]

        result = generator._normalize_service_results(service_results_list)

        self.assertEqual(result, service_results_list)

    def test_normalize_invalid_type_returns_empty(self):
        """Test invalid type returns empty list."""
        generator = ReportGenerator()

        result = generator._normalize_service_results("invalid")
        self.assertEqual(result, [])

        result = generator._normalize_service_results(None)
        self.assertEqual(result, [])


class TestGenerateIssueTitle(unittest.TestCase):
    """Tests for _generate_issue_title method."""

    def test_log_message_mode_short(self):
        """Test LOG_MESSAGE mode with short message."""
        generator = ReportGenerator()

        user_input = {"mode": "LOG_MESSAGE", "log_message": "Error in payment"}
        datadog_result = {}

        title = generator._generate_issue_title(user_input, datadog_result)

        self.assertEqual(title, "Error in payment")

    def test_log_message_mode_truncated(self):
        """Test LOG_MESSAGE mode with long message gets truncated."""
        generator = ReportGenerator()

        user_input = {
            "mode": "LOG_MESSAGE",
            "log_message": "This is a very long error message that exceeds the maximum title length allowed",
        }
        datadog_result = {}

        title = generator._generate_issue_title(user_input, datadog_result)

        self.assertEqual(len(title), 60)
        self.assertTrue(title.endswith("..."))

    def test_identifiers_mode_with_services(self):
        """Test IDENTIFIERS mode with services."""
        generator = ReportGenerator()

        user_input = {"mode": "IDENTIFIERS", "identifiers": ["12345", "67890"]}
        datadog_result = {"unique_services": ["card-service", "payment-service"]}

        title = generator._generate_issue_title(user_input, datadog_result)

        self.assertIn("card-service", title)

    def test_identifiers_mode_with_only_ids(self):
        """Test IDENTIFIERS mode without services uses identifiers."""
        generator = ReportGenerator()

        user_input = {"mode": "IDENTIFIERS", "identifiers": ["CID-12345", "TXN-67890"]}
        datadog_result = {"unique_services": []}

        title = generator._generate_issue_title(user_input, datadog_result)

        self.assertIn("CID-12345", title)

    def test_unknown_mode_default_title(self):
        """Test unknown mode returns default title."""
        generator = ReportGenerator()

        user_input = {"mode": "UNKNOWN"}
        datadog_result = {}

        title = generator._generate_issue_title(user_input, datadog_result)

        self.assertEqual(title, "Production Issue Investigation")


class TestGenerateHeader(unittest.TestCase):
    """Tests for _generate_header method."""

    def test_header_log_message_mode(self):
        """Test header generation for LOG_MESSAGE mode."""
        generator = ReportGenerator()

        user_input = {"mode": "LOG_MESSAGE", "log_message": "Test error"}
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC_TZ)

        header = generator._generate_header("Test Issue", user_input, timestamp)

        self.assertIn("# Investigation Report: Test Issue", header)
        self.assertIn("**Issue**: Test error", header)
        self.assertIn("2024-01-15", header)

    def test_header_identifiers_mode(self):
        """Test header generation for IDENTIFIERS mode."""
        generator = ReportGenerator()

        user_input = {
            "mode": "IDENTIFIERS",
            "issue_description": "Payment failed",
            "identifiers": ["TXN-123", "TXN-456"],
        }
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC_TZ)

        header = generator._generate_header("Issue", user_input, timestamp)

        self.assertIn("Payment failed", header)
        self.assertIn("TXN-123", header)

    def test_header_with_string_timestamp(self):
        """Test header with string timestamp (gets parsed)."""
        generator = ReportGenerator()

        user_input = {"mode": "LOG_MESSAGE", "log_message": "Error"}
        timestamp = "now-1h"  # Relative time string

        header = generator._generate_header("Issue", user_input, timestamp)

        self.assertIn("# Investigation Report:", header)


class TestGenerateExecutiveSummary(unittest.TestCase):
    """Tests for _generate_executive_summary method."""

    def test_summary_with_logs_and_root_cause(self):
        """Test summary with logs found and root cause identified."""
        generator = ReportGenerator()

        datadog_result = {
            "total_logs": 25,
            "unique_services": ["card-service", "payment-service"],
        }
        service_results = [{"deployment_result": {"deployments": [{"timestamp": "2024-01-15"}]}}]
        root_cause = {
            "identified": True,
            "confidence": "HIGH",
            "primary_cause": "Null pointer in Handler",
            "fix_available": True,
        }

        summary = generator._generate_executive_summary(datadog_result, service_results, root_cause)

        self.assertIn("25 log entries", summary)
        self.assertIn("2 service(s)", summary)
        self.assertIn("HIGH confidence", summary)
        self.assertIn("proposed fix", summary)

    def test_summary_no_logs_found(self):
        """Test summary when no logs found."""
        generator = ReportGenerator()

        datadog_result = {"total_logs": 0, "unique_services": []}
        service_results = []
        root_cause = {"identified": False}

        summary = generator._generate_executive_summary(datadog_result, service_results, root_cause)

        self.assertIn("No relevant logs found", summary)

    def test_summary_with_issues_but_no_root_cause(self):
        """Test summary with issues but no definitive root cause."""
        generator = ReportGenerator()

        datadog_result = {"total_logs": 10, "unique_services": ["card-service"]}
        service_results = [{"code_analysis": {"total_issues_found": 3}}]
        root_cause = {"identified": False}

        summary = generator._generate_executive_summary(datadog_result, service_results, root_cause)

        self.assertIn("3 potential issues", summary)


class TestFormatTimeline(unittest.TestCase):
    """Tests for _format_timeline method."""

    def test_timeline_with_events(self):
        """Test timeline with deployment and error events."""
        generator = ReportGenerator()

        investigation_result = {
            "datadog_result": {
                "search_attempts": [{"from_time": "now-4h", "to_time": "now"}],
                "logs": [
                    {
                        "status": "error",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "service": "card-service",
                        "message": "Error processing payment",
                    }
                ],
            },
            "service_results": [
                {
                    "service_name": "card-service",
                    "deployment_result": {
                        "deployments": [
                            {
                                "deployment_timestamp": "2024-01-15T08:00:00Z",
                                "application_commit_hash": "abc123def456",
                            }
                        ]
                    },
                }
            ],
        }

        timeline = generator._format_timeline(investigation_result)

        self.assertIn("## Timeline", timeline)
        self.assertIn("Deployment", timeline)
        self.assertIn("Error Logged", timeline)
        self.assertIn("card-service", timeline)

    def test_timeline_no_events(self):
        """Test timeline with no events."""
        generator = ReportGenerator()

        investigation_result = {
            "datadog_result": {"logs": []},
            "service_results": [],
        }

        timeline = generator._format_timeline(investigation_result)

        self.assertIn("No timeline events to display", timeline)


class TestFormatServicesSection(unittest.TestCase):
    """Tests for _format_services_section method."""

    def test_services_section_with_data(self):
        """Test services section with services data."""
        generator = ReportGenerator()

        datadog_result = {
            "unique_services": ["card-service", "payment-service"],
            "logs": [
                {"service": "card-service"},
                {"service": "card-service"},
                {"service": "payment-service"},
            ],
        }
        service_results = [
            {
                "service_name": "card-service",
                "deployment_result": {
                    "deployments": [{"dd_version": "abc123___100"}]
                },
            },
            {
                "service_name": "payment-service",
                "deployment_result": {"deployments": []},
            },
        ]

        section = generator._format_services_section(datadog_result, service_results)

        self.assertIn("## Services Involved", section)
        self.assertIn("card-service", section)
        self.assertIn("Logs found: 2", section)
        self.assertIn("payment-service", section)

    def test_services_section_no_services(self):
        """Test services section with no services."""
        generator = ReportGenerator()

        datadog_result = {"unique_services": [], "logs": []}
        service_results = []

        section = generator._format_services_section(datadog_result, service_results)

        self.assertIn("No services identified", section)


class TestDetermineRootCause(unittest.TestCase):
    """Tests for _determine_root_cause method."""

    def test_determine_root_cause_high_severity(self):
        """Test root cause identification with HIGH severity issues."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [
                {
                    "service_name": "card-service",
                    "code_analysis": {
                        "file_analyses": [
                            {
                                "file_path": "Handler.kt",
                                "potential_issues": [
                                    {
                                        "severity": "HIGH",
                                        "description": "Null pointer exception possible",
                                        "code_snippet": "val x = obj!!.value",
                                    }
                                ],
                                "diff": "+ some change",
                            }
                        ]
                    },
                }
            ],
            "datadog_result": {},
        }

        root_cause = generator._determine_root_cause(investigation_result)

        self.assertTrue(root_cause["identified"])
        self.assertEqual(root_cause["confidence"], "HIGH")
        self.assertEqual(root_cause["service"], "card-service")
        self.assertTrue(root_cause["fix_available"])

    def test_determine_root_cause_medium_severity(self):
        """Test root cause identification with MEDIUM severity issues."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [
                {
                    "service_name": "payment-service",
                    "code_analysis": {
                        "file_analyses": [
                            {
                                "file_path": "PaymentService.kt",
                                "potential_issues": [
                                    {
                                        "severity": "MEDIUM",
                                        "description": "Missing error handling",
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
            "datadog_result": {},
        }

        root_cause = generator._determine_root_cause(investigation_result)

        self.assertTrue(root_cause["identified"])
        self.assertEqual(root_cause["confidence"], "MEDIUM")

    def test_determine_root_cause_from_deployment(self):
        """Test root cause identification from recent deployment."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [
                {
                    "service_name": "card-service",
                    "deployment_result": {
                        "deployments": [
                            {"application_commit_hash": "abc123def456"}
                        ]
                    },
                    "code_analysis": {"file_analyses": []},
                }
            ],
            "datadog_result": {},
        }

        root_cause = generator._determine_root_cause(investigation_result)

        self.assertTrue(root_cause["identified"])
        self.assertEqual(root_cause["confidence"], "LOW")
        self.assertIn("Recent deployment", root_cause["primary_cause"])

    def test_determine_root_cause_dict_format_service_results(self):
        """Test root cause with dict format service results."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": {
                "card-service": {
                    "service_name": "card-service",
                    "code_analysis": {
                        "file_analyses": [
                            {
                                "file_path": "Handler.kt",
                                "potential_issues": [
                                    {"severity": "HIGH", "description": "Issue"}
                                ],
                            }
                        ]
                    },
                }
            },
            "datadog_result": {},
        }

        root_cause = generator._determine_root_cause(investigation_result)

        self.assertTrue(root_cause["identified"])


class TestFormatRootCauseSection(unittest.TestCase):
    """Tests for _format_root_cause_section method."""

    def test_root_cause_not_identified(self):
        """Test formatting when root cause not identified."""
        generator = ReportGenerator()

        root_cause = {"identified": False}

        section = generator._format_root_cause_section(root_cause)

        self.assertIn("Unable to determine", section)
        self.assertIn("Recommended Actions", section)

    def test_root_cause_identified_with_snippet(self):
        """Test formatting when root cause identified with code snippet."""
        generator = ReportGenerator()

        root_cause = {
            "identified": True,
            "confidence": "HIGH",
            "service": "card-service",
            "file_path": "Handler.kt",
            "primary_cause": "Null pointer exception",
            "code_snippet": "val x = obj!!.value",
            "line_number": 42,
            "contributing_factors": ["Recent deployment", "Missing validation"],
        }

        section = generator._format_root_cause_section(root_cause)

        self.assertIn("Handler.kt:42", section)
        self.assertIn("Null pointer exception", section)
        self.assertIn("Contributing Factors", section)
        self.assertIn("Recent deployment", section)


class TestProposeFix(unittest.TestCase):
    """Tests for _propose_fix method."""

    def test_propose_fix_not_available(self):
        """Test fix proposal when not available."""
        generator = ReportGenerator()

        root_cause = {"fix_available": False}
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("No specific fix can be proposed", section)
        self.assertIn("Recommendations", section)

    def test_propose_fix_error_handling(self):
        """Test fix proposal for error handling issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Handler.kt",
            "primary_cause": "Removed error handling in catch block",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("Add Error Handling", section)
        self.assertIn("try {", section)
        self.assertIn("catch", section)

    def test_propose_fix_exception_issue(self):
        """Test fix proposal for exception issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Handler.kt",
            "primary_cause": "Added throw statement that can fail",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("Handle Exception", section)

    def test_propose_fix_database_issue(self):
        """Test fix proposal for database issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Repository.kt",
            "primary_cause": "Database query returns null",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("Fix Database Query", section)
        self.assertIn("@Transactional", section)

    def test_propose_fix_api_issue(self):
        """Test fix proposal for API issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Client.kt",
            "primary_cause": "HTTP API call fails",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("API Error Handling", section)
        self.assertIn("timeout", section)

    def test_propose_fix_async_issue(self):
        """Test fix proposal for async issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Worker.kt",
            "primary_cause": "Async timing issue causes race condition",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("Async/Timing", section)
        self.assertIn("Mutex", section)

    def test_propose_fix_generic_issue(self):
        """Test fix proposal for generic issue."""
        generator = ReportGenerator()

        root_cause = {
            "fix_available": True,
            "service": "card-service",
            "file_path": "Service.kt",
            "primary_cause": "Some other type of issue",
            "code_snippet": "problematic code here",
        }
        service_results = []

        section = generator._propose_fix(root_cause, service_results)

        self.assertIn("Review and Fix Code", section)


class TestFormatFilesToModify(unittest.TestCase):
    """Tests for _format_files_to_modify method."""

    def test_files_to_modify_with_data(self):
        """Test files to modify with root cause file."""
        generator = ReportGenerator()

        root_cause = {
            "file_path": "Handler.kt",
            "primary_cause": "Null pointer issue",
        }
        service_results = [
            {
                "code_analysis": {
                    "file_analyses": [
                        {"file_path": "Service.kt", "potential_issues": [{"severity": "MEDIUM"}]}
                    ]
                }
            }
        ]

        section = generator._format_files_to_modify(root_cause, service_results)

        self.assertIn("Handler.kt", section)
        self.assertIn("Service.kt", section)

    def test_files_to_modify_empty(self):
        """Test files to modify when empty."""
        generator = ReportGenerator()

        root_cause = {}
        service_results = []

        section = generator._format_files_to_modify(root_cause, service_results)

        self.assertIn("Unable to identify", section)


class TestFormatInvestigationDetails(unittest.TestCase):
    """Tests for _format_investigation_details method."""

    def test_investigation_details_full(self):
        """Test investigation details with all data."""
        generator = ReportGenerator()

        datadog_result = {
            "search_attempts": [{}, {}],
            "total_logs": 15,
            "unique_services": ["card-service", "payment-service"],
        }
        service_results = [
            {
                "service_name": "card-service",
                "deployment_result": {"deployments": [{"timestamp": "2024-01-15"}]},
                "code_analysis": {"files_analyzed": 3, "file_analyses": [{"diff": "some diff"}]},
            }
        ]
        root_cause = {}

        section = generator._format_investigation_details(datadog_result, service_results, root_cause)

        self.assertIn("Query attempts: 2", section)
        self.assertIn("Logs found: 15", section)
        self.assertIn("Deployments found: 1", section)
        self.assertIn("Files analyzed: 3", section)


class TestFormatNotes(unittest.TestCase):
    """Tests for _format_notes method."""

    def test_notes_with_errors(self):
        """Test notes section with errors."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [
                {"service_name": "card-service", "error": "Failed to check deployment"},
                {
                    "service_name": "payment-service",
                    "code_analysis": {"status": "partial", "error": "Some files missing"},
                },
            ],
            "datadog_result": {},
        }

        notes = generator._format_notes(investigation_result)

        self.assertIn("Error investigating card-service", notes)
        self.assertIn("partial", notes)

    def test_notes_with_session_warning(self):
        """Test notes with session processing warning."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [],
            "datadog_result": {"efilogids_found": 10, "efilogids_processed": 5},
        }

        notes = generator._format_notes(investigation_result)

        self.assertIn("5 of 10 sessions", notes)

    def test_notes_clean(self):
        """Test notes when no issues."""
        generator = ReportGenerator()

        investigation_result = {
            "service_results": [],
            "datadog_result": {},
        }

        notes = generator._format_notes(investigation_result)

        self.assertIn("completed without warnings", notes)


class TestConvenienceFunction(unittest.TestCase):
    """Tests for generate_report convenience function."""

    def test_generate_report_function(self):
        """Test the generate_report convenience function."""
        investigation_result = {
            "user_input": {"mode": "LOG_MESSAGE", "log_message": "Test error"},
            "datadog_result": {"total_logs": 5, "unique_services": ["card-service"], "logs": []},
            "service_results": [],
            "search_timestamp": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC_TZ),
        }

        report = generate_report(investigation_result)

        self.assertIn("# Investigation Report", report)
        self.assertIn("Test error", report)


class TestFullReportGeneration(unittest.TestCase):
    """Integration tests for full report generation."""

    def test_full_report_with_all_sections(self):
        """Test generating a complete report with all sections."""
        generator = ReportGenerator()

        investigation_result = {
            "user_input": {
                "mode": "LOG_MESSAGE",
                "log_message": "Error processing payment for customer 12345",
            },
            "datadog_result": {
                "total_logs": 20,
                "unique_services": ["card-service", "payment-service"],
                "search_attempts": [{"from_time": "now-4h", "to_time": "now"}],
                "logs": [
                    {
                        "service": "card-service",
                        "status": "error",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "message": "Payment failed",
                        "logger_name": "com.sunbit.Handler",
                    }
                ],
            },
            "service_results": [
                {
                    "service_name": "card-service",
                    "deployment_result": {
                        "deployments": [
                            {
                                "deployment_timestamp": "2024-01-15T08:00:00Z",
                                "application_commit_hash": "abc123def456",
                                "build_number": "100",
                                "pr_number": 42,
                                "dd_version": "abc123___100",
                            }
                        ]
                    },
                    "code_analysis": {
                        "files_analyzed": 2,
                        "total_issues_found": 1,
                        "file_analyses": [
                            {
                                "file_path": "Handler.kt",
                                "previous_commit": "abc123",
                                "current_commit": "def456",
                                "diff": "- old code\n+ new code",
                                "analysis_summary": "Changed error handling",
                                "potential_issues": [
                                    {
                                        "severity": "HIGH",
                                        "description": "Removed error handling",
                                        "code_snippet": "// error handling removed",
                                    }
                                ],
                            }
                        ],
                    },
                    "stack_trace_files": ["src/main/kotlin/com/sunbit/Handler.kt"],
                }
            ],
            "search_timestamp": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC_TZ),
        }

        report = generator.generate_report(investigation_result)

        # Check all major sections are present
        self.assertIn("# Investigation Report", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Timeline", report)
        self.assertIn("## Services Involved", report)
        self.assertIn("## Root Cause Analysis", report)
        self.assertIn("## Evidence", report)
        self.assertIn("## Proposed Fix", report)
        self.assertIn("## Testing Required", report)
        self.assertIn("## Files to Modify", report)
        self.assertIn("## Next Steps", report)
        self.assertIn("## Investigation Details", report)
        self.assertIn("## Notes", report)

        # Check key data is present
        self.assertIn("card-service", report)
        self.assertIn("Handler.kt", report)
        self.assertIn("HIGH", report)


if __name__ == "__main__":
    unittest.main()
