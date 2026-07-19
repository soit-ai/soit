"""Product feedback API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FeedbackCategory = Literal["bug", "feature", "performance", "usability", "other"]
FeedbackPriority = Literal["low", "medium", "high", "critical"]
FeedbackStatus = Literal["open", "in_progress", "resolved", "closed"]


class FeedbackContext(BaseModel):
    page_path: str | None = Field(default=None, max_length=512)
    app_version: str | None = Field(default=None, max_length=32)
    browser: str | None = Field(default=None, max_length=128)
    os: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")


class ProductFeedbackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: FeedbackCategory = "other"
    priority: FeedbackPriority = "medium"
    context: FeedbackContext = Field(default_factory=FeedbackContext)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductFeedbackUpdate(BaseModel):
    status: FeedbackStatus | None = None
    priority: FeedbackPriority | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_resolution(self) -> "ProductFeedbackUpdate":
        if self.status in {"resolved", "closed"} and not self.resolution_note:
            raise ValueError("resolution_note is required when feedback is resolved or closed")
        if self.status is None and self.priority is None and self.resolution_note is None:
            raise ValueError("at least one feedback field must be updated")
        return self


class ProductFeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    title: str
    description: str
    category: FeedbackCategory
    priority: FeedbackPriority
    status: FeedbackStatus
    context_json: dict[str, object]
    created_by: str
    updated_by: str
    resolved_by: str | None
    resolution_note: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductFeedbackSummary(BaseModel):
    total: int
    by_status: dict[FeedbackStatus, int]
    by_category: dict[FeedbackCategory, int]
    by_priority: dict[FeedbackPriority, int]
