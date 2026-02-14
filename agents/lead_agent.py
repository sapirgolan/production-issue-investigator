"""
Lead Agent for Production Issue Investigation.

This agent orchestrates the investigation workflow by:
1. Understanding user input (Mode 1 vs Mode 2)
2. Spawning DataDog Investigator to search logs
3. Spawning Deployment Analyzer to find deployments
4. Spawning Code Reviewer to analyze changes
5. Synthesizing findings into comprehensive report
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
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
# Import MCP server instances (SDK-wrapped)
from mcp_servers.datadog_server import DATADOG_MCP_SERVER
from mcp_servers.github_server import GITHUB_MCP_SERVER

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

- Always invoke subagents in order: DataDog -> Deployment -> Code
- Read the files/ directory between subagents to check results
- If a subagent fails, try once more, then continue with partial data
- Be specific in root cause analysis - cite exact files and lines
- Provide actionable recommendations, not generic advice
- If uncertain, state confidence level and ask for more data
"""


class LeadAgent:
    """Main orchestrator agent using Claude Agent SDK."""

    def __init__(self, config=None):
        """Initialize the lead agent.

        Args:
            config: Optional configuration object. If None, loads from environment.
        """
        if config is None:
            config = get_config()
        self.config = config
        self.session_manager: Optional[SessionManager] = None
        self.tracker: Optional[SubagentTracker] = None

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

        # Setup MCP servers (SDK-wrapped instances)
        mcp_servers = {
            "datadog": DATADOG_MCP_SERVER,
            "github": GITHUB_MCP_SERVER,
        }

        # Define subagents
        agents = {
            "datadog-investigator": DATADOG_INVESTIGATOR,
            "deployment-analyzer": DEPLOYMENT_ANALYZER,
            "code-reviewer": CODE_REVIEWER,
        }

        # Get model with fallback to opus (default for lead agent)
        model = self.config.lead_agent_model
        if not isinstance(model, str):
            model = "opus"

        # Agent options
        options = ClaudeAgentOptions(
            permission_mode=self.config.bypass_permissions,
            system_prompt=LEAD_AGENT_PROMPT,
            allowed_tools=["Task", "Read", "Glob", "Write"],
            agents=agents,
            hooks=hooks,
            mcp_servers=mcp_servers,
            model=model,
        )

        report = ""

        try:
            async with ClaudeSDKClient(options) as client:
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
            print(f"\nSession logs: {session_dir}")
            print(f"Transcript: {transcript_file}")
            print(f"Report: {report_file}")

        return report

    def _generate_error_report(self, user_input: str, error: str) -> str:
        """Generate error report when investigation fails.

        Args:
            user_input: The original user input
            error: The error message

        Returns:
            Markdown-formatted error report
        """
        return f"""# Investigation Error

**User Input:** {user_input}
**Timestamp:** {datetime.now(timezone.utc).isoformat()}

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
            user_input = input("\nDescribe the issue: ").strip()

            if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break

            # Run investigation
            report = await agent.investigate(user_input)

            # Display report
            print("\n" + "=" * 70)
            print("INVESTIGATION REPORT")
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
    import asyncio
    asyncio.run(run_interactive())
