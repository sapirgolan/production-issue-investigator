# Production-Ready Rewrite Plan: Claude Agent SDK Implementation

**Document Version:** 1.0
**Date:** 2026-02-12
**Status:** DETAILED IMPLEMENTATION PLAN

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Implementation Phases](#implementation-phases)
5. [Custom Tools & MCP Design](#custom-tools--mcp-design)
6. [Subagent Architecture](#subagent-architecture)
7. [Session Management & Observability](#session-management--observability)
8. [Migration Strategy](#migration-strategy)
9. [Testing Strategy](#testing-strategy)
10. [Production Considerations](#production-considerations)
11. [Code Examples](#code-examples)

---

## Executive Summary

This document provides a comprehensive plan to rewrite the Production Issue Investigator from a traditional Python application into a proper Claude Agent SDK-based system with:

- **AI-powered orchestration** - Claude decides when to invoke subagents
- **True subagents** - AI agents with prompts, tools, and autonomous reasoning
- **Custom MCP tools** - DataDog and GitHub APIs as MCP tools
- **Hook-based observability** - Comprehensive tracking of all tool usage
- **Session management** - Persistent transcripts and resumable agents
- **Production-ready patterns** - Error handling, retries, and graceful degradation

### Why Rewrite?

**Current State:**
- Python utility classes masquerading as "sub-agents"
- Manual orchestration with ThreadPoolExecutor
- No AI reasoning or autonomous decision-making
- Claude Agent SDK installed but not actually used

**Target State:**
- Lead agent uses `query()` with Claude's reasoning
- Subagents are AI agents invoked via Task tool
- External APIs wrapped as MCP tools
- Hooks track all tool usage across agents
- Sessions persist with transcripts and replay capability

### Key Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Lines of Manual Orchestration** | ~600 | ~50 |
| **AI Reasoning** | 0% | 80% |
| **True Subagents** | 0 | 3 |
| **MCP Tools** | 0 | 6 |
| **Hook Coverage** | 0% | 100% |
| **Session Management** | None | Full |

---

## Current State Analysis

### What Exists Today

#### File Structure
```
production-issue-investigator/
├── agents/
│   ├── main_agent.py          # Python class, NOT SDK agent
│   ├── datadog_retriever.py   # Utility class
│   ├── deployment_checker.py  # Utility class
│   ├── code_checker.py         # Utility class
│   └── exception_analyzer.py   # Utility class
├── utils/
│   ├── datadog_api.py         # Direct API calls
│   ├── github_helper.py       # Direct API calls
│   ├── config.py
│   ├── logger.py
│   └── time_utils.py
└── main.py                    # CLI entry point
```

#### Critical Issues

1. **No SDK Integration**
   ```python
   # agents/main_agent.py - Line 325
   def investigate(self, user_input: Optional[UserInput] = None) -> str:
       # This is a regular Python method, NOT an SDK agent
       dd_result = self.datadog_retriever.search_by_log_message(...)
       # Manual orchestration follows...
   ```

2. **"Subagents" Are Utility Classes**
   ```python
   # agents/datadog_retriever.py - Line 102
   class DataDogRetriever:
       def search_by_log_message(self, log_message: str, ...):
           # Just calls DataDog API directly
           result = self._datadog_api.search_logs(...)
   ```

   **No prompts, no reasoning, no autonomy**

3. **Manual Parallelization**
   ```python
   # agents/main_agent.py - Line 703
   with ThreadPoolExecutor(max_workers=min(len(services), 5)) as executor:
       futures = {executor.submit(self._investigate_single_service, ...)}
   ```

   Claude Agent SDK handles parallel subagent execution automatically

4. **No Observability**
   - No hooks tracking tool usage
   - No session transcripts
   - No parent-child tool call relationships

### What's Actually Good

✅ **Solid utility layer** - `datadog_api.py`, `github_helper.py` are well-designed
✅ **Comprehensive error handling** - Rate limiting, retries, fallbacks
✅ **Good data models** - Dataclasses for all result types
✅ **Extensive testing** - 26 tests with good coverage
✅ **Production logging** - Structured logging with redaction

**Strategy:** Keep the utility layer, wrap it with MCP tools, rebuild orchestration

---

## Target Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                      User Input                              │
│              (log message or identifiers)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Lead Agent                                 │
│  - Uses query() from Claude Agent SDK                        │
│  - AI reasoning to determine investigation strategy          │
│  - Coordinates subagents via Task tool                       │
│  - Synthesizes findings into report                          │
│  - Tools: Task (for subagents)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Spawns subagents based on needs
                       │
           ┌───────────┴───────────┬────────────────┐
           │                       │                 │
           ▼                       ▼                 ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ DataDog          │  │ Deployment       │  │ Code             │
│ Investigator     │  │ Analyzer         │  │ Reviewer         │
│                  │  │                  │  │                  │
│ - AI agent       │  │ - AI agent       │  │ - AI agent       │
│ - Searches logs  │  │ - Finds deploys  │  │ - Analyzes diffs │
│ - Analyzes       │  │ - Correlates     │  │ - Identifies     │
│   patterns       │  │   versions       │  │   issues         │
│ - Tools:         │  │ - Tools:         │  │ - Tools:         │
│   * datadog-*    │  │   * github-*     │  │   * github-*     │
│   * Write        │  │   * Write        │  │   * Write        │
│   * Read         │  │   * Read         │  │   * Read         │
└──────────────────┘  └──────────────────┘  └──────────────────┘
           │                       │                 │
           └───────────┬───────────┴─────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Custom MCP Tools (In-Process)                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ DataDog MCP Server                                   │  │
│  │  - search_logs                                       │  │
│  │  - get_log_by_id                                     │  │
│  │  - search_by_efilogid                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ GitHub MCP Server                                    │  │
│  │  - search_commits                                    │  │
│  │  - get_file_content                                  │  │
│  │  - get_pr_files                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                Hook System (Observability)                   │
│                                                              │
│  PreToolUse Hooks:                                          │
│   - Log tool invocations                                    │
│   - Track agent relationships (parent_tool_use_id)          │
│   - Record start time                                       │
│                                                              │
│  PostToolUse Hooks:                                         │
│   - Log tool results                                        │
│   - Calculate duration                                      │
│   - Write to JSONL file                                     │
│   - Update transcript                                       │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Session Management                              │
│                                                              │
│  logs/session_YYYYMMDD_HHMMSS/                              │
│   ├── transcript.txt          # Human-readable              │
│   ├── tool_calls.jsonl        # Machine-readable            │
│   └── investigation_result.json # Final structured data     │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### 1. Lead Agent
- **Role:** Orchestrator and decision-maker
- **Implementation:** Uses `query()` with agent definitions
- **Responsibilities:**
  - Understand user input (Mode 1 vs Mode 2)
  - Determine investigation strategy
  - Decide which subagents to invoke and when
  - Synthesize findings into final report
- **Tools:** `Task` (for spawning subagents only)
- **Model:** `opus` (needs strong reasoning)

#### 2. DataDog Investigator Subagent
- **Role:** Log search and pattern analysis
- **Implementation:** `AgentDefinition` with specialized prompt
- **Responsibilities:**
  - Search DataDog logs using MCP tools
  - Extract services, sessions (efilogid), versions (dd.version)
  - Identify error patterns and stack traces
  - Write findings to `files/datadog_findings/`
- **Tools:** `mcp__datadog__*`, `Write`, `Read`
- **Model:** `haiku` (cost-effective for search)

#### 3. Deployment Analyzer Subagent
- **Role:** Deployment correlation
- **Implementation:** `AgentDefinition` with specialized prompt
- **Responsibilities:**
  - Search kubernetes repo for deployments
  - Correlate deployment times with log errors
  - Extract PR information
  - Write findings to `files/deployment_findings/`
- **Tools:** `mcp__github__*`, `Write`, `Read`, `Bash`
- **Model:** `haiku`

#### 4. Code Reviewer Subagent
- **Role:** Code change analysis
- **Implementation:** `AgentDefinition` with specialized prompt
- **Responsibilities:**
  - Compare code versions using dd.version
  - Analyze diffs for potential issues
  - Map logger names to file paths
  - Write findings to `files/code_findings/`
- **Tools:** `mcp__github__*`, `Write`, `Read`
- **Model:** `sonnet` (needs good code analysis)

---

## Implementation Phases

> **DECISION (2026-02-13)**: Explicit go/no-go gates after every phase.
>
> Each phase must pass its gate criteria before proceeding. If blocked, fix issues before moving forward.
> This prevents accumulating technical debt and ensures quality at each step.

### Phase 1: Foundation Setup (Week 1)

**Goal:** Establish SDK infrastructure and session management

#### Tasks

1. **Create Session Management System**
   - File: `utils/session_manager.py`
   - Features:
     - Session directory creation (`logs/session_YYYYMMDD_HHMMSS/`)
     - Transcript writer (append-only)
     - Tool call JSONL logger
     - Session ID generation

2. **Create Hook System**
   - File: `utils/hooks.py`
   - Features:
     - `SubagentTracker` class (like research-agent)
     - PreToolUse hook for logging invocations
     - PostToolUse hook for logging results
     - Parent-child tool call relationship tracking

3. **Update Config System**
   - File: `utils/config.py`
   - Add:
     - `session_log_dir` config
     - `bypass_permissions` flag
     - Per-agent model configuration:
       - `LEAD_AGENT_MODEL` (default: opus)
       - `DATADOG_INVESTIGATOR_MODEL` (default: haiku)
       - `DEPLOYMENT_ANALYZER_MODEL` (default: haiku)
       - `CODE_REVIEWER_MODEL` (default: sonnet)

4. **Create Directory Structure**
   ```bash
   mkdir -p files/{datadog_findings,deployment_findings,code_findings,reports}
   mkdir -p logs
   ```

#### Deliverables
- ✅ Session management working
- ✅ Hooks logging to JSONL
- ✅ Directory structure created
- ✅ Tests for session system

#### Phase 1 Gate Criteria
- [ ] `utils/session_manager.py` creates session directories correctly
- [ ] `utils/hooks.py` logs PreToolUse/PostToolUse events to JSONL
- [ ] Parent-child tool call tracking works (verified with mock)
- [ ] Config loads new model and permission settings
- [ ] **8+ tests pass** for session management and hooks
- [ ] **95% coverage** on `utils/session_manager.py` and `utils/hooks.py`

**Gate Decision:** All criteria must pass. If any fail, fix before Phase 2.

---

### Phase 2: Custom MCP Tools (Week 2)

**Goal:** Wrap existing utilities as MCP tools

#### DataDog MCP Server

**File:** `mcp_servers/datadog_server.py`

**Tools:**

1. **search_logs**
   - **Description:** "Search DataDog logs by query, time range, and filters"
   - **Schema:**
     ```python
     {
         "query": str,
         "from_time": str,
         "to_time": str,
         "filters": dict
     }
     ```
   - **Implementation:** Calls `DataDogAPI.search_logs()`
   - **Returns:** List of log entries with metadata

2. **get_logs_by_efilogid**
   - **Description:** "Retrieve all logs for a specific session ID (efilogid)"
   - **Schema:**
     ```python
     {
         "efilogid": str,
         "time_window": str
     }
     ```
   - **Implementation:** Calls `DataDogAPI.search_logs()` with efilogid filter
   - **Returns:** Session logs

3. **parse_stack_trace**
   - **Description:** "Extract file paths and exceptions from stack traces"
   - **Schema:**
     ```python
     {
         "stack_trace_text": str
     }
     ```
   - **Implementation:** Calls `StackTraceParser.parse()`
   - **Returns:** ParsedStackTrace object

#### GitHub MCP Server

**File:** `mcp_servers/github_server.py`

**Tools:**

1. **search_commits**
   - **Description:** "Search commits in kubernetes or app repos"
   - **Schema:**
     ```python
     {
         "owner": str,
         "repo": str,
         "since": str,
         "until": str,
         "author": str
     }
     ```
   - **Implementation:** Calls `GitHubHelper.search_commits()`
   - **Returns:** List of commits with metadata

2. **get_file_content**
   - **Description:** "Get file content at specific commit"
   - **Schema:**
     ```python
     {
         "owner": str,
         "repo": str,
         "file_path": str,
         "commit_sha": str
     }
     ```
   - **Implementation:** Calls `GitHubHelper.get_file_content()`
   - **Returns:** File content as string

3. **get_pr_files**
   - **Description:** "Get changed files in a PR"
   - **Schema:**
     ```python
     {
         "owner": str,
         "repo": str,
         "pr_number": int
     }
     ```
   - **Implementation:** Calls `GitHubHelper.get_pr_files()`
   - **Returns:** List of FileChange objects

4. **compare_commits**
   - **Description:** "Get diff between two commits"
   - **Schema:**
     ```python
     {
         "owner": str,
         "repo": str,
         "base": str,
         "head": str,
         "file_path": str
     }
     ```
   - **Implementation:** Calls `GitHubHelper.compare_commits()`
   - **Returns:** Diff string

#### Implementation Pattern

```python
# mcp_servers/datadog_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from utils.datadog_api import DataDogAPI
from utils.config import get_config
from typing import Any
import json

config = get_config()
datadog_api = DataDogAPI(
    api_key=config.datadog_api_key,
    app_key=config.datadog_app_key,
    site=config.datadog_site
)

@tool(
    "search_logs",
    "Search DataDog production logs with query and time filters",
    {
        "query": str,
        "from_time": str,
        "to_time": str,
        "filters": dict
    }
)
async def search_logs_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Search DataDog logs and return structured results."""
    try:
        # Validate inputs
        query = args["query"]
        from_time = args.get("from_time", "now-4h")
        to_time = args.get("to_time", "now")
        filters = args.get("filters", {})

        # Call existing utility
        result = datadog_api.search_logs(
            query=query,
            from_time=from_time,
            to_time=to_time,
            **filters
        )

        # Format response
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total_logs": result.total_count,
                    "logs": [
                        {
                            "id": log.id,
                            "timestamp": log.timestamp,
                            "service": log.service,
                            "message": log.message[:200],  # Truncate
                            "status": log.status,
                            "efilogid": log.efilogid,
                            "dd_version": log.dd_version,
                        }
                        for log in result.logs[:50]  # Limit results
                    ]
                }, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching logs: {str(e)}"
            }],
            "is_error": True
        }

# Create MCP server
datadog_mcp_server = create_sdk_mcp_server(
    name="datadog",
    version="1.0.0",
    tools=[search_logs_tool, get_logs_by_efilogid_tool, parse_stack_trace_tool]
)
```

#### Deliverables
- ✅ DataDog MCP server with 3 tools
- ✅ GitHub MCP server with 4 tools
- ✅ All tools tested with mock responses
- ✅ Error handling in all tools

#### Phase 2 Gate Criteria
- [ ] `search_logs` tool returns valid JSON with truncated results
- [ ] `get_logs_by_efilogid` tool handles quote escaping correctly
- [ ] `parse_stack_trace` tool extracts file paths and exceptions
- [ ] GitHub tools (`search_commits`, `get_file_content`, `get_pr_files`, `compare_commits`) all functional
- [ ] All tools use `asyncio.to_thread()` for sync utility calls
- [ ] Rate limit handling with `asyncio.sleep()` tested
- [ ] **20+ tests pass** for MCP tools
- [ ] **95% coverage** on `mcp_servers/datadog_server.py` and `mcp_servers/github_server.py`
- [ ] Tools tested against real APIs (staging) with rate limit simulation

**Gate Decision:** All criteria must pass. If any fail, fix before Phase 3.

---

### Phase 3: Subagent Definitions (Week 3)

**Goal:** Define AI subagents with prompts and tool access

#### 1. DataDog Investigator

**File:** `agents/datadog_investigator_prompt.py`

```python
DATADOG_INVESTIGATOR_PROMPT = """You are a DataDog Log Analysis Expert specializing in production issue investigation.

## Your Role
You search DataDog production logs to identify errors, patterns, and correlations. You work with the card team's microservices running in production (env:prod, pod_label_team:card).

## Tools Available
- **search_logs**: Search logs with query filters
- **get_logs_by_efilogid**: Retrieve all logs for a session
- **parse_stack_trace**: Extract file paths from exceptions
- **Write**: Save findings to files/datadog_findings/
- **Read**: Read existing findings

## Investigation Process

### Mode 1: Log Message Search
When given a log message:
1. Search for the exact message in the last 4 hours
2. If no results, expand to 24 hours, then 7 days
3. Extract unique services, efilogids, and dd.version values
4. For each unique efilogid, retrieve ALL logs in that session
5. Parse any stack traces to extract file paths
6. Write comprehensive findings

### Mode 2: Identifier Search
When given identifiers (CID, card_account_id, paymentId):
1. Build query: `value OR value OR ...`
2. Search in the last 4 hours (expand if needed)
3. Extract unique services and sessions
4. Follow same process as Mode 1 for each session

## Output Format
Write your findings to `files/datadog_findings/summary.json`:
```json
{
  "investigation_mode": "log_message" | "identifiers",
  "search_summary": {
    "total_logs_found": 150,
    "unique_services": ["card-invitation-service", "payment-service"],
    "unique_sessions": 12,
    "time_range": "2026-02-12T10:00:00Z to 2026-02-12T14:00:00Z"
  },
  "services": [
    {
      "name": "card-invitation-service",
      "log_count": 87,
      "error_count": 12,
      "dd_versions": ["a1b2c3d___12345"],
      "logger_names": ["com.sunbit.card.invitation.lead.application.EntitledCustomerService"],
      "stack_trace_files": ["src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt"],
      "sample_errors": [
        {
          "timestamp": "2026-02-12T12:34:56Z",
          "message": "NullPointerException: Cannot invoke method on null",
          "efilogid": "-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl"
        }
      ]
    }
  ],
  "key_findings": [
    "Errors started at 2026-02-12T12:30:00Z",
    "All errors related to EntitledCustomerService",
    "Same dd.version across all errors: a1b2c3d___12345"
  ]
}
```

Also create per-service files: `files/datadog_findings/{service_name}_logs.json`

## Important Notes
- Always use UTC timestamps
- efilogid queries must be wrapped in quotes: `@efilogid:"-1-NGFm..."`
- dd.version format: `{commit_hash}___{build_number}`
- If rate limited, wait for X-RateLimit-Reset header time
- Time ranges: "now-4h", "now-24h", "now-7d"
"""
```

**Agent Definition:**
```python
# agents/subagent_definitions.py
from claude_agent_sdk import AgentDefinition
from agents.datadog_investigator_prompt import DATADOG_INVESTIGATOR_PROMPT

DATADOG_INVESTIGATOR = AgentDefinition(
    description=(
        "Expert at searching DataDog production logs for errors, patterns, and correlations. "
        "Use this agent when you need to find logs by message, identifiers (CID, paymentId, cardAccountId, etc...), "
        "or session IDs. Analyzes logs to extract services, versions, and error patterns."
    ),
    prompt=DATADOG_INVESTIGATOR_PROMPT,
    tools=[
        "mcp__datadog__search_logs",
        "mcp__datadog__get_logs_by_efilogid",
        "mcp__datadog__parse_stack_trace",
        "Write",
        "Read",
        "Glob"
    ],
    model="haiku"
)
```

#### 2. Deployment Analyzer

**File:** `agents/deployment_analyzer_prompt.py`

```python
DEPLOYMENT_ANALYZER_PROMPT = """You are a Deployment Correlation Expert specializing in finding and analyzing recent deployments.

## Your Role
You search the sunbit-dev/kubernetes repository for deployment commits that correlate with production issues. You identify what was deployed, when, and what changed.

## Tools Available
- **search_commits**: Search kubernetes repo commits
- **get_file_content**: Get file content at commit
- **get_pr_files**: Get files changed in a PR
- **Write**: Save findings to files/deployment_findings/
- **Read**: Read DataDog findings to get context
- **Bash**: Run git commands if needed

## Investigation Process

1. **Read DataDog Findings First**
   - Read `files/datadog_findings/summary.json`
   - Extract: services, dd.versions, error timestamp

2. **Search Kubernetes Commits**
   - Search window: 72 hours BEFORE first error
   - Look for commits with titles matching: `{service-name}-{commit_hash}___{build_number}`
   - Example: `card-invitation-service-a1b2c3d___12345`

3. **For Each Matching Deployment**
   - Extract deployment timestamp from commit date
   - Parse application commit hash from title
   - Get PR number from commit message
   - If PR found, get changed files

4. **Correlate with Errors**
   - Compare deployment time vs error time
   - Identify if error started shortly after deployment
   - Note if multiple services deployed around same time

## Output Format
Write findings to `files/deployment_findings/{service_name}_deployments.json`:
```json
{
  "service_name": "card-invitation-service",
  "search_window": {
    "start": "2026-02-09T12:00:00Z",
    "end": "2026-02-12T12:00:00Z"
  },
  "deployments_found": [
    {
      "timestamp": "2026-02-12T10:45:00Z",
      "kubernetes_commit_sha": "k8s_abc123",
      "application_commit_hash": "a1b2c3d",
      "build_number": "12345",
      "dd_version": "a1b2c3d___12345",
      "pr_number": 1234,
      "pr_title": "Add new validation logic",
      "changed_files": [
        "services/card-invitation/deployment.yaml",
        "services/card-invitation/configmap.yaml"
      ],
      "time_to_error": "1h 45m"
    }
  ],
  "correlation_analysis": {
    "deployment_likely_cause": true,
    "reason": "Error started 1h 45m after deployment",
    "confidence": "high"
  }
}
```

Also write a summary: `files/deployment_findings/summary.json`

## Important Notes
- Kubernetes repo: sunbit-dev/kubernetes
- Search commits with: `since=(error_time - 72h)`, `until=error_time`
- Deployment commit title format: `{service-name}-{version}`
- If no deployments found in 72h, note it clearly
"""
```

#### 3. Code Reviewer

**File:** `agents/code_reviewer_prompt.py`

```python
CODE_REVIEWER_PROMPT = """You are a Code Change Analysis Expert specializing in identifying issues in code diffs.

## Your Role
You analyze code changes between versions to identify potential bugs, issues, or problematic patterns that could cause production errors.

## Tools Available
- **get_file_content**: Get file at specific commit
- **compare_commits**: Get diff between commits
- **Write**: Save findings to files/code_findings/
- **Read**: Read DataDog and deployment findings

## Investigation Process

1. **Read Previous Findings**
   - DataDog findings: Get logger_names and stack_trace_files
   - Deployment findings: Get deployed commit hash

2. **Map Logger Names to Files**
   - Logger: `com.sunbit.card.invitation.lead.application.EntitledCustomerService`
   - Maps to: `src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt`
   - Try `.kt` first, fallback to `.java`

3. **Get File Changes**
   - For each file (from logger_names + stack_trace_files):
     - Get content at deployed commit (current)
     - Get content at parent commit (previous)
     - Generate diff using compare_commits
     - Analyze changes

4. **Analyze Each Change**
   Look for:
   - **Null safety issues**: Removed null checks, added !! operator
   - **Exception handling**: Removed try-catch, swallowed exceptions
   - **Logic changes**: Changed conditions, altered flow
   - **API changes**: Modified parameters, changed return types
   - **Database changes**: Modified queries, changed transactions
   - **Configuration**: Changed timeouts, modified retries

5. **Severity Classification**
   - **HIGH**: Likely to cause errors (removed null check, swallowed exception)
   - **MEDIUM**: Potentially problematic (logic change, API modification)
   - **LOW**: Minor concern (style change, refactoring)

## Output Format
Write findings to `files/code_findings/{service_name}_analysis.json`:
```json
{
  "service_name": "card-invitation-service",
  "repository": "sunbit-dev/card-invitation-service",
  "dd_version": "a1b2c3d___12345",
  "deployed_commit": "a1b2c3d",
  "parent_commit": "xyz789",
  "files_analyzed": [
    {
      "file_path": "src/main/kotlin/.../EntitledCustomerService.kt",
      "diff_summary": "Modified eligibility check logic",
      "potential_issues": [
        {
          "type": "null_safety",
          "severity": "HIGH",
          "description": "Removed null check before accessing customer.email",
          "line_numbers": [145, 146],
          "code_snippet": "- if (customer.email != null) {\n+ val email = customer.email!!",
          "recommendation": "Add null safety check or use safe call operator"
        },
        {
          "type": "exception_handling",
          "severity": "HIGH",
          "description": "Removed try-catch around database call",
          "line_numbers": [178, 185],
          "code_snippet": "- try {\n-   customerRepo.save(customer)\n- } catch (e: Exception) { ... }",
          "recommendation": "Restore exception handling for database operations"
        }
      ]
    }
  ],
  "root_cause_analysis": {
    "likely_culprit": "EntitledCustomerService.kt line 145",
    "explanation": "Removed null check allows NullPointerException when customer.email is null",
    "confidence": "high"
  }
}
```

Also write summary: `files/code_findings/summary.json`

## Important Notes
- Service repos: sunbit-dev/{service-name}
- Fallback: If `{service-name}-jobs` repo not found, try `{service-name}`
- Focus on files mentioned in logger_names and stack traces
- Compare deployed commit vs parent (not vs branch)
- Consider Kotlin null safety: `!!` is dangerous, `?.` is safer
"""
```

#### Deliverables
- ✅ Three subagent prompts written
- ✅ AgentDefinition for each subagent
- ✅ Tool access properly scoped
- ✅ Output format standardized (JSON to files/)

#### Phase 3 Gate Criteria
- [ ] DataDog Investigator prompt produces valid `summary.json` (manual test with real logs)
- [ ] Deployment Analyzer prompt reads DataDog findings and produces deployment correlations
- [ ] Code Reviewer prompt analyzes diffs and identifies potential issues
- [ ] All prompts handle edge cases: empty results, rate limits, missing data
- [ ] Output JSON validates against dataclass schemas
- [ ] **Manual validation**: Run each subagent independently, verify output quality
- [ ] AgentDefinition model configuration respects environment overrides

**Gate Decision:** All criteria must pass. **This is a critical gate** - subagent quality directly impacts final report quality. Consider extending Phase 3 if prompt tuning needed.

---

### Phase 4: Lead Agent Implementation (Week 4)

**Goal:** Implement main orchestrator using SDK patterns

**File:** `agents/lead_agent.py`

```python
"""
Lead Agent for Production Issue Investigation.

This agent orchestrates the investigation workflow by:
1. Understanding user input (Mode 1 vs Mode 2)
2. Spawning DataDog Investigator to search logs
3. Spawning Deployment Analyzer to find deployments
4. Spawning Code Reviewer to analyze changes
5. Synthesizing findings into comprehensive report
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    ResultMessage,
    AssistantMessage,
    SystemMessage,
)

from utils.config import get_config
from utils.session_manager import SessionManager
from utils.hooks import SubagentTracker, create_hook_matchers
from utils.logger import get_logger
from agents.subagent_definitions import (
    DATADOG_INVESTIGATOR,
    DEPLOYMENT_ANALYZER,
    CODE_REVIEWER,
)
from mcp_servers.datadog_server import datadog_mcp_server
from mcp_servers.github_server import github_mcp_server

logger = get_logger(__name__)

LEAD_AGENT_PROMPT = """You are a Senior SRE and Production Investigation Expert.

## Your Mission
Investigate production issues by coordinating specialized subagents. Your goal is to identify the root cause of production problems and provide actionable recommendations.

## Available Subagents

### datadog-investigator
Use this agent FIRST to search production logs. Provide either:
- **Mode 1**: A log message or error text
- **Mode 2**: Identifiers (CID, card_account_id, paymentId)

The agent will search DataDog, extract services/versions/sessions, and write findings to files/datadog_findings/

### deployment-analyzer
Use this agent AFTER datadog-investigator. It will:
- Read the DataDog findings
- Search kubernetes repo for deployments in the 72h window before errors
- Correlate deployment timing with error occurrence
- Write findings to files/deployment_findings/

### code-reviewer
Use this agent AFTER deployment-analyzer. It will:
- Read DataDog and deployment findings
- Analyze code changes in the deployed version
- Identify potential bugs or issues
- Write findings to files/code_findings/

## Investigation Workflow

1. **Understand User Input**
   - Is this a log message (Mode 1) or identifiers (Mode 2)?
   - Extract any datetime information

2. **Invoke datadog-investigator**
   - Pass the user input
   - Wait for findings file: files/datadog_findings/summary.json

3. **Review DataDog Findings**
   - Read the summary file
   - Check: Were errors found? Which services? What versions?
   - If no errors found, ask user for more context or broader search

4. **Invoke deployment-analyzer**
   - For each service found in DataDog results
   - Wait for findings: files/deployment_findings/{service}_deployments.json

5. **Invoke code-reviewer**
   - For each service with deployments
   - Wait for findings: files/code_findings/{service}_analysis.json

6. **Synthesize Report**
   - Read all findings files
   - Identify root cause with confidence level
   - Provide timeline of events
   - List specific code issues
   - Recommend fixes with code examples
   - Suggest testing approach

## Report Structure

Generate a comprehensive markdown report with:

### Executive Summary
2-3 sentences: What happened, when, and likely cause

### Timeline
Chronological events:
- 2026-02-12 10:45 - Deployment of card-invitation-service v1.2.3
- 2026-02-12 12:30 - First errors appear in logs
- 2026-02-12 14:00 - Error rate peaks at 50/min

### Services Impacted
For each service:
- Log count, error count
- Deployed version
- Recent deployments (with timing)

### Root Cause Analysis
- **Primary Cause**: Specific file and line number
- **Contributing Factors**: Other issues found
- **Confidence Level**: High/Medium/Low with reasoning
- **Evidence**: Links to logs, commits, diffs

### Code Issues Found
For each file:
- Issue type and severity
- Code snippet (before/after)
- Why it's problematic
- Recommended fix

### Proposed Fix
- Specific code changes needed
- Risk assessment
- Rollback plan if available

### Testing Required
- Manual test cases
- Automated test additions

### Next Steps
Developer checklist:
- [ ] Review code at EntitledCustomerService.kt:145
- [ ] Add null safety check
- [ ] Add unit test for null email scenario
- [ ] Deploy to staging
- [ ] Verify fix in staging logs
- [ ] Deploy to production

## Important Guidelines

- Always invoke subagents in order: DataDog → Deployment → Code
- Read the files/ directory between subagents to check results
- If a subagent fails, try once more, then continue with partial data
- Be specific in root cause analysis - cite exact files and lines
- Provide actionable recommendations, not generic advice
- If uncertain, state confidence level and ask for more data
"""


class LeadAgent:
    """Main orchestrator agent using Claude Agent SDK."""

    def __init__(self, config=None):
        """Initialize the lead agent."""
        if config is None:
            config = get_config()
        self.config = config
        self.session_manager = None
        self.tracker = None

    async def investigate(self, user_input: str) -> str:
        """
        Run a complete investigation workflow.

        Args:
            user_input: User's description of the issue (log message or identifiers)

        Returns:
            Markdown-formatted investigation report
        """
        # Setup session
        self.session_manager = SessionManager()
        session_dir = self.session_manager.create_session()
        transcript_file = session_dir / "transcript.txt"

        self.tracker = SubagentTracker(
            log_file=session_dir / "tool_calls.jsonl",
            transcript_file=transcript_file
        )

        logger.info(f"Starting investigation in session: {session_dir}")
        self.session_manager.write_transcript(f"User: {user_input}\n\n")

        # Setup hooks
        hooks = create_hook_matchers(self.tracker)

        # Setup MCP servers
        mcp_servers = {
            "datadog": datadog_mcp_server,
            "github": github_mcp_server,
        }

        # Define subagents
        agents = {
            "datadog-investigator": DATADOG_INVESTIGATOR,
            "deployment-analyzer": DEPLOYMENT_ANALYZER,
            "code-reviewer": CODE_REVIEWER,
        }

        # Agent options
        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",  # Production: change to "acceptEdits"
            system_prompt=LEAD_AGENT_PROMPT,
            allowed_tools=["Task", "Read", "Glob", "Write"],
            agents=agents,
            hooks=hooks,
            mcp_servers=mcp_servers,
            model="opus",  # Lead agent needs strong reasoning
        )

        report = ""

        try:
            async with ClaudeSDKClient(options=options) as client:
                # Send investigation request
                await client.query(prompt=user_input)

                self.session_manager.write_transcript("Agent: ")

                # Process response stream
                async for msg in client.receive_response():
                    # Log system init
                    if isinstance(msg, SystemMessage) and msg.subtype == "init":
                        logger.info(f"MCP servers: {msg.data.get('mcp_servers', [])}")

                    # Track assistant messages
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if hasattr(block, "text"):
                                self.session_manager.write_transcript(block.text, end="")
                            elif hasattr(block, "name"):
                                # Tool use
                                self.session_manager.write_transcript(
                                    f"\n[Using tool: {block.name}]\n"
                                )

                    # Get final result
                    if isinstance(msg, ResultMessage):
                        if msg.subtype == "success":
                            report = msg.result
                        elif msg.subtype == "error_during_execution":
                            logger.error(f"Investigation failed: {msg.error}")
                            report = self._generate_error_report(user_input, msg.error)

                self.session_manager.write_transcript("\n\n")

        except Exception as e:
            logger.exception(f"Investigation error: {e}")
            report = self._generate_error_report(user_input, str(e))

        finally:
            # Save final report
            report_file = session_dir / "investigation_report.md"
            report_file.write_text(report)

            # Close tracker
            if self.tracker:
                self.tracker.close()

            logger.info(f"Investigation complete. Session: {session_dir}")
            print(f"\n📊 Session logs: {session_dir}")
            print(f"📝 Transcript: {transcript_file}")
            print(f"📄 Report: {report_file}")

        return report

    def _generate_error_report(self, user_input: str, error: str) -> str:
        """Generate error report when investigation fails."""
        return f"""# Investigation Error

**User Input:** {user_input}
**Timestamp:** {datetime.utcnow().isoformat()}Z

## Error
The investigation could not be completed due to an error:

```
{error}
```

## Troubleshooting Steps
1. Check API credentials (DataDog, GitHub)
2. Verify network connectivity
3. Review logs for details
4. Try again with different input

## Session Logs
Check the session directory for detailed logs.
"""


async def run_interactive():
    """Run the agent in interactive mode."""
    config = get_config()
    agent = LeadAgent(config)

    print("\n" + "=" * 70)
    print("         Production Issue Investigator (SDK Version)")
    print("=" * 70)
    print("\nInvestigate production issues using AI-powered analysis.")
    print("\nExamples:")
    print("  - 'NullPointerException in EntitledCustomerService'")
    print("  - 'Investigate CID 12345, paymentId abc-def'")
    print("  - 'Errors in payment-service since yesterday'")
    print("\nType 'exit' to quit.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("\n🔍 Describe the issue: ").strip()

            if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break

            # Run investigation
            report = await agent.investigate(user_input)

            # Display report
            print("\n" + "=" * 70)
            print("📊 INVESTIGATION REPORT")
            print("=" * 70)
            print(report)
            print("=" * 70)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            logger.exception(f"Error in interactive mode: {e}")
            print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(run_interactive())
```

**Entry Point:** `main.py`

```python
"""Main entry point for Production Issue Investigator (SDK version)."""
import sys
import asyncio
from agents.lead_agent import run_interactive
from utils.logger import get_logger, configure_logging
from utils.config import get_config, ConfigurationError

logger = get_logger(__name__)


async def main() -> int:
    """Main entry point."""
    # Load config
    try:
        config = get_config()
    except ConfigurationError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nEnsure these variables are set in .env:")
        print("  - ANTHROPIC_API_KEY")
        print("  - DATADOG_API_KEY")
        print("  - DATADOG_APP_KEY")
        print("  - GITHUB_TOKEN")
        return 1

    # Configure logging
    configure_logging(log_level=config.log_level)

    # Run interactive mode
    try:
        await run_interactive()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### Deliverables
- ✅ Lead agent with full SDK integration
- ✅ Subagent coordination via Task tool
- ✅ Session management integrated
- ✅ Error handling and retries
- ✅ Interactive mode working

#### Phase 4 Gate Criteria
- [ ] Lead agent invokes all three subagents in correct order (DataDog → Deployment → Code)
- [ ] File-based coordination works: lead agent reads subagent findings correctly
- [ ] Session directory contains all expected files after investigation
- [ ] `tool_calls.jsonl` shows parent-child relationships
- [ ] `transcript.txt` is human-readable and complete
- [ ] Retry policy applied correctly per failure type
- [ ] **Integration test**: Full investigation with mocked subagents passes
- [ ] **Smoke test**: Real investigation produces reasonable report (manual review)
- [ ] **95% coverage** on `agents/lead_agent.py`

**Gate Decision:** All criteria must pass. Compare output quality with legacy system on 3+ test cases.

---

### Phase 5: Testing & Refinement (Week 5)

**Goal:** Comprehensive testing and production hardening

#### Test Strategy

1. **Unit Tests**
   - File: `tests/test_mcp_tools.py`
     - Test each MCP tool with mocked APIs
     - Verify error handling
     - Check output format

   - File: `tests/test_session_manager.py`
     - Session creation
     - Transcript writing
     - Tool call logging

   - File: `tests/test_hooks.py`
     - PreToolUse logging
     - PostToolUse logging
     - Parent-child tracking

2. **Integration Tests**
   - File: `tests/test_lead_agent_integration.py`
     - End-to-end workflow with mocked subagents
     - Verify subagent invocation
     - Check file-based coordination

3. **System Tests**
   - File: `tests/test_full_workflow.py`
     - Run with real APIs (in test environment)
     - Verify complete investigation
     - Check report quality

4. **Error Scenario Tests**
   - MCP tool failures
   - Subagent failures
   - Partial results handling
   - API rate limiting

#### Performance Testing

- Parallel subagent execution
- Large log volume handling
- Session cleanup

#### Deliverables
- ✅ 40+ tests covering all components
- ✅ 85%+ code coverage
- ✅ Error scenarios tested
- ✅ Performance benchmarks

> **DECISION (2026-02-13)**: Coverage target strategy - tiered approach.
>
> **Overall Target:** 85% line coverage
>
> **Critical Paths (95% coverage required):**
> - `mcp_servers/datadog_server.py` - All MCP tools
> - `mcp_servers/github_server.py` - All MCP tools
> - `utils/session_manager.py` - Session lifecycle
> - `utils/hooks.py` - PreToolUse/PostToolUse tracking
> - `agents/lead_agent.py` - Orchestration logic
>
> **Standard Coverage (85%):**
> - `agents/*_prompt.py` - Subagent definitions
> - `agents/subagent_definitions.py`
> - Integration tests
>
> **Measurement:**
> ```bash
> # Overall coverage
> uv run pytest --cov=. --cov-report=term-missing
>
> # Critical path coverage (must be 95%+)
> uv run pytest --cov=mcp_servers --cov=utils/session_manager --cov=utils/hooks --cov-fail-under=95
> ```

#### Phase 5 Gate Criteria
- [ ] **40+ new tests** added (total 227+ tests)
- [ ] **85% overall coverage** achieved
- [ ] **95% critical path coverage** on MCP tools, session manager, hooks, lead agent
- [ ] All error scenarios tested: rate limits, timeouts, schema errors, partial data
- [ ] Performance benchmarks documented: avg investigation time, token usage
- [ ] **Comparison test**: New system produces equivalent or better reports vs legacy on 10 test cases
- [ ] No regressions in existing 187 tests
- [ ] CI pipeline configured and passing

**Gate Decision:** All criteria must pass. This is the **final quality gate** before production.

---

### Phase 6: Production Deployment (Week 6)

**Goal:** Deploy to production with monitoring

#### Pre-Deployment Checklist

1. **Security Review**
   - API credentials in environment only
   - No secrets in logs
   - Permission mode set to `acceptEdits`
   - Rate limiting in place

2. **Performance Tuning**
   - Subagent model selection optimized
   - Tool result truncation configured
   - Session cleanup scheduled

3. **Monitoring Setup**
   - Log aggregation to DataDog
   - Hook metrics to dashboard
   - Alert on failures

4. **Documentation**
   - Update README with new architecture
   - Document subagent prompts
   - Add runbook for operators

#### Deployment Steps

1. **Environment Variables**
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   export DATADOG_API_KEY=...
   export DATADOG_APP_KEY=...
   export GITHUB_TOKEN=ghp_...
   export LOG_LEVEL=INFO
   export PERMISSION_MODE=acceptEdits
   ```

2. **Install Dependencies**
   ```bash
   uv sync
   ```

3. **Run Setup Verification**
   ```bash
   uv run verify_setup.py
   ```

4. **Start Application**
   ```bash
   uv run main.py
   ```

5. **Monitor First Runs**
   - Watch session logs
   - Check tool call JSONL
   - Verify reports

#### Deliverables
- ✅ Production deployment successful
- ✅ Monitoring in place
- ✅ Documentation updated
- ✅ Team trained

#### Phase 6 Gate Criteria
- [ ] Security review completed: no secrets in logs, credentials in env only
- [ ] Monitoring dashboard operational: investigation duration, tool failures, token usage
- [ ] Alerts configured: >10% failure rate, API errors, session cleanup failures
- [ ] Documentation updated: README, CLAUDE.md, runbook for operators
- [ ] Legacy code moved to `legacy/` directory with deprecation notice
- [ ] **Production smoke tests**: 5 real investigations complete successfully
- [ ] **Rollback verified**: Can switch back to `main_legacy.py` within 5 minutes
- [ ] Team trained on new architecture and troubleshooting

**Gate Decision:** All criteria must pass for full production cutover.

**Post-Cutover (30-day validation period):**
- [ ] Monitor failure rate stays below 5%
- [ ] No critical bugs reported
- [ ] Token costs within expected range ($0.10-0.50/investigation)
- [ ] After 30 days: Delete `legacy/` directory

---

## Custom Tools & MCP Design

### Design Principles

1. **Thin Wrappers**: MCP tools should be thin wrappers around existing utilities
2. **Error Handling**: All tools return structured errors, never throw exceptions
3. **Result Truncation**: Limit response sizes to avoid context bloat
4. **Async First**: All tools are async for performance
5. **Schema Validation**: Use type hints for automatic validation
6. **Sync-to-Async Strategy**: Use `asyncio.to_thread()` to wrap existing synchronous utilities (Decision: 2026-02-13)

> **DECISION**: MCP tools will use `asyncio.to_thread()` to wrap synchronous calls to `datadog_api.py` and `github_helper.py`. This preserves the stable, tested utility code while maintaining event loop responsiveness. Rationale: Low-traffic MCP server, existing code is production-proven.

### Tool Design Pattern

```python
@tool(
    "tool_name",
    "Clear description for Claude to understand when to use this",
    {
        "param1": str,
        "param2": int,
        "optional_param": dict
    }
)
async def tool_name_impl(args: dict[str, Any]) -> dict[str, Any]:
    """
    Implementation of the tool.

    Returns:
        Always returns dict with 'content' key, optionally 'is_error'
    """
    try:
        # 1. Validate inputs
        required_param = args.get("param1")
        if not required_param:
            return {
                "content": [{"type": "text", "text": "Error: param1 is required"}],
                "is_error": True
            }

        # 2. Call existing utility (wrapped with asyncio.to_thread for sync code)
        result = await asyncio.to_thread(some_utility.do_work, required_param)

        # 3. Format response (truncate if needed)
        formatted = format_result(result, max_size=50)

        # 4. Return as JSON string in text content
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(formatted, indent=2)
            }]
        }

    except SpecificException as e:
        # Handle known errors
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }

    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in tool_name: {e}")
        return {
            "content": [{"type": "text", "text": f"Unexpected error: {str(e)}"}],
            "is_error": True
        }
```

### Response Format Standards

All MCP tools return:
- **Success**: `{"content": [{"type": "text", "text": "<JSON string>"}]}`
- **Error**: `{"content": [{"type": "text", "text": "Error: <message>"}], "is_error": True}`

JSON structure in text field:
```json
{
  "success": true,
  "data": {...},
  "metadata": {
    "count": 10,
    "truncated": false
  }
}
```

---

## Subagent Architecture

### Subagent Communication Pattern

```
Lead Agent
    │
    ├─ Spawns via Task tool: "Use datadog-investigator to search logs"
    │
    ▼
DataDog Investigator (Subagent)
    │
    ├─ Uses MCP tools: search_logs, get_logs_by_efilogid
    ├─ Uses Write tool: Saves to files/datadog_findings/summary.json
    │
    └─ Returns: Result message to Lead Agent
                ▲
                │
Lead Agent reads: files/datadog_findings/summary.json
    │
    └─ Decides: "Now use deployment-analyzer with these services"
```

### File-Based Coordination

Subagents communicate via shared files:

```
files/
├── datadog_findings/
│   ├── summary.json               # Main findings
│   └── {service}_logs.json        # Per-service details
├── deployment_findings/
│   ├── summary.json
│   └── {service}_deployments.json
└── code_findings/
    ├── summary.json
    └── {service}_analysis.json
```

**Why files?**
- Subagents can work asynchronously
- Lead agent can verify results between steps
- Easy to debug (inspect files manually)
- Results persist in session directory

> **DECISION (2026-02-13)**: Inter-subagent data schemas will use existing dataclass patterns from the current codebase.
>
> **Reuse these existing models:**
> - `LogEntry` - Individual log records from DataDog
> - `SearchResult` - Aggregated search results with unique_services, unique_efilogids
> - `DeploymentInfo` - Deployment correlation data
> - `CommitInfo`, `FileChange`, `PullRequestInfo` - GitHub data
>
> **New models to add (following same pattern):**
> - `DataDogFindingsSummary` - Wrapper for datadog_findings/summary.json
> - `DeploymentFindingsSummary` - Wrapper for deployment_findings/summary.json
> - `CodeAnalysisSummary` - Wrapper for code_findings/summary.json
>
> **Serialization:** Use `dataclasses.asdict()` for writing, reconstruct on read.
> This maintains consistency with existing code and leverages tested patterns.

### Subagent Prompt Engineering

**Effective subagent prompts include:**
1. **Role definition** - "You are a DataDog Expert"
2. **Tool descriptions** - What each tool does
3. **Process steps** - Numbered workflow
4. **Output format** - Exact JSON structure with examples
5. **Edge cases** - How to handle failures
6. **Important notes** - Gotchas and tips

**Anti-patterns to avoid:**
- ❌ Vague instructions - "analyze the data"
- ❌ No output format - Subagent makes up structure
- ❌ Missing edge cases - Fails on empty results
- ❌ Too much flexibility - Inconsistent outputs

---

## Session Management & Observability

### Session Structure

> **DECISION (2026-02-13)**: Each session is fully self-contained with all findings inside the session directory. This ensures:
> - Complete isolation between investigations
> - Easy archival (zip entire session dir)
> - No cross-session contamination
> - Simple cleanup (delete session dir)

```
logs/
└── session_20260212_143056/
    ├── transcript.txt              # Human-readable conversation
    ├── tool_calls.jsonl            # Structured tool usage log
    ├── investigation_report.md     # Final report
    └── files/                      # Subagent findings (session-scoped)
        ├── datadog_findings/
        │   ├── summary.json
        │   └── {service}_logs.json
        ├── deployment_findings/
        │   ├── summary.json
        │   └── {service}_deployments.json
        └── code_findings/
            ├── summary.json
            └── {service}_analysis.json
```

**Note:** Subagent prompts must use session-relative paths (e.g., `files/datadog_findings/summary.json`), and the session manager will set the working directory appropriately.

### Transcript Format

```
User: NullPointerException in EntitledCustomerService

Agent: I'll investigate this production issue. Let me start by searching DataDog logs.

[Using tool: Task]
[Spawning subagent: datadog-investigator]

DataDog Investigator: Searching logs for "NullPointerException in EntitledCustomerService"...
Found 87 logs in card-invitation-service
Writing findings to files/datadog_findings/summary.json

Agent: I found errors in card-invitation-service. Now checking recent deployments.

[Using tool: Task]
[Spawning subagent: deployment-analyzer]

...
```

### Tool Call JSONL Format

```jsonl
{"event":"tool_call_start","timestamp":"2026-02-12T14:31:02Z","agent_id":"LEAD","tool_name":"Task","input":{"subagent_type":"datadog-investigator","prompt":"Search for NullPointerException..."}}
{"event":"tool_call_start","timestamp":"2026-02-12T14:31:03Z","agent_id":"DATADOG-INVESTIGATOR-1","parent_tool_use_id":"task_abc123","tool_name":"mcp__datadog__search_logs","input":{"query":"NullPointerException","from_time":"now-4h"}}
{"event":"tool_call_complete","timestamp":"2026-02-12T14:31:04Z","agent_id":"DATADOG-INVESTIGATOR-1","tool_name":"mcp__datadog__search_logs","success":true,"duration_ms":987,"output_size":15234}
{"event":"tool_call_complete","timestamp":"2026-02-12T14:31:08Z","agent_id":"LEAD","tool_name":"Task","success":true,"duration_ms":6543}
```

### Hook Implementation

**File:** `utils/hooks.py`

```python
"""Hook system for tracking tool usage across all agents."""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookInput, HookContext, HookJSONOutput
from utils.logger import get_logger

logger = get_logger(__name__)


class SubagentTracker:
    """Tracks tool usage across lead agent and subagents."""

    def __init__(self, log_file: Path, transcript_file: Path):
        """
        Initialize the tracker.

        Args:
            log_file: Path to JSONL file for tool calls
            transcript_file: Path to transcript file
        """
        self.log_file = log_file
        self.transcript_file = transcript_file
        self.tool_starts: Dict[str, Dict[str, Any]] = {}

        # Create log file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.touch()

        logger.info(f"SubagentTracker initialized: {log_file}")

    async def pre_tool_use_hook(
        self,
        input_data: HookInput,
        tool_use_id: Optional[str],
        context: HookContext
    ) -> HookJSONOutput:
        """
        Pre-tool-use hook to log tool invocations.

        Captures:
        - Agent ID (lead vs subagent)
        - Tool name
        - Input parameters
        - Parent tool use ID (for subagent calls)
        - Start timestamp
        """
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        parent_id = input_data.get("parent_tool_use_id")

        # Determine agent ID
        if parent_id:
            # This is a subagent tool call
            agent_id = f"SUBAGENT-{parent_id[:8]}"
        else:
            # This is the lead agent
            agent_id = "LEAD"

        # Record start time
        start_time = time.time()
        self.tool_starts[tool_use_id] = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "start_time": start_time,
            "parent_id": parent_id
        }

        # Log to JSONL
        log_entry = {
            "event": "tool_call_start",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_use_id": tool_use_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "parent_tool_use_id": parent_id,
            "input": self._truncate_input(tool_input)
        }
        self._write_jsonl(log_entry)

        # Log to transcript
        self._write_transcript(f"[{agent_id}] → {tool_name}\n")

        logger.debug(f"Tool start: {agent_id} → {tool_name}")

        return {}

    async def post_tool_use_hook(
        self,
        input_data: HookInput,
        tool_use_id: Optional[str],
        context: HookContext
    ) -> HookJSONOutput:
        """
        Post-tool-use hook to log tool results.

        Captures:
        - Success/failure
        - Output size
        - Duration
        - Error messages if any
        """
        tool_response = input_data.get("tool_response", {})

        # Get start data
        start_data = self.tool_starts.pop(tool_use_id, {})
        agent_id = start_data.get("agent_id", "UNKNOWN")
        tool_name = start_data.get("tool_name", "unknown")
        start_time = start_data.get("start_time", time.time())

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Determine success
        is_error = tool_response.get("is_error", False)
        success = not is_error

        # Get output size
        output_str = str(tool_response)
        output_size = len(output_str)

        # Log to JSONL
        log_entry = {
            "event": "tool_call_complete",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_use_id": tool_use_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "output_size": output_size
        }

        if not success:
            log_entry["error"] = self._extract_error(tool_response)

        self._write_jsonl(log_entry)

        # Log to transcript
        status = "✓" if success else "✗"
        self._write_transcript(
            f"[{agent_id}] {status} {tool_name} ({duration_ms}ms)\n"
        )

        logger.debug(f"Tool complete: {agent_id} → {tool_name} ({duration_ms}ms)")

        return {}

    def _truncate_input(self, tool_input: Dict[str, Any], max_size: int = 500) -> Dict[str, Any]:
        """Truncate large inputs for logging."""
        truncated = {}
        for key, value in tool_input.items():
            value_str = str(value)
            if len(value_str) > max_size:
                truncated[key] = value_str[:max_size] + "... (truncated)"
            else:
                truncated[key] = value
        return truncated

    def _extract_error(self, tool_response: Dict[str, Any]) -> str:
        """Extract error message from tool response."""
        if "content" in tool_response:
            content = tool_response["content"]
            if isinstance(content, list) and len(content) > 0:
                first_block = content[0]
                if isinstance(first_block, dict):
                    return first_block.get("text", "Unknown error")
        return str(tool_response)[:200]

    def _write_jsonl(self, entry: Dict[str, Any]) -> None:
        """Append entry to JSONL file."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _write_transcript(self, text: str) -> None:
        """Append text to transcript file."""
        with open(self.transcript_file, "a") as f:
            f.write(text)

    def close(self) -> None:
        """Cleanup on session end."""
        logger.info(f"SubagentTracker closed. Logs: {self.log_file}")


def create_hook_matchers(tracker: SubagentTracker) -> Dict[str, list]:
    """
    Create hook matchers for PreToolUse and PostToolUse.

    Args:
        tracker: SubagentTracker instance

    Returns:
        Dict with hooks configuration
    """
    return {
        "PreToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[tracker.pre_tool_use_hook]
            )
        ],
        "PostToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[tracker.post_tool_use_hook]
            )
        ]
    }
```

---

## Migration Strategy

### Coexistence Approach

**Phase 1-3:** Old and new systems coexist
- Keep `agents/main_agent.py` (old) as `agents/main_agent_legacy.py`
- New SDK version in `agents/lead_agent.py`
- Two entry points: `main.py` (new) and `main_legacy.py` (old)

**Phase 4-5:** Gradual switchover
- Run both systems on test cases
- Compare outputs for quality
- Identify and fix gaps in new system

**Phase 6:** Full cutover
- Archive legacy code in `legacy/` directory
- Remove `main_legacy.py`
- Update all documentation

### Data Migration

**No data migration needed** - both systems use same:
- .env configuration
- DataDog API
- GitHub API
- Log file format

### Rollback Plan

If critical issues in production:
1. Switch entry point back to `main_legacy.py`
2. Investigate issues in new system offline
3. Fix and re-deploy when ready

> **DECISION (2026-02-13)**: Legacy code retention strategy:
>
> **During Migration (Phase 1-5):**
> - Rename legacy files with `_legacy` suffix in `agents/` directory
> - Keep `main_legacy.py` as alternate entry point
>
> **At Cutover (Phase 6):**
> - Move all legacy files to `legacy/` directory
> - Structure: `legacy/agents/`, `legacy/main_legacy.py`
> - Add `legacy/README.md` noting deprecation date
>
> **Post-Cutover:**
> - Keep `legacy/` directory for **30 days** after production cutover
> - Set calendar reminder for removal date
> - Delete `legacy/` directory after validation period
> - Git history remains available for reference if ever needed
>
> **Files to archive:**
> - `agents/main_agent.py` → `legacy/agents/main_agent.py`
> - `agents/datadog_retriever.py` → `legacy/agents/datadog_retriever.py`
> - `agents/deployment_checker.py` → `legacy/agents/deployment_checker.py`
> - `agents/code_checker.py` → `legacy/agents/code_checker.py`
> - `agents/exception_analyzer.py` → `legacy/agents/exception_analyzer.py`

---

## Testing Strategy

### Test Pyramid

```
                        ┌─────────────────┐
                        │   System Tests  │  (5%)
                        │  Full E2E Flow  │
                        └─────────────────┘
                    ┌───────────────────────┐
                    │  Integration Tests    │  (25%)
                    │  Subagent Coordination│
                    └───────────────────────┘
            ┌───────────────────────────────────┐
            │         Unit Tests                │  (70%)
            │  MCP Tools, Hooks, Session Mgmt   │
            └───────────────────────────────────┘
```

### Critical Test Cases

#### 1. MCP Tool Tests

```python
# tests/test_mcp_tools.py
import pytest
from unittest.mock import AsyncMock, patch
from mcp_servers.datadog_server import search_logs_tool

@pytest.mark.asyncio
async def test_search_logs_success():
    """Test successful log search."""
    mock_api = AsyncMock()
    mock_api.search_logs.return_value = create_mock_search_result(10)

    with patch('mcp_servers.datadog_server.datadog_api', mock_api):
        result = await search_logs_tool({
            "query": "NullPointerException",
            "from_time": "now-4h",
            "to_time": "now"
        })

    assert result["content"][0]["type"] == "text"
    assert "total_logs" in result["content"][0]["text"]
    assert "is_error" not in result

@pytest.mark.asyncio
async def test_search_logs_rate_limit():
    """Test rate limit handling."""
    mock_api = AsyncMock()
    mock_api.search_logs.side_effect = RateLimitError("Rate limited")

    with patch('mcp_servers.datadog_server.datadog_api', mock_api):
        result = await search_logs_tool({
            "query": "test",
            "from_time": "now-1h",
            "to_time": "now"
        })

    assert result["is_error"] is True
    assert "rate limited" in result["content"][0]["text"].lower()
```

#### 2. Hook Tests

```python
# tests/test_hooks.py
import pytest
from pathlib import Path
import json
from utils.hooks import SubagentTracker

@pytest.mark.asyncio
async def test_pre_tool_use_hook(tmp_path):
    """Test pre-tool-use hook logs correctly."""
    log_file = tmp_path / "tool_calls.jsonl"
    transcript = tmp_path / "transcript.txt"

    tracker = SubagentTracker(log_file, transcript)

    await tracker.pre_tool_use_hook(
        input_data={
            "tool_name": "mcp__datadog__search_logs",
            "tool_input": {"query": "test"},
            "parent_tool_use_id": None
        },
        tool_use_id="tool_123",
        context={}
    )

    # Check JSONL
    with open(log_file) as f:
        entry = json.loads(f.readline())

    assert entry["event"] == "tool_call_start"
    assert entry["agent_id"] == "LEAD"
    assert entry["tool_name"] == "mcp__datadog__search_logs"

    tracker.close()
```

#### 3. Integration Tests

```python
# tests/test_lead_agent_integration.py
import pytest
from unittest.mock import AsyncMock, patch
from agents.lead_agent import LeadAgent

@pytest.mark.asyncio
async def test_investigation_workflow():
    """Test full investigation workflow with mocked subagents."""
    # Mock ClaudeSDKClient to return predetermined responses
    mock_client = AsyncMock()
    mock_client.query.return_value = None
    mock_client.receive_response.return_value = create_mock_messages([
        ("assistant", "I'll search DataDog logs..."),
        ("tool_use", "Task", {"subagent_type": "datadog-investigator"}),
        ("tool_result", "Task", "Findings written to files/"),
        ("assistant", "Now checking deployments..."),
        ("result", "success", "Final report...")
    ])

    with patch('agents.lead_agent.ClaudeSDKClient', return_value=mock_client):
        agent = LeadAgent()
        report = await agent.investigate("Test error")

    assert "Investigation Report" in report or "investigation" in report.lower()
    # Verify session directory created
    # Verify files written
```

### Test Data

Create fixtures for common scenarios:
- `fixtures/datadog_logs.json` - Sample log entries
- `fixtures/github_commits.json` - Sample commits
- `fixtures/deployments.json` - Sample deployments

---

## Production Considerations

### Security

1. **API Credentials**
   - Store in environment variables only
   - Never log credentials
   - Rotate regularly

2. **Permission Mode**
   - Development: `bypassPermissions` for testing
   - Production: `acceptEdits` to prompt for destructive operations

   > **DECISION (2026-02-13)**: Permission mode will be configurable via `PERMISSION_MODE` environment variable.
   >
   > **Configuration:**
   > ```bash
   > # Default (CLI usage) - no prompts, tool is read-only for external systems
   > PERMISSION_MODE=bypassPermissions
   >
   > # Stricter mode for API/web interfaces or shared environments
   > PERMISSION_MODE=acceptEdits
   > ```
   >
   > **Rationale for `bypassPermissions` as default:**
   > - External system access is read-only (DataDog queries, GitHub reads)
   > - Local writes are confined to session directories (`logs/session_*/`)
   > - CLI users explicitly invoke the tool and trust it
   > - Prompts would interrupt automated/batch investigations
   >
   > **When to use `acceptEdits`:**
   > - Multi-tenant environments
   > - Web/API interfaces where users may not fully trust the tool
   > - Compliance requirements for audit trails

3. **Log Redaction**
   - Sensitive fields: efilogid (contains user data), customer IDs
   - Redact in transcripts but keep in tool_calls.jsonl for debugging

### Performance

1. **Model Selection**
   - Lead agent: `opus` (needs strong reasoning)
   - Subagents: `haiku` for search, `sonnet` for analysis
   - Estimated cost per investigation: $0.10-0.50

   > **DECISION (2026-02-13)**: Model selection will be configurable per-subagent via environment variables with sensible defaults.
   >
   > **Defaults in code:**
   > - `LEAD_AGENT_MODEL=opus`
   > - `DATADOG_INVESTIGATOR_MODEL=haiku`
   > - `DEPLOYMENT_ANALYZER_MODEL=haiku`
   > - `CODE_REVIEWER_MODEL=sonnet`
   >
   > **Override via .env:**
   > ```bash
   > # Override any subagent model
   > DATADOG_INVESTIGATOR_MODEL=sonnet  # Upgrade if haiku misses patterns
   > CODE_REVIEWER_MODEL=opus           # For complex codebases
   > ```
   >
   > This allows tuning based on real-world metrics without code changes.

2. **Rate Limiting**
   - DataDog: 300 req/hour
   - GitHub: 5000 req/hour
   - Implement backoff in MCP tools

   > **DECISION (2026-02-13)**: MCP tools will handle rate limits using `asyncio.sleep()` for async-friendly waiting. Pattern:
   > 1. Catch `DataDogRateLimitError` from sync utility (via `asyncio.to_thread`)
   > 2. Extract `retry_after_seconds` from exception
   > 3. Use `await asyncio.sleep(retry_after_seconds)` to wait
   > 4. Retry the operation once
   > This keeps the event loop responsive during rate limit waits.

3. **Result Truncation**
   - Limit log results to 50 entries per query
   - Truncate messages to 200 chars in tool logs
   - Keep full data in files/ directory

### Monitoring

1. **Metrics to Track**
   - Investigation duration
   - Subagent invocation count
   - MCP tool failures
   - Report quality (manual review)

2. **Alerts**
   - Failed investigations (> 10% failure rate)
   - API errors (rate limits, auth failures)
   - Session cleanup failures

3. **Dashboards**
   - Investigation volume over time
   - Most common services investigated
   - Average investigation duration
   - Tool usage breakdown

### Error Handling

1. **Graceful Degradation**
   - If DataDog fails: Return empty results, continue with deployment check
   - If GitHub fails: Skip code analysis, provide partial report
   - If subagent fails: Apply retry policy based on failure type

   > **DECISION (2026-02-13)**: Configurable retry counts per failure type.
   >
   > **Environment Variables (with defaults):**
   > ```bash
   > # MCP tool returns is_error: true (often transient)
   > TOOL_ERROR_RETRIES=1
   >
   > # Subagent exceeds time limit (unlikely to succeed on retry)
   > TIMEOUT_RETRIES=0
   >
   > # Findings file has invalid schema (prompt issue, not transient)
   > SCHEMA_ERROR_RETRIES=0
   >
   > # Subagent timeout in seconds
   > SUBAGENT_TIMEOUT_SECONDS=120
   > ```
   >
   > **Failure Type Detection:**
   > - **Tool error**: Task result contains `is_error: true` from MCP tool
   > - **Timeout**: Task exceeds `SUBAGENT_TIMEOUT_SECONDS`
   > - **Schema error**: Findings file exists but fails dataclass validation
   > - **Partial success**: Some expected fields missing but file is valid JSON
   >
   > **Behavior:**
   > - After exhausting retries, continue with partial data
   > - Log failure details to `tool_calls.jsonl` for debugging
   > - Include failure summary in final report

2. **User Communication**
   - Always explain what went wrong
   - Suggest next steps
   - Provide session logs for debugging

3. **Automatic Recovery**
   - Retry MCP tools on transient failures (per retry config)
   - Resume sessions if interrupted
   - Auto-cleanup old sessions

### Session Cleanup

```python
# utils/session_cleanup.py
"""Cleanup old session directories to manage disk space."""
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from utils.logger import get_logger

logger = get_logger(__name__)

def cleanup_old_sessions(logs_dir: Path, days: int = 30) -> int:
    """
    Remove session directories older than specified days.

    Args:
        logs_dir: Path to logs directory
        days: Age threshold in days

    Returns:
        Number of sessions removed
    """
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    for session_dir in logs_dir.glob("session_*"):
        if not session_dir.is_dir():
            continue

        # Parse timestamp from dirname: session_YYYYMMDD_HHMMSS
        try:
            timestamp_str = session_dir.name.replace("session_", "")
            session_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if session_time < cutoff:
                logger.info(f"Removing old session: {session_dir}")
                shutil.rmtree(session_dir)
                removed += 1
        except Exception as e:
            logger.warning(f"Could not process {session_dir}: {e}")

    logger.info(f"Cleanup complete. Removed {removed} sessions older than {days} days")
    return removed
```

Run as cron job:
```bash
# Daily cleanup
0 2 * * * cd /app && uv run python -c "from utils.session_cleanup import cleanup_old_sessions; cleanup_old_sessions(Path('logs'), days=30)"
```

---

## Code Examples

### Complete MCP Tool Example

**File:** `mcp_servers/datadog_server.py`

```python
"""DataDog MCP server with tools for log search and analysis."""
from claude_agent_sdk import tool, create_sdk_mcp_server
from utils.datadog_api import DataDogAPI
from utils.stack_trace_parser import StackTraceParser
from utils.config import get_config
from utils.logger import get_logger
from typing import Any
import json

logger = get_logger(__name__)

# Initialize utilities
config = get_config()
datadog_api = DataDogAPI(
    api_key=config.datadog_api_key,
    app_key=config.datadog_app_key,
    site=config.datadog_site
)
stack_parser = StackTraceParser()


@tool(
    "search_logs",
    "Search DataDog production logs with query filters and time range",
    {
        "query": str,
        "from_time": str,
        "to_time": str,
        "limit": int
    }
)
async def search_logs_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search DataDog logs.

    Args:
        query: DataDog query string (e.g., "NullPointerException")
        from_time: Start time (e.g., "now-4h")
        to_time: End time (e.g., "now")
        limit: Max results (default 50)

    Returns:
        JSON string with log entries
    """
    try:
        query = args["query"]
        from_time = args.get("from_time", "now-4h")
        to_time = args.get("to_time", "now")
        limit = args.get("limit", 50)

        logger.info(f"Searching DataDog logs: query={query}, time={from_time} to {to_time}")

        # Call existing utility
        result = datadog_api.search_logs(
            query=query,
            from_time=from_time,
            to_time=to_time,
            limit=limit
        )

        # Format response (truncate for context window)
        response_data = {
            "success": True,
            "total_logs": result.total_count,
            "returned_logs": len(result.logs),
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp,
                    "service": log.service,
                    "status": log.status,
                    "message": log.message[:200] + ("..." if len(log.message) > 200 else ""),
                    "logger_name": log.logger_name,
                    "efilogid": log.efilogid,
                    "dd_version": log.dd_version,
                }
                for log in result.logs[:50]  # Limit to 50 for context
            ]
        }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(response_data, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error searching logs: {e}", exc_info=True)
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching logs: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "get_logs_by_efilogid",
    "Retrieve all logs for a specific session ID (efilogid)",
    {
        "efilogid": str,
        "time_window": str
    }
)
async def get_logs_by_efilogid_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get all logs for a session.

    Args:
        efilogid: Session ID (e.g., "-1-NGFmMmVkMTgtYmU...")
        time_window: Search window (e.g., "now-24h")

    Returns:
        JSON string with session logs
    """
    try:
        efilogid = args["efilogid"]
        time_window = args.get("time_window", "now-24h")

        logger.info(f"Getting logs for efilogid: {efilogid}")

        # Build query with proper escaping
        query = f'@efilogid:"{efilogid}"'

        result = datadog_api.search_logs(
            query=query,
            from_time=time_window,
            to_time="now",
            limit=1000
        )

        response_data = {
            "success": True,
            "efilogid": efilogid,
            "log_count": len(result.logs),
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "service": log.service,
                    "status": log.status,
                    "message": log.message,
                    "logger_name": log.logger_name,
                }
                for log in result.logs
            ]
        }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(response_data, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error getting logs by efilogid: {e}", exc_info=True)
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "parse_stack_trace",
    "Extract file paths and exception info from stack trace text",
    {"stack_trace_text": str}
)
async def parse_stack_trace_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Parse stack trace.

    Args:
        stack_trace_text: Stack trace as string

    Returns:
        JSON with file paths and exception info
    """
    try:
        stack_trace = args["stack_trace_text"]

        logger.info("Parsing stack trace")

        parsed = stack_parser.parse(stack_trace)

        response_data = {
            "success": True,
            "exception_type": parsed.exception_type,
            "exception_message": parsed.exception_message,
            "file_paths": list(parsed.unique_file_paths),
            "frame_count": len(parsed.frames),
            "frames": [
                {
                    "file_path": frame.file_path,
                    "line_number": frame.line_number,
                    "method_name": frame.method_name,
                    "class_name": frame.class_name,
                }
                for frame in parsed.frames[:10]  # First 10 frames
            ]
        }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(response_data, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error parsing stack trace: {e}", exc_info=True)
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }],
            "is_error": True
        }


# Create MCP server
datadog_mcp_server = create_sdk_mcp_server(
    name="datadog",
    version="1.0.0",
    tools=[
        search_logs_tool,
        get_logs_by_efilogid_tool,
        parse_stack_trace_tool
    ]
)
```

### Complete Subagent Definition Example

Already shown in Phase 3 above. See `DATADOG_INVESTIGATOR_PROMPT` and `DATADOG_INVESTIGATOR` definition.

### Complete Session Manager Example

**File:** `utils/session_manager.py`

```python
"""Session management for investigation runs."""
from datetime import datetime
from pathlib import Path
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages investigation sessions with logging and file coordination."""

    def __init__(self, logs_dir: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            logs_dir: Base directory for logs (default: ./logs)
        """
        if logs_dir is None:
            logs_dir = Path("logs")
        self.logs_dir = logs_dir
        self.session_dir: Optional[Path] = None
        self.transcript_file: Optional[Path] = None

    def create_session(self) -> Path:
        """
        Create a new session directory.

        Returns:
            Path to session directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.logs_dir / f"session_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.session_dir / "files" / "datadog_findings").mkdir(parents=True, exist_ok=True)
        (self.session_dir / "files" / "deployment_findings").mkdir(parents=True, exist_ok=True)
        (self.session_dir / "files" / "code_findings").mkdir(parents=True, exist_ok=True)

        # Create transcript file
        self.transcript_file = self.session_dir / "transcript.txt"
        self.transcript_file.touch()

        logger.info(f"Created session: {self.session_dir}")
        return self.session_dir

    def write_transcript(self, text: str, end: str = "") -> None:
        """
        Append text to transcript.

        Args:
            text: Text to write
            end: Line ending (default: empty, use "\n" for newline)
        """
        if not self.transcript_file:
            raise RuntimeError("Session not created. Call create_session() first.")

        with open(self.transcript_file, "a") as f:
            f.write(text + end)

    def get_findings_dir(self, subagent: str) -> Path:
        """
        Get findings directory for a subagent.

        Args:
            subagent: Subagent name (e.g., "datadog_findings")

        Returns:
            Path to findings directory
        """
        if not self.session_dir:
            raise RuntimeError("Session not created. Call create_session() first.")

        return self.session_dir / "files" / subagent
```

---

## Summary

This rewrite plan transforms your production issue investigator from a traditional Python application into a true Claude Agent SDK application with:

**✅ AI-Powered Orchestration**
- Lead agent uses Claude's reasoning to coordinate investigation
- Autonomous decision-making on when to invoke subagents
- Dynamic adaptation based on findings

**✅ True Subagents**
- Three specialized AI agents with prompts and tools
- Each agent has domain expertise and reasoning capability
- File-based coordination between agents

**✅ Custom MCP Tools**
- 7 tools wrapping DataDog and GitHub APIs
- Proper error handling and result truncation
- In-process servers for performance

**✅ Complete Observability**
- Hooks track all tool usage
- Session transcripts for human review
- JSONL logs for machine analysis
- Parent-child relationship tracking

**✅ Production-Ready**
- Comprehensive error handling
- Security best practices
- Performance optimization
- Monitoring and alerts

**Implementation Timeline: 6 weeks**

This is a **production-ready, comprehensive plan** based on the latest Claude Agent SDK documentation and Anthropic's own best practices from the research-agent demo.
