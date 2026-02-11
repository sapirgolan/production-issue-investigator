"""
Logging infrastructure for the Production Issue Investigator.

Provides configured loggers with console and file output.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
DEFAULT_LOG_FILE = "logs/agent.log"
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# Track if logging has been configured
_logging_configured = False


def _ensure_log_directory(log_path: Path) -> None:
    """Ensure the log directory exists.

    Args:
        log_path: Path to the log file.
    """
    log_dir = log_path.parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)


def _get_log_level(level_name: str) -> int:
    """Convert log level name to logging constant.

    Args:
        level_name: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Logging level constant.
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name.upper(), logging.INFO)


def configure_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """Configure the logging infrastructure.

    Sets up logging with both console and rotating file handlers.
    This should be called once at application startup.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Defaults to LOG_LEVEL env var or INFO.
        log_file: Path to log file. Defaults to logs/agent.log.
        log_format: Log message format. Uses default format if not specified.
    """
    global _logging_configured

    # Determine configuration values
    level_str = log_level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
    level = _get_log_level(level_str)

    # Determine log file path (relative to project root)
    if log_file:
        log_path = Path(log_file)
    else:
        project_root = Path(__file__).parent.parent
        log_path = project_root / DEFAULT_LOG_FILE

    # Ensure log directory exists
    _ensure_log_directory(log_path)

    # Use provided format or default
    fmt = log_format or DEFAULT_LOG_FORMAT

    # Create formatter
    formatter = logging.Formatter(fmt)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _logging_configured = True

    # Log that logging is configured (at debug level to avoid noise)
    root_logger.debug(f"Logging configured: level={level_str}, file={log_path}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    If logging hasn't been configured yet, this will configure it
    with default settings.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logger instance.
    """
    global _logging_configured

    # Auto-configure if not already done
    if not _logging_configured:
        configure_logging()

    return logging.getLogger(name)


def reset_logging() -> None:
    """Reset the logging configuration.

    Removes all handlers from the root logger and resets the
    configuration flag. Useful for testing.
    """
    global _logging_configured

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

    _logging_configured = False
