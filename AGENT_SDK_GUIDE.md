# Claude Agent SDK Integration Guide

## Overview

This project now includes the **Claude Agent SDK** for building AI agents that can autonomously investigate production issues, analyze logs, and provide SRE support.

## Installation

The Claude Agent SDK is already installed in your virtual environment (version 0.1.35).

### Verify Installation

```bash
# Activate virtual environment
source .venv/bin/activate  # or: .venv/Scripts/activate on Windows

# Verify SDK version
python -c "import claude_agent_sdk; print(claude_agent_sdk.__version__)"
```

## Setup

### 1. API Key Configuration

Ensure your `.env` file has the Anthropic API key:

```env
ANTHROPIC_API_KEY=your_api_key_here
```

Get your API key from: https://console.anthropic.com/

### 2. Running the SRE Agent Example

The project includes `sre_agent_example.py` which demonstrates a full SRE/Support agent:

```bash
python sre_agent_example.py
```

This will present you with three modes:
1. **Example Scenarios** - Pre-configured investigation scenarios
2. **Interactive Mode** - Ask questions and get follow-up responses
3. **Single Investigation** - Investigate a specific issue

## Agent Capabilities

The SRE agent has been configured with these tools:

- **Read** - Read log files, configurations, and code
- **Grep** - Search through logs and files for patterns
- **Glob** - Find files by pattern (e.g., `*.log`, `**/*.py`)
- **Bash** - Run diagnostic commands (e.g., `ps aux`, `df -h`, `netstat`)
- **Write** - Create analysis reports and documentation

## Example Usage

### Quick Start Example

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def quick_investigation():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Bash"],
        permission_mode="acceptEdits"
    )

    async for message in query(
        prompt="Check the system logs for any errors in the last hour",
        options=options
    ):
        print(message)

asyncio.run(quick_investigation())
```

### SRE Investigation Example

```python
issue_description = """
Our API is returning 500 errors since the last deployment.

Please investigate:
1. Check error logs for patterns
2. Review recent code changes
3. Check system resources
4. Identify the root cause
"""

await investigate_issue(issue_description)
```

## Common SRE Tasks

### Log Analysis

```python
prompt = "Analyze logs in ./logs directory and identify error patterns"
```

### System Diagnostics

```python
prompt = """
Run system diagnostics:
1. Check CPU and memory usage
2. Check disk space
3. Review running processes
4. Check network connections
"""
```

### Configuration Review

```python
prompt = "Review all configuration files and identify any potential issues"
```

### Deployment Investigation

```python
prompt = """
We deployed version 2.3.1 an hour ago and users are reporting slow response times.
Please investigate and identify the root cause.
"""
```

## Advanced Features

### Using ClaudeSDKClient for Continuous Conversations

For multi-turn conversations where context is preserved:

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def continuous_investigation():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Bash"],
        permission_mode="acceptEdits"
    )

    async with ClaudeSDKClient(options=options) as client:
        # First question
        await client.query("What files are in the logs directory?")
        async for msg in client.receive_response():
            print(msg)

        # Follow-up - Claude remembers the previous context
        await client.query("Can you analyze the most recent log file?")
        async for msg in client.receive_response():
            print(msg)
```

### Custom Tools with MCP

You can add custom tools specific to your infrastructure:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("check_deployment", "Check deployment status", {"service": str})
async def check_deployment(args):
    # Your custom deployment check logic
    service = args["service"]
    # ... implementation ...
    return {
        "content": [{
            "type": "text",
            "text": f"Deployment status for {service}: ..."
        }]
    }

# Create MCP server with custom tools
deployment_server = create_sdk_mcp_server(
    name="deployment_tools",
    version="1.0.0",
    tools=[check_deployment]
)

# Use it in your agent
options = ClaudeAgentOptions(
    mcp_servers={"deploy": deployment_server},
    allowed_tools=["mcp__deploy__check_deployment"]
)
```

## Permission Modes

Control how the agent interacts with your system:

- **`default`** - Prompts for approval before each action (recommended for production)
- **`acceptEdits`** - Auto-approves file edits (good for development)
- **`bypassPermissions`** - No prompts (use with caution)
- **`plan`** - Creates a plan without executing (useful for review)

Example:

```python
options = ClaudeAgentOptions(
    permission_mode="default",  # Safer for production
    allowed_tools=["Read", "Grep", "Bash"]
)
```

## Best Practices

### 1. Start with Limited Tools

Begin with read-only tools and gradually add more capabilities:

```python
# Start conservative
allowed_tools=["Read", "Grep", "Glob"]

# Add diagnostics after testing
allowed_tools=["Read", "Grep", "Glob", "Bash"]

# Add write capabilities when needed
allowed_tools=["Read", "Grep", "Glob", "Bash", "Write"]
```

### 2. Use Descriptive Prompts

Be specific about what you want the agent to investigate:

```python
# ❌ Vague
prompt = "Check the logs"

# ✅ Specific
prompt = """
Analyze the application logs in ./logs/app.log for the time period
between 14:00 and 15:00 today. Focus on error messages related to
database connections and provide a summary of patterns found.
"""
```

### 3. Set Appropriate Working Directories

```python
from pathlib import Path

options = ClaudeAgentOptions(
    cwd=str(Path("/var/log/myapp")),  # Set to your log directory
    allowed_tools=["Read", "Grep"]
)
```

### 4. Monitor Costs

The SDK provides usage statistics:

```python
if isinstance(message, ResultMessage):
    print(f"Duration: {message.duration_ms}ms")
    print(f"Cost: ${message.total_cost_usd:.4f}")
    print(f"Turns: {message.num_turns}")
```

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not found"

**Solution:** Ensure your `.env` file exists and contains your API key:

```bash
# Check if .env exists
ls -la .env

# Create from example if needed
cp .env.example .env

# Edit and add your API key
# ANTHROPIC_API_KEY=sk-ant-...
```

### Issue: "CLI not found" errors

**Solution:** The Python SDK doesn't require the CLI to be installed separately. If you see this error, ensure `claude-agent-sdk` is installed:

```bash
uv pip install claude-agent-sdk==0.1.35
```

### Issue: Permission denied errors

**Solution:** If the agent needs to access restricted files or run privileged commands:

1. Use `permission_mode="default"` to approve actions manually
2. Or adjust file permissions: `chmod +r /path/to/file`
3. Or run with appropriate user privileges

## Resources

- **Official Documentation**: https://docs.anthropic.com/en/api/agent-sdk/overview
- **Python SDK Reference**: https://docs.anthropic.com/en/api/agent-sdk/python
- **Example Agents**: https://github.com/anthropics/claude-agent-sdk-demos
- **API Console**: https://console.anthropic.com/

## Next Steps

1. ✅ Set up your API key in `.env`
2. ✅ Run `python sre_agent_example.py` to test the agent
3. 📝 Customize the agent for your specific infrastructure
4. 🔧 Add custom tools for your monitoring systems (DataDog, Prometheus, etc.)
5. 🚀 Integrate into your incident response workflow

## Support

For issues or questions:
- Check the official documentation
- Review example code in `sre_agent_example.py`
- Consult the Python SDK reference for detailed API information
