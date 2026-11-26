"""List endpoints read related rows in one query per list, not one per row."""

from datetime import UTC, datetime

import pytest

from app.kernel.contracts.context import RequestContext
from app.modules.identity.domain.models import User
from app.modules.identity.infra.repository import UserRepository
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.modelhub.infra.repository import ProviderModelRepository
from app.modules.plugin.domain.models import PluginInstallation
from app.modules.plugin.infra.repository import PluginInstallationRepository


@pytest.fixture
def scope() -> RequestContext:
    return RequestContext(tenant_id="t1", workspace_id="w1", user_id="u1", workspace_role="Owner")


@pytest.mark.asyncio
async def test_users_are_read_together_and_unknown_ids_are_absent(async_db):
    async_db.add(User(id="usr_a", email="a@example.com", password_hash="x"))
    async_db.add(User(id="usr_b", email="b@example.com", password_hash="x"))
    await async_db.commit()

    users = await UserRepository(async_db).get_by_ids(["usr_a", "usr_b", "usr_gone", "usr_a"])

    assert sorted(users) == ["usr_a", "usr_b"]
    assert users["usr_b"].email == "b@example.com"
    assert await UserRepository(async_db).get_by_ids([]) == {}


@pytest.mark.asyncio
async def test_provider_sync_times_are_grouped_per_provider_and_scoped(async_db, scope):
    early = datetime(2026, 11, 1, tzinfo=UTC)
    late = datetime(2026, 11, 20, tzinfo=UTC)
    for provider_id, model_id, synced, workspace in (
        ("prv_1", "m1", early, "w1"),
        ("prv_1", "m2", late, "w1"),
        ("prv_2", "m3", early, "w1"),
        ("prv_2", "m4", late, "w2"),
    ):
        async_db.add(
            ProviderModel(
                tenant_id="t1",
                workspace_id=workspace,
                provider_id=provider_id,
                provider_kind="openai",
                model_id=model_id,
                last_synced_at=synced,
            )
        )
    await async_db.commit()

    synced_at = await ProviderModelRepository(async_db, scope).latest_synced_at_by_providers(
        ["prv_1", "prv_2", "prv_3"]
    )

    assert set(synced_at) == {"prv_1", "prv_2"}
    assert synced_at["prv_1"].replace(tzinfo=UTC) == late
    # The later sync belongs to another workspace.
    assert synced_at["prv_2"].replace(tzinfo=UTC) == early


@pytest.mark.asyncio
async def test_plugin_installations_are_read_together_for_this_workspace(async_db, scope):
    async_db.add(PluginInstallation(tenant_id="t1", workspace_id="w1", plugin_id="plg_1"))
    async_db.add(PluginInstallation(tenant_id="t1", workspace_id="w2", plugin_id="plg_2"))
    await async_db.commit()

    installations = await PluginInstallationRepository(async_db, scope).get_by_plugins(["plg_1", "plg_2"])

    assert list(installations) == ["plg_1"]
