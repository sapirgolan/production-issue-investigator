"""
Hook system for tracking tool usage across all agents.

Provides observability for Claude Agent SDK tool calls by:
- Logging tool invocations with timestamps
- Tracking parent-child tool call relationships
- Recording success/failure and duration
- Writing to JSONL for analysis and transcript for readability
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SubagentTracker:
    """Tracks tool usage across lead agent and subagents."""

    def __init__(self, log_file: Path, transcript_file: Path):
        """
        Initialize the tracker.

        Args:
            log_file: Path to JSONL file for tool calls
            transcript_file: Path to transcript file
        """
        self.log_file = log_file
        self.transcript_file = transcript_file
        self.tool_starts: Dict[str, Dict[str, Any]] = {}

        # Create log file and parent directories
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.touch()

        logger.info(f"SubagentTracker initialized: {log_file}")

    async def pre_tool_use_hook(
        self,
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pre-tool-use hook to log tool invocations.

        Captures:
        - Agent ID (lead vs subagent)
        - Tool name
        - Input parameters
        - Parent tool use ID (for subagent calls)
        - Start timestamp

        Args:
            input_data: Dictionary containing tool_name, tool_input, parent_tool_use_id
            tool_use_id: Unique identifier for this tool call
            context: Additional context (unused currently)

        Returns:
            Empty dict (hook doesn't modify the tool call)
        """
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        parent_id = input_data.get("parent_tool_use_id")

        # Determine agent ID
        if parent_id:
            # This is a subagent tool call
            # Build agent ID that includes parent reference for traceability
            # Skip common prefixes (like "parent_task_") to get to the unique identifier part
            if "_" in parent_id:
                # Get the last segment (unique identifier part) and take first 2 chars
                parts = parent_id.split("_")
                identifier = parts[-1][:2] if parts else parent_id[:2]
                agent_id = f"SUBAGENT-parent_{identifier}"
            else:
                agent_id = f"SUBAGENT-{parent_id[:8]}"
        else:
            # This is the lead agent
            agent_id = "LEAD"

        # Record start time
        start_time = time.time()
        self.tool_starts[tool_use_id] = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "start_time": start_time,
            "parent_id": parent_id
        }

        # Log to JSONL
        log_entry = {
            "event": "tool_call_start",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "tool_use_id": tool_use_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "parent_tool_use_id": parent_id,
            "input": self._truncate_input(tool_input)
        }
        self._write_jsonl(log_entry)

        # Log to transcript
        self._write_transcript(f"[{agent_id}] Starting {tool_name}\n")

        logger.debug(f"Tool start: {agent_id} -> {tool_name}")

        return {}

    async def post_tool_use_hook(
        self,
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Post-tool-use hook to log tool completion.

        Captures:
        - Success/failure status
        - Duration in milliseconds
        - Output size
        - Error message (on failure)

        Args:
            input_data: Dictionary containing tool_response
            tool_use_id: Unique identifier for this tool call
            context: Additional context (unused currently)

        Returns:
            Empty dict (hook doesn't modify the result)
        """
        tool_response = input_data.get("tool_response", {})

        # Get start info
        start_info = self.tool_starts.get(tool_use_id, {})
        agent_id = start_info.get("agent_id", "UNKNOWN")
        tool_name = start_info.get("tool_name", "unknown")
        start_time = start_info.get("start_time", time.time())

        # Calculate duration
        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        # Determine success
        success = not tool_response.get("is_error", False)

        # Calculate output size
        output_size = len(json.dumps(tool_response))

        # Log to JSONL
        log_entry = {
            "event": "tool_call_complete",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "tool_use_id": tool_use_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "output_size": output_size
        }

        if not success:
            log_entry["error"] = self._extract_error(tool_response)

        self._write_jsonl(log_entry)

        # Log to transcript
        status = "completed" if success else "FAILED"
        self._write_transcript(
            f"[{agent_id}] {tool_name} {status} ({duration_ms}ms)\n"
        )

        logger.debug(f"Tool complete: {agent_id} -> {tool_name} ({duration_ms}ms)")

        return {}

    def _truncate_input(self, tool_input: Dict[str, Any], max_size: int = 500) -> Dict[str, Any]:
        """
        Truncate large inputs for logging.

        Args:
            tool_input: Dictionary of tool input parameters
            max_size: Maximum size for string values before truncation

        Returns:
            Dictionary with large values truncated
        """
        truncated = {}
        for key, value in tool_input.items():
            value_str = str(value)
            if len(value_str) > max_size:
                truncated[key] = value_str[:max_size] + "... (truncated)"
            else:
                truncated[key] = value
        return truncated

    def _extract_error(self, tool_response: Dict[str, Any]) -> str:
        """
        Extract error message from tool response.

        Args:
            tool_response: Tool response dictionary

        Returns:
            Error message string
        """
        if "content" in tool_response:
            content = tool_response["content"]
            if isinstance(content, list) and len(content) > 0:
                first_block = content[0]
                if isinstance(first_block, dict):
                    return first_block.get("text", "Unknown error")
        return str(tool_response)[:200]

    def _write_jsonl(self, entry: Dict[str, Any]) -> None:
        """
        Append entry to JSONL file.

        Args:
            entry: Dictionary to write as JSON line
        """
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _write_transcript(self, text: str) -> None:
        """
        Append text to transcript file.

        Args:
            text: Text to append
        """
        with open(self.transcript_file, "a") as f:
            f.write(text)

    def close(self) -> None:
        """Cleanup on session end."""
        logger.info(f"SubagentTracker closed. Logs: {self.log_file}")


def create_hook_matchers(tracker: SubagentTracker) -> Dict[str, list]:
    """
    Create hook matchers for PreToolUse and PostToolUse.

    Args:
        tracker: SubagentTracker instance

    Returns:
        Dict with hooks configuration containing PreToolUse and PostToolUse lists
    """
    return {
        "PreToolUse": [
            {
                "matcher": None,  # Match all tools
                "hooks": [tracker.pre_tool_use_hook]
            }
        ],
        "PostToolUse": [
            {
                "matcher": None,  # Match all tools
                "hooks": [tracker.post_tool_use_hook]
            }
        ]
    }
