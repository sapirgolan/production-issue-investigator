"""
Tests for Hook System functionality.

Tests for Phase 1 component: utils/hooks.py

Covers:
- SubagentTracker initialization
- PreToolUse hook logging (tool_name, input, parent_tool_use_id)
- PostToolUse hook logging (success, duration, output_size)
- Parent-child tool call relationship tracking
- JSONL file writing
- Transcript file writing
"""
import asyncio
import json
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestSubagentTrackerInitialization(unittest.TestCase):
    """Tests for SubagentTracker initialization."""

    def test_tracker_init_creates_log_file(self):
        """Test that SubagentTracker creates log file on initialization."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            self.assertTrue(log_file.exists())

    def test_tracker_init_creates_parent_directories(self):
        """Test that SubagentTracker creates parent directories for log file."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "nested" / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            self.assertTrue(log_file.parent.exists())
            self.assertTrue(log_file.exists())

    def test_tracker_init_stores_file_paths(self):
        """Test that SubagentTracker stores log and transcript file paths."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            self.assertEqual(tracker.log_file, log_file)
            self.assertEqual(tracker.transcript_file, transcript_file)

    def test_tracker_init_empty_tool_starts(self):
        """Test that SubagentTracker initializes with empty tool_starts dict."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            self.assertEqual(tracker.tool_starts, {})


class TestPreToolUseHook(unittest.TestCase):
    """Tests for pre_tool_use_hook functionality."""

    def test_pre_tool_use_hook_logs_tool_call_start(self):
        """Test that pre_tool_use_hook logs tool call start event to JSONL."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            # Run the async hook
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "test error"},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_123",
                context={}
            ))

            # Read and verify JSONL entry
            with open(log_file) as f:
                entry = json.loads(f.readline())

            self.assertEqual(entry["event"], "tool_call_start")
            self.assertEqual(entry["tool_name"], "mcp__datadog__search_logs")
            self.assertEqual(entry["tool_use_id"], "tool_123")
            self.assertIn("timestamp", entry)

    def test_pre_tool_use_hook_lead_agent_id(self):
        """Test that pre_tool_use_hook assigns LEAD agent ID when no parent."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {"task": "search logs"},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_456",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            self.assertEqual(entry["agent_id"], "LEAD")

    def test_pre_tool_use_hook_subagent_id_with_parent(self):
        """Test that pre_tool_use_hook assigns SUBAGENT ID when parent exists."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "test"},
                    "parent_tool_use_id": "parent_task_abc123def"
                },
                tool_use_id="tool_789",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            # Agent ID should include truncated parent ID
            self.assertTrue(entry["agent_id"].startswith("SUBAGENT-"))
            self.assertIn("parent_ab", entry["agent_id"])

    def test_pre_tool_use_hook_logs_parent_tool_use_id(self):
        """Test that pre_tool_use_hook logs parent_tool_use_id in JSONL."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "test"},
                    "parent_tool_use_id": "parent_xyz123"
                },
                tool_use_id="tool_101",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            self.assertEqual(entry["parent_tool_use_id"], "parent_xyz123")

    def test_pre_tool_use_hook_logs_input(self):
        """Test that pre_tool_use_hook logs tool input parameters."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "NullPointerException", "from_time": "now-4h"},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_102",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            self.assertIn("input", entry)
            self.assertIn("query", entry["input"])
            self.assertEqual(entry["input"]["query"], "NullPointerException")

    def test_pre_tool_use_hook_writes_to_transcript(self):
        """Test that pre_tool_use_hook writes to transcript file."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "test"},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_103",
                context={}
            ))

            with open(transcript_file) as f:
                content = f.read()

            self.assertIn("LEAD", content)
            self.assertIn("mcp__datadog__search_logs", content)

    def test_pre_tool_use_hook_stores_start_time(self):
        """Test that pre_tool_use_hook stores start time for duration calculation."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            before = time.time()
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_104",
                context={}
            ))
            after = time.time()

            self.assertIn("tool_104", tracker.tool_starts)
            self.assertIn("start_time", tracker.tool_starts["tool_104"])
            self.assertGreaterEqual(tracker.tool_starts["tool_104"]["start_time"], before)
            self.assertLessEqual(tracker.tool_starts["tool_104"]["start_time"], after)

    def test_pre_tool_use_hook_truncates_large_input(self):
        """Test that pre_tool_use_hook truncates large input values."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            large_input = "x" * 1000
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {"large_field": large_input},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_105",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            # Input should be truncated
            self.assertIn("truncated", entry["input"]["large_field"])
            self.assertLess(len(entry["input"]["large_field"]), len(large_input))


class TestPostToolUseHook(unittest.TestCase):
    """Tests for post_tool_use_hook functionality."""

    def test_post_tool_use_hook_logs_tool_call_complete(self):
        """Test that post_tool_use_hook logs tool call complete event."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            # First call pre-hook to register the tool
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "test"},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_200",
                context={}
            ))

            # Then call post-hook
            asyncio.run(tracker.post_tool_use_hook(
                input_data={
                    "tool_response": {"content": [{"type": "text", "text": "Found 10 logs"}]}
                },
                tool_use_id="tool_200",
                context={}
            ))

            # Read JSONL and find complete event
            with open(log_file) as f:
                lines = f.readlines()
            complete_entry = json.loads(lines[-1])

            self.assertEqual(complete_entry["event"], "tool_call_complete")
            self.assertEqual(complete_entry["tool_use_id"], "tool_200")

    def test_post_tool_use_hook_logs_success(self):
        """Test that post_tool_use_hook logs success status correctly."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={"tool_name": "Task", "tool_input": {}, "parent_tool_use_id": None},
                tool_use_id="tool_201",
                context={}
            ))

            asyncio.run(tracker.post_tool_use_hook(
                input_data={
                    "tool_response": {"content": [{"type": "text", "text": "Success"}]}
                },
                tool_use_id="tool_201",
                context={}
            ))

            with open(log_file) as f:
                lines = f.readlines()
            complete_entry = json.loads(lines[-1])

            self.assertTrue(complete_entry["success"])

    def test_post_tool_use_hook_logs_failure(self):
        """Test that post_tool_use_hook logs failure status correctly."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={"tool_name": "Task", "tool_input": {}, "parent_tool_use_id": None},
                tool_use_id="tool_202",
                context={}
            ))

            asyncio.run(tracker.post_tool_use_hook(
                input_data={
                    "tool_response": {
                        "content": [{"type": "text", "text": "Error: rate limited"}],
                        "is_error": True
                    }
                },
                tool_use_id="tool_202",
                context={}
            ))

            with open(log_file) as f:
                lines = f.readlines()
            complete_entry = json.loads(lines[-1])

            self.assertFalse(complete_entry["success"])
            self.assertIn("error", complete_entry)

    def test_post_tool_use_hook_logs_duration(self):
        """Test that post_tool_use_hook logs duration in milliseconds."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={"tool_name": "Task", "tool_input": {}, "parent_tool_use_id": None},
                tool_use_id="tool_203",
                context={}
            ))

            # Small delay to have measurable duration
            time.sleep(0.1)

            asyncio.run(tracker.post_tool_use_hook(
                input_data={"tool_response": {"content": []}},
                tool_use_id="tool_203",
                context={}
            ))

            with open(log_file) as f:
                lines = f.readlines()
            complete_entry = json.loads(lines[-1])

            self.assertIn("duration_ms", complete_entry)
            self.assertGreaterEqual(complete_entry["duration_ms"], 100)

    def test_post_tool_use_hook_logs_output_size(self):
        """Test that post_tool_use_hook logs output size."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={"tool_name": "Task", "tool_input": {}, "parent_tool_use_id": None},
                tool_use_id="tool_204",
                context={}
            ))

            asyncio.run(tracker.post_tool_use_hook(
                input_data={
                    "tool_response": {"content": [{"type": "text", "text": "Response data here"}]}
                },
                tool_use_id="tool_204",
                context={}
            ))

            with open(log_file) as f:
                lines = f.readlines()
            complete_entry = json.loads(lines[-1])

            self.assertIn("output_size", complete_entry)
            self.assertGreater(complete_entry["output_size"], 0)

    def test_post_tool_use_hook_writes_to_transcript(self):
        """Test that post_tool_use_hook writes completion to transcript."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {},
                    "parent_tool_use_id": None
                },
                tool_use_id="tool_205",
                context={}
            ))

            asyncio.run(tracker.post_tool_use_hook(
                input_data={"tool_response": {"content": []}},
                tool_use_id="tool_205",
                context={}
            ))

            with open(transcript_file) as f:
                content = f.read()

            # Should contain success marker and tool name and duration
            self.assertIn("mcp__datadog__search_logs", content)
            self.assertIn("ms", content)


class TestParentChildTracking(unittest.TestCase):
    """Tests for parent-child tool call relationship tracking."""

    def test_parent_child_relationship_logged(self):
        """Test that parent-child relationships are properly tracked."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            # Lead agent calls Task
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {"subagent": "datadog-investigator"},
                    "parent_tool_use_id": None
                },
                tool_use_id="task_parent_123",
                context={}
            ))

            # Subagent calls search_logs with parent reference
            asyncio.run(tracker.pre_tool_use_hook(
                input_data={
                    "tool_name": "mcp__datadog__search_logs",
                    "tool_input": {"query": "error"},
                    "parent_tool_use_id": "task_parent_123"
                },
                tool_use_id="search_child_456",
                context={}
            ))

            with open(log_file) as f:
                lines = f.readlines()

            # First entry (Task) should have no parent
            task_entry = json.loads(lines[0])
            self.assertIsNone(task_entry["parent_tool_use_id"])
            self.assertEqual(task_entry["agent_id"], "LEAD")

            # Second entry (search_logs) should reference Task as parent
            search_entry = json.loads(lines[1])
            self.assertEqual(search_entry["parent_tool_use_id"], "task_parent_123")
            self.assertTrue(search_entry["agent_id"].startswith("SUBAGENT-"))


class TestCreateHookMatchers(unittest.TestCase):
    """Tests for create_hook_matchers function."""

    def test_create_hook_matchers_returns_dict(self):
        """Test that create_hook_matchers returns a dictionary."""
        from utils.hooks import SubagentTracker, create_hook_matchers

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)
            matchers = create_hook_matchers(tracker)

            self.assertIsInstance(matchers, dict)

    def test_create_hook_matchers_has_pre_tool_use(self):
        """Test that create_hook_matchers includes PreToolUse matcher."""
        from utils.hooks import SubagentTracker, create_hook_matchers

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)
            matchers = create_hook_matchers(tracker)

            self.assertIn("PreToolUse", matchers)
            self.assertIsInstance(matchers["PreToolUse"], list)
            self.assertGreater(len(matchers["PreToolUse"]), 0)

    def test_create_hook_matchers_has_post_tool_use(self):
        """Test that create_hook_matchers includes PostToolUse matcher."""
        from utils.hooks import SubagentTracker, create_hook_matchers

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)
            matchers = create_hook_matchers(tracker)

            self.assertIn("PostToolUse", matchers)
            self.assertIsInstance(matchers["PostToolUse"], list)
            self.assertGreater(len(matchers["PostToolUse"]), 0)


class TestSubagentTrackerClose(unittest.TestCase):
    """Tests for SubagentTracker.close() method."""

    def test_close_completes_without_error(self):
        """Test that close() method completes without raising errors."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            # Should not raise
            tracker.close()


class TestTimestampFormat(unittest.TestCase):
    """Tests for timestamp format in JSONL entries."""

    def test_timestamp_format_iso8601_utc(self):
        """Test that timestamps are in ISO 8601 UTC format."""
        from utils.hooks import SubagentTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "tool_calls.jsonl"
            transcript_file = Path(tmpdir) / "transcript.txt"
            transcript_file.touch()

            tracker = SubagentTracker(log_file, transcript_file)

            asyncio.run(tracker.pre_tool_use_hook(
                input_data={"tool_name": "Task", "tool_input": {}, "parent_tool_use_id": None},
                tool_use_id="tool_300",
                context={}
            ))

            with open(log_file) as f:
                entry = json.loads(f.readline())

            timestamp = entry["timestamp"]
            # Should end with Z for UTC
            self.assertTrue(timestamp.endswith("Z"))
            # Should be valid ISO format (YYYY-MM-DDTHH:MM:SS.ffffffZ or YYYY-MM-DDTHH:MM:SSZ)
            # Parse to validate
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                self.fail(f"Timestamp '{timestamp}' is not valid ISO 8601 format")


if __name__ == "__main__":
    unittest.main()
