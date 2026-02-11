"""
Time and date utility functions for timezone conversion and parsing.
"""
from datetime import datetime
from dateutil import parser
import pytz


def parse_time(time_str: str) -> datetime:
    """Parse a flexible time string into a datetime object.

    Args:
        time_str: Time string in various formats

    Returns:
        Parsed datetime object
    """
    return parser.parse(time_str)


def tel_aviv_to_utc(dt: datetime) -> datetime:
    """Convert Tel Aviv time to UTC.

    Args:
        dt: Datetime object (naive or aware)

    Returns:
        UTC datetime object
    """
    tel_aviv_tz = pytz.timezone('Asia/Tel_Aviv')

    # If naive, localize to Tel Aviv
    if dt.tzinfo is None:
        dt = tel_aviv_tz.localize(dt)

    # Convert to UTC
    return dt.astimezone(pytz.UTC)


def utc_to_tel_aviv(dt: datetime) -> datetime:
    """Convert UTC time to Tel Aviv time.

    Args:
        dt: UTC datetime object

    Returns:
        Tel Aviv datetime object
    """
    tel_aviv_tz = pytz.timezone('Asia/Tel_Aviv')

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    # Convert to Tel Aviv
    return dt.astimezone(tel_aviv_tz)
