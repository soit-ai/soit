"""Pure pagination token contract shared across application and transport layers."""

from __future__ import annotations

import base64
import json

from pydantic import BaseModel


class PageToken(BaseModel):
    """Offset pagination token encoded as base64 JSON."""

    offset: int
    limit: int

    @classmethod
    def from_string(cls, token_str: str) -> PageToken:
        try:
            decoded = base64.b64decode(token_str).decode("utf-8")
            data = json.loads(decoded)
            return cls(**data)
        except Exception as exc:
            raise ValueError(f"Invalid page token: {exc}") from exc

    def to_string(self) -> str:
        json_str = json.dumps(self.model_dump(), ensure_ascii=True, separators=(",", ":"))
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def parse_page_params(
    page_token: str | None = None,
    page_size: int = 20,
    max_page_size: int = 100,
) -> tuple[int, PageToken | None]:
    """Parse and clamp offset pagination parameters."""
    limit = min(max(1, page_size), max_page_size)
    token_obj = None
    if page_token:
        try:
            token_obj = PageToken.from_string(page_token)
            limit = min(max(1, token_obj.limit), max_page_size)
        except ValueError:
            pass
    return limit, token_obj
