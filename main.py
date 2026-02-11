"""
Main entry point for the Production Issue Investigator agent.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def main():
    """Main entry point for the agent."""
    # Load environment variables
    load_dotenv()

    # Verify we're in the right directory
    project_root = Path(__file__).parent
    print(f"Project root: {project_root}")

    # Verify API key is loaded (without printing it)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print("✓ ANTHROPIC_API_KEY loaded")
    else:
        print("⚠ ANTHROPIC_API_KEY not found in environment")

    # Print hello world
    print("\n" + "="*50)
    print("Hello World from Production Issue Investigator!")
    print("="*50 + "\n")

    print("Agent components:")
    print("  - Main orchestrator agent")
    print("  - DataDog retriever sub-agent")
    print("  - Deployment checker sub-agent")
    print("  - Code checker sub-agent")
    print("\nReady to investigate production issues! 🚀")

    return 0


if __name__ == "__main__":
    sys.exit(main())
