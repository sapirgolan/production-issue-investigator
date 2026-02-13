"""
Agent modules for the Production Issue Investigator.

This package contains the Claude Agent SDK-based implementation:
- LeadAgent: The main orchestrator agent using SDK query()
- Subagent Definitions: AI agents for DataDog, Deployment, and Code analysis
- Prompts: Specialized prompts for each subagent

Legacy agents have been moved to legacy/agents/ directory.
"""

from agents.lead_agent import LeadAgent, run_interactive, LEAD_AGENT_PROMPT
from agents.subagent_definitions import (
    SUBAGENT_DEFINITIONS,
    DATADOG_INVESTIGATOR,
    DEPLOYMENT_ANALYZER,
    CODE_REVIEWER,
)
from agents.datadog_investigator_prompt import DATADOG_INVESTIGATOR_PROMPT
from agents.deployment_analyzer_prompt import DEPLOYMENT_ANALYZER_PROMPT
from agents.code_reviewer_prompt import CODE_REVIEWER_PROMPT

__all__ = [
    # Lead Agent
    "LeadAgent",
    "run_interactive",
    "LEAD_AGENT_PROMPT",
    # Subagent Definitions
    "SUBAGENT_DEFINITIONS",
    "DATADOG_INVESTIGATOR",
    "DEPLOYMENT_ANALYZER",
    "CODE_REVIEWER",
    # Prompts
    "DATADOG_INVESTIGATOR_PROMPT",
    "DEPLOYMENT_ANALYZER_PROMPT",
    "CODE_REVIEWER_PROMPT",
]
