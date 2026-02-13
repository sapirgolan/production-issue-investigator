"""Session management for investigation runs."""
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages investigation sessions with logging and file coordination."""

    def __init__(self, logs_dir: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            logs_dir: Base directory for logs (default: ./logs)
        """
        if logs_dir is None:
            logs_dir = Path("logs")
        self.logs_dir = logs_dir
        self.session_dir: Optional[Path] = None
        self.transcript_file: Optional[Path] = None

    def create_session(self) -> Path:
        """
        Create a new session directory.

        Returns:
            Path to session directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.logs_dir / f"session_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.session_dir / "files" / "datadog_findings").mkdir(parents=True, exist_ok=True)
        (self.session_dir / "files" / "deployment_findings").mkdir(parents=True, exist_ok=True)
        (self.session_dir / "files" / "code_findings").mkdir(parents=True, exist_ok=True)

        # Create transcript file
        self.transcript_file = self.session_dir / "transcript.txt"
        self.transcript_file.touch()

        logger.info(f"Created session: {self.session_dir}")
        return self.session_dir

    def write_transcript(self, text: str, end: str = "") -> None:
        """
        Append text to transcript.

        Args:
            text: Text to write
            end: Line ending (default: empty, use "\n" for newline)
        """
        if not self.transcript_file:
            raise RuntimeError("Session not created. Call create_session() first.")

        with open(self.transcript_file, "a", encoding="utf-8") as f:
            f.write(text + end)

    def get_findings_dir(self, subagent: str) -> Path:
        """
        Get findings directory for a subagent.

        Args:
            subagent: Subagent name (e.g., "datadog_findings")

        Returns:
            Path to findings directory
        """
        if not self.session_dir:
            raise RuntimeError("Session not created. Call create_session() first.")

        return self.session_dir / "files" / subagent
