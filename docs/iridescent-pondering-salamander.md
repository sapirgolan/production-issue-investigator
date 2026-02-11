# Stack Trace Extraction and Analysis Implementation Plan

## Context

The Production Issue Investigator agent finds DataDog logs but fails to analyze stack traces. When an exception occurs, the stack trace contains the actual file locations where the error happened (e.g., `BankruptcyHandler.kt:45`), but the agent only uses the `logger_name` field which may point to a different class than where the exception originated.

**Example**: For error "Error processing consumeBankruptCustomerStatusChange event for customer 6222309", the stack trace shows:
```
at com.sunbit.card.bankruptcy.handler.BankruptcyHandler.handleEvent(BankruptcyHandler.kt:45)
at com.sunbit.card.kafka.consumer.EventConsumer.consume(EventConsumer.kt:123)
```

But the agent only analyzes the logger's class, missing the actual error location.

## Solution Overview

1. Extract `stack_trace` field from DataDog logs
2. Parse stack traces to extract file paths (filtering to `com.sunbit` packages)
3. Pass stack trace files to the existing `analyze_files_directly()` method in Code Checker
4. Merge results with logger-based analysis, avoiding duplicates

---

## Implementation Steps

### Phase 1: Add Stack Trace to LogEntry

**File**: `utils/datadog_api.py`

1. Add `stack_trace: Optional[str] = None` field to `LogEntry` dataclass (line ~59)

2. Update `_extract_log_entry()` method to extract stack trace from:
   - `nested_attrs.get("error", {}).get("stack")`
   - `nested_attrs.get("stack_trace")` (fallback)
   - `nested_attrs.get("exception", {}).get("stacktrace")` (fallback)

---

### Phase 2: Create Stack Trace Parser

**New File**: `utils/stack_trace_parser.py`

Create a parser that:
- Parses Java/Kotlin stack trace strings using regex
- Extracts `StackFrame` objects with: class_name, method_name, file_name, line_number
- Filters to only `com.sunbit` packages (skip framework classes)
- Handles inner classes (e.g., `MyService$Companion` → `MyService.kt`)
- Converts frames to file paths: `com.sunbit.card.Handler` → `src/main/kotlin/com/sunbit/card/Handler.kt`
- Also extracts stack traces embedded in log `message` field

**Key classes**:
- `StackFrame` - Single stack trace frame
- `ParsedStackTrace` - Contains frames, sunbit_frames, unique_file_paths
- `StackTraceParser` - Main parser class
- `extract_file_paths(stack_trace, message)` - Convenience function

**Regex pattern for frames**:
```python
r'^\s*at\s+([\w.$]+)\.([\w$<>]+)\(([^:)]+)?(?::(\d+))?\)'
```

---

### Phase 3: Update Main Agent

**File**: `agents/main_agent.py`

1. Add new method `_extract_stack_trace_files_per_service()`:
   - Iterate through logs
   - Parse `log.stack_trace` field using `StackTraceParser`
   - Also check `log.message` for embedded stack traces (for error/warn logs)
   - Return `Dict[str, Set[str]]` mapping service → file paths

2. Update `investigate()` method (around line 378):
   - Call `_extract_stack_trace_files_per_service(dd_result)`
   - Pass result to `_investigate_services_parallel()`

3. Update `_investigate_services_parallel()`:
   - Add `service_stack_trace_files: Dict[str, Set[str]]` parameter
   - Pass to `_investigate_single_service()`

4. Update `_investigate_single_service()`:
   - Add `stack_trace_files: Set[str]` parameter
   - After logger-based analysis, call `code_checker.analyze_files_directly()` with stack trace files
   - Deduplicate: exclude files already analyzed via logger_names
   - Merge `FileAnalysis` results into `code_result`

5. Add helper methods:
   - `_get_repo_for_service()` - Get owner/repo from service name
   - `_extract_commit_hash()` - Delegate to code_checker method

6. Update `ServiceInvestigationResult` dataclass:
   - Add `stack_trace_files: Optional[Set[str]] = None`

---

### Phase 4: Enhance Code Checker

**File**: `agents/code_checker.py`

Update `analyze_files_directly()` method:
- When file not found at path, try alternative extension
- `.kt` → try `.java` equivalent
- `.java` → try `.kt` equivalent
- Update `file_analysis.file_path` to actual found path

---

### Phase 5: Update Report Generator

**File**: `utils/report_generator.py`

Add "Stack Trace Analysis" section to evidence:
- List files discovered from stack traces per service
- Show which files were analyzed

---

## Files to Modify

| File | Changes |
|------|---------|
| `utils/datadog_api.py` | Add `stack_trace` field, extract in `_extract_log_entry()` |
| `utils/stack_trace_parser.py` | **NEW FILE** - Parser with `StackFrame`, `ParsedStackTrace`, `StackTraceParser` |
| `agents/main_agent.py` | Add extraction method, update investigation flow, add helper methods |
| `agents/code_checker.py` | Add Kotlin/Java fallback in `analyze_files_directly()` |
| `utils/report_generator.py` | Add stack trace files section |

---

## Existing Code to Reuse

- `code_checker.analyze_files_directly()` (`agents/code_checker.py:920-990`) - Already handles direct file path analysis
- `code_checker._analyze_diff()` - Issue detection pipeline
- `github_helper.get_file_content()` - File fetching
- `github_helper.get_parent_commit()` - Commit history

---

## Verification

1. **Unit test stack trace parser**:
   ```bash
   uv run pytest tests/test_stack_trace_parser.py -v
   ```

2. **Integration test with real error**:
   ```bash
   uv run main.py
   # Input: "Error processing consumeBankruptCustomerStatusChange event for customer 6222309"
   # DateTime: Feb 11, 9:29
   ```

3. **Verify output includes**:
   - Stack trace files listed in report
   - Code analysis for files from stack traces
   - No duplicate file analyses

4. **Check logs** for:
   - `"Parsed stack trace: X frames, Y sunbit frames, Z unique files"`
   - `"Analyzing N additional files from stack traces"`
