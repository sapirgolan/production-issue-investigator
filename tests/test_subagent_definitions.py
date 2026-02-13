"""
Tests for Subagent Definitions.

Tests that the subagent definitions are properly configured with
correct prompts, tools, and models.
"""

import pytest
from claude_agent_sdk import AgentDefinition

from agents.subagent_definitions import (
    SUBAGENT_DEFINITIONS,
    DATADOG_INVESTIGATOR,
    DEPLOYMENT_ANALYZER,
    CODE_REVIEWER,
)
from agents.datadog_investigator_prompt import DATADOG_INVESTIGATOR_PROMPT
from agents.deployment_analyzer_prompt import DEPLOYMENT_ANALYZER_PROMPT
from agents.code_reviewer_prompt import CODE_REVIEWER_PROMPT


class TestSubagentDefinitionsModule:
    """Test that the module exports correctly."""

    def test_subagent_definitions_dict_has_all_agents(self):
        """SUBAGENT_DEFINITIONS should contain all three agents."""
        assert "datadog-investigator" in SUBAGENT_DEFINITIONS
        assert "deployment-analyzer" in SUBAGENT_DEFINITIONS
        assert "code-reviewer" in SUBAGENT_DEFINITIONS
        assert len(SUBAGENT_DEFINITIONS) == 3

    def test_all_agents_are_agent_definitions(self):
        """Each agent in SUBAGENT_DEFINITIONS should be an AgentDefinition."""
        for name, agent in SUBAGENT_DEFINITIONS.items():
            assert isinstance(agent, AgentDefinition), f"{name} should be an AgentDefinition"

    def test_individual_exports_match_dict(self):
        """Individual exports should match the dict entries."""
        assert DATADOG_INVESTIGATOR is SUBAGENT_DEFINITIONS["datadog-investigator"]
        assert DEPLOYMENT_ANALYZER is SUBAGENT_DEFINITIONS["deployment-analyzer"]
        assert CODE_REVIEWER is SUBAGENT_DEFINITIONS["code-reviewer"]


class TestDataDogInvestigator:
    """Tests for the DataDog Investigator subagent definition."""

    def test_is_agent_definition(self):
        """Should be an AgentDefinition instance."""
        assert isinstance(DATADOG_INVESTIGATOR, AgentDefinition)

    def test_has_correct_model(self):
        """Should use haiku model for cost-effectiveness."""
        assert DATADOG_INVESTIGATOR.model == "haiku"

    def test_has_correct_prompt(self):
        """Should use the DataDog investigator prompt."""
        assert DATADOG_INVESTIGATOR.prompt == DATADOG_INVESTIGATOR_PROMPT

    def test_has_description(self):
        """Should have a description."""
        assert DATADOG_INVESTIGATOR.description
        assert "DataDog" in DATADOG_INVESTIGATOR.description or "datadog" in DATADOG_INVESTIGATOR.description.lower()

    def test_has_datadog_mcp_tools(self):
        """Should have DataDog MCP tools."""
        tools = DATADOG_INVESTIGATOR.tools
        assert "mcp__datadog__search_logs" in tools
        assert "mcp__datadog__get_logs_by_efilogid" in tools
        assert "mcp__datadog__parse_stack_trace" in tools

    def test_has_file_operation_tools(self):
        """Should have file operation tools."""
        tools = DATADOG_INVESTIGATOR.tools
        assert "Write" in tools
        assert "Read" in tools

    def test_prompt_mentions_key_concepts(self):
        """Prompt should mention key concepts like efilogid and dd.version."""
        prompt = DATADOG_INVESTIGATOR.prompt
        assert "efilogid" in prompt
        assert "dd.version" in prompt


class TestDeploymentAnalyzer:
    """Tests for the Deployment Analyzer subagent definition."""

    def test_is_agent_definition(self):
        """Should be an AgentDefinition instance."""
        assert isinstance(DEPLOYMENT_ANALYZER, AgentDefinition)

    def test_has_correct_model(self):
        """Should use haiku model for cost-effectiveness."""
        assert DEPLOYMENT_ANALYZER.model == "haiku"

    def test_has_correct_prompt(self):
        """Should use the Deployment Analyzer prompt."""
        assert DEPLOYMENT_ANALYZER.prompt == DEPLOYMENT_ANALYZER_PROMPT

    def test_has_description(self):
        """Should have a description."""
        assert DEPLOYMENT_ANALYZER.description
        assert "deployment" in DEPLOYMENT_ANALYZER.description.lower()

    def test_has_github_mcp_tools(self):
        """Should have GitHub MCP tools."""
        tools = DEPLOYMENT_ANALYZER.tools
        assert "mcp__github__search_commits" in tools
        assert "mcp__github__get_file_content" in tools
        assert "mcp__github__get_pr_files" in tools

    def test_has_file_and_bash_tools(self):
        """Should have file operation and Bash tools."""
        tools = DEPLOYMENT_ANALYZER.tools
        assert "Write" in tools
        assert "Read" in tools
        assert "Bash" in tools

    def test_prompt_mentions_kubernetes(self):
        """Prompt should mention kubernetes repository."""
        prompt = DEPLOYMENT_ANALYZER.prompt
        assert "kubernetes" in prompt.lower()


class TestCodeReviewer:
    """Tests for the Code Reviewer subagent definition."""

    def test_is_agent_definition(self):
        """Should be an AgentDefinition instance."""
        assert isinstance(CODE_REVIEWER, AgentDefinition)

    def test_has_correct_model(self):
        """Should use sonnet model for better code analysis."""
        assert CODE_REVIEWER.model == "sonnet"

    def test_has_correct_prompt(self):
        """Should use the Code Reviewer prompt."""
        assert CODE_REVIEWER.prompt == CODE_REVIEWER_PROMPT

    def test_has_description(self):
        """Should have a description."""
        assert CODE_REVIEWER.description
        assert "code" in CODE_REVIEWER.description.lower()

    def test_has_github_mcp_tools(self):
        """Should have GitHub MCP tools for code comparison."""
        tools = CODE_REVIEWER.tools
        assert "mcp__github__get_file_content" in tools
        assert "mcp__github__compare_commits" in tools

    def test_has_file_operation_tools(self):
        """Should have file operation tools."""
        tools = CODE_REVIEWER.tools
        assert "Write" in tools
        assert "Read" in tools

    def test_does_not_have_bash_tool(self):
        """Code reviewer should not need Bash tool."""
        assert "Bash" not in CODE_REVIEWER.tools

    def test_prompt_mentions_null_safety(self):
        """Prompt should mention null safety analysis."""
        prompt = CODE_REVIEWER.prompt
        assert "null" in prompt.lower()

    def test_prompt_mentions_severity_levels(self):
        """Prompt should define severity levels."""
        prompt = CODE_REVIEWER.prompt
        assert "HIGH" in prompt
        assert "MEDIUM" in prompt
        assert "LOW" in prompt


class TestModelConfiguration:
    """Tests for model configuration across agents."""

    def test_datadog_uses_haiku(self):
        """DataDog investigator should use haiku (cost-effective for search)."""
        assert DATADOG_INVESTIGATOR.model == "haiku"

    def test_deployment_uses_haiku(self):
        """Deployment analyzer should use haiku (cost-effective for search)."""
        assert DEPLOYMENT_ANALYZER.model == "haiku"

    def test_code_reviewer_uses_sonnet(self):
        """Code reviewer should use sonnet (better code analysis)."""
        assert CODE_REVIEWER.model == "sonnet"


class TestToolConfiguration:
    """Tests for tool configuration across agents."""

    def test_datadog_has_datadog_tools(self):
        """DataDog investigator should only use DataDog MCP tools."""
        tools = DATADOG_INVESTIGATOR.tools
        mcp_tools = [t for t in tools if t.startswith("mcp__")]
        for tool in mcp_tools:
            assert tool.startswith("mcp__datadog__")

    def test_deployment_has_github_tools(self):
        """Deployment analyzer should use GitHub MCP tools."""
        tools = DEPLOYMENT_ANALYZER.tools
        mcp_tools = [t for t in tools if t.startswith("mcp__")]
        for tool in mcp_tools:
            assert tool.startswith("mcp__github__")

    def test_code_reviewer_has_github_tools(self):
        """Code reviewer should use GitHub MCP tools."""
        tools = CODE_REVIEWER.tools
        mcp_tools = [t for t in tools if t.startswith("mcp__")]
        for tool in mcp_tools:
            assert tool.startswith("mcp__github__")

    def test_all_agents_have_write_tool(self):
        """All agents should have Write tool to save findings."""
        for agent in SUBAGENT_DEFINITIONS.values():
            assert "Write" in agent.tools

    def test_all_agents_have_read_tool(self):
        """All agents should have Read tool to read previous findings."""
        for agent in SUBAGENT_DEFINITIONS.values():
            assert "Read" in agent.tools
