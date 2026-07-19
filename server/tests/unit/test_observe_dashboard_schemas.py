from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.observe.application.dashboard_schemas import DashboardSectionResponse


def test_dashboard_section_rejects_charts_from_another_tab() -> None:
    adapter = TypeAdapter(DashboardSectionResponse)
    payload = {
        "id": "tool_reliability",
        "summary_cards": [],
        "charts": {
            "trend": [],
            "error_distribution": [],
            "health_distribution": [{"status": "healthy", "count": 1}],
            "alert_compression": {"raw_alerts": 1, "compressed_alerts": 1},
        },
        "rows": [],
        "page": {"page_size": 0, "next_page_token": None, "total_count": 0},
        "empty_state": {"title": "暂无数据", "description": "暂无数据"},
    }

    with pytest.raises(ValidationError):
        adapter.validate_python(payload)
