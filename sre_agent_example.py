"""
SRE/Support Agent Example using Claude Agent SDK

This agent demonstrates common SRE tasks:
- Reading log files and system configurations
- Running diagnostic commands
- Analyzing system state
- Investigating production issues
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage


async def investigate_issue(issue_description: str):
    """
    Main SRE agent that investigates production issues.

    Args:
        issue_description: Description of the issue to investigate
    """
    # Load environment variables
    load_dotenv()

    # Verify API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment")
        print("Please set your API key in .env file")
        return

    print("="*70)
    print("🔍 Production Issue Investigator - SRE Agent")
    print("="*70)
    print(f"\n📋 Issue Description: {issue_description}\n")

    # Configure the agent with SRE-focused tools
    options = ClaudeAgentOptions(
        # Allow tools commonly needed for SRE work
        allowed_tools=[
            "Read",      # Read log files, configs, code
            "Grep",      # Search through logs and files
            "Glob",      # Find files by pattern
            "Bash",      # Run diagnostic commands
            "Write",     # Create analysis reports
        ],
        # Use acceptEdits mode to allow file operations without prompting
        # (use "default" if you want to approve each action)
        permission_mode="acceptEdits",
        # Set working directory
        cwd=str(Path.cwd()),
        # Use a system prompt tailored for SRE work
        system_prompt="""You are an expert SRE/Support engineer investigating production issues.

Your responsibilities:
1. Analyze the issue description thoroughly
2. Gather relevant data (logs, configs, system state)
3. Run diagnostic commands when needed
4. Identify root causes and patterns
5. Provide clear, actionable findings

When investigating:
- Start with the most likely causes based on the symptoms
- Check logs for errors, warnings, and patterns
- Review recent changes (deployments, config updates)
- Verify system resources and health
- Document your findings clearly

Be methodical, thorough, and clear in your analysis."""
    )

    # Run the investigation
    print("🤖 Agent is investigating...\n")

    try:
        async for message in query(
            prompt=issue_description,
            options=options
        ):
            # Print assistant responses in real-time
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"💭 {block.text}")
                        print()

            # Print final results
            elif isinstance(message, ResultMessage):
                print("="*70)
                print("📊 Investigation Complete")
                print("="*70)

                if message.result:
                    print(f"\n{message.result}\n")

                # Print usage statistics
                print(f"⏱️  Duration: {message.duration_ms / 1000:.2f}s")
                print(f"🔄 Turns: {message.num_turns}")
                if message.total_cost_usd:
                    print(f"💰 Cost: ${message.total_cost_usd:.4f}")
                print()

    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        raise


async def interactive_mode():
    """
    Run the agent in interactive mode where you can ask follow-up questions.
    """
    print("="*70)
    print("🔍 Production Issue Investigator - Interactive Mode")
    print("="*70)
    print("\nType 'exit' or 'quit' to end the session\n")

    while True:
        issue = input("🔍 Describe the issue (or 'exit'): ").strip()

        if issue.lower() in ['exit', 'quit', '']:
            print("\n👋 Goodbye!")
            break

        await investigate_issue(issue)
        print()


# Example usage scenarios
async def example_scenarios():
    """
    Run example SRE investigation scenarios.
    """
    scenarios = [
        {
            "name": "High CPU Usage",
            "description": """
            Our production service is experiencing high CPU usage (90%+) since 2 hours ago.

            Please investigate:
            1. Check system resource usage
            2. Look for any unusual processes
            3. Review recent logs for errors or patterns
            4. Check if there were any recent deployments

            Project directory: /Users/sapirgolan/workspace/production-issue-investigator
            """
        },
        {
            "name": "Log Analysis",
            "description": """
            Analyze the log files in the ./logs directory and identify:
            1. Any error patterns
            2. Warning trends
            3. Potential issues
            4. Recommendations for improvement
            """
        },
        {
            "name": "Configuration Review",
            "description": """
            Review the current project configuration and verify:
            1. All required environment variables are documented
            2. Configuration files are valid
            3. Dependencies are up to date
            4. Any potential security issues
            """
        }
    ]

    print("="*70)
    print("📚 Available Example Scenarios")
    print("="*70)
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")

    choice = input("\nSelect a scenario (1-3) or press Enter to skip: ").strip()

    if choice and choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        scenario = scenarios[int(choice) - 1]
        print(f"\n🎯 Running scenario: {scenario['name']}\n")
        await investigate_issue(scenario['description'])


async def main():
    """
    Main entry point with multiple modes.
    """
    print("="*70)
    print("🚀 Claude Agent SDK - SRE Agent Example")
    print("="*70)
    print("\nModes:")
    print("1. Run example scenarios")
    print("2. Interactive mode")
    print("3. Single investigation")
    print()

    mode = input("Select mode (1-3): ").strip()

    if mode == "1":
        await example_scenarios()
    elif mode == "2":
        await interactive_mode()
    elif mode == "3":
        issue = input("Describe the issue: ").strip()
        if issue:
            await investigate_issue(issue)
    else:
        print("Invalid mode. Exiting.")


if __name__ == "__main__":
    # Run the agent
    asyncio.run(main())
