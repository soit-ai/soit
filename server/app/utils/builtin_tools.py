"""builtin_tools

Built-in tool functions for minimal runtime.
"""

from typing import Dict, Any
from datetime import datetime, timezone
import random


def time_now() -> Dict[str, Any]:
    """Return current UTC time."""
    now = datetime.now(timezone.utc)
    return {
        "iso": now.isoformat(),
        "timestamp": now.timestamp(),
    }


def random_int(min: int, max: int) -> Dict[str, Any]:
    """Return a random integer within range."""
    value = random.randint(min, max)
    return {"value": value}
