"""
Main entry point for the Production Issue Investigator agent.

This is the interactive chat entry point that:
- Loads configuration from .env
- Initializes the MainAgent
- Runs the interactive investigation loop
"""
import sys
from pathlib import Path

from utils.config import get_config, ConfigurationError
from utils.logger import configure_logging, get_logger
from agents.main_agent import MainAgent


def main() -> int:
    """Main entry point for the agent.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # First, try to load and validate configuration
    try:
        config = get_config()
    except ConfigurationError as e:
        print(f"\nConfiguration Error: {e}")
        print("\nPlease ensure your .env file is properly configured with:")
        print("  - ANTHROPIC_API_KEY")
        print("  - DATADOG_API_KEY")
        print("  - DATADOG_APP_KEY")
        print("  - GITHUB_TOKEN")
        print("\nSee .env.example for a template.")
        return 1

    # Configure logging based on config
    configure_logging(log_level=config.log_level)
    logger = get_logger(__name__)

    logger.info("Starting Production Issue Investigator")
    logger.debug(f"Config loaded: log_level={config.log_level}, timezone={config.timezone}")

    # Verify we're in the right directory
    project_root = Path(__file__).parent
    logger.debug(f"Project root: {project_root}")

    # Print startup banner
    print("\n" + "=" * 70)
    print("  Production Issue Investigator")
    print("  Phase 2: DataDog Sub-Agent + Basic Orchestration")
    print("=" * 70)

    # Show configuration status
    print("\nConfiguration Status:")
    print(f"  [OK] ANTHROPIC_API_KEY loaded")
    print(f"  [OK] DATADOG_API_KEY loaded")
    print(f"  [OK] DATADOG_APP_KEY loaded")
    print(f"  [OK] GITHUB_TOKEN loaded")
    print(f"  Log Level: {config.log_level}")
    print(f"  Timezone: {config.timezone}")
    print(f"  DataDog Site: {config.datadog_site}")

    try:
        # Initialize and run the main agent
        agent = MainAgent(config=config)
        agent.run_interactive()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nUnexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
