"""
Time and date utility functions for timezone conversion and parsing.

Handles conversion between Tel Aviv timezone and UTC for DataDog API.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple

from dateutil import parser
import pytz


# Constants
TEL_AVIV_TZ = pytz.timezone("Asia/Tel_Aviv")
UTC_TZ = pytz.UTC

# Time window defaults
DEFAULT_WINDOW_HOURS = 4
INITIAL_WINDOW_HOURS = 2  # +/- 2 hours when datetime provided
EXPANDED_WINDOW_HOURS = 12  # +/- 12 hours for expansion level 1
EXPANDED_WINDOW_DAYS = 3.5  # +/- 3.5 days for expansion level 2


def parse_time(time_str: str) -> datetime:
    """Parse a flexible time string into a datetime object.

    Args:
        time_str: Time string in various formats (ISO 8601, human-readable, etc.)

    Returns:
        Parsed datetime object (may be naive or aware depending on input)
    """
    return parser.parse(time_str)


def tel_aviv_to_utc(dt: datetime) -> datetime:
    """Convert Tel Aviv time to UTC.

    Args:
        dt: Datetime object (naive or aware). If naive, assumes Tel Aviv timezone.

    Returns:
        UTC datetime object (timezone-aware)
    """
    # If naive, localize to Tel Aviv
    if dt.tzinfo is None:
        dt = TEL_AVIV_TZ.localize(dt)

    # Convert to UTC
    return dt.astimezone(UTC_TZ)


def utc_to_tel_aviv(dt: datetime) -> datetime:
    """Convert UTC time to Tel Aviv time.

    Args:
        dt: UTC datetime object (naive or aware). If naive, assumes UTC.

    Returns:
        Tel Aviv datetime object (timezone-aware)
    """
    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)

    # Convert to Tel Aviv
    return dt.astimezone(TEL_AVIV_TZ)


def datetime_to_iso8601(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string in UTC.

    Args:
        dt: Datetime object (naive or aware)

    Returns:
        ISO 8601 formatted string in UTC (e.g., "2026-02-10T14:30:00Z")
    """
    # Ensure UTC
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)
    else:
        dt = dt.astimezone(UTC_TZ)

    # Format as ISO 8601 with Z suffix for UTC
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def datetime_to_milliseconds(dt: datetime) -> int:
    """Convert datetime to Unix timestamp in milliseconds.

    Args:
        dt: Datetime object (naive or aware). If naive, assumes UTC.

    Returns:
        Unix timestamp in milliseconds
    """
    # Ensure UTC
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)
    else:
        dt = dt.astimezone(UTC_TZ)

    # Convert to milliseconds
    return int(dt.timestamp() * 1000)


def milliseconds_to_datetime(ms: int) -> datetime:
    """Convert Unix timestamp in milliseconds to UTC datetime.

    Args:
        ms: Unix timestamp in milliseconds

    Returns:
        UTC datetime object (timezone-aware)
    """
    return datetime.fromtimestamp(ms / 1000, tz=UTC_TZ)


def parse_relative_time(time_str: str) -> datetime:
    """Parse relative time strings like "now-4h" or "now".

    Args:
        time_str: Relative time string. Supported formats:
            - "now": Current UTC time
            - "now-Xh": X hours ago
            - "now-Xd": X days ago
            - ISO 8601 strings are also accepted

    Returns:
        UTC datetime object (timezone-aware)
    """
    now = datetime.now(UTC_TZ)

    if time_str == "now":
        return now

    if time_str.startswith("now-"):
        # Parse the offset
        offset_str = time_str[4:]

        if offset_str.endswith("h"):
            hours = float(offset_str[:-1])
            return now - timedelta(hours=hours)
        elif offset_str.endswith("d"):
            days = float(offset_str[:-1])
            return now - timedelta(days=days)
        else:
            raise ValueError(f"Unknown time offset format: {offset_str}")

    # Try parsing as ISO 8601
    dt = parser.parse(time_str)
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)
    return dt


def calculate_time_window(
    user_datetime: Optional[datetime] = None,
) -> Tuple[str, str]:
    """Calculate the time window for DataDog log search.

    Args:
        user_datetime: Optional datetime provided by user (assumed Tel Aviv timezone
                      if naive). If not provided, returns default window.

    Returns:
        Tuple of (from_time, to_time) as strings suitable for DataDog API.
        - If no datetime provided: ("now-4h", "now")
        - If datetime provided: ISO 8601 strings in UTC for (datetime - 2h, datetime + 2h)
          The 'to' time is capped at current time (never future).
    """
    if user_datetime is None:
        return ("now-4h", "now")

    # Convert to UTC if needed
    utc_datetime = tel_aviv_to_utc(user_datetime)
    now = datetime.now(UTC_TZ)

    # Calculate window: +/- 2 hours
    from_time = utc_datetime - timedelta(hours=INITIAL_WINDOW_HOURS)
    to_time = utc_datetime + timedelta(hours=INITIAL_WINDOW_HOURS)

    # Cap to_time at current time (never search future)
    if to_time > now:
        to_time = now

    return (datetime_to_iso8601(from_time), datetime_to_iso8601(to_time))


def expand_time_window(
    original_from: str,
    original_to: str,
    expansion_level: int,
    user_datetime: Optional[datetime] = None,
) -> Tuple[str, str]:
    """Expand the time window for retry searches.

    Args:
        original_from: Original from time (relative or ISO 8601)
        original_to: Original to time (relative or ISO 8601)
        expansion_level: Expansion level (1 for 24h/12h, 2 for 7d/3.5d)
        user_datetime: Optional user-provided datetime for centering expansion.
                      If provided, expansion is centered on this datetime.

    Returns:
        Tuple of (from_time, to_time) as strings suitable for DataDog API.
        The 'to' time is capped at current time (never future).

    Raises:
        ValueError: If expansion_level is not 1 or 2.
    """
    now = datetime.now(UTC_TZ)

    if expansion_level == 1:
        if user_datetime is None:
            # No datetime provided: expand to 24 hours
            return ("now-24h", "now")
        else:
            # Datetime provided: expand to +/- 12 hours centered on user datetime
            utc_datetime = tel_aviv_to_utc(user_datetime)
            from_time = utc_datetime - timedelta(hours=EXPANDED_WINDOW_HOURS)
            to_time = utc_datetime + timedelta(hours=EXPANDED_WINDOW_HOURS)

            # Cap at current time
            if to_time > now:
                to_time = now

            return (datetime_to_iso8601(from_time), datetime_to_iso8601(to_time))

    elif expansion_level == 2:
        if user_datetime is None:
            # No datetime provided: expand to 7 days
            return ("now-7d", "now")
        else:
            # Datetime provided: expand to +/- 3.5 days centered on user datetime
            utc_datetime = tel_aviv_to_utc(user_datetime)
            from_time = utc_datetime - timedelta(days=EXPANDED_WINDOW_DAYS)
            to_time = utc_datetime + timedelta(days=EXPANDED_WINDOW_DAYS)

            # Cap at current time
            if to_time > now:
                to_time = now

            return (datetime_to_iso8601(from_time), datetime_to_iso8601(to_time))

    else:
        raise ValueError(f"Invalid expansion_level: {expansion_level}. Must be 1 or 2.")


def format_time_range_for_display(
    from_time: str, to_time: str, display_tz: str = "Asia/Tel_Aviv"
) -> str:
    """Format a time range for human-readable display.

    Args:
        from_time: From time (relative or ISO 8601)
        to_time: To time (relative or ISO 8601)
        display_tz: Timezone for display (default: Tel Aviv)

    Returns:
        Human-readable string describing the time range
    """
    display_timezone = pytz.timezone(display_tz)

    from_dt = parse_relative_time(from_time)
    to_dt = parse_relative_time(to_time)

    # Convert to display timezone
    from_local = from_dt.astimezone(display_timezone)
    to_local = to_dt.astimezone(display_timezone)

    # Format for display
    from_str = from_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    to_str = to_local.strftime("%Y-%m-%d %H:%M:%S %Z")

    return f"{from_str} to {to_str}"


def get_deployment_window_start(log_search_from: str) -> datetime:
    """Calculate the start time for deployment search (72 hours before log search).

    Args:
        log_search_from: The 'from' time used for log search (relative or ISO 8601)

    Returns:
        UTC datetime object for deployment search start (72 hours before log search start)
    """
    from_dt = parse_relative_time(log_search_from)
    return from_dt - timedelta(hours=72)
