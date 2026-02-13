# Quick Start: Rewrite Implementation

**TL;DR**: Step-by-step guide to start implementing the SDK rewrite

---

## Prerequisites

✅ Read the full plan: [`REWRITE_PLAN.md`](./REWRITE_PLAN.md)
✅ Understand current architecture issues
✅ Latest SDK documentation reviewed

---

## Week 1: Foundation (Start Here)

### Day 1: Session Management

```bash
# Create new files
touch utils/session_manager.py
touch tests/test_session_manager.py
```

**Implement:**
- Session directory creation
- Transcript writer
- Tool call JSONL logger

**Test:**
```bash
uv run pytest tests/test_session_manager.py -v
```

### Day 2-3: Hook System

```bash
touch utils/hooks.py
touch tests/test_hooks.py
```

**Implement:**
- `SubagentTracker` class
- PreToolUse hook
- PostToolUse hook
- Parent-child tracking

**Test:**
```bash
uv run pytest tests/test_hooks.py -v
```

### Day 4-5: Directory Structure & Config

```bash
# Create directories
mkdir -p files/{datadog_findings,deployment_findings,code_findings,reports}
mkdir -p mcp_servers
mkdir -p agents/prompts

# Update config
# Add: session_log_dir, default_model, bypass_permissions
```

---

## Week 2: MCP Tools

### Day 1-2: DataDog MCP Server

```bash
touch mcp_servers/datadog_server.py
touch tests/test_datadog_mcp.py
```

**Implement 3 tools:**
1. `search_logs` - Search DataDog logs
2. `get_logs_by_efilogid` - Get session logs
3. `parse_stack_trace` - Parse stack traces

**Pattern:**
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("search_logs", "Description", {"query": str, "from_time": str})
async def search_logs_tool(args):
    # Call existing utils/datadog_api.py
    # Return formatted JSON
    pass

datadog_mcp_server = create_sdk_mcp_server(
    name="datadog",
    version="1.0.0",
    tools=[search_logs_tool, ...]
)
```

### Day 3-4: GitHub MCP Server

```bash
touch mcp_servers/github_server.py
touch tests/test_github_mcp.py
```

**Implement 4 tools:**
1. `search_commits`
2. `get_file_content`
3. `get_pr_files`
4. `compare_commits`

### Day 5: Integration Testing

Test both MCP servers together:
```bash
uv run pytest tests/test_mcp_integration.py -v
```

---

## Week 3: Subagent Definitions

### Day 1: DataDog Investigator

```bash
touch agents/prompts/datadog_investigator_prompt.py
touch agents/subagent_definitions.py
```

**Write:**
1. Comprehensive prompt (see REWRITE_PLAN.md Phase 3)
2. AgentDefinition with tools list
3. Output format specification

### Day 2: Deployment Analyzer

```bash
touch agents/prompts/deployment_analyzer_prompt.py
```

**Write:**
1. Deployment search prompt
2. Correlation logic
3. AgentDefinition

### Day 3: Code Reviewer

```bash
touch agents/prompts/code_reviewer_prompt.py
```

**Write:**
1. Code analysis prompt
2. Issue detection guidelines
3. AgentDefinition

### Day 4-5: Prompt Testing

Manually test each prompt:
```python
# Test DataDog Investigator prompt standalone
# Verify it produces correct JSON output
# Check edge cases
```

---

## Week 4: Lead Agent

### Day 1-2: Lead Agent Core

```bash
touch agents/lead_agent.py
```

**Implement:**
```python
from claude_agent_sdk import query, ClaudeSDKClient, ClaudeAgentOptions
from agents.subagent_definitions import DATADOG_INVESTIGATOR, ...
from mcp_servers.datadog_server import datadog_mcp_server
from mcp_servers.github_server import github_mcp_server

class LeadAgent:
    async def investigate(self, user_input: str) -> str:
        # Setup session
        # Create hooks
        # Configure options
        # Use ClaudeSDKClient
        # Stream responses
        # Generate report
```

### Day 3: Lead Agent Prompt

Write comprehensive prompt (see REWRITE_PLAN.md Phase 4):
- Subagent descriptions
- Investigation workflow
- Report structure

### Day 4: Main Entry Point

```bash
# Update main.py
touch main_legacy.py  # Backup old version
```

**New main.py:**
```python
import asyncio
from agents.lead_agent import run_interactive

async def main():
    await run_interactive()

if __name__ == "__main__":
    asyncio.run(main())
```

### Day 5: End-to-End Test

```bash
# Manual test
uv run main.py

# Input: "NullPointerException in EntitledCustomerService"
# Verify: Full workflow completes
# Check: Session logs created
# Review: Report quality
```

---

## Week 5: Testing

### Day 1-2: Unit Tests

Write tests for:
- All MCP tools (50+ tests)
- Session manager
- Hooks
- Helper utilities

**Target: 85% coverage**

### Day 3: Integration Tests

Test subagent coordination:
```python
# Mock ClaudeSDKClient
# Verify subagent invocations
# Check file coordination
```

### Day 4: Error Scenarios

Test failures:
- MCP tool errors
- Subagent failures
- Partial results
- Rate limiting

### Day 5: Performance Testing

Measure:
- Investigation duration
- Cost per investigation
- Context window usage

---

## Week 6: Production Deployment

### Day 1: Security Review

- [ ] API credentials in .env only
- [ ] No secrets in logs
- [ ] Permission mode = `acceptEdits`
- [ ] Rate limiting configured

### Day 2: Documentation

Update:
- README.md
- CLAUDE.md
- Add troubleshooting guide

### Day 3: Deployment

```bash
# Set production env vars
export PERMISSION_MODE=acceptEdits
export LOG_LEVEL=INFO

# Deploy
uv sync
uv run main.py
```

### Day 4: Monitoring

Setup:
- Log aggregation
- Metrics dashboard
- Alerts

### Day 5: Training & Handoff

- Demo to team
- Document common issues
- Setup support process

---

## Validation Checklist

After each week, verify:

### Week 1 Checklist
- [ ] Session directories created correctly
- [ ] Transcript file written
- [ ] Tool calls logged to JSONL
- [ ] Hooks fire on all tools
- [ ] Tests pass (pytest)

### Week 2 Checklist
- [ ] DataDog MCP server created
- [ ] GitHub MCP server created
- [ ] All 7 tools implemented
- [ ] Tools return correct format
- [ ] Error handling works
- [ ] Tests pass

### Week 3 Checklist
- [ ] Three prompts written
- [ ] AgentDefinitions created
- [ ] Tool access properly scoped
- [ ] Output formats standardized
- [ ] Manual prompt testing done

### Week 4 Checklist
- [ ] Lead agent uses query()
- [ ] Subagents invoked via Task
- [ ] File coordination works
- [ ] Session logs complete
- [ ] End-to-end test passes

### Week 5 Checklist
- [ ] 40+ tests written
- [ ] 85%+ coverage achieved
- [ ] All error scenarios tested
- [ ] Performance acceptable
- [ ] Cost per investigation < $0.50

### Week 6 Checklist
- [ ] Security review passed
- [ ] Documentation complete
- [ ] Production deployment done
- [ ] Monitoring active
- [ ] Team trained

---

## Common Issues & Solutions

### Issue: "MCP server not connecting"
**Solution:** Check server name in `mcpServers` matches tool prefix
```python
mcp_servers={"datadog": datadog_mcp_server}
# Tools must be: mcp__datadog__search_logs
```

### Issue: "Hooks not firing"
**Solution:** Verify HookMatcher has `matcher=None` for all tools
```python
HookMatcher(matcher=None, hooks=[...])  # Matches ALL tools
```

### Issue: "Subagent not invoked"
**Solution:** Check Task tool in `allowed_tools`
```python
allowed_tools=["Task", "Read", "Write"]  # Task required!
```

### Issue: "Context window exceeded"
**Solution:** Truncate MCP tool results
```python
logs = result.logs[:50]  # Limit to 50 entries
message = log.message[:200]  # Truncate long messages
```

---

## Quick Reference Commands

```bash
# Run new SDK version
uv run main.py

# Run legacy version (for comparison)
uv run main_legacy.py

# Run specific test file
uv run pytest tests/test_mcp_tools.py -v

# Run with DEBUG logging
LOG_LEVEL=DEBUG uv run main.py

# Check session logs
tail -f logs/session_*/transcript.txt

# View tool calls
cat logs/session_*/tool_calls.jsonl | jq

# Cleanup old sessions (30+ days)
uv run python -c "from utils.session_cleanup import cleanup_old_sessions; from pathlib import Path; cleanup_old_sessions(Path('logs'), days=30)"
```

---

## Resources

- **Full Plan:** [`REWRITE_PLAN.md`](./REWRITE_PLAN.md)
- **SDK Docs:** https://platform.claude.com/docs/en/agent-sdk
- **Research Agent Example:** https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent
- **Current CLAUDE.md:** [`../CLAUDE.md`](../CLAUDE.md)

---

## Getting Help

1. Check REWRITE_PLAN.md for detailed explanations
2. Review research-agent demo for patterns
3. Test with DEBUG logging enabled
4. Check session logs for errors
5. Ask team for code review

---

**Ready to start? Begin with Week 1, Day 1! 🚀**
