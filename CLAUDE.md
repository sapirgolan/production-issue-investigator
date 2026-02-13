# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Claude Agent SDK-based application** for investigating production issues. The system uses true AI-powered orchestration with the `query()` function and `ClaudeAgentOptions` to coordinate specialized subagents.

**Core capabilities:**
- Searching DataDog logs for errors and patterns
- Correlating issues with recent deployments from the `sunbit-dev/kubernetes` repository
- Analyzing code changes between versions in application repositories (`sunbit-dev/{service-name}`)
- Generating structured investigation reports with root cause analysis

## Architecture

### SDK-Based Design

The project uses the **Claude Agent SDK** for AI-powered orchestration:

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Input                                  │
│              (log message or identifiers)                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Lead Agent                                     │
│  - Uses query() from Claude Agent SDK                            │
│  - AI reasoning to determine investigation strategy              │
│  - Coordinates subagents via Task tool                           │
│  - Synthesizes findings into report                              │
│  - Tools: Task (for subagents)                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
           ┌───────────┴───────────┬────────────────┐
           │                       │                 │
           ▼                       ▼                 ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ datadog-         │  │ deployment-      │  │ code-            │
│ investigator     │  │ analyzer         │  │ reviewer         │
│                  │  │                  │  │                  │
│ - AI agent       │  │ - AI agent       │  │ - AI agent       │
│ - Searches logs  │  │ - Finds deploys  │  │ - Analyzes diffs │
│ - Analyzes       │  │ - Correlates     │  │ - Identifies     │
│   patterns       │  │   versions       │  │   issues         │
│ - Model: haiku   │  │ - Model: haiku   │  │ - Model: sonnet  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
           │                       │                 │
           └───────────┬───────────┴─────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Custom MCP Tools (In-Process)                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ DataDog MCP Server (mcp_servers/datadog_server.py)       │  │
│  │  - search_logs                                           │  │
│  │  - get_logs_by_efilogid                                  │  │
│  │  - parse_stack_trace                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ GitHub MCP Server (mcp_servers/github_server.py)         │  │
│  │  - search_commits                                        │  │
│  │  - get_file_content                                      │  │
│  │  - get_pr_files                                          │  │
│  │  - compare_commits                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key SDK Components

**Lead Agent** (`agents/lead_agent.py`)
- Uses `query()` with `ClaudeAgentOptions` for AI-powered orchestration
- Spawns subagents via the `Task` tool based on investigation needs
- Model: `opus` (requires strong reasoning for orchestration)

**Subagent Definitions** (`agents/subagent_definitions.py`)
- `DATADOG_INVESTIGATOR` - Log search and pattern analysis (haiku)
- `DEPLOYMENT_ANALYZER` - Deployment correlation (haiku)
- `CODE_REVIEWER` - Code change analysis (sonnet)

Each subagent is defined using `AgentDefinition` with:
- `description` - When to use this agent
- `prompt` - Detailed instructions
- `tools` - Available MCP and file tools
- `model` - Optimized model selection

### File Structure

```
production-issue-investigator/
├── main.py                              # Entry point (SDK version)
├── main_legacy.py                       # Legacy entry point (deprecated)
├── agents/
│   ├── lead_agent.py                    # SDK orchestrator with query()
│   ├── subagent_definitions.py          # AgentDefinition instances
│   ├── datadog_investigator_prompt.py   # DataDog subagent prompt
│   ├── deployment_analyzer_prompt.py    # Deployment subagent prompt
│   ├── code_reviewer_prompt.py          # Code reviewer subagent prompt
│   ├── main_agent.py                    # Legacy orchestrator (deprecated)
│   ├── datadog_retriever.py             # Legacy utility class
│   ├── deployment_checker.py            # Legacy utility class
│   ├── code_checker.py                  # Legacy utility class
│   └── exception_analyzer.py            # Exception analysis utilities
├── mcp_servers/
│   ├── datadog_server.py                # DataDog MCP tool definitions
│   └── github_server.py                 # GitHub MCP tool definitions
├── utils/
│   ├── session_manager.py               # Session directory management
│   ├── hooks.py                         # PreToolUse/PostToolUse hooks
│   ├── datadog_api.py                   # DataDog API wrapper
│   ├── github_helper.py                 # GitHub API wrapper
│   ├── config.py                        # Configuration with model settings
│   ├── logger.py                        # Logging setup
│   ├── time_utils.py                    # Timezone utilities
│   ├── stack_trace_parser.py            # Stack trace parsing
│   └── report_generator.py              # Report generation utilities
├── logs/
│   └── session_YYYYMMDD_HHMMSS/         # Session directories
│       ├── transcript.txt               # Human-readable conversation
│       ├── tool_calls.jsonl             # Machine-readable tool logs
│       ├── investigation_report.md      # Final report
│       └── files/
│           ├── datadog_findings/        # DataDog subagent output
│           ├── deployment_findings/     # Deployment subagent output
│           └── code_findings/           # Code reviewer output
└── tests/                               # Test suite
```

## Running the Application

```bash
# Run with UV (recommended - handles venv and dependencies automatically)
uv run main.py

# Or run the legacy version (deprecated)
uv run main_legacy.py

# Verify setup
uv run verify_setup.py
```

## Development Commands

### Dependency Management
```bash
# Install/sync dependencies
uv sync

# Update dependencies
uv lock --upgrade

# Add a new dependency (edit pyproject.toml, then):
uv sync
```

### Testing
```bash
# Run all tests
uv run python -m pytest tests/ -v

# Run specific test file
uv run python -m pytest tests/test_datadog_api_coverage.py -v

# Run with coverage
uv run python -m pytest tests/ --cov=utils --cov=agents --cov-report=term-missing

# Run critical path coverage (must be 95%+)
uv run pytest --cov=mcp_servers --cov=utils/session_manager --cov=utils/hooks --cov-fail-under=95
```

### Logging
```bash
# Run with DEBUG logs (shows full HTTP bodies and CLI commands)
LOG_LEVEL=DEBUG uv run main.py

# Run with INFO logs (default - shows summaries only)
LOG_LEVEL=INFO uv run main.py

# View session transcript
cat logs/session_*/transcript.txt

# Analyze tool calls
cat logs/session_*/tool_calls.jsonl | jq .
```

### Python Requirements
- **Minimum**: Python 3.10 (Claude Agent SDK requirement)
- **Current**: Python 3.14.2 (tested and working)
- **Recommended for production**: Python 3.10-3.12

## Subagent Details

### datadog-investigator

**Role:** Log search and pattern analysis

**Tools:**
- `mcp__datadog__search_logs` - Search DataDog logs with query filters
- `mcp__datadog__get_logs_by_efilogid` - Retrieve session logs
- `mcp__datadog__parse_stack_trace` - Extract file paths from exceptions
- `Write`, `Read`, `Glob` - File operations

**Output:** Writes to `files/datadog_findings/summary.json`

**Model:** haiku (cost-effective for search operations)

### deployment-analyzer

**Role:** Find and correlate deployments with errors

**Tools:**
- `mcp__github__search_commits` - Search kubernetes repo commits
- `mcp__github__get_file_content` - Get file at commit
- `mcp__github__get_pr_files` - Get PR changed files
- `Write`, `Read`, `Bash` - File and shell operations

**Output:** Writes to `files/deployment_findings/{service}_deployments.json`

**Model:** haiku (cost-effective for search)

### code-reviewer

**Role:** Analyze code changes for potential issues

**Tools:**
- `mcp__github__get_file_content` - Get file at specific commit
- `mcp__github__compare_commits` - Get diff between commits
- `Write`, `Read` - File operations

**Output:** Writes to `files/code_findings/{service}_analysis.json`

**Model:** sonnet (needs good code analysis capabilities)

## Session Management

Each investigation creates a session directory with:

```
logs/session_YYYYMMDD_HHMMSS/
├── transcript.txt           # Human-readable conversation log
├── tool_calls.jsonl         # Machine-readable tool invocations
├── investigation_report.md  # Final Markdown report
└── files/
    ├── datadog_findings/    # DataDog subagent outputs
    │   └── summary.json
    ├── deployment_findings/ # Deployment subagent outputs
    │   └── {service}_deployments.json
    └── code_findings/       # Code reviewer outputs
        └── {service}_analysis.json
```

**transcript.txt** - Human-readable log of the conversation:
```
User: NullPointerException in EntitledCustomerService

Agent: [LEAD] Starting Task
[datadog-investigator] Starting mcp__datadog__search_logs
[datadog-investigator] mcp__datadog__search_logs completed (1234ms)
...
```

**tool_calls.jsonl** - Machine-readable tool call logs:
```json
{"event":"tool_call_start","timestamp":"2026-02-13T10:00:00.123Z","tool_use_id":"abc123","agent_id":"LEAD","tool_name":"Task","parent_tool_use_id":null}
{"event":"tool_call_complete","timestamp":"2026-02-13T10:00:05.456Z","tool_use_id":"abc123","agent_id":"LEAD","tool_name":"Task","success":true,"duration_ms":5333}
```

## Environment Configuration

Required in `.env`:
```bash
# Claude Agent SDK
ANTHROPIC_API_KEY=sk-ant-...

# DataDog
DATADOG_API_KEY=...
DATADOG_APP_KEY=...
DATADOG_SITE=datadoghq.com

# GitHub
GITHUB_TOKEN=ghp_...

# Application
LOG_LEVEL=INFO  # Use DEBUG for full HTTP/CLI logs
TIMEZONE=Asia/Tel_Aviv

# Model Configuration (optional - defaults shown)
LEAD_AGENT_MODEL=opus
DATADOG_INVESTIGATOR_MODEL=haiku
DEPLOYMENT_ANALYZER_MODEL=haiku
CODE_REVIEWER_MODEL=sonnet

# Permission Mode (optional)
BYPASS_PERMISSIONS=bypassPermissions  # Use "acceptEdits" in production
```

## Key Technical Details

### Hook System

The hook system (`utils/hooks.py`) provides observability:

**PreToolUse Hooks:**
- Log tool invocations with timestamp
- Track parent-child relationships (lead vs subagent)
- Record start time for duration calculation

**PostToolUse Hooks:**
- Log success/failure status
- Calculate and record duration
- Write to both JSONL and transcript

### MCP Tool Design

Tools in `mcp_servers/` follow this pattern:
```python
@tool(
    "tool_name",
    "Description for Claude to understand when to use this",
    {"param1": str, "param2": int}
)
async def tool_name_impl(args: dict[str, Any]) -> dict[str, Any]:
    try:
        # Call existing utility via asyncio.to_thread()
        result = await asyncio.to_thread(utility.method, args["param1"])
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "is_error": True
        }
```

### Timezone Handling
- **Default user timezone**: Tel Aviv (Asia/Jerusalem)
- **DataDog API**: Always use UTC timestamps
- **Utilities**: `utils/time_utils.py` handles conversion

### Version Correlation
- **DataDog logs** contain `attributes.dd.version`: `{commit_hash}___{build_number}`
- **Kubernetes commits** have title pattern: `{service-name}-{commit_hash}___{build_number}`
- **Code comparison**: Compare deployed version (from dd.version) vs its parent commit

### DataDog Query Escaping
**Important**: When querying by efilogid, the value must be wrapped in quotes:
```python
# Correct format (Python string with quotes)
query = '@efilogid:"-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl"'

# Wrong format (no quotes - will not match)
query = '@efilogid:-1-NGFmMmVkMTgtYmU2YS00MmFiLTg0Y2UtNjBmNTU0N2UwYjFl'
```

## Investigation Report Structure

The agent generates Markdown reports with:
- **Executive Summary**: 2-3 sentence overview
- **Timeline**: Chronological events (deployments, errors)
- **Services Impacted**: List with log counts, deployments, versions
- **Root Cause Analysis**: Primary cause + contributing factors with confidence level
- **Code Issues Found**: Specific files, issues, and recommended fixes
- **Proposed Fix**: Options with risk assessment and code examples
- **Testing Required**: Manual and automated test cases
- **Next Steps**: Developer checklist

## Common Pitfalls to Avoid

1. **Don't assume timezones**: Always convert user input (Tel Aviv) to UTC for DataDog
2. **Don't skip efilogid session retrieval**: After initial search, fetch logs for ALL unique efilogids
3. **Don't use branch names for version comparison**: Always use exact commit hashes from dd.version
4. **Don't forget query escaping**: efilogid queries must have escaped quotes around the value
5. **Don't ignore session files**: Subagents communicate via files in the session directory

## Project-Specific Constraints

### From Global CLAUDE.md (Kotlin/Spring)
While this project is Python-based, it investigates Kotlin/Spring services:
- Expect Kotlin `.kt` files (fallback to `.java`)
- Services follow Spring Boot patterns
- Constructor injection with `val` properties
- No JPA relationships (entities reference by ID)
- First-layer packages are by feature (not layer)

### DataDog Query Filters
Always include in queries:
- `env:prod` - Production environment only
- `pod_label_team:card` - Card team services
- Additional filters: service names, identifiers, log messages

### GitHub Organization
- Kubernetes configs: `sunbit-dev/kubernetes`
- Application repos: `sunbit-dev/{service-name}`
- All repos are private (requires GITHUB_TOKEN)

## Additional Documentation

- **Rewrite Plan**: `docs/REWRITE_PLAN.md` - Comprehensive SDK migration plan
- **Design Document**: `docs/designs/production-issue-investigator-design.md` - Original design
- **Agent SDK Guide**: `AGENT_SDK_GUIDE.md` - Complete Claude Agent SDK usage guide
- **README**: `README.md` - Installation and basic usage
- **Quick Start**: `QUICK_START.md` - Fast getting-started guide
