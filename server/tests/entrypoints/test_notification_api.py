""" test_notification_api

Integration tests for Notification API endpoints.
"""

import pytest
from fastapi import status
from sqlmodel import select

from app.modules.notification.domain.models import NotificationEndpoint
from app.modules.secrets.domain.models import Secret

HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


class TestNotificationAPI:
    """Test notification API endpoints."""

    @pytest.mark.asyncio
    async def test_create_and_list_notifications(self, async_client):
        response = await async_client.post(
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

        list_response = await async_client.get(
            "/api/v1/notifications",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True
        items = list_data["data"]["items"]
        assert isinstance(items, list)
        assert any(item["id"] == payload["id"] for item in items)

    @pytest.mark.asyncio
    async def test_unread_count_and_mark_read(self, async_client):
        create_response = await async_client.post(
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

        count_response = await async_client.get(
            "/api/v1/notifications/unread-count",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert count_response.status_code == status.HTTP_200_OK
        count_data = count_response.json()
        assert count_data["success"] is True
        assert count_data["data"]["count"] >= 1

        read_response = await async_client.post(
            f"/api/v1/notifications/{notification_id}/read",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert read_response.status_code == status.HTTP_200_OK
        read_data = read_response.json()
        assert read_data["success"] is True
        assert read_data["data"]["status"] == "read"

    @pytest.mark.asyncio
    async def test_mark_all_read(self, async_client):
        await async_client.post(
            "/api/v1/notifications",
            json={"title": "Reminder", "type": "reminder"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        await async_client.post(
            "/api/v1/notifications",
            json={"title": "Message", "type": "message"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )

        bulk_response = await async_client.post(
            "/api/v1/notifications/read",
            json={"all": True},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert bulk_response.status_code == status.HTTP_200_OK
        bulk_data = bulk_response.json()
        assert bulk_data["success"] is True
        assert bulk_data["data"]["updated"] >= 1

    @pytest.mark.asyncio
    async def test_preferences_endpoints_and_delivery_queue(self, async_client, async_db):
        default_response = await async_client.get("/api/v1/notifications/preferences", headers=HEADERS)
        assert default_response.status_code == status.HTTP_200_OK
        assert default_response.json()["data"]["delivery_mode"] == "in_app"
        assert default_response.json()["data"]["categories"]["security"] is True

        endpoint_response = await async_client.post(
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
        assert "secret_id" not in endpoint
        endpoint_row = (await async_db.exec(
            select(NotificationEndpoint).where(NotificationEndpoint.id == endpoint["id"])
        )).one()
        secret_row = (await async_db.exec(
            select(Secret).where(Secret.id == endpoint_row.secret_id)
        )).one()
        assert secret_row.tenant_id == endpoint_row.tenant_id
        assert secret_row.workspace_id == endpoint_row.workspace_id

        preference_response = await async_client.put(
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

        notification_response = await async_client.post(
            "/api/v1/notifications",
            headers=HEADERS,
            json={"title": "Outbound test", "type": "system", "content": "queued"},
        )
        notification_id = notification_response.json()["data"]["id"]
        deliveries_response = await async_client.get(
            f"/api/v1/notifications/{notification_id}/deliveries",
            headers=HEADERS,
        )
        assert deliveries_response.status_code == status.HTTP_200_OK
        deliveries = deliveries_response.json()["data"]
        assert len(deliveries) == 1
        assert deliveries[0]["status"] == "queued"
        assert deliveries[0]["endpoint_id"] == endpoint["id"]

        test_response = await async_client.post(
            f"/api/v1/notifications/endpoints/{endpoint['id']}/test",
            headers=HEADERS,
        )
        assert test_response.status_code == status.HTTP_202_ACCEPTED
        assert test_response.json()["data"]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_workspace_endpoints_are_kept_by_admins(self, async_client, ctx):
        created = await async_client.post(
            "/api/v1/notifications/workspace-endpoints",
            headers=HEADERS,
            json={
                "name": "Team channel",
                "kind": "webhook",
                "url": "json://hooks.example.com/team",
                "categories": ["alert", "task"],
            },
        )
        assert created.status_code == status.HTTP_201_CREATED
        endpoint = created.json()["data"]
        assert (endpoint["scope"], endpoint["categories"]) == ("workspace", ["alert", "task"])

        personal = await async_client.get("/api/v1/notifications/endpoints", headers=HEADERS)
        assert all(item["id"] != endpoint["id"] for item in personal.json()["data"])
        listed = await async_client.get("/api/v1/notifications/workspace-endpoints", headers=HEADERS)
        assert [item["id"] for item in listed.json()["data"]] == [endpoint["id"]]
        tested = await async_client.post(
            f"/api/v1/notifications/workspace-endpoints/{endpoint['id']}/test", headers=HEADERS
        )
        assert tested.status_code == status.HTTP_202_ACCEPTED

        import dataclasses

        from app.main import app
        from app.middleware.auth import get_current_context

        developer = dataclasses.replace(ctx, workspace_role="Dev", tenant_role=None)
        app.dependency_overrides[get_current_context] = lambda: developer
        try:
            refused = await async_client.get(
                "/api/v1/notifications/workspace-endpoints", headers=HEADERS
            )
        finally:
            app.dependency_overrides[get_current_context] = lambda: ctx
        assert refused.status_code == status.HTTP_403_FORBIDDEN

        removed = await async_client.delete(
            f"/api/v1/notifications/workspace-endpoints/{endpoint['id']}", headers=HEADERS
        )
        assert removed.status_code == status.HTTP_204_NO_CONTENT
