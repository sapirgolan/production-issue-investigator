"""
Tests for the Exception Analyzer agent.

Tests cover:
- Call flow building and ordering
- Line number correlation with diff changes
- Root cause explanation generation
- Exception-specific fix suggestions
"""
import unittest
from typing import List, Dict, Optional


# Sample diff for testing correlation
SAMPLE_DIFF = """--- a/src/main/kotlin/com/sunbit/card/service/CustomerService.kt
+++ b/src/main/kotlin/com/sunbit/card/service/CustomerService.kt
@@ -42,7 +42,8 @@ class CustomerService {
     fun findCustomer(id: Long): Customer {
-        val customer = repository.findById(id).orElse(null)
+        val customer = repository.findById(id).orElseThrow {
+            IllegalArgumentException("Customer not found")
+        }
         return customer
     }

@@ -55,6 +56,7 @@ class CustomerService {
     fun validateCustomer(customer: Customer): Boolean {
+        // Added new validation
         if (customer.status == null) {
             throw IllegalStateException("Customer status cannot be null")
         }
"""


class TestCallFlowBuilding(unittest.TestCase):
    """Tests for building call flow from parsed stack traces."""

    def test_build_call_flow_ordering(self):
        """Test that call flow is built in correct order (deepest to shallowest)."""
        from agents.exception_analyzer import ExceptionAnalyzer, CallFlowStep
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.A", "methodA", "A.kt", 10, index=0, is_root_frame=True),
            StackFrame("com.sunbit.card.service.B", "methodB", "B.kt", 20, index=1),
            StackFrame("com.sunbit.card.service.C", "methodC", "C.kt", 30, index=2),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.NullPointerException",
        )

        analyzer = ExceptionAnalyzer()
        call_flow = analyzer._build_call_flow(parsed)

        # Call flow should be in order from root cause (first frame) outward
        self.assertEqual(len(call_flow), 3)
        self.assertEqual(call_flow[0].method_name, "methodA")
        self.assertEqual(call_flow[0].step_number, 1)
        self.assertTrue(call_flow[0].is_root_cause)
        self.assertEqual(call_flow[1].method_name, "methodB")
        self.assertEqual(call_flow[2].method_name, "methodC")

    def test_build_call_flow_empty_frames(self):
        """Test call flow with empty frames."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import ParsedStackTrace

        parsed = ParsedStackTrace()
        analyzer = ExceptionAnalyzer()
        call_flow = analyzer._build_call_flow(parsed)

        self.assertEqual(len(call_flow), 0)


class TestLineCorrelation(unittest.TestCase):
    """Tests for correlating stack trace lines with diff changes."""

    def test_correlate_direct_line_match(self):
        """Test correlation when stack frame line directly matches changed line."""
        from agents.exception_analyzer import ExceptionAnalyzer, LineCorrelation
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.service.CustomerService",
            method_name="findCustomer",
            file_name="CustomerService.kt",
            line_number=44,  # Line 44 is in the changed range (42-50)
        )

        analyzer = ExceptionAnalyzer()
        correlation = analyzer._correlate_line_with_diff(
            frame=frame,
            diff=SAMPLE_DIFF,
            file_path="src/main/kotlin/com/sunbit/card/service/CustomerService.kt",
        )

        self.assertTrue(correlation.is_changed)
        self.assertTrue(correlation.is_in_change_range)

    def test_correlate_nearby_changes(self):
        """Test correlation when line is near but not in changed lines."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.service.CustomerService",
            method_name="findCustomer",
            file_name="CustomerService.kt",
            line_number=40,  # Line 40 is near the changed range (42-50), within proximity
        )

        analyzer = ExceptionAnalyzer()
        correlation = analyzer._correlate_line_with_diff(
            frame=frame,
            diff=SAMPLE_DIFF,
            file_path="src/main/kotlin/com/sunbit/card/service/CustomerService.kt",
            proximity=5,
        )

        self.assertFalse(correlation.is_changed)
        self.assertTrue(correlation.is_near_changes)

    def test_correlate_no_match(self):
        """Test correlation when line has no relation to changes."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import StackFrame

        frame = StackFrame(
            class_name="com.sunbit.card.service.CustomerService",
            method_name="unrelatedMethod",
            file_name="CustomerService.kt",
            line_number=200,  # Far from any changes
        )

        analyzer = ExceptionAnalyzer()
        correlation = analyzer._correlate_line_with_diff(
            frame=frame,
            diff=SAMPLE_DIFF,
            file_path="src/main/kotlin/com/sunbit/card/service/CustomerService.kt",
        )

        self.assertFalse(correlation.is_changed)
        self.assertFalse(correlation.is_near_changes)


class TestRootCauseExplanation(unittest.TestCase):
    """Tests for generating root cause explanations."""

    def test_generate_explanation_for_npe(self):
        """Test generating explanation for NullPointerException."""
        from agents.exception_analyzer import ExceptionAnalyzer, ExceptionAnalysis
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.CustomerService", "findCustomer", "CustomerService.kt", 44, index=0, is_root_frame=True),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.NullPointerException",
            exception_message="Customer object is null",
            exception_short_type="NullPointerException",
        )

        analyzer = ExceptionAnalyzer()
        explanation = analyzer._generate_root_cause_explanation(parsed)

        self.assertIn("NullPointerException", explanation)
        self.assertIn("Customer object is null", explanation)
        self.assertIn("CustomerService", explanation)

    def test_generate_explanation_for_illegal_state(self):
        """Test generating explanation for IllegalStateException."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.PaymentService", "process", "PaymentService.kt", 78, index=0, is_root_frame=True),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.IllegalStateException",
            exception_message="Payment already processed",
            exception_short_type="IllegalStateException",
        )

        analyzer = ExceptionAnalyzer()
        explanation = analyzer._generate_root_cause_explanation(parsed)

        self.assertIn("IllegalStateException", explanation)
        self.assertIn("Payment already processed", explanation)


class TestFixSuggestions(unittest.TestCase):
    """Tests for generating exception-specific fix suggestions."""

    def test_suggest_fixes_for_npe(self):
        """Test fix suggestions for NullPointerException."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.CustomerService", "findCustomer", "CustomerService.kt", 44, index=0, is_root_frame=True),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.NullPointerException",
            exception_short_type="NullPointerException",
        )

        analyzer = ExceptionAnalyzer()
        fixes = analyzer._suggest_fixes(parsed)

        self.assertGreater(len(fixes), 0)
        # Should suggest null check or safe call
        fix_descriptions = [f.description.lower() for f in fixes]
        self.assertTrue(
            any("null" in desc for desc in fix_descriptions),
            "Expected fix suggestion for null handling"
        )

    def test_suggest_fixes_for_illegal_argument(self):
        """Test fix suggestions for IllegalArgumentException."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.ValidationService", "validate", "ValidationService.kt", 30, index=0, is_root_frame=True),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.IllegalArgumentException",
            exception_short_type="IllegalArgumentException",
        )

        analyzer = ExceptionAnalyzer()
        fixes = analyzer._suggest_fixes(parsed)

        self.assertGreater(len(fixes), 0)
        # Should suggest input validation
        fix_descriptions = [f.description.lower() for f in fixes]
        self.assertTrue(
            any("valid" in desc or "argument" in desc for desc in fix_descriptions),
            "Expected fix suggestion for argument validation"
        )


class TestFullAnalysis(unittest.TestCase):
    """Tests for full exception analysis workflow."""

    def test_analyze_returns_complete_analysis(self):
        """Test that analyze() returns a complete ExceptionAnalysis."""
        from agents.exception_analyzer import ExceptionAnalyzer, ExceptionAnalysis
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.CustomerService", "findCustomer", "CustomerService.kt", 44, index=0, is_root_frame=True),
            StackFrame("com.sunbit.card.handler.EventHandler", "handle", "EventHandler.kt", 23, index=1),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.NullPointerException",
            exception_message="Customer not found",
            exception_short_type="NullPointerException",
        )

        analyzer = ExceptionAnalyzer()
        analysis = analyzer.analyze(
            parsed_trace=parsed,
            diff=SAMPLE_DIFF,
            file_path="src/main/kotlin/com/sunbit/card/service/CustomerService.kt",
        )

        self.assertIsInstance(analysis, ExceptionAnalysis)
        self.assertEqual(analysis.exception_type, "NullPointerException")
        self.assertIsNotNone(analysis.call_flow)
        self.assertIsNotNone(analysis.root_cause_explanation)
        self.assertIsNotNone(analysis.suggested_fixes)

    def test_analyze_with_no_diff(self):
        """Test analyze() when no diff is provided."""
        from agents.exception_analyzer import ExceptionAnalyzer
        from utils.stack_trace_parser import ParsedStackTrace, StackFrame

        frames = [
            StackFrame("com.sunbit.card.service.CustomerService", "findCustomer", "CustomerService.kt", 44, index=0, is_root_frame=True),
        ]
        parsed = ParsedStackTrace(
            frames=frames,
            sunbit_frames=frames,
            exception_type="java.lang.NullPointerException",
        )

        analyzer = ExceptionAnalyzer()
        analysis = analyzer.analyze(parsed_trace=parsed)

        self.assertIsNotNone(analysis)
        # Should still provide call flow and basic analysis
        self.assertGreater(len(analysis.call_flow), 0)


class TestExceptionPatterns(unittest.TestCase):
    """Tests for exception patterns knowledge base."""

    def test_exception_patterns_exist(self):
        """Test that EXCEPTION_PATTERNS knowledge base exists and has common exceptions."""
        from agents.exception_analyzer import EXCEPTION_PATTERNS

        expected_exceptions = [
            "NullPointerException",
            "IllegalStateException",
            "IllegalArgumentException",
        ]

        for exc in expected_exceptions:
            self.assertIn(exc, EXCEPTION_PATTERNS, f"Missing pattern for {exc}")

    def test_exception_pattern_has_required_fields(self):
        """Test that each exception pattern has required fields."""
        from agents.exception_analyzer import EXCEPTION_PATTERNS

        required_fields = ["common_causes", "fix_patterns"]

        for exc_name, pattern in EXCEPTION_PATTERNS.items():
            for field in required_fields:
                self.assertIn(
                    field, pattern,
                    f"Exception {exc_name} missing required field: {field}"
                )


if __name__ == "__main__":
    unittest.main()
