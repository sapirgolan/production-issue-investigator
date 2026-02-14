"""
DataDog MCP Server for Production Issue Investigator.

Provides MCP tools that wrap the existing DataDog API utilities.
Tools are designed to be used by the DataDog Investigator subagent.

Tools:
- search_logs: Search DataDog logs with query and time filters
- get_logs_by_efilogid: Get all logs for a session ID
- parse_stack_trace: Extract file paths and exceptions from stack traces
"""
import asyncio
import json
from typing import Any, Dict, List, Optional

from utils.config import get_cached_config, ConfigurationError
from utils.datadog_api import (
    DataDogAPI,
    DataDogAPIError,
    DataDogAuthError,
    DataDogRateLimitError,
    DataDogTimeoutError,
    LogEntry,
    SearchResult,
)
from utils.logger import get_logger
from utils.stack_trace_parser import StackTraceParser, ParsedStackTrace
from claude_agent_sdk import tool, create_sdk_mcp_server

logger = get_logger(__name__)

# Global instances - lazily initialized
_datadog_api: Optional[DataDogAPI] = None
_stack_parser: Optional[StackTraceParser] = None

# Maximum logs to return to avoid context bloat
MAX_LOGS_RETURNED = 50
# Maximum message length before truncation
MAX_MESSAGE_LENGTH = 200
# Maximum frames to include in stack trace response
MAX_FRAMES_RETURNED = 10


def get_datadog_api() -> DataDogAPI:
    """Get or create the DataDog API instance.

    Returns:
        Configured DataDogAPI instance

    Raises:
        ConfigurationError: If configuration is missing
    """
    global _datadog_api
    if _datadog_api is None:
        config = get_cached_config()
        _datadog_api = DataDogAPI(
            api_key=config.datadog_api_key,
            app_key=config.datadog_app_key,
            site=config.datadog_site,
        )
    return _datadog_api


def get_stack_parser() -> StackTraceParser:
    """Get or create the stack trace parser instance.

    Returns:
        StackTraceParser instance
    """
    global _stack_parser
    if _stack_parser is None:
        _stack_parser = StackTraceParser()
    return _stack_parser


def _truncate_message(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate a message to the specified length.

    Args:
        message: Message to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated message with '...' suffix if needed
    """
    if not message:
        return ""
    if len(message) <= max_length:
        return message
    return message[:max_length] + "..."


def _format_log_entry(log: LogEntry) -> Dict[str, Any]:
    """Format a LogEntry for MCP response.

    Args:
        log: LogEntry to format

    Returns:
        Dictionary with formatted log fields
    """
    return {
        "id": log.id,
        "timestamp": log.timestamp,
        "service": log.service,
        "message": _truncate_message(log.message),
        "status": log.status,
        "efilogid": log.efilogid,
        "dd_version": log.dd_version,
        "logger_name": log.logger_name,
        "has_stack_trace": bool(log.stack_trace),
    }


def _create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a successful MCP tool response.

    Args:
        data: Response data to include

    Returns:
        MCP-compliant response dict
    """
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2),
            }
        ]
    }


def _create_error_response(error_message: str, error_type: str = "error") -> Dict[str, Any]:
    """Create an error MCP tool response.

    Args:
        error_message: Error message to include
        error_type: Type of error

    Returns:
        MCP-compliant error response dict
    """
    return {
        "is_error": True,
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "error": error_message,
                    "error_type": error_type,
                }),
            }
        ]
    }


async def search_logs_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search DataDog logs with query and time filters.

    MCP tool that wraps DataDogAPI.search_logs() with async support.

    Args:
        args: Dictionary with:
            - query (str): DataDog query string
            - from_time (str): Start time (relative like "now-4h" or ISO 8601)
            - to_time (str): End time (relative like "now" or ISO 8601)
            - limit (int, optional): Maximum logs to fetch from API

    Returns:
        MCP response with search results or error
    """
    try:
        query = args.get("query", "")
        from_time = args.get("from_time", "now-4h")
        to_time = args.get("to_time", "now")
        limit = args.get("limit", 200)

        if not query:
            return _create_error_response("Query is required", "validation_error")

        logger.info(f"MCP search_logs: query='{query[:50]}...' from={from_time} to={to_time}")

        # Call the sync API in a thread to avoid blocking
        datadog_api = get_datadog_api()
        result: SearchResult = await asyncio.to_thread(
            datadog_api.search_logs,
            query=query,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )

        # Truncate logs to avoid context bloat
        logs_to_return = result.logs[:MAX_LOGS_RETURNED]
        formatted_logs = [_format_log_entry(log) for log in logs_to_return]

        response_data = {
            "success": True,
            "total_logs": result.total_count,
            "returned_logs": len(formatted_logs),
            "unique_services": list(result.unique_services),
            "unique_efilogids": list(result.unique_efilogids)[:10],  # Limit to 10
            "logs": formatted_logs,
        }

        logger.info(f"MCP search_logs: returned {len(formatted_logs)} of {result.total_count} logs")
        return _create_success_response(response_data)

    except DataDogRateLimitError as e:
        logger.warning(f"MCP search_logs: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except DataDogAuthError as e:
        logger.error(f"MCP search_logs: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except DataDogTimeoutError as e:
        logger.error(f"MCP search_logs: Timeout - {e}")
        return _create_error_response(f"Request timeout: {e}", "timeout_error")

    except DataDogAPIError as e:
        logger.error(f"MCP search_logs: API error - {e}")
        return _create_error_response(f"DataDog API error: {e}", "api_error")

    except Exception as e:
        logger.exception(f"MCP search_logs: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


async def get_logs_by_efilogid_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get all logs for a specific session ID (efilogid).

    MCP tool that searches for logs matching a specific efilogid.
    The efilogid is properly quoted in the query as required by DataDog.

    Args:
        args: Dictionary with:
            - efilogid (str): Session identifier
            - time_window (str, optional): Time range like "now-24h" (default)

    Returns:
        MCP response with session logs or error
    """
    try:
        efilogid = args.get("efilogid", "")
        time_window = args.get("time_window", "now-24h")

        if not efilogid:
            return _create_error_response("efilogid is required", "validation_error")

        logger.info(f"MCP get_logs_by_efilogid: efilogid='{efilogid}' window={time_window}")

        # Build query with properly quoted efilogid
        datadog_api = get_datadog_api()
        query = datadog_api.build_efilogid_query(efilogid)

        # Call the sync API in a thread
        result: SearchResult = await asyncio.to_thread(
            datadog_api.search_logs,
            query=query,
            from_time=time_window,
            to_time="now",
            limit=200,
        )

        # Format logs
        formatted_logs = [_format_log_entry(log) for log in result.logs[:MAX_LOGS_RETURNED]]

        # Extract unique dd.versions from the logs
        dd_versions = list({log.dd_version for log in result.logs if log.dd_version})

        response_data = {
            "success": True,
            "efilogid": efilogid,
            "log_count": result.total_count,
            "unique_services": list(result.unique_services),
            "dd_versions": dd_versions,
            "logs": formatted_logs,
        }

        logger.info(f"MCP get_logs_by_efilogid: found {result.total_count} logs for session")
        return _create_success_response(response_data)

    except DataDogRateLimitError as e:
        logger.warning(f"MCP get_logs_by_efilogid: Rate limit exceeded - {e}")
        return _create_error_response(f"Rate limit exceeded: {e}", "rate_limit_error")

    except DataDogAuthError as e:
        logger.error(f"MCP get_logs_by_efilogid: Authentication error - {e}")
        return _create_error_response(f"Authentication error: {e}", "auth_error")

    except DataDogTimeoutError as e:
        logger.error(f"MCP get_logs_by_efilogid: Timeout - {e}")
        return _create_error_response(f"Request timeout: {e}", "timeout_error")

    except DataDogAPIError as e:
        logger.error(f"MCP get_logs_by_efilogid: API error - {e}")
        return _create_error_response(f"DataDog API error: {e}", "api_error")

    except Exception as e:
        logger.exception(f"MCP get_logs_by_efilogid: Unexpected error - {e}")
        return _create_error_response(f"Unexpected error: {e}", "error")


async def parse_stack_trace_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Extract file paths and exceptions from stack traces.

    MCP tool that parses Java/Kotlin stack traces and extracts
    com.sunbit file paths and exception information.

    Args:
        args: Dictionary with:
            - stack_trace_text (str): Stack trace string to parse

    Returns:
        MCP response with parsed stack trace info or error
    """
    try:
        stack_trace_text = args.get("stack_trace_text", "")

        logger.info(f"MCP parse_stack_trace: parsing {len(stack_trace_text)} chars")

        # Parse is a sync operation but very fast, so we can call it directly
        # However, for consistency we use to_thread
        parser = get_stack_parser()
        result: ParsedStackTrace = await asyncio.to_thread(
            parser.parse,
            stack_trace_text,
        )

        # Format frames for response (limit to MAX_FRAMES_RETURNED)
        frames = []
        for frame in result.sunbit_frames[:MAX_FRAMES_RETURNED]:
            frames.append({
                "class_name": frame.class_name,
                "method_name": frame.method_name,
                "file_name": frame.file_name,
                "line_number": frame.line_number,
                "file_path": frame.to_file_path(),
                "is_root_frame": frame.is_root_frame,
            })

        response_data = {
            "success": True,
            "exception_type": result.exception_type,
            "exception_message": result.exception_message,
            "exception_short_type": result.exception_short_type,
            "has_chained_cause": result.has_chained_cause,
            "total_frames": len(result.frames),
            "sunbit_frames": len(result.sunbit_frames),
            "frame_count": len(frames),
            "file_paths": list(result.unique_file_paths),
            "frames": frames,
        }

        logger.info(
            f"MCP parse_stack_trace: found {len(frames)} sunbit frames, "
            f"{len(result.unique_file_paths)} unique paths"
        )
        return _create_success_response(response_data)

    except Exception as e:
        logger.exception(f"MCP parse_stack_trace: Unexpected error - {e}")
        return _create_error_response(f"Parse error: {e}", "error")


# Reset functions for testing
def reset_datadog_api():
    """Reset the cached DataDog API instance (for testing)."""
    global _datadog_api
    _datadog_api = None


def reset_stack_parser():
    """Reset the cached stack parser instance (for testing)."""
    global _stack_parser
    _stack_parser = None


def set_datadog_api(api: DataDogAPI):
    """Set the DataDog API instance (for testing).

    Args:
        api: DataDogAPI instance to use
    """
    global _datadog_api
    _datadog_api = api


def set_stack_parser(parser: StackTraceParser):
    """Set the stack parser instance (for testing).

    Args:
        parser: StackTraceParser instance to use
    """
    global _stack_parser
    _stack_parser = parser


# Create SDK-wrapped versions for MCP server
search_logs_sdk_tool = tool(
    name="search_logs",
    description="Search DataDog logs with query and time filters. Use this to find logs matching specific criteria like error messages, service names, or identifiers.",
    input_schema={
        "query": str,
        "from_time": str,
        "to_time": str,
        "limit": int,
    }
)(search_logs_tool)

get_logs_by_efilogid_sdk_tool = tool(
    name="get_logs_by_efilogid",
    description="Get all logs for a specific session ID (efilogid). Use this to retrieve the complete log trail for a user session.",
    input_schema={
        "efilogid": str,
        "time_window": str,
    }
)(get_logs_by_efilogid_tool)

parse_stack_trace_sdk_tool = tool(
    name="parse_stack_trace",
    description="Extract file paths and exceptions from Java/Kotlin stack traces. Use this to identify which source files are involved in an error.",
    input_schema={
        "stack_trace_text": str,
    }
)(parse_stack_trace_tool)


# Export MCP server for use by lead agent
DATADOG_MCP_SERVER = create_sdk_mcp_server(
    name="datadog",
    version="1.0.0",
    tools=[
        search_logs_sdk_tool,
        get_logs_by_efilogid_sdk_tool,
        parse_stack_trace_sdk_tool,
    ]
)
