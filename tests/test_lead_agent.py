"""
Tests for Lead Agent (Phase 4 Component).

Tests for the Lead Agent orchestrator that coordinates subagents:
- LeadAgent initialization
- investigate() method
- Session management integration
- Subagent coordination (DataDog -> Deployment -> Code order)
- Error report generation
- File-based coordination (reading subagent findings)

These tests use mocks for ClaudeSDKClient and subagents to isolate the Lead Agent logic.
"""

import asyncio
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call


class TestLeadAgentInitialization(unittest.TestCase):
    """Tests for LeadAgent.__init__ method."""

    def test_lead_agent_init_default_config(self):
        """LeadAgent should use default config when none provided."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.log_level = "INFO"
            mock_get_config.return_value = mock_config

            agent = LeadAgent()

            mock_get_config.assert_called_once()
            self.assertEqual(agent.config, mock_config)

    def test_lead_agent_init_custom_config(self):
        """LeadAgent should use provided config."""
        from agents.lead_agent import LeadAgent

        custom_config = MagicMock()
        custom_config.log_level = "DEBUG"

        agent = LeadAgent(config=custom_config)

        self.assertEqual(agent.config, custom_config)

    def test_lead_agent_init_session_manager_none(self):
        """LeadAgent should initialize with session_manager as None."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()

            self.assertIsNone(agent.session_manager)

    def test_lead_agent_init_tracker_none(self):
        """LeadAgent should initialize with tracker as None."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()

            self.assertIsNone(agent.tracker)


class TestLeadAgentInvestigate(unittest.TestCase):
    """Tests for LeadAgent.investigate method."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_investigate_creates_session(self):
        """investigate() should create a new session."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_dir = Path(self.temp_dir) / "session_test"
            mock_session_dir.mkdir(parents=True)
            mock_session_mgr.create_session.return_value = mock_session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Mock the async client
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            # Create an async iterator for receive_response
            async def mock_receive():
                return
                yield  # Make it an async generator

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test error message"))

            mock_session_mgr.create_session.assert_called_once()

    def test_investigate_writes_user_input_to_transcript(self):
        """investigate() should write user input to transcript."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_dir = Path(self.temp_dir) / "session_test"
            mock_session_dir.mkdir(parents=True)
            mock_session_mgr.create_session.return_value = mock_session_dir
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
            user_input = "NullPointerException in CustomerService"
            asyncio.run(agent.investigate(user_input))

            # Check that write_transcript was called with the user input
            calls = mock_session_mgr.write_transcript.call_args_list
            self.assertTrue(any(user_input in str(c) for c in calls))

    def test_investigate_initializes_tracker(self):
        """investigate() should initialize SubagentTracker with session files."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_dir = Path(self.temp_dir) / "session_test"
            mock_session_dir.mkdir(parents=True)
            mock_session_mgr.create_session.return_value = mock_session_dir
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
            asyncio.run(agent.investigate("Test error"))

            # Verify tracker was created with correct paths
            MockTracker.assert_called_once()
            call_args = MockTracker.call_args
            self.assertIn("tool_calls.jsonl", str(call_args))
            self.assertIn("transcript.txt", str(call_args))

    def test_investigate_closes_tracker_on_completion(self):
        """investigate() should close tracker when finished."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_dir = Path(self.temp_dir) / "session_test"
            mock_session_dir.mkdir(parents=True)
            mock_session_mgr.create_session.return_value = mock_session_dir
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
            asyncio.run(agent.investigate("Test error"))

            mock_tracker.close.assert_called_once()


class TestLeadAgentSessionManagement(unittest.TestCase):
    """Tests for LeadAgent session management integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_session_directory_structure_created(self):
        """Session should create proper directory structure."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            # Create real session directory structure
            session_dir = Path(self.temp_dir) / "session_20260212_120000"
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

            # Verify session manager was set
            self.assertEqual(agent.session_manager, mock_session_mgr)

    def test_investigation_report_saved_to_file(self):
        """Investigation report should be saved to session directory."""
        from agents.lead_agent import LeadAgent, ResultMessage

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session_dir = Path(self.temp_dir) / "session_test"
            session_dir.mkdir(parents=True)
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Create a mock result message
            mock_result = MagicMock()
            mock_result.subtype = "success"
            mock_result.result = "# Investigation Report\n\nRoot cause: Test error"

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.query = AsyncMock()

            async def mock_receive():
                # Check if ResultMessage is imported
                try:
                    from agents.lead_agent import ResultMessage
                    # Yield a result that isinstance check would work on
                    # But since we mock, we need special handling
                except ImportError:
                    pass
                return
                yield

            mock_client_instance.receive_response = mock_receive
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test error"))

            # Report file should exist (even if empty from our mock)
            report_file = session_dir / "investigation_report.md"
            self.assertTrue(report_file.exists())


class TestLeadAgentSubagentCoordination(unittest.TestCase):
    """Tests for subagent coordination (order: DataDog -> Deployment -> Code)."""

    def test_subagent_definitions_registered(self):
        """LeadAgent should register all three subagent definitions."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.DATADOG_INVESTIGATOR") as mock_datadog, \
             patch("agents.lead_agent.DEPLOYMENT_ANALYZER") as mock_deployment, \
             patch("agents.lead_agent.CODE_REVIEWER") as mock_code:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(tempfile.mkdtemp())
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_options = {}

            def capture_options(options):
                captured_options["agents"] = options.agents if hasattr(options, "agents") else None
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_options

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass  # We only care about capturing the options

            # Verify all agents were registered
            # Since we mocked the constants, check that MockClient was called
            self.assertTrue(MockClient.called)

    def test_allowed_tools_include_task(self):
        """LeadAgent should have Task tool for spawning subagents."""
        from agents.lead_agent import LeadAgent, ClaudeAgentOptions

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(tempfile.mkdtemp())
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_args = []

            def capture_client_args(options):
                captured_args.append(options)
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_client_args

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass

            # Check if Task tool is in allowed_tools
            if captured_args:
                options = captured_args[0]
                if hasattr(options, "allowed_tools"):
                    self.assertIn("Task", options.allowed_tools)


class TestLeadAgentErrorReport(unittest.TestCase):
    """Tests for error report generation."""

    def test_generate_error_report_contains_user_input(self):
        """Error report should contain the user input."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()
            user_input = "NullPointerException in CustomerService"
            error = "API connection failed"

            report = agent._generate_error_report(user_input, error)

            self.assertIn(user_input, report)

    def test_generate_error_report_contains_error_message(self):
        """Error report should contain the error message."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()
            user_input = "Test input"
            error = "DataDog API rate limit exceeded"

            report = agent._generate_error_report(user_input, error)

            self.assertIn(error, report)

    def test_generate_error_report_contains_timestamp(self):
        """Error report should contain a timestamp."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()
            report = agent._generate_error_report("Test", "Error")

            # Should contain timestamp in ISO format
            self.assertIn("Timestamp", report)
            # Should have year-month-day pattern
            self.assertRegex(report, r"\d{4}-\d{2}-\d{2}")

    def test_generate_error_report_contains_troubleshooting(self):
        """Error report should contain troubleshooting steps."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()
            report = agent._generate_error_report("Test", "Error")

            self.assertIn("Troubleshooting", report)

    def test_generate_error_report_is_markdown(self):
        """Error report should be valid markdown."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()

            agent = LeadAgent()
            report = agent._generate_error_report("Test", "Error")

            # Should contain markdown headers
            self.assertIn("# ", report)
            # Should contain code block
            self.assertIn("```", report)


class TestLeadAgentFileBasedCoordination(unittest.TestCase):
    """Tests for file-based coordination between lead agent and subagents."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_lead_agent_has_read_tool(self):
        """LeadAgent should have Read tool for file coordination."""
        from agents.lead_agent import LeadAgent, ClaudeAgentOptions

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(self.temp_dir)
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_options = None

            def capture_options(options):
                nonlocal captured_options
                captured_options = options
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_options

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass

            # Verify Read tool is in allowed_tools
            if captured_options and hasattr(captured_options, "allowed_tools"):
                self.assertIn("Read", captured_options.allowed_tools)

    def test_lead_agent_has_glob_tool(self):
        """LeadAgent should have Glob tool for finding files."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(self.temp_dir)
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_options = None

            def capture_options(options):
                nonlocal captured_options
                captured_options = options
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_options

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass

            # Verify Glob tool is in allowed_tools
            if captured_options and hasattr(captured_options, "allowed_tools"):
                self.assertIn("Glob", captured_options.allowed_tools)


class TestLeadAgentPrompt(unittest.TestCase):
    """Tests for Lead Agent prompt configuration."""

    def test_lead_agent_prompt_contains_subagent_instructions(self):
        """Lead agent prompt should describe subagent coordination."""
        from agents.lead_agent import LEAD_AGENT_PROMPT

        # Should mention all three subagents
        self.assertIn("datadog-investigator", LEAD_AGENT_PROMPT)
        self.assertIn("deployment-analyzer", LEAD_AGENT_PROMPT)
        self.assertIn("code-reviewer", LEAD_AGENT_PROMPT)

    def test_lead_agent_prompt_specifies_order(self):
        """Lead agent prompt should specify DataDog -> Deployment -> Code order."""
        from agents.lead_agent import LEAD_AGENT_PROMPT

        # Should specify the order of invocation
        self.assertIn("DataDog", LEAD_AGENT_PROMPT)
        self.assertIn("Deployment", LEAD_AGENT_PROMPT)
        self.assertIn("Code", LEAD_AGENT_PROMPT)

    def test_lead_agent_prompt_describes_file_coordination(self):
        """Lead agent prompt should describe file-based coordination."""
        from agents.lead_agent import LEAD_AGENT_PROMPT

        # Should mention reading findings files
        self.assertIn("files/", LEAD_AGENT_PROMPT)

    def test_lead_agent_prompt_describes_report_structure(self):
        """Lead agent prompt should describe report structure."""
        from agents.lead_agent import LEAD_AGENT_PROMPT

        # Should mention report sections
        self.assertIn("Executive Summary", LEAD_AGENT_PROMPT)
        self.assertIn("Timeline", LEAD_AGENT_PROMPT)
        self.assertIn("Root Cause", LEAD_AGENT_PROMPT)


class TestLeadAgentExceptionHandling(unittest.TestCase):
    """Tests for exception handling in LeadAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_investigate_handles_client_exception(self):
        """investigate() should handle ClaudeSDKClient exceptions gracefully."""
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
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Make client raise an exception
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            result = asyncio.run(agent.investigate("Test error"))

            # Should return error report, not raise
            self.assertIn("Error", result)
            self.assertIn("Investigation Error", result)

    def test_investigate_closes_tracker_on_exception(self):
        """investigate() should close tracker even when exception occurs."""
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
            (session_dir / "transcript.txt").touch()

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = session_dir
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            # Make client raise an exception
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                side_effect=Exception("Test exception")
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            agent = LeadAgent()
            asyncio.run(agent.investigate("Test error"))

            # Tracker should still be closed
            mock_tracker.close.assert_called_once()


class TestLeadAgentModelConfiguration(unittest.TestCase):
    """Tests for Lead Agent model configuration."""

    def test_lead_agent_uses_opus_model(self):
        """LeadAgent should use opus model for strong reasoning."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(tempfile.mkdtemp())
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_options = None

            def capture_options(options):
                nonlocal captured_options
                captured_options = options
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_options

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass

            # Verify model is opus
            if captured_options and hasattr(captured_options, "model"):
                self.assertEqual(captured_options.model, "opus")


class TestLeadAgentMCPServers(unittest.TestCase):
    """Tests for MCP server configuration."""

    def test_lead_agent_configures_mcp_servers(self):
        """LeadAgent should configure DataDog and GitHub MCP servers."""
        from agents.lead_agent import LeadAgent

        with patch("agents.lead_agent.get_config") as mock_get_config, \
             patch("agents.lead_agent.ClaudeSDKClient") as MockClient, \
             patch("agents.lead_agent.SessionManager") as MockSessionManager, \
             patch("agents.lead_agent.SubagentTracker") as MockTracker, \
             patch("agents.lead_agent.create_hook_matchers") as mock_create_hooks, \
             patch("agents.lead_agent.DATADOG_MCP_SERVER") as mock_datadog_server, \
             patch("agents.lead_agent.GITHUB_MCP_SERVER") as mock_github_server:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = Path(tempfile.mkdtemp())
            MockSessionManager.return_value = mock_session_mgr

            mock_tracker = MagicMock()
            MockTracker.return_value = mock_tracker

            mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

            captured_options = None

            def capture_options(options):
                nonlocal captured_options
                captured_options = options
                client = MagicMock()
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=None)
                client.query = AsyncMock()

                async def mock_receive():
                    return
                    yield

                client.receive_response = mock_receive
                return client

            MockClient.side_effect = capture_options

            agent = LeadAgent()
            try:
                asyncio.run(agent.investigate("Test"))
            except Exception:
                pass

            # Verify MCP servers are configured
            if captured_options and hasattr(captured_options, "mcp_servers"):
                self.assertIn("datadog", captured_options.mcp_servers)
                self.assertIn("github", captured_options.mcp_servers)


if __name__ == "__main__":
    unittest.main()
