"""Deterministic demo ticket tools."""

from __future__ import annotations

import hashlib
from typing import Any


async def create_review_ticket(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    data = payload or kwargs
    customer_id = str(data.get("customer_id") or "unknown")
    priority = str(data.get("priority") or "normal")
    message = str(data.get("message") or "")
    base_url = str(data.get("url") or "https://tickets.example.local/reviews").rstrip("/")
    suffix = hashlib.sha256(f"{customer_id}|{priority}|{message}".encode()).hexdigest()[:8].upper()
    ticket_id = f"TICKET-{suffix}"
    return {
        "ticket_id": ticket_id,
        "status": "created",
        "review_url": f"{base_url}/{ticket_id}",
    }
