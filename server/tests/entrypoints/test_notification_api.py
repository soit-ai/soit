""" test_notification_api

Integration tests for Notification API endpoints.
"""

from fastapi import status

HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


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

    def test_preferences_endpoints_and_delivery_queue(self, client):
        default_response = client.get("/api/v1/notifications/preferences", headers=HEADERS)
        assert default_response.status_code == status.HTTP_200_OK
        assert default_response.json()["data"]["delivery_mode"] == "in_app"
        assert default_response.json()["data"]["categories"]["security"] is True

        endpoint_response = client.post(
            "/api/v1/notifications/endpoints",
            headers=HEADERS,
            json={
                "name": "Operations email",
                "kind": "email",
                "url": "mailto://user:password@example.com",
            },
        )
        assert endpoint_response.status_code == status.HTTP_201_CREATED
        endpoint = endpoint_response.json()["data"]
        assert endpoint["kind"] == "email"
        assert "password" not in endpoint["display_target"]
        assert "secret_ref" not in endpoint

        preference_response = client.put(
            "/api/v1/notifications/preferences",
            headers=HEADERS,
            json={
                "delivery_mode": "in_app_all",
                "categories": {"system": True, "security": False, "task": True},
                "quiet_hours_enabled": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
                "timezone": "Asia/Shanghai",
            },
        )
        assert preference_response.status_code == status.HTTP_200_OK
        assert preference_response.json()["data"]["categories"]["security"] is True

        notification_response = client.post(
            "/api/v1/notifications",
            headers=HEADERS,
            json={"title": "Outbound test", "type": "system", "content": "queued"},
        )
        notification_id = notification_response.json()["data"]["id"]
        deliveries_response = client.get(
            f"/api/v1/notifications/{notification_id}/deliveries",
            headers=HEADERS,
        )
        assert deliveries_response.status_code == status.HTTP_200_OK
        deliveries = deliveries_response.json()["data"]
        assert len(deliveries) == 1
        assert deliveries[0]["status"] == "queued"
        assert deliveries[0]["endpoint_id"] == endpoint["id"]

        test_response = client.post(
            f"/api/v1/notifications/endpoints/{endpoint['id']}/test",
            headers=HEADERS,
        )
        assert test_response.status_code == status.HTTP_202_ACCEPTED
        assert test_response.json()["data"]["status"] == "queued"
