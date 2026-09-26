"""Virtual models: kept by modelhub, called through the gateway, failed over by policy."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.llm.virtual_model_resolver import DatabaseVirtualModelResolver
from app.kernel.commons.errors import TimeoutError as KernelTimeoutError
from app.kernel.ports.llm.interface import ChatResponse
from app.kernel.runtime.db.models.runs import RunStep
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.wiring import get_container

LIVE = "model:openai-main:gpt-live"
BACKUP = "model:openai-main:gpt-backup"
BASE = "/api/v1/modelhub/virtual-models"


@pytest_asyncio.fixture
async def workspace_models(async_db, ctx) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    provider = Provider(**scope, kind="openai", slug="openai-main", name="OpenAI main")
    async_db.add(provider)
    for model_id in ("gpt-live", "gpt-backup"):
        async_db.add(
            ProviderModel(**scope, provider_id=provider.id, provider_kind="openai", model_id=model_id)
        )
    await async_db.commit()


@pytest.fixture
def resolver_on_test_db(async_db):
    container = get_container()
    original = container.get("virtual_model_resolver")
    container.register_singleton(
        "virtual_model_resolver",
        DatabaseVirtualModelResolver(
            lambda: AsyncSession(bind=async_db.bind, expire_on_commit=False)
        ),
    )
    yield
    container.register_singleton("virtual_model_resolver", original)


async def _create(async_client, **fields: Any):
    body = {"slug": "fast", "name": "Fast chat", "targets": [LIVE, BACKUP], **fields}
    return await async_client.post(BASE, json=body)


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_models")
async def test_virtual_models_are_created_listed_changed_and_removed(async_client) -> None:
    created = await _create(async_client)
    assert created.status_code == 201
    item = created.json()["data"]
    assert item["model_ref"] == "vmodel:fast"
    assert item["targets"] == [LIVE, BACKUP]

    assert (await _create(async_client)).status_code == 409
    listed = (await async_client.get(BASE)).json()["data"]
    assert [model["slug"] for model in listed] == ["fast"]

    changed = await async_client.patch(
        f"{BASE}/{item['id']}", json={"targets": [BACKUP, LIVE], "status": "disabled"}
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["targets"] == [BACKUP, LIVE]
    assert changed.json()["data"]["status"] == "disabled"

    assert (await async_client.delete(f"{BASE}/{item['id']}")).status_code == 204
    assert (await async_client.get(f"{BASE}/{item['id']}")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_models")
async def test_targets_must_be_concrete_models_of_the_workspace(async_client) -> None:
    unknown = await _create(async_client, targets=[LIVE, "model:openai-main:gpt-typo"])
    assert unknown.status_code == 400
    assert unknown.json()["details"]["unknown"] == ["model:openai-main:gpt-typo"]

    nested = await _create(async_client, targets=["vmodel:other"])
    assert nested.status_code == 400
    duplicated = await _create(async_client, targets=[LIVE, LIVE])
    assert duplicated.status_code == 400


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_models", "resolver_on_test_db")
async def test_the_gateway_calls_a_virtual_model_and_lists_it(async_client, async_db) -> None:
    await _create(async_client)

    listed = await async_client.get("/v1/models")
    response = await async_client.post(
        "/v1/chat/completions",
        json={"model": "vmodel:fast", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert "vmodel:fast" in [model["id"] for model in listed.json()["data"]]
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"
    step = (
        await async_db.exec(
            select(RunStep).where(RunStep.run_id == response.headers["x-soit-run-id"])
        )
    ).first()
    assert step.metrics_json["attempts"] == [{"model_ref": LIVE, "outcome": "succeeded"}]


class _FirstTargetTimesOut:
    def __init__(self) -> None:
        self.models: list[str] = []

    async def chat(self, *, model: str, **kwargs: Any) -> ChatResponse:
        self.models.append(model)
        if model == LIVE:
            raise KernelTimeoutError("provider timed out", {"model": model})
        return ChatResponse(text=f"served by {model}", tokens_prompt=1, tokens_completion=1)


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_models", "resolver_on_test_db")
async def test_a_timed_out_target_fails_over_to_the_next(async_client, async_db) -> None:
    await _create(async_client)
    container = get_container()
    original = container.get("llm_port")
    port = _FirstTargetTimesOut()
    container.register_singleton("llm_port", port)
    try:
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": "vmodel:fast", "messages": [{"role": "user", "content": "hello"}]},
        )
    finally:
        container.register_singleton("llm_port", original)

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == f"served by {BACKUP}"
    assert port.models == [LIVE, BACKUP]
    step = (
        await async_db.exec(
            select(RunStep).where(RunStep.run_id == response.headers["x-soit-run-id"])
        )
    ).first()
    assert step.metrics_json["attempts"] == [
        {"model_ref": LIVE, "outcome": "failed", "reason": "TIMEOUT"},
        {"model_ref": BACKUP, "outcome": "succeeded"},
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_models", "resolver_on_test_db")
async def test_a_disabled_virtual_model_is_not_found(async_client) -> None:
    item = (await _create(async_client)).json()["data"]
    await async_client.patch(f"{BASE}/{item['id']}", json={"status": "disabled"})

    response = await async_client.post(
        "/v1/chat/completions",
        json={"model": "vmodel:fast", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_runtime_not_found"
