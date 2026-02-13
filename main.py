"""Main entry point for Production Issue Investigator (SDK version).

This is the interactive entry point that:
- Loads configuration from .env
- Validates required environment variables
- Configures logging
- Runs the Lead Agent in interactive mode
"""
import sys
import asyncio
from agents.lead_agent import run_interactive
from utils.logger import get_logger, configure_logging
from utils.config import get_config, ConfigurationError

logger = get_logger(__name__)


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Load and validate configuration
    try:
        config = get_config()
    except ConfigurationError as e:
        print(f"\nConfiguration Error: {e}")
        print("\nEnsure these variables are set in .env:")
        print("  - ANTHROPIC_API_KEY")
        print("  - DATADOG_API_KEY")
        print("  - DATADOG_APP_KEY")
        print("  - GITHUB_TOKEN")
        return 1

    # Configure logging
    configure_logging(log_level=config.log_level)

    # Run interactive mode
    try:
        await run_interactive()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
