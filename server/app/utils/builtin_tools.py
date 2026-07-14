"""builtin_tools

Built-in tool functions for minimal runtime.
"""

import random
from datetime import UTC, datetime
from typing import Any


def time_now(**_: Any) -> dict[str, Any]:
    """Return current UTC time."""
    now = datetime.now(UTC)
    return {
        "iso": now.isoformat(),
        "timestamp": now.timestamp(),
    }


def random_int(min: int, max: int) -> dict[str, Any]:
    """Return a random integer within range."""
    value = random.randint(min, max)
    return {"value": value}
