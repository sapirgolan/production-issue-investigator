# Production Issue Investigator Agent - Design Document

**Version:** 2.0
**Date:** 2026-02-11
**Status:** Design Verified & Finalized - Ready for Implementation

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Input Modes](#input-modes)
4. [Sub-Agents](#sub-agents)
5. [Orchestration Logic](#orchestration-logic)
6. [Configuration & Secrets](#configuration--secrets)
7. [Output Format](#output-format)
8. [Error Handling](#error-handling)
9. [Technical Specifications](#technical-specifications)
10. [Implementation Notes](#implementation-notes)

---

## Overview

### Purpose
Create an AI agent to help investigate failures and errors in production environments by:
- Searching DataDog logs for error patterns
- Checking recent deployments
- Analyzing code changes
- Generating structured investigation reports with root cause analysis and proposed fixes

### Technology Stack
- **Framework:** Claude Agent SDK (Python)
- **Python Version:** 3.x
- **Interface:** Interactive chat
- **Deployment:** Separate Git repository
- **Integrations:** DataDog API, GitHub MCP/CLI

---

## Architecture

### Main Agent
The orchestrator that:
- Determines input mode (log message vs free text)
- Coordinates sub-agents
- Aggregates findings
- Generates investigation report
- Can ask follow-up questions if stuck
- Can invoke investigation skills when initial results are unclear

### Sub-Agents
Three specialized Claude SDK sub-agents:

1. **DataDog Information Retriever** - Searches and retrieves production logs
2. **Deployment Checker** - Identifies recent deployments and changes
3. **Code Checker** - Analyzes code changes between versions

All sub-agents:
- Cannot interact with the user
- Log all actions (inputs, outputs, tasks performed)
- Retry once on failure with same parameters
- Return partial results if retry fails

---

## Input Modes

**Mode Detection:** The agent must **explicitly ask** the user to select their input mode at the start of the conversation:

**Prompt to user:**
```
Please select how you want to investigate:

1. **Log Message** - You have a specific log message or error text from DataDog
2. **Identifiers** - You have customer/transaction identifiers (CID, card_account_id, paymentId)

Which option? (Enter 1 or 2)
```

After user selects, ask for the corresponding inputs:

### Mode 1: Log Message + DateTime (Optional)
**When user selects Option 1, prompt:**
```
Please provide:
- Log message: [The exact or partial log text from DataDog]
- DateTime (optional): [When did this occur? Format: any human-readable format]
```

**Inputs collected:**
- Log message (string) - exact or partial log text
- DateTime (optional) - timestamp in any human-readable format

**Flow:**
```
User provides log message
  ↓
DataDog Information Retriever (search for log message)
  ↓
If logs found → Extract services
  ↓
For each service:
  - Deployment Checker
  - Code Checker
```

### Mode 2: Free Text + Identifiers + DateTime (Optional)
**When user selects Option 2, prompt:**
```
Please provide:
- Issue description: [Describe the problem/error]
- Identifiers: [Provide one or more: CID, card_account_id, paymentId]
- DateTime (optional): [When did this occur? Format: any human-readable format]
```

**Inputs collected:**
- Free text description of the issue/error
- Identifiers: One or more of:
  - `CID` (Customer ID)
  - `card_account_id`
  - `paymentId`
- DateTime (optional) - timestamp in any human-readable format

**Flow:**
```
User provides free text + identifiers
  ↓
DataDog Information Retriever (search for identifiers)
  ↓
If logs found → Extract services
  ↓
For each service:
  - Deployment Checker
  - Code Checker
  ↓
If initial investigation doesn't yield clear results:
  - Invoke investigation skills (systematic-debugging or investigate)
  - Work with GitHub-fetched files
```

### Mode 3: DateTime Only (Rejected)
If user provides only datetime without log message or identifiers:
- Agent responds: "Cannot perform search with only datetime. Please provide either a log message or free text with identifiers."

---

## Sub-Agents

### 1. DataDog Information Retriever

**Purpose:** Search and retrieve production logs from DataDog

#### API Configuration
- **Endpoint:** `https://api.datadoghq.com/api/v2/logs/events/search`
- **Headers:**
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `DD-API-KEY: {from .env}`
  - `DD-APPLICATION-KEY: {from .env}`
- **Rate Limits:** See https://docs.datadoghq.com/api/latest/rate-limits/
  - Respect `X-RateLimit-*` headers in responses
  - Wait until `X-RateLimit-Reset` time if 429 received
  - See Error Handling section for detailed rate limit handling strategy

#### Search Logic

**Step 1: Initial Search**

For **Mode 1 (Log Message):**
```json
{
  "filter": {
    "from": "{calculated_from}",
    "to": "{calculated_to}",
    "query": "env:prod AND pod_label_team:card AND \"{log_message}\""
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}
```

For **Mode 2 (Free Text + Identifiers):**
```json
{
  "filter": {
    "from": "{calculated_from}",
    "to": "{calculated_to}",
    "query": "env:prod AND pod_label_team:card AND ({id1} OR {id2} OR {id3})"
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}
```

**Step 2: Session-Based Retrieval**

If Step 1 returns results, extract ALL unique `efilogid` values from results and search for each:

**Process:**
1. Parse Step 1 results and collect all unique `efilogid` values
2. For EACH unique `efilogid`, execute a search:

```json
{
  "filter": {
    "from": "{same_as_step1}",
    "to": "{same_as_step1}",
    "query": "@efilogid:{extracted_efilogid}"
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}
```

**Practical Considerations:**
- This could result in many API calls if there are many unique sessions
- Consider implementing a reasonable limit (e.g., up to 20-30 unique efilogids)
- If more than the limit, prioritize:
  1. Sessions with ERROR-level logs
  2. Most recent sessions (by timestamp)
  3. Sessions with most log entries in Step 1 results
- Log how many unique efilogids were found and how many were processed

#### Time Window Calculation

**Default (no datetime provided):**
- `from`: `"now-4h"`
- `to`: `"now"`

**With datetime provided:**
1. Parse datetime (flexible format)
2. Assume Tel Aviv timezone if not specified
3. Convert to UTC
4. Calculate window:
   - `from`: datetime - 2 hours (in UTC)
   - `to`: datetime + 2 hours (in UTC)
5. Format as milliseconds timestamp or ISO 8601

**Retry Logic (if no results):**
1. First attempt: Use calculated window (±2h or default 4h)
2. If no results → Expand window:
   - **No datetime provided:** Expand to `"now-24h"` to `"now"`
   - **Datetime provided:** Expand to ±12 hours centered on user's datetime, but **never beyond current time**
     - `from`: user_datetime - 12 hours
     - `to`: min(user_datetime + 12 hours, current_time)
     - Example: User provides Feb 10 6:00, current time is Feb 10 10:20 → search Feb 9 18:00 to Feb 10 10:20
3. If still no results → Expand to 7 days:
   - **No datetime provided:** Expand to `"now-7d"` to `"now"`
   - **Datetime provided:** Expand to ±3.5 days centered on user's datetime, but **never beyond current time**
     - `from`: user_datetime - 3.5 days
     - `to`: min(user_datetime + 3.5 days, current_time)
4. If still no results → Report "no logs found" and ask user for clarification

#### Response Processing

**Extract from each log entry:**
- `message` - The log message text
- `attributes.logger_name` - Full qualified class name (e.g., `com.sunbit.card.invitation.lead.application.EntitledCustomerService`)
- `attributes.service` - Service name (e.g., `card-invitation-service`)
- `attributes.efilogid` - Session identifier
- `attributes.dd.version` - Deployment version (e.g., `08b9cd7acf38ddf65e3e470bbb27137fe682323e___618`)
- `timestamp` - Log timestamp

**Output:**
- All matching log entries from Step 1 (up to 200 per query)
- All matching log entries from Step 2 (up to 200 per efilogid)
- Combined and deduplicated results
- List of unique services found
- List of unique efilogids processed
- If no logs found: "No logs found" message

**Logging:**
- Log Step 1 query constructed
- Log Step 1 API response status and results count
- Log number of unique efilogids found
- Log which efilogids are being processed (if limited)
- Log Step 2 queries for each efilogid
- Log Step 2 API responses
- Log final combined results count
- Log extracted services and efilogids

---

### 2. Deployment Checker

**Purpose:** Check for recent deployments that may correlate with the issue

#### GitHub Repository
- **Org:** `sunbit-dev`
- **Repo:** `kubernetes`
- **Branch:** Any branch with commits

#### Search Logic

**Time Window:**
- 72 hours BEFORE the timestamp used to search DataDog logs
- Example: If logs searched from 2026-02-10 14:00, check deployments from 2026-02-07 14:00 to 2026-02-10 14:00

**Commit Title Pattern:**
```
{service-name}-{commit_hash}___{build_number}
```

Example: `card-invitation-service-08b9cd7acf38ddf65e3e470bbb27137fe682323e___618`

**Correlation with DataDog:**
The `dd.version` attribute in DataDog logs equals the second part of the commit title:
- Commit title: `purchase-service-f0d1e9eb78545f1a5f71434d94f069edde128e3b___27650`
- DataDog `dd.version`: `f0d1e9eb78545f1a5f71434d94f069edde128e3b___27650`
- Application commit hash: `f0d1e9eb78545f1a5f71434d94f069edde128e3b` (before `___`)

#### For Each Service Found in Logs

1. Search `sunbit-dev/kubernetes` commits for titles containing the service name
2. Filter commits within 72-hour window
3. For each matching commit:
   - Extract commit timestamp
   - Extract application commit hash (part before `___`)
   - Find the associated closed PR
   - From the PR, retrieve list of changed files

#### GitHub MCP Integration
- **Primary:** Use MCP directly through Agent SDK's MCP integration
- **Fallback:** Use GitHub CLI (`gh`) via subprocess

#### Output
List of deployments for each service:
- Service name
- Deployment timestamp
- Application commit hash
- Kubernetes commit hash
- List of files changed in that deployment (from PR)

**Logging:**
- Log each service being checked
- Log commits found
- Log PR retrieval attempts
- Log any MCP/CLI errors

---

### 3. Code Checker

**Purpose:** Analyze code changes between versions to identify potential issues

#### GitHub Repository Mapping

**Primary Pattern:** `{service-name}` → `sunbit-dev/{service-name}`

**Fallback Strategy (if repo not found):**
1. Attempt to access `sunbit-dev/{service-name}`
2. If repo not found (404 error) AND service name contains "jobs":
   - Remove "-jobs" from the service name
   - Retry with `sunbit-dev/{service-name-without-jobs}`
   - Example: `card-jobs-service` → try `sunbit-dev/card-jobs-service` → 404 → try `sunbit-dev/card-service`
3. If still not found or service doesn't contain "jobs":
   - Log the error
   - Skip Code Checker for this service
   - Note in final report: "Code analysis unavailable - repository not found: sunbit-dev/{service-name}"

**Examples:**
- `card-invitation-service` → `sunbit-dev/card-invitation-service` (direct match)
- `card-account-service` → `sunbit-dev/card-account-service` (direct match)
- `card-jobs-service` → `sunbit-dev/card-jobs-service` (404) → `sunbit-dev/card-service` (success)
- `payment-jobs-service` → `sunbit-dev/payment-jobs-service` (404) → `sunbit-dev/payment-service` (attempt)
- `unknown-service` → `sunbit-dev/unknown-service` (404) → skip Code Checker, note in report

#### File Identification

**From DataDog logs, extract `logger_name`:**

Example: `com.sunbit.card.invitation.lead.application.EntitledCustomerService`

**Map to file path:**
- Language: Kotlin/Java (based on repository)
- Path: `src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt`
- Fallback: Try `.java` extension if `.kt` not found

#### Version Comparison

**Versions to compare:**
1. **Deployed version:** The commit hash from `dd.version` in the error logs (the code that was actually running when error occurred)
2. **Previous version:** Parent commit of the deployed version

**Process:**
1. Extract `dd.version` from DataDog logs where errors occurred
   - Format: `{commit_hash}___{build_number}`
   - Extract the `commit_hash` portion (before `___`)
2. From Deployment Checker results, find the deployment matching this `dd.version`
3. Fetch the parent commit (commit before this deployment)
4. For each file identified from `logger_name`:
   - Fetch file at parent commit (previous version)
   - Fetch file at deployed commit hash (version with errors)
   - Generate full diff showing what changed in the problematic deployment

**Note:** If multiple different `dd.version` values appear in error logs, prioritize the most frequently occurring one, or analyze all unique versions if they're significantly different.

#### Git References
- Use commit hash from `dd.version` for deployed version (the code with errors)
- Use parent commit hash for previous version (code before the problematic deployment)
- Both versions fetched by commit hash (not branch), ensuring exact version accuracy

#### Output

For each file:
- File path
- Full git diff (previous version → deployed version with errors)
- Analysis of potential issues:
  - Removed error handling
  - Changed business logic
  - New exceptions introduced
  - Modified SQL/database queries
  - Changed external API calls
  - Modified timing/async behavior
  - Security concerns

**Note:** The main agent can use this analysis or ignore it based on relevance.

**Logging:**
- Log files being fetched
- Log commit hashes used
- Log GitHub API calls
- Log analysis performed

---

## Orchestration Logic

### Flow Diagram

```
START
  ↓
Ask user: "Log message" or "Free text with identifiers"?
  ↓
┌─────────────────┬─────────────────┐
│   Log Message   │   Free Text     │
└─────────────────┴─────────────────┘
         ↓                 ↓
    Check DateTime?    Check DateTime?
         ↓                 ↓
  Calculate time     Calculate time
    window              window
         ↓                 ↓
┌────────────────────────────────────┐
│  DataDog Information Retriever     │
│  - Search logs                     │
│  - Extract services & efilogids    │
└────────────────────────────────────┘
         ↓
    Logs found?
         ↓
       YES → Extract unique services
         ↓
    For ALL services (in parallel):
         ↓
    ┌──────────────────────────────────────┐
    │  For Service 1, 2, 3... (parallel):  │
    │                                      │
    │  1. Run Deployment Checker           │
    │  2. When complete, run Code Checker  │
    │     (uses deployment commit hash)    │
    └──────────────────────────────────────┘
         ↓
    Aggregate results from all services
         ↓
    Clear results? ──NO──→ (If Mode 2) Apply investigation methodologies
         ↓                   on GitHub-fetched files to find root cause
       YES
         ↓
┌────────────────────────────────────┐
│  Generate Investigation Report     │
│  - Executive Summary               │
│  - Root Cause Analysis             │
│  - Evidence                        │
│  - Proposed Fix                    │
│  - Next Steps                      │
└────────────────────────────────────┘
         ↓
    Display report
         ↓
       END
```

### Decision Points

**If no logs found after retries:**
- Ask user for clarification
- Suggest alternative search terms/identifiers

**If logs found but unclear results (Mode 2 only):**
- Apply `systematic-debugging` or `investigate` methodology to dig deeper
- Work with files fetched from GitHub by Code Checker
- Methodologies guide analysis of GitHub-fetched files, not local codebase
- Only document in report if methodology was critical to finding root cause

**If multiple services found:**
- Investigate ALL services in parallel
- For each service: Run Deployment Checker → then Code Checker (sequential per service)
- Multiple services run in parallel: Service1(Deploy→Code) || Service2(Deploy→Code) || Service3(Deploy→Code)
- This maximizes parallelism while respecting the dependency: Code Checker needs deployment commit hash

**If sub-agent fails:**
- Retry once with same parameters
- If still fails, continue with partial results
- Note failure in final report

**If main agent is stuck:**
- Can ask user follow-up questions
- Cannot delegate to sub-agents for user interaction

---

## Configuration & Secrets

### Environment File: `.env`

**Location:** Agent project directory root

**Required Variables:**
```bash
DD_API_KEY=your_datadog_api_key
DD_APPLICATION_KEY=your_datadog_application_key
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
```

**Security:**
- Never commit `.env` to Git
- Add to `.gitignore`
- Load at agent startup using `python-dotenv` or similar

### GitHub MCP Configuration

**Reference:** `~/.claude.json` contains:
```json
{
  "github": {
    "command": "docker",
    "args": [
      "run",
      "-i",
      "--rm",
      "-e",
      "GITHUB_PERSONAL_ACCESS_TOKEN",
      "mcp/github"
    ],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
    }
  }
}
```

**Agent Usage:**
- Primary: Use MCP through Agent SDK integration
- Fallback: Use `gh` CLI commands via subprocess
- Token from `.env` file overrides config

---

## Output Format

### Investigation Report Structure

**Format:** Markdown
**Display:** Console/chat only (not saved to file)

**Template:**

```markdown
# Investigation Report: [Brief Issue Title]

**Issue**: [Original issue description]
**Investigated**: [DateTime]
**Status**: PROPOSED FIX (awaiting human review)

---

## Executive Summary

[2-3 sentences: What's the issue, what's the root cause, what's the fix]

---

## Timeline

**Log Search Window**: [from] to [to] (UTC)
**Deployments Checked**: 72 hours before [timestamp]

| Timestamp | Event | Service | Details |
|-----------|-------|---------|---------|
| [time] | Deployment | [service] | Commit: [hash] |
| [time] | Error Logged | [service] | [brief description] |

---

## Services Involved

[List of services found in logs]

1. **[service-name]**
   - Logs found: [count]
   - Deployments: [count]
   - Latest version: [dd.version]

---

## Root Cause Analysis

### Primary Cause
**Confidence**: [HIGH/MEDIUM/LOW]
**Service**: [service-name]
**Location**: `[file:line]`

[Detailed explanation with code snippets]

### Contributing Factors
[List any secondary issues that contribute]

---

## Evidence

### DataDog Logs
[Key log entries with timestamps]

```
[timestamp] [service] [logger] - [message]
```

### Code Changes
**Service**: [service-name]
**File**: [file-path]
**Commit**: [previous] → [current]

```diff
[show relevant diff]
```

**Analysis**: [Code Checker's analysis of potential issues]

### Deployments
[List of relevant deployments from Deployment Checker]

---

## Proposed Fix

### Option A: [Name] (Recommended)
**Risk**: [LOW/MEDIUM/HIGH]
**Scope**: [Files affected]

```kotlin
[Show the fix in the appropriate language]
```

**Why this works**: [Explanation]

### Option B: [Name] (Alternative)
[If applicable]

---

## Testing Required

### Manual Tests
1. [ ] [Test case]
2. [ ] [Test case]

### Automated Tests Needed
1. [ ] [Test to add]

---

## Files to Modify

1. `[file]` - [what change]
2. `[file]` - [what change]

---

## Next Steps for Developer

1. [ ] Review this report
2. [ ] Verify root cause hypothesis
3. [ ] Implement proposed fix
4. [ ] Run tests
5. [ ] Create PR with fix
6. [ ] Monitor for recurrence

---

## Investigation Details

### Sub-Agent Results

**DataDog Information Retriever**:
- Query attempts: [count]
- Logs found: [count]
- Services identified: [list]

**Deployment Checker**:
- Services checked: [list]
- Deployments found: [count]
- Status: [Success/Partial/Failed]

**Code Checker**:
- Files analyzed: [count]
- Diffs generated: [count]
- Status: [Success/Partial/Failed]

### Investigation Methodologies Applied
[**Only include this section if methodologies led to breakthrough/root cause**]
[Omit if standard investigation (DataDog + Deployment + Code Checker) was sufficient]

**When included:**
- Methodology: [systematic-debugging | investigate]
- Why it was critical: [explain how standard investigation was insufficient and methodology led to root cause]
- Key insight: [what the methodology revealed that standard investigation missed]
- Result: [outcome]

---

## Notes

[Any additional context, caveats, or observations]

---

*Generated by Production Issue Investigator Agent*
```

---

## Error Handling

### Sub-Agent Failures

**Retry Strategy:**
1. Catch exception from sub-agent
2. Log error details
3. Retry once with identical parameters
4. If second attempt fails:
   - Log failure
   - Continue investigation with partial results
   - Note failure in final report

**Error Logging:**
All sub-agents must log:
- Input parameters
- Actions performed
- API calls made
- Responses received
- Errors encountered
- Retry attempts

**Log Format:**
```
[TIMESTAMP] [SUB-AGENT-NAME] [LEVEL] [MESSAGE]
Example: [2026-02-10 14:30:00] [DataDogRetriever] [ERROR] API call failed: 429 Rate Limit
```

### Main Agent Error Handling

**DataDog API Errors:**
- **401 Unauthorized** → Report: "Check DD_API_KEY and DD_APPLICATION_KEY in .env"
- **429 Rate Limit** → Respect rate limit headers (see Rate Limit Handling below)
- **Timeout** → Expand time window and retry
- **Other errors** → Continue with partial results

**DataDog API Rate Limit Handling:**
Reference: https://docs.datadoghq.com/api/latest/rate-limits/

When 429 response received:
1. Parse response headers:
   - `X-RateLimit-Limit` - Maximum requests allowed in period
   - `X-RateLimit-Remaining` - Requests remaining in current period
   - `X-RateLimit-Reset` - Timestamp when limit resets (Unix epoch)
   - `X-RateLimit-Period` - Length of rate limit period in seconds
2. Calculate wait time: `wait_seconds = X-RateLimit-Reset - current_time`
3. Log: "Rate limit exceeded. Waiting {wait_seconds}s until {reset_time}"
4. Wait until reset time
5. Retry the same request
6. If rate limited again after wait → Report error and continue with partial results

**Rate Limit Prevention:**
- Log each API call with timestamp
- Track requests per period to anticipate limits
- If approaching limit (< 10% remaining), add small delays between requests

**GitHub MCP/CLI Errors:**
- MCP fails → Fallback to GitHub CLI
- CLI fails → Continue without deployment/code info
- Note in report: "Unable to retrieve [data type]"

**No Results Scenarios:**
- No logs found (after retries) → Ask user for clarification
- No deployments found → Note in report, continue with logs analysis
- No code changes found → Note in report, rely on logs

**Stuck/Unclear Scenarios:**
- Main agent can ask user follow-up questions
- Examples:
  - "The logs show errors in multiple services. Which service would you like to focus on?"
  - "No clear root cause found. Can you provide more context about when this issue started?"

---

## Technical Specifications

### Programming Language
- **Python 3.x** (3.9 or higher recommended)

### Framework
- **Claude Agent SDK** (Python)
- Sub-agents implemented using SDK's sub-agent functionality

### Key Dependencies

**Dependency Management:**
- Use `requirements.txt` with **minimum version constraints** (`>=`)
- Allows compatible updates while ensuring minimum required features
- Project uses `uv` for dependency management (preferred over pip)
- `uv sync` handles virtual environment and dependency installation automatically

**Required packages:**
```
# Claude Agent SDK and AI
anthropic>=0.40.0                 # Anthropic Python SDK
claude-agent-sdk>=0.1.35          # Claude Agent SDK framework

# Environment management
python-dotenv>=1.0.0              # Environment variable management

# HTTP and API clients
requests>=2.31.0                  # HTTP API calls (DataDog)
PyGithub>=2.1.1                   # GitHub API (fallback)

# Date and time utilities
python-dateutil>=2.8.2            # Flexible datetime parsing
pytz>=2023.3                      # Timezone handling (Tel Aviv → UTC)
```

**Virtual Environment & Dependency Installation:**
- **Recommended:** Use `uv` for automatic virtual environment and dependency management
- Setup and run: `uv run main.py` (handles everything automatically)
- Manual sync: `uv sync` (creates venv and installs dependencies)
- **Alternative:** Use Python's built-in `venv` module
  - Setup: `python3 -m venv venv`
  - Activate: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
  - Install: `pip install -r requirements.txt`

### Project Structure
```
production-issue-investigator/
├── .env                          # Secrets (not in Git, use .env.example as template)
├── .env.example                  # Environment variables template
├── .gitignore                    # Includes: .env, .venv/, logs/, __pycache__/
├── pyproject.toml                # Project metadata and dependencies (uv)
├── uv.lock                       # Locked dependency versions (uv)
├── requirements.txt              # Minimum version dependencies (pip fallback)
├── README.md                     # Setup and usage instructions
├── CLAUDE.md                     # Project-specific instructions for Claude Code
├── AGENT_SDK_GUIDE.md            # Complete Claude Agent SDK usage guide
├── QUICK_START.md                # Fast getting-started guide
├── SETUP_COMPLETE.md             # Setup verification documentation
├── ISSUE_RESOLVED.md             # Known issues and resolutions
├── .venv/                        # Virtual environment (not in Git, created by uv)
├── main.py                       # Main agent entry point
├── sre_agent_example.py          # Example SRE agent implementation
├── verify_setup.py               # Setup verification script
├── agents/
│   ├── __init__.py
│   ├── main_agent.py            # Main orchestrator
│   ├── datadog_retriever.py     # DataDog sub-agent
│   ├── deployment_checker.py    # Deployment sub-agent
│   └── code_checker.py          # Code sub-agent
├── utils/
│   ├── __init__.py
│   ├── datadog_api.py           # DataDog API wrapper
│   ├── github_helper.py         # GitHub MCP/CLI wrapper
│   ├── time_utils.py            # Datetime parsing & conversion
│   └── report_generator.py      # Report template renderer
├── docs/
│   └── designs/
│       └── production-issue-investigator-design.md  # This document
└── logs/
    └── agent.log                # Agent execution logs (not in Git)
```

### Logging Configuration
- **Level:** INFO for normal operation, DEBUG for troubleshooting
- **Format:** `[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s`
- **Output:** Both console and `logs/agent.log` file
- **Rotation:** Rotate logs when size > 10MB, keep 5 backups

### Performance Considerations
- Run Deployment Checker and Code Checker in parallel for each service
- DataDog pagination limit: 200 (sufficient for most investigations)
- GitHub API rate limits: Monitor and implement backoff if needed
- Timeout: 30 seconds per API call, 5 minutes total per sub-agent

---

## Implementation Notes

**Strategy:** Incremental build-and-test approach. Each phase delivers testable functionality.

### Phase 1: Foundation
**Goal:** Set up infrastructure and test basic connectivity

1. Set up project structure (directories, venv, requirements.txt)
2. Configure `.env` and secrets loading
3. Implement logging infrastructure
4. Create time_utils.py (datetime parsing and timezone conversion)
5. Create DataDog API wrapper with rate limit handling
6. **Test:** Verify DataDog API connectivity, rate limit header parsing, time conversions

**Deliverable:** Working DataDog API client that can make authenticated requests

---

### Phase 2: DataDog Sub-Agent + Basic Orchestration
**Goal:** Get logs from production and display them

1. Implement DataDog Information Retriever sub-agent:
   - Mode 1 search logic (log message)
   - Mode 2 search logic (identifiers)
   - Session-based retrieval (all unique efilogids)
   - Time window calculation and retry logic
   - Response parsing and deduplication
2. Implement minimal main agent orchestration:
   - Input mode detection (ask user to select Mode 1 or 2)
   - Call DataDog sub-agent
   - Display raw results
3. **Test:** Run real searches against production DataDog, verify log retrieval works for both modes

**Deliverable:** Agent can search DataDog logs and return results based on user input

---

### Phase 3: Deployment Checker Sub-Agent
**Goal:** Correlate errors with deployments

1. Create GitHub helper (MCP + CLI fallback)
2. Implement Deployment Checker sub-agent:
   - Search kubernetes repo for service commits
   - Filter by 72-hour window
   - Extract commit hashes and find PRs
   - Retrieve changed files from PRs
   - Handle repository mapping with fallback for "jobs" services
3. Integrate with main agent:
   - Extract services from DataDog results
   - Call Deployment Checker for each service (in parallel)
   - Display deployments and changed files
4. **Test:** Verify deployment correlation, test repository mapping edge cases

**Deliverable:** Agent can identify recent deployments for services found in logs

---

### Phase 4: Code Checker Sub-Agent
**Goal:** Show what code changed in problematic deployments

1. Implement Code Checker sub-agent:
   - File path mapping from logger_name
   - Extract dd.version from logs
   - Version comparison logic (deployed vs parent)
   - Fetch files at specific commits
   - Generate diffs
   - Code analysis (error handling, business logic, etc.)
2. Integrate with main agent:
   - Run Code Checker after Deployment Checker (sequential per service)
   - Multiple services in parallel
   - Apply investigation methodologies if results unclear (Mode 2)
3. **Test:** Verify diffs are accurate, test file path mapping for .kt and .java files

**Deliverable:** Agent can show code changes between versions

---

### Phase 5: Reporting + Full Integration
**Goal:** Generate comprehensive investigation reports

1. Implement report_generator.py:
   - Markdown report template
   - Fill in all sections from aggregated data
   - Handle partial results gracefully
   - Include methodology section only when critical
2. Full main agent orchestration:
   - Aggregate all sub-agent results
   - Determine if methodologies needed
   - Generate final report
   - Console output formatting
3. Error handling refinement:
   - All error scenarios covered
   - Partial results handled
   - User prompts for unclear situations
4. **Test with real production scenarios:**
   - Known issues with clear root causes
   - Issues requiring investigation methodologies
   - API failures and partial results
   - Time window edge cases
   - Multiple services
   - Repository mapping edge cases
5. **Performance optimization:**
   - Verify parallelism works correctly
   - Optimize API call patterns
   - Test rate limit handling

**Deliverable:** Fully functional agent that produces complete investigation reports

### Special Considerations

**Investigation Methodologies:**
- `systematic-debugging` and `investigate` are **process methodologies** (not executable skills)
- The main agent will follow these methodologies as guidance when investigating unclear results
- The methodology descriptions will be provided in the agent's system prompt
- Main agent applies these processes directly (no skill invocation)
- Only used by main agent (not sub-agents)
- Applied to GitHub-fetched files when initial investigation doesn't yield clear results (Mode 2)
- Implementation: Include methodology descriptions in main agent's initialization prompt

**Timezone Handling:**
- Default timezone for user input: Tel Aviv (Asia/Jerusalem)
- Always convert to UTC for DataDog API
- Display times in report in both Tel Aviv and UTC

**Service Name to Repository Mapping:**
- Primary: Direct mapping `{service-name}` → `sunbit-dev/{service-name}`
- Fallback: If repo not found AND name contains "jobs", remove "-jobs" and retry
- If still not found: Skip Code Checker, log error, note in report

**Version Correlation:**
- Parse `dd.version` from DataDog logs
- Match to kubernetes repo commit title pattern
- Extract application commit hash (part before `___`)
- Use for code comparison

---

## Appendix: API Examples

### DataDog Search by Log Message

**Request:**
```bash
curl --location 'https://api.datadoghq.com/api/v2/logs/events/search' \
--header 'Content-Type: application/json' \
--header 'Accept: application/json' \
--header 'DD-API-KEY: xxx' \
--header 'DD-APPLICATION-KEY: xxx' \
--data '{
  "filter": {
    "from": "now-4h",
    "query": "env:prod AND pod_label_team:card AND \"Trying to create new invitation for entitled customer\"",
    "to": "now"
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}'
```

**Response Structure:**
```json
{
  "data": [
    {
      "id": "...",
      "type": "log",
      "attributes": {
        "service": "card-invitation-service",
        "host": "i-0ad5f7b2675d2d629",
        "attributes": {
          "dd": {
            "service": "card-invitation-service",
            "env": "prod",
            "version": "08b9cd7acf38ddf65e3e470bbb27137fe682323e___618"
          },
          "efilogid": "-1-OTQ1NWU2MzEtNGQwNC00ZTE4LWE1Y2ItM2M3OGNkMmE4OGUw",
          "trace_id": "698b810c000000004462b61c1fa5ef21",
          "logger_name": "com.sunbit.card.invitation.lead.application.EntitledCustomerService"
        },
        "message": "Trying to create new invitation for entitled customer 9035428",
        "status": "info",
        "timestamp": "2026-02-10T19:03:43.990Z"
      }
    }
  ]
}
```

### DataDog Search by EfilogID

**Request:**
```bash
curl --location 'https://api.datadoghq.com/api/v2/logs/events/search' \
--header 'Content-Type: application/json' \
--header 'Accept: application/json' \
--header 'DD-API-KEY: xxx' \
--header 'DD-APPLICATION-KEY: xxx' \
--data '{
  "filter": {
    "from": "now-4h",
    "query": "@efilogid:-1-OTQ1NWU2MzEtNGQwNC00ZTE4LWE1Y2ItM2M3OGNkMmE4OGUw",
    "to": "now"
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}'
```

### DataDog Search by Identifiers

**Request:**
```bash
curl --location 'https://api.datadoghq.com/api/v2/logs/events/search' \
--header 'Content-Type: application/json' \
--header 'Accept: application/json' \
--header 'DD-API-KEY: xxx' \
--header 'DD-APPLICATION-KEY: xxx' \
--data '{
  "filter": {
    "from": "now-4h",
    "query": "env:prod AND pod_label_team:card AND (9035428 OR 12345 OR 67890)",
    "to": "now"
  },
  "page": {
    "limit": 200
  },
  "sort": "-timestamp"
}'
```

### GitHub CLI Examples

**List recent commits in kubernetes repo:**
```bash
gh api repos/sunbit-dev/kubernetes/commits \
  --jq '.[] | select(.commit.message | contains("card-invitation-service")) | {sha: .sha, message: .commit.message, date: .commit.author.date}'
```

**Get PR for a commit:**
```bash
gh api repos/sunbit-dev/kubernetes/commits/{commit_sha}/pulls \
  --jq '.[0] | {number: .number, title: .title, state: .state}'
```

**Get files changed in PR:**
```bash
gh api repos/sunbit-dev/kubernetes/pulls/{pr_number}/files \
  --jq '.[] | {filename: .filename, status: .status, additions: .additions, deletions: .deletions}'
```

**Get file content at specific commit:**
```bash
gh api repos/sunbit-dev/card-invitation-service/contents/src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt?ref={commit_hash} \
  --jq '.content' | base64 -d
```

---

## Document Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-02-10 | Initial design complete | Design Session |
| 2.0 | 2026-02-11 | Design verification with 12 key clarifications:<br>1. Investigation methodologies as guidance (not executable skills)<br>2. Time window retry centered on user datetime, never future<br>3. GitHub repo discovery with "-jobs" fallback<br>4. Parallel service execution, sequential Deploy→Code per service<br>5. Code comparison uses exact dd.version from error logs<br>6. Session retrieval for ALL unique efilogids<br>7. Explicit input mode selection (Mode 1 or 2)<br>8. Report methodology section only when critical<br>9. Pinned dependencies in requirements.txt<br>10. DataDog rate limit handling via X-RateLimit headers<br>11. Incremental implementation with testable phases<br>12. Multiple minor clarifications and refinements | Verification Session |
| 2.1 | 2026-02-11 | Updated to reflect actual implementation:<br>1. Changed dependencies from pinned (`==`) to minimum versions (`>=`)<br>2. Added `claude-agent-sdk` as explicit dependency<br>3. Updated all package versions to match requirements.txt<br>4. Added `uv` as recommended dependency manager<br>5. Updated project structure to include actual files:<br>   - pyproject.toml, uv.lock (uv files)<br>   - .env.example template<br>   - Documentation files (AGENT_SDK_GUIDE.md, QUICK_START.md, etc.)<br>   - sre_agent_example.py, verify_setup.py<br>   - docs/designs/ directory structure<br>6. Changed venv to .venv (uv convention) | Implementation Update |

---

**END OF DESIGN DOCUMENT**