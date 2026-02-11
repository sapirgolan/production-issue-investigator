"""
Exception Analyzer for correlating stack traces with code changes.

This module provides:
- Call flow building from parsed stack traces
- Line number correlation with diff changes
- Root cause explanation generation
- Exception-specific fix suggestions
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from utils.logger import get_logger
from utils.stack_trace_parser import ParsedStackTrace, StackFrame

logger = get_logger(__name__)


# Knowledge base of common exceptions with their patterns and fixes
EXCEPTION_PATTERNS: Dict[str, Dict[str, Any]] = {
    "NullPointerException": {
        "common_causes": [
            "Accessing a method or property on a null reference",
            "Missing null check before dereferencing",
            "Unexpected null return from method call",
            "Uninitialized object field",
        ],
        "fix_patterns": [
            "Add null check before accessing the object",
            "Use Kotlin safe call operator (?.) or Elvis operator (?:)",
            "Use Optional/nullable type properly",
            "Add @NotNull or requireNotNull() assertion",
        ],
        "code_example": """// Before (problematic)
val customer = repository.findById(id)
customer.name // NPE if customer is null

// After (fixed)
val customer = repository.findById(id)
customer?.name ?: throw CustomerNotFoundException(id)""",
    },
    "IllegalStateException": {
        "common_causes": [
            "Object in invalid state for the operation",
            "Method called at inappropriate time in lifecycle",
            "State machine transition violation",
            "Missing initialization before method call",
        ],
        "fix_patterns": [
            "Add state validation before operation",
            "Ensure proper initialization sequence",
            "Add state machine guards",
            "Document and validate preconditions",
        ],
        "code_example": """// Before (problematic)
fun process() {
    check(state == State.READY) { "Invalid state" }
}

// After (fixed)
fun process() {
    if (state != State.READY) {
        logger.warn("Attempted process in state: $state")
        return // or initialize state first
    }
}""",
    },
    "IllegalArgumentException": {
        "common_causes": [
            "Invalid input parameter passed to method",
            "Parameter fails validation check",
            "Null passed where non-null expected",
            "Out of range value for parameter",
        ],
        "fix_patterns": [
            "Validate arguments at method entry",
            "Use require() with descriptive message",
            "Add input sanitization before calling",
            "Document parameter constraints",
        ],
        "code_example": """// Before (problematic)
fun setAge(age: Int) {
    require(age >= 0) { "Age must be non-negative" }
}

// After (fixed with better handling)
fun setAge(age: Int) {
    if (age < 0) {
        logger.warn("Invalid age $age, defaulting to 0")
        this.age = 0
        return
    }
    this.age = age
}""",
    },
    "RuntimeException": {
        "common_causes": [
            "Unchecked exception from business logic",
            "Wrapper for checked exceptions",
            "Generic error condition",
        ],
        "fix_patterns": [
            "Add appropriate exception handling",
            "Use more specific exception type",
            "Add error recovery logic",
        ],
        "code_example": """// Add proper exception handling
try {
    performOperation()
} catch (e: SpecificException) {
    logger.error("Operation failed: ${e.message}", e)
    // Handle or recover
}""",
    },
    "NoSuchElementException": {
        "common_causes": [
            "Calling next() on empty iterator",
            "Using first()/single() on empty collection",
            "Optional.get() on empty Optional",
        ],
        "fix_patterns": [
            "Use firstOrNull() instead of first()",
            "Check hasNext() before next()",
            "Use orElse()/orElseGet() for Optional",
        ],
        "code_example": """// Before (problematic)
val item = list.first() // throws if empty

// After (fixed)
val item = list.firstOrNull() ?: defaultItem""",
    },
}


@dataclass
class LineCorrelation:
    """Correlation result between a stack frame line and diff changes.

    Attributes:
        line_number: The line number from stack frame
        is_changed: True if this exact line was modified
        is_near_changes: True if line is within proximity of changes
        is_in_change_range: True if line is within a changed block
        change_type: Type of change ('added', 'removed', 'modified', None)
        nearby_change_lines: List of nearby changed line numbers
    """
    line_number: int
    is_changed: bool = False
    is_near_changes: bool = False
    is_in_change_range: bool = False
    change_type: Optional[str] = None
    nearby_change_lines: List[int] = field(default_factory=list)


@dataclass
class CallFlowStep:
    """A single step in the call flow.

    Attributes:
        step_number: Order in the call flow (1 = root cause)
        class_name: Full qualified class name
        method_name: Method name
        file_name: Source file name
        line_number: Line number in source
        is_root_cause: True if this is the root cause frame
        line_correlation: Correlation with diff changes (if available)
    """
    step_number: int
    class_name: str
    method_name: str
    file_name: Optional[str] = None
    line_number: Optional[int] = None
    is_root_cause: bool = False
    line_correlation: Optional[LineCorrelation] = None


@dataclass
class FixSuggestion:
    """A suggested fix for the exception.

    Attributes:
        description: Human-readable description of the fix
        code_example: Example code showing the fix
        risk_level: Risk level of the fix (LOW, MEDIUM, HIGH)
    """
    description: str
    code_example: Optional[str] = None
    risk_level: str = "MEDIUM"


@dataclass
class ExceptionAnalysis:
    """Complete analysis result for an exception.

    Attributes:
        exception_type: Short exception type (e.g., NullPointerException)
        exception_message: Exception message if available
        call_flow: Ordered list of call flow steps
        root_cause_explanation: Human-readable explanation
        suggested_fixes: List of fix suggestions
        changed_frames_count: Number of frames with line changes
        confidence: Confidence level in the analysis (LOW, MEDIUM, HIGH)
    """
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    call_flow: List[CallFlowStep] = field(default_factory=list)
    root_cause_explanation: Optional[str] = None
    suggested_fixes: List[FixSuggestion] = field(default_factory=list)
    changed_frames_count: int = 0
    confidence: str = "MEDIUM"


class ExceptionAnalyzer:
    """Analyzer for correlating exceptions with code changes.

    This analyzer:
    - Builds call flow from parsed stack traces
    - Correlates stack frame lines with diff changes
    - Generates root cause explanations
    - Suggests exception-specific fixes
    """

    # Pattern to extract line numbers from unified diff
    DIFF_HUNK_PATTERN = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', re.MULTILINE)

    def __init__(self):
        """Initialize the exception analyzer."""
        logger.debug("ExceptionAnalyzer initialized")

    def analyze(
        self,
        parsed_trace: ParsedStackTrace,
        diff: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> ExceptionAnalysis:
        """Analyze a parsed stack trace and correlate with code changes.

        Args:
            parsed_trace: Parsed stack trace from StackTraceParser
            diff: Optional unified diff string
            file_path: File path for the diff (for matching)

        Returns:
            ExceptionAnalysis with call flow, explanation, and fixes
        """
        logger.debug(
            f"Analyzing exception: {parsed_trace.exception_short_type}, "
            f"frames: {len(parsed_trace.sunbit_frames)}"
        )

        # Build call flow
        call_flow = self._build_call_flow(parsed_trace)

        # Correlate with diff if provided
        changed_frames_count = 0
        if diff and file_path:
            for step in call_flow:
                if step.line_number:
                    frame = StackFrame(
                        class_name=step.class_name,
                        method_name=step.method_name,
                        file_name=step.file_name,
                        line_number=step.line_number,
                    )
                    correlation = self._correlate_line_with_diff(frame, diff, file_path)
                    step.line_correlation = correlation
                    if correlation.is_changed or correlation.is_in_change_range:
                        changed_frames_count += 1

        # Generate explanation
        root_cause_explanation = self._generate_root_cause_explanation(parsed_trace)

        # Generate fix suggestions
        suggested_fixes = self._suggest_fixes(parsed_trace)

        # Determine confidence
        confidence = self._determine_confidence(
            parsed_trace, call_flow, changed_frames_count
        )

        return ExceptionAnalysis(
            exception_type=parsed_trace.exception_short_type,
            exception_message=parsed_trace.exception_message,
            call_flow=call_flow,
            root_cause_explanation=root_cause_explanation,
            suggested_fixes=suggested_fixes,
            changed_frames_count=changed_frames_count,
            confidence=confidence,
        )

    def _build_call_flow(self, parsed_trace: ParsedStackTrace) -> List[CallFlowStep]:
        """Build ordered call flow from parsed stack trace.

        The call flow is ordered from root cause (first/deepest frame)
        to the outermost caller.

        Args:
            parsed_trace: Parsed stack trace

        Returns:
            List of CallFlowStep in order
        """
        if not parsed_trace.sunbit_frames:
            return []

        call_flow = []
        for i, frame in enumerate(parsed_trace.sunbit_frames):
            step = CallFlowStep(
                step_number=i + 1,
                class_name=frame.class_name,
                method_name=frame.method_name,
                file_name=frame.file_name,
                line_number=frame.line_number,
                is_root_cause=frame.is_root_frame,
            )
            call_flow.append(step)

        return call_flow

    def _correlate_line_with_diff(
        self,
        frame: StackFrame,
        diff: str,
        file_path: str,
        proximity: int = 5,
    ) -> LineCorrelation:
        """Correlate a stack frame line with diff changes.

        Args:
            frame: The stack frame to correlate
            diff: Unified diff string
            file_path: File path for the diff
            proximity: Number of lines to consider "near"

        Returns:
            LineCorrelation with match results
        """
        if not frame.line_number:
            return LineCorrelation(line_number=0)

        line_number = frame.line_number
        correlation = LineCorrelation(line_number=line_number)

        # Parse diff to find changed line ranges
        changed_lines = self._parse_changed_lines(diff)

        # Check for direct match
        if line_number in changed_lines:
            correlation.is_changed = True
            correlation.is_in_change_range = True
            correlation.change_type = changed_lines[line_number]
            return correlation

        # Check for changes in range (within a hunk)
        change_ranges = self._parse_change_ranges(diff)
        for start, end in change_ranges:
            if start <= line_number <= end:
                correlation.is_in_change_range = True
                break

        # Check for nearby changes
        nearby_changes = []
        for changed_line, change_type in changed_lines.items():
            if abs(changed_line - line_number) <= proximity:
                nearby_changes.append(changed_line)

        if nearby_changes:
            correlation.is_near_changes = True
            correlation.nearby_change_lines = sorted(nearby_changes)

        return correlation

    def _parse_changed_lines(self, diff: str) -> Dict[int, str]:
        """Parse diff to extract changed line numbers.

        Args:
            diff: Unified diff string

        Returns:
            Dict mapping line number to change type
        """
        changed_lines = {}
        current_line = 0

        for line in diff.split('\n'):
            # Parse hunk header
            hunk_match = self.DIFF_HUNK_PATTERN.match(line)
            if hunk_match:
                current_line = int(hunk_match.group(2))
                continue

            if line.startswith('+++') or line.startswith('---'):
                continue

            if line.startswith('+'):
                changed_lines[current_line] = 'added'
                current_line += 1
            elif line.startswith('-'):
                # Removed lines don't increment current_line
                pass
            else:
                current_line += 1

        return changed_lines

    def _parse_change_ranges(self, diff: str) -> List[tuple]:
        """Parse diff to extract change ranges (line start, line end).

        Args:
            diff: Unified diff string

        Returns:
            List of (start, end) tuples for each changed range
        """
        ranges = []

        for match in self.DIFF_HUNK_PATTERN.finditer(diff):
            start = int(match.group(2))
            # Estimate end by counting lines in the hunk
            # This is a simplification - for a more accurate result,
            # we'd need to parse the full hunk
            ranges.append((start, start + 20))  # Approximate range

        return ranges

    def _generate_root_cause_explanation(
        self,
        parsed_trace: ParsedStackTrace,
    ) -> str:
        """Generate human-readable root cause explanation.

        Args:
            parsed_trace: Parsed stack trace

        Returns:
            Explanation string
        """
        exc_type = parsed_trace.exception_short_type or "Unknown Exception"
        exc_message = parsed_trace.exception_message or ""

        # Get the root frame
        root_frame = None
        for frame in parsed_trace.sunbit_frames:
            if frame.is_root_frame:
                root_frame = frame
                break

        # Build explanation
        parts = []

        # Exception type and message
        if exc_message:
            parts.append(f"A **{exc_type}** occurred with message: \"{exc_message}\"")
        else:
            parts.append(f"A **{exc_type}** occurred")

        # Location
        if root_frame:
            class_short = root_frame.class_name.split('.')[-1]
            parts.append(
                f"The error originated in `{class_short}.{root_frame.method_name}()` "
                f"at line {root_frame.line_number}"
            )

        # Known patterns
        if exc_type in EXCEPTION_PATTERNS:
            pattern = EXCEPTION_PATTERNS[exc_type]
            causes = pattern.get("common_causes", [])
            if causes:
                parts.append(f"\n**Common causes for {exc_type}:**")
                for cause in causes[:3]:  # Top 3 causes
                    parts.append(f"- {cause}")

        return "\n".join(parts)

    def _suggest_fixes(self, parsed_trace: ParsedStackTrace) -> List[FixSuggestion]:
        """Generate exception-specific fix suggestions.

        Args:
            parsed_trace: Parsed stack trace

        Returns:
            List of FixSuggestion
        """
        fixes = []
        exc_type = parsed_trace.exception_short_type

        if exc_type and exc_type in EXCEPTION_PATTERNS:
            pattern = EXCEPTION_PATTERNS[exc_type]

            # Add fix patterns
            for fix_desc in pattern.get("fix_patterns", [])[:3]:
                fixes.append(FixSuggestion(
                    description=fix_desc,
                    code_example=pattern.get("code_example"),
                    risk_level="LOW",
                ))
        else:
            # Generic fix suggestions
            fixes.append(FixSuggestion(
                description="Review the stack trace and add appropriate error handling",
                risk_level="MEDIUM",
            ))
            fixes.append(FixSuggestion(
                description="Add logging to understand the context of the error",
                risk_level="LOW",
            ))

        return fixes

    def _determine_confidence(
        self,
        parsed_trace: ParsedStackTrace,
        call_flow: List[CallFlowStep],
        changed_frames_count: int,
    ) -> str:
        """Determine confidence level of the analysis.

        Args:
            parsed_trace: Parsed stack trace
            call_flow: Built call flow
            changed_frames_count: Number of frames with changes

        Returns:
            Confidence level: HIGH, MEDIUM, or LOW
        """
        # High confidence if:
        # - Known exception type
        # - Has root frame
        # - Frame has changes in diff
        has_known_type = parsed_trace.exception_short_type in EXCEPTION_PATTERNS
        has_root_frame = any(f.is_root_frame for f in parsed_trace.sunbit_frames)
        has_changes = changed_frames_count > 0

        if has_known_type and has_root_frame and has_changes:
            return "HIGH"
        elif has_known_type and has_root_frame:
            return "MEDIUM"
        elif has_known_type or has_root_frame:
            return "LOW"
        else:
            return "LOW"
