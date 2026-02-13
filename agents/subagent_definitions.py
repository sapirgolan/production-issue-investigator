"""
Subagent Definitions for Production Issue Investigator.

This module defines the three specialized subagents using Claude Agent SDK's
AgentDefinition class. Each subagent has a specific role, tools, and model
configuration optimized for its task.

Usage:
    from agents.subagent_definitions import SUBAGENT_DEFINITIONS

    # Use in ClaudeAgentOptions
    options = ClaudeAgentOptions(
        agents=SUBAGENT_DEFINITIONS,
        ...
    )
"""

from claude_agent_sdk import AgentDefinition

from agents.datadog_investigator_prompt import DATADOG_INVESTIGATOR_PROMPT
from agents.deployment_analyzer_prompt import DEPLOYMENT_ANALYZER_PROMPT
from agents.code_reviewer_prompt import CODE_REVIEWER_PROMPT


# DataDog Investigator Subagent
# - Role: Log search and pattern analysis
# - Model: haiku (cost-effective for search operations)
# - Tools: DataDog MCP tools + Read/Write for findings
DATADOG_INVESTIGATOR = AgentDefinition(
    description=(
        "Searches DataDog production logs for errors and patterns. "
        "Extracts services, session IDs (efilogid), and version info (dd.version). "
        "Writes findings to files/datadog_findings/."
    ),
    prompt=DATADOG_INVESTIGATOR_PROMPT,
    tools=[
        # DataDog MCP tools (prefixed with mcp__datadog__)
        "mcp__datadog__search_logs",
        "mcp__datadog__get_logs_by_efilogid",
        "mcp__datadog__parse_stack_trace",
        # File operations
        "Write",
        "Read",
        "Glob",
    ],
    model="haiku",
)


# Deployment Analyzer Subagent
# - Role: Find and correlate deployments with errors
# - Model: haiku (cost-effective for search)
# - Tools: GitHub MCP tools for kubernetes repo + file operations
DEPLOYMENT_ANALYZER = AgentDefinition(
    description=(
        "Searches sunbit-dev/kubernetes for recent deployments. "
        "Correlates deployment times with log errors. "
        "Extracts PR information and changed files. "
        "Writes findings to files/deployment_findings/."
    ),
    prompt=DEPLOYMENT_ANALYZER_PROMPT,
    tools=[
        # GitHub MCP tools (prefixed with mcp__github__)
        "mcp__github__search_commits",
        "mcp__github__get_file_content",
        "mcp__github__get_pr_files",
        # File operations
        "Write",
        "Read",
        # Shell for git operations if needed
        "Bash",
    ],
    model="haiku",
)


# Code Reviewer Subagent
# - Role: Analyze code changes for potential issues
# - Model: sonnet (needs good code analysis capabilities)
# - Tools: GitHub MCP tools for code comparison + file operations
CODE_REVIEWER = AgentDefinition(
    description=(
        "Analyzes code changes between deployed version and parent commit. "
        "Identifies potential issues like null safety, exception handling, logic changes. "
        "Maps logger names to file paths. "
        "Writes findings to files/code_findings/."
    ),
    prompt=CODE_REVIEWER_PROMPT,
    tools=[
        # GitHub MCP tools (prefixed with mcp__github__)
        "mcp__github__get_file_content",
        "mcp__github__compare_commits",
        # File operations
        "Write",
        "Read",
    ],
    model="sonnet",
)


# Combined dictionary for use in ClaudeAgentOptions
SUBAGENT_DEFINITIONS = {
    "datadog-investigator": DATADOG_INVESTIGATOR,
    "deployment-analyzer": DEPLOYMENT_ANALYZER,
    "code-reviewer": CODE_REVIEWER,
}


# Individual definitions for direct access
__all__ = [
    "SUBAGENT_DEFINITIONS",
    "DATADOG_INVESTIGATOR",
    "DEPLOYMENT_ANALYZER",
    "CODE_REVIEWER",
]
