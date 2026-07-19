"""Unit tests for the standalone Agent repositories."""

from datetime import UTC, datetime

from app.modules.agent.domain.models import (
    Agent,
    AgentBinding,
    AgentPublish,
    AgentVersion,
)
from app.modules.agent.infra.repository import (
    AgentBindingRepository,
    AgentPublishRepository,
    AgentRepository,
    AgentVersionRepository,
)


def test_agent_repository_create_list_and_update(db, tenant1_ctx):
    """AgentRepository should manage the new Agent aggregate tables."""

    repo = AgentRepository(db, tenant1_ctx)
    agent = repo.create(
        Agent(
            name="research-agent",
            description="first agent",
            visibility="workspace",
            default_model_ref="model:openai:gpt-5.1",
        )
    )

    assert agent.id.startswith("agt_")
    assert agent.tenant_id == tenant1_ctx.tenant_id
    assert repo.get_by_id(agent.id) is not None

    items = repo.list(limit=10, offset=0)
    assert [item.id for item in items] == [agent.id]

    agent.description = "updated"
    updated = repo.update(agent)
    assert updated.description == "updated"


def test_agent_version_binding_and_publish_repositories(db, tenant1_ctx):
    """Version, binding and publish records should hang off the new Agent tables."""

    agent_repo = AgentRepository(db, tenant1_ctx)
    version_repo = AgentVersionRepository(db, tenant1_ctx)
    binding_repo = AgentBindingRepository(db, tenant1_ctx)
    publish_repo = AgentPublishRepository(db, tenant1_ctx)

    agent = agent_repo.create(Agent(name="ops-agent"))
    version = version_repo.create(
        AgentVersion(
            agent_id=agent.id,
            version=agent_repo.next_version_number(agent.id),
            status="draft",
            spec_schema="agent.v1",
            spec_json={"model": {"ref_key": "model:openai:gpt-5.1"}},
        )
    )

    binding = binding_repo.create(
        AgentBinding(
            agent_id=agent.id,
            agent_version_id=version.id,
            binding_type="tool",
            target_key="tool:http:search",
            sort_order=10,
        )
    )
    publish = publish_repo.create(
        AgentPublish(
            agent_id=agent.id,
            agent_version_id=version.id,
            scope="workspace",
            status="published",
        )
    )

    assert version.id.startswith("agtv_")
    assert binding.id.startswith("agtb_")
    assert publish.id.startswith("agtp_")
    assert version_repo.list_by_agent(agent.id)[0].id == version.id
    assert binding_repo.list_for_version(version.id)[0].target_key == "tool:http:search"
    assert publish_repo.list_by_agent(agent.id)[0].agent_version_id == version.id


def test_agent_binding_repository_create_many_preserves_order(db, tenant1_ctx):
    agent_repo = AgentRepository(db, tenant1_ctx)
    version_repo = AgentVersionRepository(db, tenant1_ctx)
    binding_repo = AgentBindingRepository(db, tenant1_ctx)

    agent = agent_repo.create(Agent(name="bindings-agent"))
    version = version_repo.create(
        AgentVersion(
            agent_id=agent.id,
            version=agent_repo.next_version_number(agent.id),
            status="draft",
            spec_schema="agent.v1",
            spec_json={"model": {"ref_key": "model:openai:gpt-5.1"}},
        )
    )

    binding_repo.create_many(
        [
            AgentBinding(
                agent_id=agent.id,
                agent_version_id=version.id,
                binding_type="workflow",
                target_key="wf:handoff",
                sort_order=0,
            ),
            AgentBinding(
                agent_id=agent.id,
                agent_version_id=version.id,
                binding_type="tool",
                target_key="tool:http:search",
                sort_order=1,
            ),
        ]
    )

    bindings = binding_repo.list_for_version(version.id)
    assert [(binding.binding_type, binding.target_key) for binding in bindings] == [
        ("workflow", "wf:handoff"),
        ("tool", "tool:http:search"),
    ]


def test_agent_publish_repository_orders_equal_timestamps_by_ledger_sequence(db, tenant1_ctx):
    agent_repo = AgentRepository(db, tenant1_ctx)
    version_repo = AgentVersionRepository(db, tenant1_ctx)
    publish_repo = AgentPublishRepository(db, tenant1_ctx)
    agent = agent_repo.create(Agent(name="release-order-agent"))
    fixed_time = datetime(2026, 7, 18, tzinfo=UTC)

    for version_number, status in enumerate(("published", "published", "rolled_back"), start=1):
        version = version_repo.create(
            AgentVersion(
                agent_id=agent.id,
                version=version_number,
                status="published",
                spec_schema="agent.v1",
                spec_json={},
            )
        )
        publish_repo.create(
            AgentPublish(
                agent_id=agent.id,
                agent_version_id=version.id,
                status=status,
                created_at=fixed_time,
            )
        )

    releases = publish_repo.list_by_agent(agent.id)

    assert [release.status for release in releases] == ["rolled_back", "published", "published"]
    assert [release.sequence for release in releases] == [3, 2, 1]
