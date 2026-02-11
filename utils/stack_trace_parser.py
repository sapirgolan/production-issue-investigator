"""
Stack trace parser for extracting file paths from Java/Kotlin stack traces.

This module provides utilities to:
- Parse Java/Kotlin stack trace strings
- Extract stack frames with class, method, file, and line info
- Filter to only com.sunbit packages
- Convert frames to file paths for code analysis
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StackFrame:
    """A single stack trace frame.

    Attributes:
        class_name: Full qualified class name (e.g., com.sunbit.card.Handler)
        method_name: Method name (e.g., handleEvent)
        file_name: Source file name (e.g., Handler.kt)
        line_number: Line number in source file (may be None)
    """
    class_name: str
    method_name: str
    file_name: Optional[str] = None
    line_number: Optional[int] = None

    def to_file_path(self) -> str:
        """Convert this frame to a source file path.

        Maps class name to expected file path:
        - com.sunbit.card.Handler -> src/main/kotlin/com/sunbit/card/Handler.kt
        - Handles inner classes: MyClass$Companion -> MyClass.kt

        Returns:
            Source file path string
        """
        # Handle inner classes - strip $... suffix
        base_class = self.class_name.split("$")[0]

        # Convert package to path
        path_part = base_class.replace(".", "/")

        # Determine extension from file_name if available
        if self.file_name:
            if self.file_name.endswith(".kt"):
                return f"src/main/kotlin/{path_part}.kt"
            elif self.file_name.endswith(".java"):
                return f"src/main/java/{path_part}.java"

        # Default to Kotlin
        return f"src/main/kotlin/{path_part}.kt"


@dataclass
class ParsedStackTrace:
    """Result from parsing a stack trace.

    Attributes:
        frames: All parsed stack frames
        sunbit_frames: Only frames from com.sunbit packages
        unique_file_paths: Set of unique file paths from sunbit frames
    """
    frames: List[StackFrame] = field(default_factory=list)
    sunbit_frames: List[StackFrame] = field(default_factory=list)
    unique_file_paths: Set[str] = field(default_factory=set)


class StackTraceParser:
    """Parser for Java/Kotlin stack traces.

    Extracts stack frames and filters to application-specific packages.
    """

    # Regex pattern for stack trace frames
    # Matches: at com.sunbit.card.Handler.handleEvent(Handler.kt:45)
    # Groups: (full_class).(method)(file_name):(line_number)
    FRAME_PATTERN = re.compile(
        r'^\s*at\s+'            # "at " prefix
        r'([\w.$]+)\.'         # Full class name (group 1)
        r'([\w$<>]+)'          # Method name (group 2)
        r'\('                  # Opening paren
        r'([^:)]+)?'           # File name (group 3, optional)
        r'(?::(\d+))?'         # Line number (group 4, optional)
        r'\)',                 # Closing paren
        re.MULTILINE
    )

    # Package prefix to filter on
    SUNBIT_PREFIX = "com.sunbit"

    def parse(self, stack_trace: Optional[str]) -> ParsedStackTrace:
        """Parse a stack trace string.

        Args:
            stack_trace: Stack trace string to parse

        Returns:
            ParsedStackTrace with extracted frames
        """
        if not stack_trace:
            return ParsedStackTrace()

        frames: List[StackFrame] = []
        sunbit_frames: List[StackFrame] = []
        unique_paths: Set[str] = set()

        for match in self.FRAME_PATTERN.finditer(stack_trace):
            class_name = match.group(1)
            method_name = match.group(2)
            file_name = match.group(3)
            line_number_str = match.group(4)

            # Parse line number
            line_number = None
            if line_number_str:
                try:
                    line_number = int(line_number_str)
                except ValueError:
                    pass

            # Skip "Native Method" and similar
            if file_name and file_name.lower() in ("native method", "unknown source"):
                file_name = None

            frame = StackFrame(
                class_name=class_name,
                method_name=method_name,
                file_name=file_name,
                line_number=line_number,
            )
            frames.append(frame)

            # Check if this is a sunbit package
            if class_name.startswith(self.SUNBIT_PREFIX):
                sunbit_frames.append(frame)
                file_path = frame.to_file_path()
                unique_paths.add(file_path)

        if frames:
            logger.debug(
                f"Parsed stack trace: {len(frames)} frames, "
                f"{len(sunbit_frames)} sunbit frames, "
                f"{len(unique_paths)} unique files"
            )

        return ParsedStackTrace(
            frames=frames,
            sunbit_frames=sunbit_frames,
            unique_file_paths=unique_paths,
        )


def extract_file_paths(
    stack_trace: Optional[str] = None,
    message: Optional[str] = None,
) -> Set[str]:
    """Convenience function to extract file paths from stack trace and/or message.

    Parses both the dedicated stack_trace field and the message field
    (which may contain embedded stack traces), then returns the union
    of all unique file paths found.

    Args:
        stack_trace: Dedicated stack trace string
        message: Log message that may contain embedded stack trace

    Returns:
        Set of unique file paths from com.sunbit packages
    """
    parser = StackTraceParser()
    all_paths: Set[str] = set()

    if stack_trace:
        result = parser.parse(stack_trace)
        all_paths.update(result.unique_file_paths)

    if message:
        result = parser.parse(message)
        all_paths.update(result.unique_file_paths)

    return all_paths
