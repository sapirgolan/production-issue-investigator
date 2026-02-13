"""
Tests for Session Manager functionality.

Tests for Phase 1 component: utils/session_manager.py

Covers:
- Session directory creation (logs/session_YYYYMMDD_HHMMSS/)
- Transcript writing (append-only)
- Tool call JSONL logging (via get_findings_dir)
- Session ID generation
- Subdirectory creation (files/datadog_findings/, etc.)
"""
import json
import os
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


class TestSessionManagerCreation(unittest.TestCase):
    """Tests for SessionManager initialization and session creation."""

    def test_session_manager_init_default_logs_dir(self):
        """Test that SessionManager uses default logs directory."""
        from utils.session_manager import SessionManager

        manager = SessionManager()
        self.assertEqual(manager.logs_dir, Path("logs"))

    def test_session_manager_init_custom_logs_dir(self):
        """Test that SessionManager accepts custom logs directory."""
        from utils.session_manager import SessionManager

        custom_dir = Path("/tmp/custom_logs")
        manager = SessionManager(logs_dir=custom_dir)
        self.assertEqual(manager.logs_dir, custom_dir)

    def test_create_session_creates_directory(self):
        """Test that create_session creates a session directory."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            self.assertTrue(session_dir.exists())
            self.assertTrue(session_dir.is_dir())

    def test_create_session_directory_name_format(self):
        """Test that session directory follows naming pattern session_YYYYMMDD_HHMMSS."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            # Verify name pattern
            dir_name = session_dir.name
            pattern = r"^session_\d{8}_\d{6}$"
            self.assertRegex(
                dir_name,
                pattern,
                f"Directory name '{dir_name}' does not match pattern 'session_YYYYMMDD_HHMMSS'"
            )

    def test_create_session_directory_timestamp_is_current(self):
        """Test that session directory timestamp is close to current time."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            before = datetime.now().strftime("%Y%m%d_%H%M")
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()
            after = datetime.now().strftime("%Y%m%d_%H%M")

            # Extract timestamp from directory name (session_YYYYMMDD_HHMMSS)
            dir_timestamp = session_dir.name[8:21]  # Skip "session_", get YYYYMMDD_HHMM

            # Timestamp should be between before and after (allow for minute boundary)
            self.assertTrue(
                before <= dir_timestamp <= after or dir_timestamp == before or dir_timestamp == after,
                f"Timestamp {dir_timestamp} not in range [{before}, {after}]"
            )


class TestSessionManagerSubdirectories(unittest.TestCase):
    """Tests for subdirectory creation in session directory."""

    def test_create_session_creates_files_directory(self):
        """Test that create_session creates files/ subdirectory."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            files_dir = session_dir / "files"
            self.assertTrue(files_dir.exists())
            self.assertTrue(files_dir.is_dir())

    def test_create_session_creates_datadog_findings_directory(self):
        """Test that create_session creates files/datadog_findings/ subdirectory."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            datadog_dir = session_dir / "files" / "datadog_findings"
            self.assertTrue(datadog_dir.exists())
            self.assertTrue(datadog_dir.is_dir())

    def test_create_session_creates_deployment_findings_directory(self):
        """Test that create_session creates files/deployment_findings/ subdirectory."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            deployment_dir = session_dir / "files" / "deployment_findings"
            self.assertTrue(deployment_dir.exists())
            self.assertTrue(deployment_dir.is_dir())

    def test_create_session_creates_code_findings_directory(self):
        """Test that create_session creates files/code_findings/ subdirectory."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            code_dir = session_dir / "files" / "code_findings"
            self.assertTrue(code_dir.exists())
            self.assertTrue(code_dir.is_dir())


class TestSessionManagerTranscript(unittest.TestCase):
    """Tests for transcript writing functionality."""

    def test_create_session_creates_transcript_file(self):
        """Test that create_session creates transcript.txt file."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            transcript_file = session_dir / "transcript.txt"
            self.assertTrue(transcript_file.exists())
            self.assertTrue(transcript_file.is_file())

    def test_write_transcript_appends_text(self):
        """Test that write_transcript appends text to transcript file."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            manager.write_transcript("First line")
            manager.write_transcript("Second line")

            with open(session_dir / "transcript.txt") as f:
                content = f.read()

            self.assertEqual(content, "First lineSecond line")

    def test_write_transcript_with_newline(self):
        """Test that write_transcript handles end parameter for newlines."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            manager.write_transcript("First line", end="\n")
            manager.write_transcript("Second line", end="\n")

            with open(session_dir / "transcript.txt") as f:
                content = f.read()

            self.assertEqual(content, "First line\nSecond line\n")

    def test_write_transcript_before_session_raises_error(self):
        """Test that write_transcript raises error if session not created."""
        from utils.session_manager import SessionManager

        manager = SessionManager()

        with self.assertRaises(RuntimeError) as context:
            manager.write_transcript("Test text")

        self.assertIn("Session not created", str(context.exception))

    def test_write_transcript_preserves_unicode(self):
        """Test that write_transcript preserves unicode characters."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            unicode_text = "Test with unicode: \u2713 \u2717 \u263A"
            manager.write_transcript(unicode_text)

            with open(session_dir / "transcript.txt", encoding="utf-8") as f:
                content = f.read()

            self.assertEqual(content, unicode_text)


class TestSessionManagerFindingsDir(unittest.TestCase):
    """Tests for get_findings_dir functionality."""

    def test_get_findings_dir_datadog(self):
        """Test that get_findings_dir returns correct path for datadog_findings."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            datadog_dir = manager.get_findings_dir("datadog_findings")
            expected = session_dir / "files" / "datadog_findings"

            self.assertEqual(datadog_dir, expected)
            self.assertTrue(datadog_dir.exists())

    def test_get_findings_dir_deployment(self):
        """Test that get_findings_dir returns correct path for deployment_findings."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            deployment_dir = manager.get_findings_dir("deployment_findings")
            expected = session_dir / "files" / "deployment_findings"

            self.assertEqual(deployment_dir, expected)
            self.assertTrue(deployment_dir.exists())

    def test_get_findings_dir_code(self):
        """Test that get_findings_dir returns correct path for code_findings."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))
            session_dir = manager.create_session()

            code_dir = manager.get_findings_dir("code_findings")
            expected = session_dir / "files" / "code_findings"

            self.assertEqual(code_dir, expected)
            self.assertTrue(code_dir.exists())

    def test_get_findings_dir_before_session_raises_error(self):
        """Test that get_findings_dir raises error if session not created."""
        from utils.session_manager import SessionManager

        manager = SessionManager()

        with self.assertRaises(RuntimeError) as context:
            manager.get_findings_dir("datadog_findings")

        self.assertIn("Session not created", str(context.exception))


class TestSessionManagerMultipleSessions(unittest.TestCase):
    """Tests for multiple session handling."""

    def test_create_multiple_sessions_creates_unique_directories(self):
        """Test that creating multiple sessions results in unique directories."""
        from utils.session_manager import SessionManager
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))

            # Create first session
            session1 = manager.create_session()

            # Small delay to ensure different timestamp
            time.sleep(1.1)

            # Create second session
            session2 = manager.create_session()

            self.assertNotEqual(session1, session2)
            self.assertTrue(session1.exists())
            self.assertTrue(session2.exists())

    def test_session_dir_is_updated_after_create(self):
        """Test that session_dir is updated after each create_session call."""
        from utils.session_manager import SessionManager
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))

            session1 = manager.create_session()
            self.assertEqual(manager.session_dir, session1)

            time.sleep(1.1)

            session2 = manager.create_session()
            self.assertEqual(manager.session_dir, session2)


class TestSessionManagerIntegration(unittest.TestCase):
    """Integration tests for SessionManager."""

    def test_full_workflow(self):
        """Test a complete session workflow: create, write, get findings."""
        from utils.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(logs_dir=Path(tmpdir))

            # Create session
            session_dir = manager.create_session()

            # Write to transcript
            manager.write_transcript("User: Search for NullPointerException\n\n")
            manager.write_transcript("[LEAD] -> Task (datadog-investigator)\n")
            manager.write_transcript("[DATADOG-INVESTIGATOR] -> search_logs\n")
            manager.write_transcript("[DATADOG-INVESTIGATOR] <- search_logs (245ms)\n")

            # Get findings directory and write a file
            findings_dir = manager.get_findings_dir("datadog_findings")
            findings_file = findings_dir / "summary.json"
            findings_data = {
                "total_logs": 150,
                "unique_services": ["card-invitation-service"],
                "search_time_ms": 245
            }
            with open(findings_file, "w") as f:
                json.dump(findings_data, f)

            # Verify everything
            self.assertTrue(session_dir.exists())
            self.assertTrue((session_dir / "transcript.txt").exists())
            self.assertTrue(findings_file.exists())

            # Verify transcript content
            with open(session_dir / "transcript.txt") as f:
                transcript = f.read()
            self.assertIn("NullPointerException", transcript)
            self.assertIn("LEAD", transcript)
            self.assertIn("DATADOG-INVESTIGATOR", transcript)

            # Verify findings file
            with open(findings_file) as f:
                loaded_data = json.load(f)
            self.assertEqual(loaded_data["total_logs"], 150)


if __name__ == "__main__":
    unittest.main()
