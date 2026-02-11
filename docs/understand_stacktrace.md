# Enhanced Stack Trace Analysis Implementation Plan

## Context

The Production Issue Investigator currently extracts stack traces from DataDog logs but fails to fully analyze them. While files are identified and code changes are fetched, critical information is lost:

- **Exception type** (e.g., `NullPointerException`) is not extracted
- **Call flow order** is lost - frames are treated as an unordered set
- **Line numbers** from stack traces are not correlated with code changes
- **Root cause explanation** linking exception + call flow + diff is missing
- **Targeted fixes** based on exception type are not generated

**Goal**: Enable the agent to understand the call flow, explain why the exception occurred, and suggest targeted fixes based on the exception type and code changes.

---

## Solution Overview

| Phase | Component | Enhancement |
|-------|-----------|-------------|
| 1 | Stack Trace Parser | Extract exception type/message, preserve frame order |
| 2 | Exception Analyzer | NEW module: correlate exception with code changes |
| 3 | Code Checker | Add line-level correlation methods |
| 4 | Main Agent | Pass full ParsedStackTrace, integrate analyzer |
| 5 | Report Generator | Add call flow section, exception-specific fixes |

---

## Phase 1: Enhance Stack Trace Parser

**File**: `utils/stack_trace_parser.py`

### Changes to StackFrame Dataclass

```python
@dataclass
class StackFrame:
    class_name: str
    method_name: str
    file_name: Optional[str] = None
    line_number: Optional[int] = None
    index: int = 0                    # NEW: Position in call stack (0 = top)
    is_root_frame: bool = False       # NEW: True for exception origin
```

### Changes to ParsedStackTrace Dataclass

```python
@dataclass
class ParsedStackTrace:
    frames: List[StackFrame] = field(default_factory=list)
    sunbit_frames: List[StackFrame] = field(default_factory=list)
    unique_file_paths: Set[str] = field(default_factory=set)
    # NEW fields:
    exception_type: Optional[str] = None       # e.g., "java.lang.NullPointerException"
    exception_message: Optional[str] = None    # e.g., "Customer not found"
    exception_short_type: Optional[str] = None # e.g., "NullPointerException"
    has_chained_cause: bool = False            # True if "Caused by:" present
```

### New Regex Pattern

```python
EXCEPTION_PATTERN = re.compile(
    r'^([\w.$]+(?:Exception|Error|Throwable))'  # Exception type
    r'(?::\s*(.+))?$',                          # Optional message
    re.MULTILINE
)
```

### New Method: `_extract_exception_info()`

Extract exception type and message from stack trace header (first line before `at`).

### Update `parse()` Method

- Call `_extract_exception_info()` first
- Set `index` and `is_root_frame` on each StackFrame
- Populate new ParsedStackTrace fields

---

## Phase 2: Create Exception Analyzer

**File**: `agents/exception_analyzer.py` (NEW)

### New Dataclasses

```python
@dataclass
class LineCorrelation:
    file_path: str
    stack_frame_line: int
    changed_lines: List[int]
    is_direct_match: bool      # Stack line was changed
    nearby_changes: bool       # Changes within 5 lines
    change_type: str           # "added", "removed", "modified"

@dataclass
class CallFlowStep:
    index: int
    class_name: str
    method_name: str
    file_path: str
    line_number: Optional[int]
    is_exception_origin: bool
    is_sunbit_code: bool
    correlation: Optional[LineCorrelation] = None

@dataclass
class ExceptionAnalysis:
    exception_type: Optional[str]
    exception_message: Optional[str]
    exception_short_type: Optional[str]
    call_flow: List[CallFlowStep]
    root_cause_explanation: str
    confidence: str                      # HIGH, MEDIUM, LOW
    suggested_fixes: List[Dict[str, Any]]
    correlations: List[LineCorrelation]
    contributing_factors: List[str]
```

### Exception Knowledge Base

```python
EXCEPTION_PATTERNS = {
    "NullPointerException": {
        "common_causes": ["Null reference access", "Missing null check", "Optional.get() without check"],
        "fix_patterns": ["Add null check", "Use safe call operator", "Add @Nullable handling"],
        "code_patterns": [r"\.get\(\)", r"!!", r"= null"],
    },
    "IllegalStateException": {...},
    "IllegalArgumentException": {...},
    # ... more exception types
}
```

### Key Methods

```python
class ExceptionAnalyzer:
    def analyze(self, parsed_stack_trace, file_analyses, service_name) -> ExceptionAnalysis
    def _build_call_flow(self, parsed_stack_trace, file_analyses) -> List[CallFlowStep]
    def _correlate_line_numbers(self, frame, file_analysis) -> Optional[LineCorrelation]
    def _generate_root_cause_explanation(self, exception_type, call_flow, correlations) -> str
    def _suggest_fixes(self, exception_type, call_flow, correlations) -> List[Dict]
```

---

## Phase 3: Update Code Checker

**File**: `agents/code_checker.py`

### New Methods

```python
def get_changed_line_numbers(self, diff: str) -> Dict[str, List[int]]:
    """Extract line numbers that changed from a diff.
    Returns: {"added": [...], "removed": [...], "all": [...]}
    """

def check_line_in_changes(self, line_number: int, diff: str, proximity: int = 5) -> Dict:
    """Check if line is in or near code changes.
    Returns: {"is_changed": bool, "is_nearby": bool, "nearest_change_distance": int}
    """

def _check_exception_specific_issues(self, exception_type, removed_lines, added_lines) -> List[PotentialIssue]:
    """Detect issues specific to the exception type (e.g., removed null checks for NPE)."""
```

---

## Phase 4: Update Main Agent Integration

**File**: `agents/main_agent.py`

### Update ServiceInvestigationResult

```python
@dataclass
class ServiceInvestigationResult:
    # ... existing fields ...
    parsed_stack_traces: Optional[List[ParsedStackTrace]] = None  # NEW
    exception_analysis: Optional[ExceptionAnalysis] = None        # NEW
```

### Update `_extract_stack_trace_files_per_service()`

Rename to `_extract_stack_trace_data_per_service()` and return:
```python
{
    "file_paths": Set[str],
    "parsed_traces": List[ParsedStackTrace]
}
```

### Update `_investigate_single_service()`

After code analysis, run exception analysis:
```python
if result.code_analysis and result.parsed_stack_traces:
    result.exception_analysis = self._run_exception_analysis(
        service_name, parsed_traces, file_analyses
    )
```

### New Method: `_run_exception_analysis()`

Select primary stack trace (first with exception_type) and call ExceptionAnalyzer.

---

## Phase 5: Enhance Report Generator

**File**: `utils/report_generator.py`

### New Section: Call Flow Analysis

```markdown
## Call Flow Analysis

### card-service

**Exception**: `NullPointerException`
**Message**: Customer not found

**Call Stack** (top = exception origin):
| # | Class | Method | Line | Changed? |
|---|-------|--------|------|----------|
| 0 | BankruptcyHandler | handleEvent | 45 | **YES** (direct) |
| 1 | EventConsumer | consume | 123 | NEARBY |
| 2 | KafkaListener | onMessage | 89 | - |
```

### Enhanced Root Cause Section

Add "Exception Context" subsection:
```markdown
### Exception Context

**Exception Type**: `NullPointerException`

The exception occurred because a null check was removed in the recent deployment.
Line 45 of BankruptcyHandler.kt was directly modified, removing the validation
that previously prevented null customer access.
```

### Enhanced Fix Suggestions

Use exception-specific fixes from ExceptionAnalysis:
- NullPointerException → null check suggestions
- IllegalStateException → state validation suggestions
- etc.

### Update `_determine_root_cause()`

Incorporate exception analysis:
- Boost confidence to HIGH if direct line correlation found
- Add `exception_context` and `correlations` to root_cause dict

---

## Files to Modify

| File | Changes |
|------|---------|
| `utils/stack_trace_parser.py` | Add exception extraction, frame ordering |
| `agents/exception_analyzer.py` | **NEW FILE** - Exception analysis module |
| `agents/code_checker.py` | Add line correlation methods |
| `agents/main_agent.py` | Pass full ParsedStackTrace, integrate analyzer |
| `utils/report_generator.py` | Add call flow section, exception-specific fixes |

---

## Existing Code to Reuse

- `StackTraceParser.parse()` - extend with exception extraction
- `CodeChecker._analyze_diff()` - reuse for pattern detection
- `ReportGenerator._format_root_cause_section()` - extend with exception context
- `ReportGenerator._propose_fix()` - add exception-specific templates

---

## Test Strategy (TDD)

### Phase 1 Tests
```python
def test_extract_exception_type_with_message()
def test_extract_exception_type_without_message()
def test_frame_index_preserved()
def test_first_frame_is_root_frame()
def test_chained_cause_detected()
```

### Phase 2 Tests
```python
def test_build_call_flow_ordering()
def test_correlate_direct_line_match()
def test_correlate_nearby_changes()
def test_generate_explanation_for_npe()
def test_suggest_fixes_for_npe()
```

### Phase 3 Tests
```python
def test_get_changed_line_numbers()
def test_check_line_in_changes_direct()
def test_check_line_in_changes_nearby()
def test_exception_specific_issues_null_check()
```

### Phase 4 Tests
```python
def test_parsed_traces_passed_through()
def test_exception_analysis_populated()
def test_primary_trace_selection()
```

### Phase 5 Tests
```python
def test_call_flow_section_formatting()
def test_exception_context_in_root_cause()
def test_exception_specific_fix_suggestions()
```

---

## Verification

1. **Unit tests**:
   ```bash
   uv run pytest tests/test_stack_trace.py tests/test_exception_analyzer.py -v
   ```

2. **Integration test**:
   ```bash
   uv run main.py
   # Input: "Error processing consumeBankruptCustomerStatusChange event for customer 6222309"
   # DateTime: Feb 11, 9:29
   ```

3. **Verify output includes**:
   - Exception type in report (e.g., `NullPointerException`)
   - Call flow table with frame order
   - Line correlation (which lines changed)
   - Root cause explanation based on exception type
   - Exception-specific fix suggestions

4. **Coverage verification**:
   ```bash
   uv run pytest --cov=utils.stack_trace_parser --cov=agents.exception_analyzer --cov-report=term-missing
   # Target: 80%+ coverage
   ```

---

## Implementation Order

```
Phase 1 (Parser Enhancement)
    ↓
Phase 2 (Exception Analyzer) + Phase 3 (Code Checker) [parallel]
    ↓
Phase 4 (Main Agent Integration)
    ↓
Phase 5 (Report Generator)
```

---

## Backwards Compatibility

All changes maintain backwards compatibility:
- New StackFrame fields have defaults (`index=0`, `is_root_frame=False`)
- New ParsedStackTrace fields default to `None`/`False`
- New ServiceInvestigationResult fields are `Optional` with `None` default
- New report sections only appear when data exists
- Existing tests continue to pass
