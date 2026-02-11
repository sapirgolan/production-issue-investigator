# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Agent SDK-based application for investigating production issues by:
- Searching DataDog logs for errors and patterns
- Correlating issues with recent deployments from the `sunbit-dev/kubernetes` repository
- Analyzing code changes between versions in application repositories (`sunbit-dev/{service-name}`)
- Generating structured investigation reports with root cause analysis

The project uses a **main orchestrator agent** that coordinates three specialized **sub-agents** (DataDog retriever, deployment checker, code checker) to conduct comprehensive investigations.

## Running the Application

```bash
# Run with UV (recommended - handles venv and dependencies automatically)
uv run main.py

# Or run the SRE agent example
uv run sre_agent_example.py

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

### Python Requirements
- **Minimum**: Python 3.10 (Claude Agent SDK requirement)
- **Current**: Python 3.14.2 (tested and working)
- **Recommended for production**: Python 3.10-3.12

## Architecture

### Main Components

**Main Agent** (`agents/main_agent.py`)
- Orchestrates the investigation flow
- Determines input mode (log message vs identifiers)
- Coordinates sub-agents in parallel (one per service)
- Aggregates findings and generates final report
- Can apply investigation methodologies when initial results are unclear

**Sub-Agents**
1. **DataDog Information Retriever** (`agents/datadog_retriever.py`)
   - Searches production logs using DataDog API
   - Extracts services, sessions (efilogid), and version info (dd.version)
   - Time window: defaults to 4h, expands on retry (up to 7 days)

2. **Deployment Checker** (`agents/deployment_checker.py`)
   - Searches `sunbit-dev/kubernetes` for recent deployments (72h window)
   - Correlates kubernetes commits with application versions
   - Retrieves PR file changes

3. **Code Checker** (`agents/code_checker.py`)
   - Maps service names to GitHub repositories (`sunbit-dev/{service-name}`)
   - Compares deployed version (from dd.version) with parent commit
   - Generates diffs and analyzes potential issues
   - **Fallback**: If `{service-name}-jobs` repo not found, tries `{service-name}`

### Execution Flow

```
User Input (Mode 1: Log Message OR Mode 2: Identifiers)
  ↓
DataDog Search (Step 1: initial search, Step 2: all unique efilogids)
  ↓
Extract unique services
  ↓
For each service IN PARALLEL:
  ├─ Deployment Checker (find kubernetes commits)
  └─ Code Checker (uses deployment info, runs sequentially after)
  ↓
Aggregate results → Generate investigation report
```

**Key parallelization**: Multiple services are checked in parallel, but for each service, Code Checker runs sequentially after Deployment Checker (needs deployment commit hash).

## Key Technical Details

### Timezone Handling
- **Default user timezone**: Tel Aviv (Asia/Jerusalem)
- **DataDog API**: Always use UTC timestamps
- **Utilities**: `utils/time_utils.py` handles conversion

### Version Correlation
- **DataDog logs** contain `attributes.dd.version`: `{commit_hash}___{build_number}`
- **Kubernetes commits** have title pattern: `{service-name}-{commit_hash}___{build_number}`
- **Code comparison**: Compare deployed version (from dd.version) vs its parent commit

### Service to Repository Mapping
```python
# Primary pattern
service_name → sunbit-dev/{service-name}

# Fallback for "-jobs" services
card-jobs-service → sunbit-dev/card-jobs-service (404)
                  → sunbit-dev/card-service (retry)
```

### Logger Name to File Path
```python
# Logger name from DataDog
"com.sunbit.card.invitation.lead.application.EntitledCustomerService"

# Maps to file path
"src/main/kotlin/com/sunbit/card/invitation/lead/application/EntitledCustomerService.kt"
# Fallback: Try .java if .kt not found
```

### Rate Limit Handling (DataDog)
When 429 received:
1. Parse `X-RateLimit-Reset` header (Unix timestamp)
2. Calculate wait time: `reset_time - current_time`
3. Wait until reset
4. Retry request once

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
LOG_LEVEL=INFO
TIMEZONE=Asia/Tel_Aviv
```

## Important Design Patterns

### Sub-Agent Retry Logic
```python
try:
    result = sub_agent.execute()
except Exception as e:
    log_error(e)
    result = sub_agent.execute()  # Retry once with same parameters
    if failed_again:
        return partial_results  # Continue with what we have
```

### Investigation Methodologies
When Mode 2 (identifiers) doesn't yield clear results:
- Main agent can apply `systematic-debugging` or `investigate` methodologies
- These are **guidance processes** (not executable skills)
- Applied to GitHub-fetched files to find root cause
- Only documented in report if methodology was critical to breakthrough

### Parallel vs Sequential Execution
```python
# Multiple services: PARALLEL
asyncio.gather(
    investigate_service("card-invitation-service"),
    investigate_service("payment-service"),
    investigate_service("card-account-service")
)

# Per service: SEQUENTIAL (Code Checker needs deployment info)
deployment_info = await deployment_checker.check(service)
code_analysis = await code_checker.analyze(service, deployment_info)
```

## Investigation Report Structure

The agent generates Markdown reports with:
- **Executive Summary**: 2-3 sentence overview
- **Timeline**: Chronological events (deployments, errors)
- **Services Involved**: List with log counts, deployments, versions
- **Root Cause Analysis**: Primary cause + contributing factors with confidence level
- **Evidence**: DataDog logs, code diffs, deployment info
- **Proposed Fix**: Options with risk assessment and code examples
- **Testing Required**: Manual and automated test cases
- **Next Steps**: Developer checklist

**Note**: "Investigation Methodologies Applied" section only included when methodologies led to breakthrough (not for standard investigations).

## Testing Strategy

### Phase-Based Development
The design document (see `docs/designs/production-issue-investigator-design.md`) outlines 5 implementation phases:

1. **Phase 1: Foundation** - DataDog API connectivity, time utils, logging
2. **Phase 2: DataDog Sub-Agent** - Log retrieval and basic orchestration
3. **Phase 3: Deployment Checker** - Kubernetes commit correlation
4. **Phase 4: Code Checker** - Code diff and analysis
5. **Phase 5: Reporting** - Full integration and comprehensive reports

Each phase has specific deliverables and test scenarios.

### Manual Testing Scenarios
- Known production issues with clear root causes
- Issues requiring investigation methodologies
- Time window edge cases (no datetime, future datetime, very old datetime)
- Multiple services with different error patterns
- Repository mapping edge cases (jobs services, missing repos)
- API failures and rate limits

## Common Pitfalls to Avoid

1. **Don't assume timezones**: Always convert user input (Tel Aviv) → UTC for DataDog
2. **Don't skip efilogid session retrieval**: After initial search, fetch logs for ALL unique efilogids (not just first one)
3. **Don't use branch names for version comparison**: Always use exact commit hashes from dd.version
4. **Don't parallelize deployment→code checks per service**: Code Checker needs deployment info first
5. **Don't retry infinitely on rate limits**: Wait for X-RateLimit-Reset, retry once, then fail gracefully
6. **Don't expand time window into the future**: When user provides datetime, never search beyond current time

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

- **Design Document**: `docs/designs/production-issue-investigator-design.md` - Comprehensive 1150-line design with API examples
- **Agent SDK Guide**: `AGENT_SDK_GUIDE.md` - Complete Claude Agent SDK usage guide
- **README**: `README.md` - Installation and basic usage
- **Quick Start**: `QUICK_START.md` - Fast getting-started guide
