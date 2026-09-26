"""Regression sets replay on a candidate model next to the model they use."""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.commons.errors import KernelError
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.runs import Run
from app.main import app
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.modules.evaluation.domain.models import RegressionCase, RegressionReport

pytestmark = pytest.mark.asyncio

CURRENT = "model:test:current"
NEXT = "model:test:next"
MISSING = "model:test:missing"
ANSWERS = {
    CURRENT: "Refunds are issued within 14 days. Exchanges take a week.",
    NEXT: "Refunds are issued within 14 days, and exchanges within 5 days.",
}


class _ModelAwareLLM(LLMPort):
    """Each model answers the way that model would."""

    def __init__(self) -> None:
        self.models: list[str] = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        self.models.append(model)
        if model == MISSING:
            raise KernelError("MODEL_RUNTIME_NOT_FOUND", f"No model could serve: {model}")
        return ChatResponse(text=ANSWERS[model], tokens_prompt=3, tokens_completion=5, finish_reason="stop")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class _Tools(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={})


@pytest.fixture
def llm() -> _ModelAwareLLM:
    return _ModelAwareLLM()


@pytest.fixture(autouse=True)
def _agents(async_db, ctx, llm):
    async def build() -> AgentApplicationService:
        return AgentApplicationService(
            db=async_db,
            ctx=ctx,
            llm_port=llm,
            tool_port=_Tools(),
            regression_evaluator=RegressionEvaluationService(db=async_db, ctx=ctx),
        )

    app.dependency_overrides[get_agent_application_service] = build
    yield
    app.dependency_overrides.pop(get_agent_application_service, None)


async def _published_agent(async_client, name: str) -> tuple[str, str]:
    agent_id = (await async_client.post("/api/v1/agents", json={"name": name})).json()["data"]["id"]
    version = await async_client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"system_prompt": "Answer policy questions.", "bindings": {"model_ref": CURRENT}},
    )
    version_id = version.json()["data"]["id"]
    published = await async_client.post(f"/api/v1/agents/{agent_id}/publish", json={"version_id": version_id})
    assert published.status_code == 200, published.text
    return agent_id, version_id


async def _case(async_db, ctx, agent_id: str, name: str, terms: list[str], dataset: str = "default") -> str:
    case = RegressionCase(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_kind="agent",
        subject_id=agent_id,
        source_run_id=f"run_source_{name}",
        name=name,
        dataset=dataset,
        input_snapshot_json={"input": f"Question about {name}"},
        expected_features_json={"minimum_output_terms": terms},
    )
    async_db.add(case)
    await async_db.commit()
    return case.id


async def test_every_case_runs_on_both_models_and_the_difference_is_reported(
    async_client, async_db, ctx, llm
) -> None:
    agent_id, version_id = await _published_agent(async_client, "policy-agent")
    refunds = await _case(async_db, ctx, agent_id, "refunds", ["14 days"])
    exchanges = await _case(async_db, ctx, agent_id, "exchanges", ["a week"])
    faster = await _case(async_db, ctx, agent_id, "faster-exchanges", ["5 days"])

    response = await async_client.post("/api/v1/evaluations/model-replays", json={"model_ref": NEXT})

    assert response.status_code == 201, response.text
    replay = response.json()["data"]
    assert (replay["model_ref"], replay["case_count"]) == (NEXT, 3)
    assert sorted(llm.models) == sorted([CURRENT] * 3 + [NEXT] * 3)
    [subject] = replay["subjects"]
    assert (subject["agent_id"], subject["version_id"], subject["baseline_model_ref"]) == (
        agent_id,
        version_id,
        CURRENT,
    )
    assert (subject["baseline"]["passed"], subject["candidate"]["passed"]) == (2, 2)
    assert subject["regressed"] == [exchanges]
    assert subject["fixed"] == [faster]
    cases = {case["case_id"]: case for case in subject["cases"]}
    assert cases[refunds]["baseline"]["passed"] and cases[refunds]["candidate"]["passed"]
    assert cases[exchanges]["candidate"]["failure_reasons"] == ["output missing term: a week"]
    totals = replay["totals"]
    assert (totals["baseline"]["pass_rate"], totals["candidate"]["pass_rate"]) == (0.6667, 0.6667)
    assert totals["delta"]["pass_rate"] == 0.0
    assert (totals["regressed"], totals["fixed"]) == (1, 1)

    # Every replayed run is a rehearsal, so it is kept out of spend and dashboards.
    runs = (await async_db.exec(select(Run).where(Run.subject_id == agent_id))).all()
    assert len(runs) == 6 and all(run.sandbox for run in runs)
    # And no replay becomes the baseline a publish is compared against.
    assert (await async_db.exec(select(RegressionReport))).all() == []

    listed = await async_client.get("/api/v1/evaluations/model-replays")
    detail = await async_client.get(f"/api/v1/evaluations/model-replays/{replay['id']}")
    assert [item["id"] for item in listed.json()["data"]] == [replay["id"]]
    assert "subjects" not in listed.json()["data"][0]
    assert detail.json()["data"]["subjects"][0]["regressed"] == [exchanges]


async def test_a_replay_can_be_narrowed_to_agents_and_a_dataset(async_client, async_db, ctx) -> None:
    first, _ = await _published_agent(async_client, "first-agent")
    second, _ = await _published_agent(async_client, "second-agent")
    await _case(async_db, ctx, first, "smoke", ["14 days"], dataset="smoke")
    await _case(async_db, ctx, first, "full", ["14 days"], dataset="full")
    await _case(async_db, ctx, second, "other", ["14 days"], dataset="smoke")

    response = await async_client.post(
        "/api/v1/evaluations/model-replays",
        json={"model_ref": NEXT, "agent_ids": [first], "dataset": "smoke"},
    )

    replay = response.json()["data"]
    assert replay["case_count"] == 1
    assert [(subject["agent_id"], subject["dataset"]) for subject in replay["subjects"]] == [(first, "smoke")]


async def test_a_replay_larger_than_its_limit_is_refused_before_anything_runs(
    async_client, async_db, ctx, llm
) -> None:
    agent_id, _ = await _published_agent(async_client, "big-agent")
    for index in range(3):
        await _case(async_db, ctx, agent_id, f"case-{index}", ["14 days"])

    response = await async_client.post(
        "/api/v1/evaluations/model-replays", json={"model_ref": NEXT, "max_cases": 2}
    )

    assert response.status_code == 400
    assert response.json()["details"] == {"case_count": 3, "max_cases": 2}
    assert llm.models == []


async def test_a_model_that_cannot_serve_stops_the_replay(async_client, async_db, ctx) -> None:
    agent_id, _ = await _published_agent(async_client, "policy-agent")
    await _case(async_db, ctx, agent_id, "refunds", ["14 days"])

    response = await async_client.post("/api/v1/evaluations/model-replays", json={"model_ref": MISSING})

    assert response.status_code == 404
    assert response.json()["code"] == "MODEL_RUNTIME_NOT_FOUND"
    listed = await async_client.get("/api/v1/evaluations/model-replays")
    assert listed.json()["data"] == []


async def test_agents_without_a_published_version_are_skipped_and_said_so(async_client, async_db, ctx) -> None:
    agent_id, _ = await _published_agent(async_client, "live-agent")
    draft_id = (await async_client.post("/api/v1/agents", json={"name": "draft-agent"})).json()["data"]["id"]
    await _case(async_db, ctx, agent_id, "refunds", ["14 days"])
    await _case(async_db, ctx, draft_id, "draft-case", ["14 days"])

    replay = (await async_client.post("/api/v1/evaluations/model-replays", json={"model_ref": NEXT})).json()["data"]

    assert [subject["agent_id"] for subject in replay["subjects"]] == [agent_id]
    assert replay["totals"]["skipped"] == [
        {"agent_id": draft_id, "agent_name": "draft-agent", "reason": "no_published_version"}
    ]


async def test_nothing_to_replay_is_a_clear_refusal(async_client) -> None:
    response = await async_client.post("/api/v1/evaluations/model-replays", json={"model_ref": NEXT})

    assert response.status_code == 400
    assert "no regression cases" in response.json()["message"]
