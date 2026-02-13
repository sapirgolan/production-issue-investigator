# Production Issue Investigator

An AI-powered agent for investigating production issues using **Claude Agent SDK**, DataDog, and GitHub.

## Architecture Overview

This project uses the **Claude Agent SDK** with true AI-powered orchestration:

```
                    ┌─────────────────┐
                    │   Lead Agent    │
                    │  (query() SDK)  │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│     datadog-     │ │  deployment- │ │     code-        │
│   investigator   │ │   analyzer   │ │    reviewer      │
│    (haiku)       │ │   (haiku)    │ │    (sonnet)      │
└──────────────────┘ └──────────────┘ └──────────────────┘
           │                 │                 │
           └─────────────────┴─────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │        MCP Tools             │
              │  - DataDog (search, logs)    │
              │  - GitHub (commits, diffs)   │
              └──────────────────────────────┘
```

**Key Features:**
- **Lead Agent**: Uses `query()` with `ClaudeAgentOptions` for AI reasoning
- **True Subagents**: AI agents with prompts, tools, and autonomous reasoning
- **Custom MCP Tools**: DataDog and GitHub APIs as MCP tools
- **Hook-based Observability**: Comprehensive tracking of all tool usage
- **Session Management**: Persistent transcripts and tool call logs

## Requirements

- Python 3.10 or higher (Claude Agent SDK requirement)
- UV (recommended) or pip for dependency management
- API keys for:
  - Anthropic (Claude)
  - DataDog
  - GitHub

## Installation

### Using UV (Recommended)

UV is a fast Python package installer and runner. Install it first if you haven't:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then run the project directly with UV:

```bash
# Run directly with UV (handles venv and dependencies automatically)
uv run main.py

# Or sync dependencies first
uv sync
uv run main.py
```

### Using Traditional Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Unix/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```bash
   # Required
   ANTHROPIC_API_KEY=your_api_key_here
   DATADOG_API_KEY=your_datadog_api_key
   DATADOG_APP_KEY=your_datadog_app_key
   GITHUB_TOKEN=your_github_token_here

   # Optional
   LOG_LEVEL=INFO
   TIMEZONE=Asia/Tel_Aviv
   ```

## Project Structure

```
production-issue-investigator/
├── main.py                      # Main entry point (SDK version)
├── main_legacy.py               # Legacy entry point (deprecated)
├── agents/
│   ├── lead_agent.py            # SDK orchestrator with query()
│   ├── subagent_definitions.py  # AgentDefinition instances
│   ├── datadog_investigator_prompt.py
│   ├── deployment_analyzer_prompt.py
│   └── code_reviewer_prompt.py
├── mcp_servers/
│   ├── datadog_server.py        # DataDog MCP tools
│   └── github_server.py         # GitHub MCP tools
├── utils/
│   ├── session_manager.py       # Session directory management
│   ├── hooks.py                 # Tool usage tracking
│   ├── datadog_api.py           # DataDog API wrapper
│   ├── github_helper.py         # GitHub API wrapper
│   └── config.py                # Configuration
├── logs/
│   └── session_YYYYMMDD_HHMMSS/ # Session directories
│       ├── transcript.txt       # Human-readable log
│       ├── tool_calls.jsonl     # Machine-readable log
│       └── investigation_report.md
└── tests/                       # Test suite
```

## Usage

### Interactive Mode

```bash
# Using UV (recommended)
uv run main.py

# Using Python directly
python main.py
```

The agent will prompt you to describe the issue:

```
======================================================================
         Production Issue Investigator (SDK Version)
======================================================================

Investigate production issues using AI-powered analysis.

Examples:
  - 'NullPointerException in EntitledCustomerService'
  - 'Investigate CID 12345, paymentId abc-def'
  - 'Errors in payment-service since yesterday'

Type 'exit' to quit.
======================================================================

Describe the issue:
```

### Session Output

Each investigation creates a session directory in `logs/`:

```
logs/session_20260213_100000/
├── transcript.txt           # Human-readable conversation
├── tool_calls.jsonl         # Tool invocation logs
├── investigation_report.md  # Final report
└── files/
    ├── datadog_findings/    # Log analysis results
    ├── deployment_findings/ # Deployment correlations
    └── code_findings/       # Code review results
```

## Subagents

| Agent | Role | Model | Tools |
|-------|------|-------|-------|
| `datadog-investigator` | Log search and pattern analysis | haiku | search_logs, get_logs_by_efilogid, parse_stack_trace |
| `deployment-analyzer` | Deployment correlation | haiku | search_commits, get_file_content, get_pr_files |
| `code-reviewer` | Code change analysis | sonnet | get_file_content, compare_commits |

## Development

```bash
# Run tests
uv run python -m pytest tests/ -v

# Run with coverage
uv run python -m pytest tests/ --cov=utils --cov=agents --cov-report=term-missing

# Run with debug logging
LOG_LEVEL=DEBUG uv run main.py
```

## Dependencies

Core dependencies:
- `anthropic>=0.40.0` - Anthropic Python client
- `claude-agent-sdk>=0.1.35` - Claude Agent SDK for AI orchestration
- `python-dotenv>=1.0.0` - Environment variable management
- `requests>=2.31.0` - HTTP API calls
- `PyGithub>=2.1.1` - GitHub API client
- `python-dateutil>=2.8.2` - Flexible datetime parsing
- `pytz>=2023.3` - Timezone handling

## Documentation

- [CLAUDE.md](CLAUDE.md) - Detailed architecture and development guide
- [docs/REWRITE_PLAN.md](docs/REWRITE_PLAN.md) - SDK migration plan
- [AGENT_SDK_GUIDE.md](AGENT_SDK_GUIDE.md) - Claude Agent SDK usage guide
- [QUICK_START.md](QUICK_START.md) - Fast getting-started guide

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
