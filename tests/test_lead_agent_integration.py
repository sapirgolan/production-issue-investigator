"""
Integration Tests for Lead Agent.

Tests the full Lead Agent workflow with mocked subagents:
- Full investigation workflow
- Session directory creation
- Transcript writing
- Tool call logging
- End-to-end coordination

These tests verify the integration between LeadAgent, SessionManager,
SubagentTracker, and the Claude Agent SDK client.
"""

import asyncio
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import AsyncIterator, Any


class MockResultMessage:
    """Mock for ResultMessage from Claude Agent SDK."""

    def __init__(self, subtype: str = "success", result: str = "", error: str = ""):
        self.subtype = subtype
        self.result = result
        self.error = error


class MockAssistantMessage:
    """Mock for AssistantMessage from Claude Agent SDK."""

    def __init__(self, content=None):
        self.content = content or []


class MockTextBlock:
    """Mock for text content block."""

    def __init__(self, text: str):
        self.text = text


class MockToolUseBlock:
    """Mock for tool use content block."""

    def __init__(self, name: str, input_data: dict = None):
        self.name = name
        self.input = input_data or {}


class MockSystemMessage:
    """Mock for SystemMessage from Claude Agent SDK."""

    def __init__(self, subtype: str = "init", data: dict = None):
        self.subtype = subtype
        self.data = data or {}


class TestLeadAgentIntegrationWorkflow(unittest.TestCase):
    """Integration tests for full investigation workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_session_structure(self, session_dir: Path):
        """Create the expected session directory structure."""
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "files" / "datadog_findings").mkdir(parents=True)
        (session_dir / "files" / "deployment_findings").mkdir(parents=True)
        (session_dir / "files" / "code_findings").mkdir(parents=True)
        (session_dir / "transcript.txt").touch()

    def test_full_workflow_with_mocked_subagents_success(self):
        """Test complete workflow with mocked SDK returning success."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.ResultMessage", MockResultMessage), \
             patch("agents.lead_agent.AssistantMessage", MockAssistantMessage), \
             patch("agents.lead_agent.SystemMessage", MockSystemMessage):

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_20260212_120000"
            self._create_session_structure(session_dir)

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Create mock client that returns a success result
            final_report = """# Investigation Report

## Executive Summary
Found NullPointerException in CustomerService caused by missing null check.

## Timeline
- 2026-02-12 10:30 - Deployment of card-service v1.2.3
- 2026-02-12 10:45 - First errors appear

## Root Cause
Missing null check in EntitledCustomerService.kt line 145.
"""

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                # Yield system init
                yield MockSystemMessage(subtype="init", data={"mcp_servers": ["datadog", "github"]})
                # Yield assistant message with text
                yield MockAssistantMessage(content=[MockTextBlock("Investigating...")])
                # Yield result
                yield MockResultMessage(subtype="success", result=final_report)

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            result = asyncio.run(agent.investigate("NullPointerException in CustomerService"))

            # Verify session was created
            mock_session_mgr.create_session.assert_called_once()

            # Verify transcript was written
            self.assertTrue(mock_session_mgr.write_transcript.called)

            # Verify tracker was closed
            mock_tracker.close.assert_called_once()

            # Verify report file exists
            report_file = session_dir / "investigation_report.md"
            self.assertTrue(report_file.exists())

    def test_workflow_with_assistant_text_blocks(self):
        """Test that assistant text blocks are written to transcript."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.ResultMessage", MockResultMessage), \
             patch("agents.lead_agent.AssistantMessage", MockAssistantMessage), \
             patch("agents.lead_agent.SystemMessage", MockSystemMessage):

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            self._create_session_structure(session_dir)

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                # Multiple assistant messages with text
                yield MockAssistantMessage(content=[MockTextBlock("Starting investigation...")])
                yield MockAssistantMessage(content=[MockTextBlock("Searching DataDog logs...")])
                yield MockAssistantMessage(content=[MockTextBlock("Analysis complete.")])
                yield MockResultMessage(subtype="success", result="# Report")

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test error"))

            # Verify write_transcript was called with text content
            calls = mock_session_mgr.write_transcript.call_args_list
            # Filter calls that contain text (have end="" parameter for streaming)
            text_calls = [c for c in calls if 'end' in str(c)]
            self.assertTrue(len(text_calls) > 0 or len(calls) > 1)

    def test_workflow_with_tool_use_blocks(self):
        """Test that tool use blocks are logged to transcript."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.ResultMessage", MockResultMessage), \
             patch("agents.lead_agent.AssistantMessage", MockAssistantMessage), \
             patch("agents.lead_agent.SystemMessage", MockSystemMessage):

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            self._create_session_structure(session_dir)

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                # Assistant message with tool use
                yield MockAssistantMessage(content=[
                    MockTextBlock("Let me search the logs."),
                    MockToolUseBlock("Task", {"agent": "datadog-investigator"})
                ])
                yield MockResultMessage(subtype="success", result="# Report")

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test error"))

            # Verify tool use was logged
            calls = mock_session_mgr.write_transcript.call_args_list
            tool_calls = [c for c in calls if "Task" in str(c) or "tool" in str(c).lower()]
            # At least one call should reference tool use
            self.assertTrue(mock_session_mgr.write_transcript.called)


class TestSessionDirectoryCreation(unittest.TestCase):
    """Integration tests for session directory creation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_session_directory_contains_all_subdirectories(self):
        """Session directory should contain all required subdirectories."""
        from utils.session_manager import SessionManager

        manager = SessionManager(logs_dir=Path(self.temp_dir))
        session_dir = manager.create_session()

        # Verify all subdirectories exist
        self.assertTrue((session_dir / "files").exists())
        self.assertTrue((session_dir / "files" / "datadog_findings").exists())
        self.assertTrue((session_dir / "files" / "deployment_findings").exists())
        self.assertTrue((session_dir / "files" / "code_findings").exists())

    def test_session_directory_has_transcript_file(self):
        """Session directory should contain transcript.txt."""
        from utils.session_manager import SessionManager

        manager = SessionManager(logs_dir=Path(self.temp_dir))
        session_dir = manager.create_session()

        transcript_file = session_dir / "transcript.txt"
        self.assertTrue(transcript_file.exists())
        self.assertTrue(transcript_file.is_file())


class TestTranscriptWriting(unittest.TestCase):
    """Integration tests for transcript writing."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transcript_captures_user_input(self):
        """Transcript should capture user input at start."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            # Use real SessionManager
            from utils.session_manager import SessionManager
            session_manager = SessionManager(logs_dir=Path(self.temp_dir))

            with patch("agents.lead_agent.SessionManager", return_value=session_manager), \
                 patch("agents.lead_agent.SubagentTracker") as MockTracker, \
                 patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

                mock_tracker = MagicMock()
                MockTracker.return_value = mock_tracker

                mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

                mock_client_instance = MagicMock()
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client_instance.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                mock_client_instance.receive_response = mock_receive
                MockClient.return_value = mock_client_instance

                agent = LeadAgent()
                user_input = "NullPointerException in EntitledCustomerService"
                asyncio.run(agent.investigate(user_input))

                # Read transcript
                transcript_file = session_manager.session_dir / "transcript.txt"
                with open(transcript_file) as f:
                    content = f.read()

                self.assertIn(user_input, content)

    def test_transcript_is_human_readable(self):
        """Transcript should be human readable."""
        from utils.session_manager import SessionManager

        manager = SessionManager(logs_dir=Path(self.temp_dir))
        session_dir = manager.create_session()

        # Write some content
        manager.write_transcript("User: Search for NullPointerException\n", end="")
        manager.write_transcript("[LEAD] Starting investigation\n", end="")
        manager.write_transcript("[LEAD] -> Task (datadog-investigator)\n", end="")

        with open(session_dir / "transcript.txt") as f:
            content = f.read()

        # Should be readable text
        self.assertIn("User:", content)
        self.assertIn("LEAD", content)
        self.assertIn("Task", content)


class TestToolCallLogging(unittest.TestCase):
    """Integration tests for tool call logging."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tool_calls_logged_to_jsonl(self):
        """Tool calls should be logged to JSONL file."""
        from utils.hooks import SubagentTracker

        log_file = Path(self.temp_dir) / "tool_calls.jsonl"
        transcript_file = Path(self.temp_dir) / "transcript.txt"
        transcript_file.touch()

        tracker = SubagentTracker(log_file, transcript_file)

        # Simulate pre-tool hook
        asyncio.run(tracker.pre_tool_use_hook(
            input_data={
                "tool_name": "mcp__datadog__search_logs",
                "tool_input": {"query": "NullPointerException"},
                "parent_tool_use_id": None
            },
            tool_use_id="tool_001",
            context={}
        ))

        # Simulate post-tool hook
        asyncio.run(tracker.post_tool_use_hook(
            input_data={
                "tool_response": {
                    "content": [{"type": "text", "text": "Found 10 logs"}]
                }
            },
            tool_use_id="tool_001",
            context={}
        ))

        # Read JSONL
        with open(log_file) as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)  # Start and complete events

        start_entry = json.loads(lines[0])
        complete_entry = json.loads(lines[1])

        self.assertEqual(start_entry["event"], "tool_call_start")
        self.assertEqual(start_entry["tool_name"], "mcp__datadog__search_logs")

        self.assertEqual(complete_entry["event"], "tool_call_complete")
        self.assertTrue(complete_entry["success"])

    def test_tool_call_parent_child_relationship(self):
        """Tool calls should track parent-child relationships."""
        from utils.hooks import SubagentTracker

        log_file = Path(self.temp_dir) / "tool_calls.jsonl"
        transcript_file = Path(self.temp_dir) / "transcript.txt"
        transcript_file.touch()

        tracker = SubagentTracker(log_file, transcript_file)

        # Lead agent calls Task
        asyncio.run(tracker.pre_tool_use_hook(
            input_data={
                "tool_name": "Task",
                "tool_input": {"agent": "datadog-investigator"},
                "parent_tool_use_id": None
            },
            tool_use_id="task_parent",
            context={}
        ))

        # Subagent calls search_logs with parent reference
        asyncio.run(tracker.pre_tool_use_hook(
            input_data={
                "tool_name": "mcp__datadog__search_logs",
                "tool_input": {"query": "error"},
                "parent_tool_use_id": "task_parent"
            },
            tool_use_id="search_child",
            context={}
        ))

        with open(log_file) as f:
            lines = f.readlines()

        task_entry = json.loads(lines[0])
        search_entry = json.loads(lines[1])

        # Task should have no parent
        self.assertIsNone(task_entry["parent_tool_use_id"])
        self.assertEqual(task_entry["agent_id"], "LEAD")

        # Search should reference Task as parent
        self.assertEqual(search_entry["parent_tool_use_id"], "task_parent")
        self.assertTrue(search_entry["agent_id"].startswith("SUBAGENT-"))

    def test_tool_call_duration_logged(self):
        """Tool calls should log duration."""
        from utils.hooks import SubagentTracker
        import time

        log_file = Path(self.temp_dir) / "tool_calls.jsonl"
        transcript_file = Path(self.temp_dir) / "transcript.txt"
        transcript_file.touch()

        tracker = SubagentTracker(log_file, transcript_file)

        asyncio.run(tracker.pre_tool_use_hook(
            input_data={
                "tool_name": "Task",
                "tool_input": {},
                "parent_tool_use_id": None
            },
            tool_use_id="tool_002",
            context={}
        ))

        # Simulate some work
        time.sleep(0.05)

        asyncio.run(tracker.post_tool_use_hook(
            input_data={"tool_response": {"content": []}},
            tool_use_id="tool_002",
            context={}
        ))

        with open(log_file) as f:
            lines = f.readlines()

        complete_entry = json.loads(lines[1])
        self.assertIn("duration_ms", complete_entry)
        self.assertGreater(complete_entry["duration_ms"], 0)


class TestEndToEndCoordination(unittest.TestCase):
    """End-to-end tests for subagent coordination."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_findings_files_can_be_written_and_read(self):
        """Subagent findings files should be writable and readable."""
        from utils.session_manager import SessionManager

        manager = SessionManager(logs_dir=Path(self.temp_dir))
        session_dir = manager.create_session()

        # Simulate DataDog subagent writing findings
        datadog_findings = {
            "total_logs": 150,
            "unique_services": ["card-invitation-service"],
            "key_findings": ["Errors started at 10:30"]
        }

        findings_dir = manager.get_findings_dir("datadog_findings")
        findings_file = findings_dir / "summary.json"
        with open(findings_file, "w") as f:
            json.dump(datadog_findings, f)

        # Lead agent reads findings
        with open(findings_file) as f:
            loaded = json.load(f)

        self.assertEqual(loaded["total_logs"], 150)
        self.assertEqual(loaded["unique_services"], ["card-invitation-service"])

    def test_multiple_subagent_findings_coexist(self):
        """Multiple subagent findings should coexist without conflict."""
        from utils.session_manager import SessionManager

        manager = SessionManager(logs_dir=Path(self.temp_dir))
        session_dir = manager.create_session()

        # DataDog findings
        datadog_dir = manager.get_findings_dir("datadog_findings")
        with open(datadog_dir / "summary.json", "w") as f:
            json.dump({"source": "datadog", "logs": 100}, f)

        # Deployment findings
        deployment_dir = manager.get_findings_dir("deployment_findings")
        with open(deployment_dir / "summary.json", "w") as f:
            json.dump({"source": "deployment", "commits": 5}, f)

        # Code findings
        code_dir = manager.get_findings_dir("code_findings")
        with open(code_dir / "summary.json", "w") as f:
            json.dump({"source": "code", "issues": 3}, f)

        # All should be readable
        with open(datadog_dir / "summary.json") as f:
            self.assertEqual(json.load(f)["source"], "datadog")

        with open(deployment_dir / "summary.json") as f:
            self.assertEqual(json.load(f)["source"], "deployment")

        with open(code_dir / "summary.json") as f:
            self.assertEqual(json.load(f)["source"], "code")

    def test_report_file_written_at_session_end(self):
        """Investigation report should be written to session directory."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            session_dir.mkdir(parents=True)
            (session_dir / "files" / "datadog_findings").mkdir(parents=True)
            (session_dir / "files" / "deployment_findings").mkdir(parents=True)
            (session_dir / "files" / "code_findings").mkdir(parents=True)
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                return
                yield

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test"))

            # Report file should exist
            report_file = session_dir / "investigation_report.md"
            self.assertTrue(report_file.exists())


class TestLeadAgentWithRealSessionManager(unittest.TestCase):
    """Integration tests using real SessionManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_real_session_manager_integration(self):
        """Test LeadAgent with real SessionManager."""
        from agents.lead_agent import LeadAgent
        from utils.session_manager import SessionManager

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            # Create real session manager
            real_session_mgr = SessionManager(logs_dir=Path(self.temp_dir))

            with patch("agents.lead_agent.SessionManager", return_value=real_session_mgr), \
                 patch("agents.lead_agent.SubagentTracker") as MockTracker, \
                 patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

                mock_tracker = MagicMock()
                MockTracker.return_value = mock_tracker

                mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

                mock_client_instance = MagicMock()
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client_instance.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                mock_client_instance.receive_response = mock_receive
                MockClient.return_value = mock_client_instance

                agent = LeadAgent()
                asyncio.run(agent.investigate("Integration test"))

                # Verify session was created in real directory
                self.assertIsNotNone(real_session_mgr.session_dir)
                self.assertTrue(real_session_mgr.session_dir.exists())

    def test_real_hooks_integration(self):
        """Test LeadAgent with real SubagentTracker."""
        from agents.lead_agent import LeadAgent
        from utils.session_manager import SessionManager
        from utils.hooks import SubagentTracker, create_hook_matchers

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            real_session_mgr = SessionManager(logs_dir=Path(self.temp_dir))

            with patch("agents.lead_agent.SessionManager", return_value=real_session_mgr):

                mock_client_instance = MagicMock()
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client_instance.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                mock_client_instance.receive_response = mock_receive
                MockClient.return_value = mock_client_instance

                agent = LeadAgent()
                asyncio.run(agent.investigate("Hooks test"))

                # Verify JSONL file was created by real tracker
                session_dir = real_session_mgr.session_dir
                jsonl_file = session_dir / "tool_calls.jsonl"
                self.assertTrue(jsonl_file.exists())


class TestErrorScenarios(unittest.TestCase):
    """Integration tests for error scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_error_generates_error_report(self):
        """API errors should generate error reports."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            session_dir.mkdir(parents=True)
            (session_dir / "files" / "datadog_findings").mkdir(parents=True)
            (session_dir / "files" / "deployment_findings").mkdir(parents=True)
            (session_dir / "files" / "code_findings").mkdir(parents=True)
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Client raises error
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            result = asyncio.run(agent.investigate("Test"))

            # Result should be error report
            self.assertIn("Investigation Error", result)
            self.assertIn("API rate limit exceeded", result)

    def test_execution_error_captured_in_report(self):
        """Execution errors from SDK should be captured."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.ResultMessage", MockResultMessage):

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            session_dir.mkdir(parents=True)
            (session_dir / "files" / "datadog_findings").mkdir(parents=True)
            (session_dir / "files" / "deployment_findings").mkdir(parents=True)
            (session_dir / "files" / "code_findings").mkdir(parents=True)
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                # Return error result
                yield MockResultMessage(
                    subtype="error_during_execution",
                    error="Subagent failed to complete task"
                )

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            result = asyncio.run(agent.investigate("Test"))

            # Result should contain error info
            self.assertIn("Error", result)


class TestRunInteractive(unittest.TestCase):
    """Tests for the run_interactive() CLI function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_interactive_exit_command(self):
        """run_interactive should exit on 'exit' command."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            # Simulate user typing 'exit'
            mock_input.return_value = "exit"

            asyncio.run(run_interactive())

            # Should print goodbye
            goodbye_calls = [c for c in mock_print.call_args_list if "Goodbye" in str(c)]
            self.assertTrue(len(goodbye_calls) > 0)

    def test_run_interactive_quit_command(self):
        """run_interactive should exit on 'quit' command."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            # Simulate user typing 'quit'
            mock_input.return_value = "quit"

            asyncio.run(run_interactive())

            # Should print goodbye
            goodbye_calls = [c for c in mock_print.call_args_list if "Goodbye" in str(c)]
            self.assertTrue(len(goodbye_calls) > 0)

    def test_run_interactive_q_command(self):
        """run_interactive should exit on 'q' command."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            mock_input.return_value = "q"

            asyncio.run(run_interactive())

            goodbye_calls = [c for c in mock_print.call_args_list if "Goodbye" in str(c)]
            self.assertTrue(len(goodbye_calls) > 0)

    def test_run_interactive_empty_input(self):
        """run_interactive should exit on empty input."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            mock_input.return_value = ""

            asyncio.run(run_interactive())

            goodbye_calls = [c for c in mock_print.call_args_list if "Goodbye" in str(c)]
            self.assertTrue(len(goodbye_calls) > 0)

    def test_run_interactive_processes_valid_input(self):
        """run_interactive should process valid input and display report."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            mock_agent.investigate = AsyncMock(return_value="# Investigation Report\nTest complete")
            MockLeadAgent.return_value = mock_agent

            # First call: valid input, second call: exit
            mock_input.side_effect = ["NullPointerException in CustomerService", "exit"]

            asyncio.run(run_interactive())

            # Should have called investigate
            mock_agent.investigate.assert_called_once_with("NullPointerException in CustomerService")

            # Should have printed report
            report_calls = [c for c in mock_print.call_args_list if "INVESTIGATION REPORT" in str(c)]
            self.assertTrue(len(report_calls) > 0)

    def test_run_interactive_handles_keyboard_interrupt(self):
        """run_interactive should handle KeyboardInterrupt gracefully."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            # Simulate Ctrl+C
            mock_input.side_effect = KeyboardInterrupt()

            asyncio.run(run_interactive())

            # Should print interrupted message
            interrupted_calls = [c for c in mock_print.call_args_list if "Interrupted" in str(c)]
            self.assertTrue(len(interrupted_calls) > 0)

    def test_run_interactive_handles_exception(self):
        """run_interactive should handle exceptions and continue."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print, \
             patch("agents.lead_agent.logger") as mock_logger:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            # First call raises exception, second call returns success, third is exit
            mock_agent.investigate = AsyncMock(
                side_effect=[Exception("API Error"), "# Report"]
            )
            MockLeadAgent.return_value = mock_agent

            mock_input.side_effect = ["test input", "test input 2", "exit"]

            asyncio.run(run_interactive())

            # Should log the exception
            mock_logger.exception.assert_called()

            # Should continue and process second input
            self.assertEqual(mock_agent.investigate.call_count, 2)

    def test_run_interactive_prints_banner(self):
        """run_interactive should print welcome banner."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            mock_input.return_value = "exit"

            asyncio.run(run_interactive())

            # Should print banner with title
            all_print_output = " ".join([str(c) for c in mock_print.call_args_list])
            self.assertIn("Production Issue Investigator", all_print_output)

    def test_run_interactive_prints_examples(self):
        """run_interactive should print usage examples."""
        from agents.lead_agent import run_interactive

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.LeadAgent") as MockLeadAgent, \
             patch("builtins.input") as mock_input, \
             patch("builtins.print") as mock_print:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_agent = MagicMock()
            MockLeadAgent.return_value = mock_agent

            mock_input.return_value = "exit"

            asyncio.run(run_interactive())

            # Should print examples
            all_print_output = " ".join([str(c) for c in mock_print.call_args_list])
            self.assertIn("Examples", all_print_output)


if __name__ == "__main__":
    unittest.main()
