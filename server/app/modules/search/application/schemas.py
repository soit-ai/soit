"""Global search API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SearchKind = Literal[
    "agent",
    "workflow",
    "knowledge",
    "plugin",
    "model",
    "thread",
    "run",
]


class GlobalSearchResult(BaseModel):
    kind: SearchKind
    id: str
    title: str
    subtitle: str | None = None
    status: str | None = None
    url: str
    updated_at: datetime | None = None


class GlobalSearchResponse(BaseModel):
    query: str
    items: list[GlobalSearchResult]
    counts: dict[SearchKind, int] = Field(default_factory=dict)
