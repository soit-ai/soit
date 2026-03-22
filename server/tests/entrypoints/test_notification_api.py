""" test_notification_api

Integration tests for Notification API endpoints.
"""

from fastapi import status


class TestNotificationAPI:
    """Test notification API endpoints."""

    def test_create_and_list_notifications(self, client):
        response = client.post(
            "/api/v1/notifications",
            json={
                "title": "System update",
                "content": "Maintenance tonight",
                "type": "system",
                "severity": "info",
                "source_module": "system",
                "action": {"route": "/settings"},
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["title"] == "System update"
        assert payload["status"] == "unread"

        list_response = client.get(
            "/api/v1/notifications",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True
        items = list_data["data"]["items"]
        assert isinstance(items, list)
        assert any(item["id"] == payload["id"] for item in items)

    def test_unread_count_and_mark_read(self, client):
        create_response = client.post(
            "/api/v1/notifications",
            json={
                "title": "Alert",
                "content": "Knowledge warning",
                "type": "alert",
                "severity": "warning",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        notification_id = create_response.json()["data"]["id"]

        count_response = client.get(
            "/api/v1/notifications/unread-count",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert count_response.status_code == status.HTTP_200_OK
        count_data = count_response.json()
        assert count_data["success"] is True
        assert count_data["data"]["count"] >= 1

        read_response = client.post(
            f"/api/v1/notifications/{notification_id}/read",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert read_response.status_code == status.HTTP_200_OK
        read_data = read_response.json()
        assert read_data["success"] is True
        assert read_data["data"]["status"] == "read"

    def test_mark_all_read(self, client):
        client.post(
            "/api/v1/notifications",
            json={"title": "Reminder", "type": "reminder"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        client.post(
            "/api/v1/notifications",
            json={"title": "Message", "type": "message"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )

        bulk_response = client.post(
            "/api/v1/notifications/read",
            json={"all": True},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert bulk_response.status_code == status.HTTP_200_OK
        bulk_data = bulk_response.json()
        assert bulk_data["success"] is True
        assert bulk_data["data"]["updated"] >= 1
