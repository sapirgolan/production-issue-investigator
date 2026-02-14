# MCP Tools Fix Specification

**Date:** 2026-02-14
**Status:** Ready for Implementation
**Severity:** Critical - Application is non-functional

---

## Executive Summary

The production issue investigator application fails to start due to incorrect MCP (Model Context Protocol) tool registration. The Claude Agent SDK cannot serialize function objects when passing MCP server configurations to its subprocess CLI. This document provides a complete specification for fixing the issue while maintaining all existing test compatibility.

---

## Issue Description

### What's Happening

When running `uv run main.py`, the application crashes immediately with:

```
TypeError: Object of type function is not JSON serializable
  File "/Users/sapirgolan/workspace/production-issue-investigator/agents/lead_agent.py", line 254, in investigate
    async with ClaudeSDKClient(options) as client:
  File ".../claude_agent_sdk/_internal/transport/subprocess_cli.py", line 260, in _build_command
    json.dumps({"mcpServers": servers_for_cli}),
TypeError: Object of type function is not JSON serializable
when serializing list item 0
when serializing dict item 'tools'
when serializing dict item 'datadog'
when serializing dict item 'mcpServers'
```

### User Impact

- Application cannot start or perform any investigations
- All MCP tool functionality is inaccessible
- Complete system failure - no workarounds available

---

## Root Cause Analysis

### Primary Cause

**Location:** `/Users/sapirgolan/workspace/production-issue-investigator/agents/lead_agent.py`, lines 40-59

The MCP server configuration incorrectly passes raw function objects directly:

```python
# INCORRECT - Current implementation
datadog_mcp_server = {
    "name": "datadog",
    "version": "1.0.0",
    "tools": [
        datadog_server.search_logs_tool,        # ← Function object!
        datadog_server.get_logs_by_efilogid_tool,
        datadog_server.parse_stack_trace_tool,
    ]
}

github_mcp_server = {
    "name": "github",
    "version": "1.0.0",
    "tools": [
        github_server.search_commits_tool,      # ← Function object!
        github_server.get_file_content_tool,
        github_server.get_pr_files_tool,
        github_server.compare_commits_tool,
    ]
}
```

### Why This Fails

1. `search_logs_tool`, `get_logs_by_efilogid_tool`, etc. are plain `async def` functions
2. They are NOT decorated with `@tool` from Claude Agent SDK
3. They are NOT wrapped with `create_sdk_mcp_server()`
4. When the SDK tries to serialize this config to JSON for the subprocess CLI, Python cannot serialize function objects

### Expected Pattern (from AGENT_SDK_GUIDE.md)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("check_deployment", "Check deployment status", {"service": str})
async def check_deployment(args):
    # implementation
    return {"content": [...]}

# Create MCP server with decorated tools
deployment_server = create_sdk_mcp_server(
    name="deployment_tools",
    version="1.0.0",
    tools=[check_deployment]  # SDK-decorated functions
)
```

---

## Scope of Changes

### Files Requiring Modification

#### 1. `/mcp_servers/datadog_server.py` (3 tools)
- `search_logs_tool` (line 157)
- `get_logs_by_efilogid_tool` (line 230)
- `parse_stack_trace_tool` (line 305)

#### 2. `/mcp_servers/github_server.py` (4 tools)
- `search_commits_tool` (line 153)
- `get_file_content_tool` (line 249)
- `get_pr_files_tool` (line 326)
- `compare_commits_tool` (line 403)

#### 3. `/agents/lead_agent.py`
- Lines 32-33: Add SDK imports
- Lines 40-59: Remove manual server dicts, import wrapped servers
- Lines 223-226: Update MCP server registration

#### 4. Test Files (Potential Modifications)
- `/tests/test_mcp_tools.py` - Already imports tools correctly, should pass
- `/tests/test_lead_agent.py` - Mocks lead_agent components, should pass

---

## Solution Design

### Architecture Overview

```
Before (Broken):
┌─────────────────────────────────────┐
│ lead_agent.py                       │
│                                     │
│ datadog_mcp_server = {              │
│   "tools": [                        │
│     datadog_server.search_logs_tool │  ← Raw function!
│   ]                                 │
│ }                                   │
└─────────────────────────────────────┘
           │
           ▼
    ❌ JSON Serialization Fails

After (Fixed):
┌─────────────────────────────────────┐
│ datadog_server.py                   │
│                                     │
│ @tool("search_logs", ...)           │  ← SDK decorator
│ async def search_logs_tool(...):    │
│   ...                               │
│                                     │
│ DATADOG_MCP_SERVER =                │
│   create_sdk_mcp_server(            │  ← SDK wrapper
│     name="datadog",                 │
│     tools=[search_logs_tool, ...]   │
│   )                                 │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ lead_agent.py                       │
│                                     │
│ from mcp_servers.datadog_server     │
│   import DATADOG_MCP_SERVER         │  ← Import wrapped
│                                     │
│ mcp_servers = {                     │
│   "datadog": DATADOG_MCP_SERVER     │
│ }                                   │
└─────────────────────────────────────┘
           │
           ▼
    ✅ JSON Serialization Succeeds
```

### Tool Decorator Signature

Each tool needs to be decorated with specific metadata:

```python
@tool(
    name="tool_name",              # MCP tool name (no prefix)
    description="...",              # What the tool does
    parameters={"param": type}      # Parameter schema
)
async def tool_name_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Implementation remains unchanged
    ...
```

---

## Detailed Implementation Tasks

### Task 1: Add SDK Imports to DataDog Server

**File:** `/mcp_servers/datadog_server.py`

**Action:** Add imports at the top of the file (after existing imports, around line 28)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
```

**Verification:** No syntax errors, imports resolve correctly

---

### Task 2: Decorate DataDog Tools with @tool

**File:** `/mcp_servers/datadog_server.py`

#### 2.1: Decorate `search_logs_tool`

**Location:** Line 157 (before `async def search_logs_tool`)

**Add:**
```python
@tool(
    name="search_logs",
    description="Search DataDog logs with query and time filters. Use this to find logs matching specific criteria like error messages, service names, or identifiers.",
    parameters={
        "query": str,
        "from_time": str,
        "to_time": str,
        "limit": int,
    }
)
```

**Rationale:**
- Name matches tool naming without prefix (SDK adds `mcp__datadog__` automatically)
- Description is clear for AI to understand when to use this tool
- Parameters match the existing function signature

#### 2.2: Decorate `get_logs_by_efilogid_tool`

**Location:** Line 230 (before `async def get_logs_by_efilogid_tool`)

**Add:**
```python
@tool(
    name="get_logs_by_efilogid",
    description="Get all logs for a specific session ID (efilogid). Use this to retrieve the complete log trail for a user session.",
    parameters={
        "efilogid": str,
        "time_window": str,
    }
)
```

#### 2.3: Decorate `parse_stack_trace_tool`

**Location:** Line 305 (before `async def parse_stack_trace_tool`)

**Add:**
```python
@tool(
    name="parse_stack_trace",
    description="Extract file paths and exceptions from Java/Kotlin stack traces. Use this to identify which source files are involved in an error.",
    parameters={
        "stack_trace_text": str,
    }
)
```

**Verification:** All three tools have decorators, function signatures remain unchanged

---

### Task 3: Create DataDog MCP Server Instance

**File:** `/mcp_servers/datadog_server.py`

**Action:** Add at the END of the file (after all tool definitions, around line 396)

```python
# Export MCP server for use by lead agent
DATADOG_MCP_SERVER = create_sdk_mcp_server(
    name="datadog",
    version="1.0.0",
    tools=[
        search_logs_tool,
        get_logs_by_efilogid_tool,
        parse_stack_trace_tool,
    ]
)
```

**Note:** Keep existing utility functions (`reset_datadog_api`, `set_datadog_api`, etc.) for testing

**Verification:**
- `DATADOG_MCP_SERVER` is defined and exported
- Existing test helper functions remain untouched

---

### Task 4: Add SDK Imports to GitHub Server

**File:** `/mcp_servers/github_server.py`

**Action:** Add imports at the top of the file (after existing imports, around line 28)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
```

**Verification:** No syntax errors, imports resolve correctly

---

### Task 5: Decorate GitHub Tools with @tool

**File:** `/mcp_servers/github_server.py`

#### 5.1: Decorate `search_commits_tool`

**Location:** Line 153 (before `async def search_commits_tool`)

**Add:**
```python
@tool(
    name="search_commits",
    description="Search commits in a GitHub repository within a time range. Use this to find deployments or code changes in a specific time window.",
    parameters={
        "owner": str,
        "repo": str,
        "since": str,
        "until": str,
        "author": str,
        "path": str,
    }
)
```

#### 5.2: Decorate `get_file_content_tool`

**Location:** Line 249 (before `async def get_file_content_tool`)

**Add:**
```python
@tool(
    name="get_file_content",
    description="Get the content of a file at a specific commit. Use this to review code at the exact version that was deployed.",
    parameters={
        "owner": str,
        "repo": str,
        "file_path": str,
        "commit_sha": str,
    }
)
```

#### 5.3: Decorate `get_pr_files_tool`

**Location:** Line 326 (before `async def get_pr_files_tool`)

**Add:**
```python
@tool(
    name="get_pr_files",
    description="Get the list of files changed in a pull request. Use this to see what was modified in a PR.",
    parameters={
        "owner": str,
        "repo": str,
        "pr_number": int,
    }
)
```

#### 5.4: Decorate `compare_commits_tool`

**Location:** Line 403 (before `async def compare_commits_tool`)

**Add:**
```python
@tool(
    name="compare_commits",
    description="Compare two commits to see what changed. Use this to generate a diff between a deployed version and its parent.",
    parameters={
        "owner": str,
        "repo": str,
        "base": str,
        "head": str,
        "file_path": str,
    }
)
```

**Verification:** All four tools have decorators, function signatures remain unchanged

---

### Task 6: Create GitHub MCP Server Instance

**File:** `/mcp_servers/github_server.py`

**Action:** Add at the END of the file (after all tool definitions, around line 500+)

```python
# Export MCP server for use by lead agent
GITHUB_MCP_SERVER = create_sdk_mcp_server(
    name="github",
    version="1.0.0",
    tools=[
        search_commits_tool,
        get_file_content_tool,
        get_pr_files_tool,
        compare_commits_tool,
    ]
)
```

**Note:** Keep existing utility functions (`reset_github_helper`, `set_github_helper`, etc.) for testing

**Verification:**
- `GITHUB_MCP_SERVER` is defined and exported
- Existing test helper functions remain untouched

---

### Task 7: Update Lead Agent Imports

**File:** `/agents/lead_agent.py`

**Action:** Replace lines 32-33

**Remove:**
```python
# Import MCP server tool functions for registration
from mcp_servers import datadog_server, github_server
```

**Replace with:**
```python
# Import MCP server instances (SDK-wrapped)
from mcp_servers.datadog_server import DATADOG_MCP_SERVER
from mcp_servers.github_server import GITHUB_MCP_SERVER
```

**Verification:** Imports resolve without errors

---

### Task 8: Remove Manual MCP Server Definitions

**File:** `/agents/lead_agent.py`

**Action:** DELETE lines 37-59 (entire section)

**Remove:**
```python
# MCP Server definitions - these are placeholder objects representing MCP server configuration
# They will be used by ClaudeAgentOptions.mcp_servers to register the tools
# In production, these would be actual MCP server instances
datadog_mcp_server = {
    "name": "datadog",
    "version": "1.0.0",
    "tools": [
        datadog_server.search_logs_tool,
        datadog_server.get_logs_by_efilogid_tool,
        datadog_server.parse_stack_trace_tool,
    ]
}

github_mcp_server = {
    "name": "github",
    "version": "1.0.0",
    "tools": [
        github_server.search_commits_tool,
        github_server.get_file_content_tool,
        github_server.get_pr_files_tool,
        github_server.compare_commits_tool,
    ]
}
```

**Rationale:** These manual dictionaries are no longer needed - we import the SDK-wrapped servers instead

**Verification:** No references to `datadog_mcp_server` or `github_mcp_server` remain except in the registration section

---

### Task 9: Update MCP Server Registration

**File:** `/agents/lead_agent.py`

**Action:** Update lines 223-226 (inside `investigate()` method)

**Replace:**
```python
        # Setup MCP servers
        mcp_servers = {
            "datadog": datadog_mcp_server,
            "github": github_mcp_server,
        }
```

**With:**
```python
        # Setup MCP servers (SDK-wrapped instances)
        mcp_servers = {
            "datadog": DATADOG_MCP_SERVER,
            "github": GITHUB_MCP_SERVER,
        }
```

**Verification:** Variables reference the imported constants

---

## Testing Strategy

### Pre-Implementation Test Verification

**Before making changes, verify current test status:**

```bash
# Run all tests to establish baseline
uv run python -m pytest tests/ -v

# Run specific test files
uv run python -m pytest tests/test_mcp_tools.py -v
uv run python -m pytest tests/test_lead_agent.py -v
```

**Expected:** Tests should currently PASS (they import tools correctly and use mocks)

### Post-Implementation Test Verification

**After making changes, run the same tests:**

```bash
# Run all tests
uv run python -m pytest tests/ -v

# Run critical path tests (should maintain 95%+ coverage)
uv run pytest --cov=mcp_servers --cov-fail-under=95

# Run specific test files
uv run python -m pytest tests/test_mcp_tools.py -v
uv run python -m pytest tests/test_lead_agent.py -v
```

**Expected:** All tests should STILL PASS because:
- `test_mcp_tools.py` already imports tools directly (`from mcp_servers.datadog_server import search_logs_tool`)
- `test_lead_agent.py` mocks lead_agent components, doesn't care about internal implementation
- The function implementations themselves are unchanged, only their decoration

### Manual Verification

**After tests pass, verify the application runs:**

```bash
# Try to start the application
uv run main.py

# Should NOT crash with JSON serialization error
# Should start and prompt for input
```

**Success Criteria:**
- No `TypeError: Object of type function is not JSON serializable`
- Application reaches interactive prompt
- MCP servers are logged during initialization
- Can input a test query without immediate crash

---

## Test Impact Analysis

### Tests That Should NOT Need Changes

#### `/tests/test_mcp_tools.py`
**Reason:** Already imports tools correctly
```python
from mcp_servers.datadog_server import (
    search_logs_tool,  # ← Direct import, works with decorator
    get_logs_by_efilogid_tool,
    parse_stack_trace_tool,
    set_datadog_api,  # ← Utility functions unchanged
    ...
)
```

**Verification:** All 100+ test cases should pass without modification

#### `/tests/test_lead_agent.py`
**Reason:** Uses mocks for all components
```python
with patch("agents.lead_agent.get_config") as mock_get_config, \
     patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
     patch("agents.lead_agent.datadog_mcp_server") as mock_datadog_server:
```

**Note:** Line 878 and 879 mock `datadog_mcp_server` and `github_mcp_server` - these will change to:
```python
     patch("agents.lead_agent.DATADOG_MCP_SERVER") as mock_datadog_server, \
     patch("agents.lead_agent.GITHUB_MCP_SERVER") as mock_github_server:
```

**Action Required:** Update 2 test patches to use new constant names

---

### Task 10: Update test_lead_agent.py Patches

**File:** `/tests/test_lead_agent.py`

**Location:** Line 878-879 in `TestLeadAgentMCPServers.test_lead_agent_configures_mcp_servers`

**Replace:**
```python
             patch("agents.lead_agent.datadog_mcp_server") as mock_datadog_server, \
             patch("agents.lead_agent.github_mcp_server") as mock_github_server:
```

**With:**
```python
             patch("agents.lead_agent.DATADOG_MCP_SERVER") as mock_datadog_server, \
             patch("agents.lead_agent.GITHUB_MCP_SERVER") as mock_github_server:
```

**Verification:** Test `test_lead_agent_configures_mcp_servers` passes

---

## Rollback Plan

If the fix causes unexpected issues:

### Immediate Rollback (Git)

```bash
# Stash changes
git stash

# Or revert specific files
git checkout HEAD -- agents/lead_agent.py
git checkout HEAD -- mcp_servers/datadog_server.py
git checkout HEAD -- mcp_servers/github_server.py
git checkout HEAD -- tests/test_lead_agent.py
```

### What to Check If Issues Occur

1. **Import errors:** Verify `claude_agent_sdk` is installed (`uv run python -c "import claude_agent_sdk; print(claude_agent_sdk.__version__)"`)
2. **Decorator errors:** Check that `@tool` decorator is directly above function definition (no blank lines)
3. **Parameter schema errors:** Ensure parameter types match actual function expectations
4. **Test failures:** Check test output for specific assertion failures

---

## Implementation Checklist

Copy this checklist when implementing:

### Phase 1: DataDog Server
- [ ] Task 1: Add SDK imports to `datadog_server.py`
- [ ] Task 2.1: Decorate `search_logs_tool`
- [ ] Task 2.2: Decorate `get_logs_by_efilogid_tool`
- [ ] Task 2.3: Decorate `parse_stack_trace_tool`
- [ ] Task 3: Create `DATADOG_MCP_SERVER` instance
- [ ] Verify: No syntax errors in `datadog_server.py`

### Phase 2: GitHub Server
- [ ] Task 4: Add SDK imports to `github_server.py`
- [ ] Task 5.1: Decorate `search_commits_tool`
- [ ] Task 5.2: Decorate `get_file_content_tool`
- [ ] Task 5.3: Decorate `get_pr_files_tool`
- [ ] Task 5.4: Decorate `compare_commits_tool`
- [ ] Task 6: Create `GITHUB_MCP_SERVER` instance
- [ ] Verify: No syntax errors in `github_server.py`

### Phase 3: Lead Agent
- [ ] Task 7: Update imports in `lead_agent.py`
- [ ] Task 8: Remove manual MCP server dicts
- [ ] Task 9: Update MCP server registration
- [ ] Verify: No syntax errors in `lead_agent.py`

### Phase 4: Tests
- [ ] Task 10: Update patches in `test_lead_agent.py`
- [ ] Verify: `test_lead_agent.py` has no syntax errors

### Phase 5: Verification
- [ ] Run: `uv run python -m pytest tests/test_mcp_tools.py -v`
- [ ] Run: `uv run python -m pytest tests/test_lead_agent.py -v`
- [ ] Run: `uv run python -m pytest tests/ -v` (all tests)
- [ ] Run: `uv run main.py` (application starts without crash)
- [ ] Verify: No `TypeError: Object of type function is not JSON serializable`
- [ ] Verify: Application reaches interactive prompt

---

## Additional Notes

### Why This Approach

1. **Minimal Changes:** Only modifies what's necessary to fix the issue
2. **Test Preservation:** Existing tests continue to work with minimal changes
3. **SDK Compliant:** Follows the official Claude Agent SDK pattern
4. **Maintainable:** Clear separation between tool definition and server registration

### Future Considerations

- Consider adding more descriptive tool descriptions for better AI understanding
- May want to add parameter validation within tools (currently handled by SDK)
- Could extract common tool patterns into utility decorators

### Dependencies

- `claude-agent-sdk` version 0.1.35+ (already installed)
- No new dependencies required

---

## Approval & Sign-off

**Technical Review:** [ ] Approved
**Test Coverage:** [ ] Verified (95%+ maintained)
**Ready for Implementation:** [ ] Yes

---

**Document Version:** 1.0
**Last Updated:** 2026-02-14
**Author:** Claude (Opus 4.6)
