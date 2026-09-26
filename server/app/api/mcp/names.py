"""MCP tool names for SOIT tool refs.

A SOIT ref such as ``tool:function:time_now`` or ``mcp_tool:github:create_issue``
has characters MCP clients and model APIs do not accept in a tool name. Each
ref is given a name of letters, digits, ``_`` and ``-``, at most 64 long, that
is stable for as long as the workspace's tools are: a name that would collide
with another tool's, or run too long, carries a short digest of its ref.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable

MAX_TOOL_NAME_LENGTH = 64
_PREFIXES = ("mcp_tool:", "tool:")
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _base_name(ref: str) -> str:
    for prefix in _PREFIXES:
        if ref.startswith(prefix):
            ref = ref[len(prefix) :]
            break
    return _UNSAFE.sub("_", ref).strip("_") or "tool"


def _digest_name(base: str, ref: str) -> str:
    digest = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:8]
    return f"{base[: MAX_TOOL_NAME_LENGTH - len(digest) - 1]}_{digest}"


def tool_names(refs: Iterable[str]) -> dict[str, str]:
    """Map each ref to a distinct MCP tool name."""

    bases = {ref: _base_name(ref) for ref in refs}
    counts = Counter(bases.values())
    return {
        ref: base if counts[base] == 1 and len(base) <= MAX_TOOL_NAME_LENGTH else _digest_name(base, ref)
        for ref, base in bases.items()
    }
