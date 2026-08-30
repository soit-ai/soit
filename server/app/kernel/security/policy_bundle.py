"""policy_bundle

A stable identifier for the governance policy a call was evaluated against.

A policy that is only ever "the current value" cannot be cited. A run says it
was allowed, and a month later nobody can say what it was allowed by. The
identifier here is derived from the policy content itself, so the same rules
always produce the same identifier and different rules never share one -- an
identifier can therefore be recorded in run evidence and matched against a
stored revision without a lookup at the time of the call.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

BUNDLE_ID_PREFIX = "pb_"

_DIGEST_LENGTH = 16
"""Half a SHA-256, in hex.

Long enough that two policies colliding is not a thing that happens, short
enough to read out of a log line or paste into a ticket.
"""


def canonical_policy_document(document: Mapping[str, Any]) -> str:
    """Render a policy document so equal policies render identically.

    Key order, list order inside the rule lists and whitespace must not change
    the identifier: reordering an allowlist in the console is not a policy
    change, and a bundle that shifted every time rows moved would be worthless
    as evidence.
    """
    return json.dumps(
        _normalize(document),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, list | tuple | set):
        items = [_normalize(item) for item in value]
        # Rule lists are sets in meaning, so they are compared as sets.
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def policy_bundle_id(document: Mapping[str, Any]) -> str:
    """Return the identifier for this exact policy content."""
    digest = hashlib.sha256(canonical_policy_document(document).encode("utf-8")).hexdigest()
    return f"{BUNDLE_ID_PREFIX}{digest[:_DIGEST_LENGTH]}"
