""" time

Time utilities (UTC, ISO8601).
"""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Get current UTC datetime.
    
    Returns:
        Current datetime in UTC timezone.
    """
    return datetime.now(timezone.utc)


def to_iso8601(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO8601 string.
    
    Args:
        dt: Datetime to convert. If None, returns None.
        
    Returns:
        ISO8601 formatted string (e.g., "2025-01-01T00:00:00Z").
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def from_iso8601(iso_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601 string to datetime.
    
    Args:
        iso_str: ISO8601 formatted string.
        
    Returns:
        Datetime object, or None if parsing fails.
    """
    if not iso_str:
        return None
    try:
        # Handle both "Z" and "+00:00" formats
        iso_str = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_str)
    except (ValueError, AttributeError):
        return None
