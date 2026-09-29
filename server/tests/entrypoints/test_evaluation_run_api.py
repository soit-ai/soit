"""A regression set runs on demand and its report is the one the publish gate would record."""

from __future__ import annotations

import pytest
from fastapi import status
from sqlmodel import select

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.commons.errors import KernelError
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.main import app
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.modules.evaluation.domain.models import RegressionCase, RegressionReport

CURRENT = "model:test:current"
CANDIDATE = "model:test:candidate"
MISSING = "model:test:missing"
ANSWERS = {CURRENT: "Refunds take 14 days.", CANDIDATE: "We do not refund."}


class _ModelAwareLLM(LLMPort):
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


async def _agent(async_client, name: str, *, publish: bool = True) -> tuple[str, str]:
    agent_id = (await async_client.post("/api/v1/agents", json={"name": name})).json()["data"]["id"]
    version = await async_client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"system_prompt": "Answer policy questions.", "bindings": {"model_ref": CURRENT}},
    )
    version_id = version.json()["data"]["id"]
    if publish:
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


@pytest.mark.asyncio
async def test_a_regression_set_runs_on_demand_and_records_its_report(async_client, async_db, ctx, llm) -> None:
    agent_id, version_id = await _agent(async_client, "support")
    refunds = await _case(async_db, ctx, agent_id, "refunds", ["14 days"])
    tone = await _case(async_db, ctx, agent_id, "tone", ["sorry"])

    response = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id})

    assert response.status_code == status.HTTP_201_CREATED, response.text
    report = response.json()["data"]
    assert report["subject_version_id"] == version_id
    assert report["summary_json"]["total"] == 2
    assert report["summary_json"]["passed"] == 1
    assert "model_ref" not in report["summary_json"]
    by_case = {item["case_id"]: item for item in report["case_results_json"]}
    assert by_case[refunds]["passed"] and not by_case[tone]["passed"]
    assert llm.models == [CURRENT, CURRENT]

    latest = await async_client.get(
        "/api/v1/evaluations/regression-reports/latest",
        params={"subject_kind": "agent", "subject_id": agent_id},
    )
    assert latest.json()["data"]["id"] == report["id"]


@pytest.mark.asyncio
async def test_a_run_on_another_model_is_recorded_but_is_no_baseline(async_client, async_db, ctx, llm) -> None:
    agent_id, _ = await _agent(async_client, "support")
    await _case(async_db, ctx, agent_id, "refunds", ["14 days"])

    first = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id})
    other = await async_client.post(
        "/api/v1/evaluations/run", json={"subject_id": agent_id, "model_ref": CANDIDATE}
    )
    again = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id})

    assert other.status_code == status.HTTP_201_CREATED, other.text
    assert other.json()["data"]["summary_json"]["model_ref"] == CANDIDATE
    assert other.json()["data"]["summary_json"]["passed"] == 0
    # The candidate's failure is not a regression of the version: the next run
    # compares to the first report, not to the candidate's.
    assert again.json()["data"]["summary_json"]["baseline_report_id"] == first.json()["data"]["id"]
    assert again.json()["data"]["summary_json"]["regressed"] == 0
    assert llm.models == [CURRENT, CANDIDATE, CURRENT]
    reports = (await async_db.exec(select(RegressionReport))).all()
    assert len(reports) == 3


@pytest.mark.asyncio
async def test_a_draft_version_can_be_evaluated_by_id(async_client, async_db, ctx) -> None:
    agent_id, version_id = await _agent(async_client, "draft-only", publish=False)
    await _case(async_db, ctx, agent_id, "refunds", ["14 days"])

    unnamed = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id})
    named = await async_client.post(
        "/api/v1/evaluations/run", json={"subject_id": agent_id, "subject_version_id": version_id}
    )

    assert unnamed.status_code == status.HTTP_400_BAD_REQUEST
    assert unnamed.json()["details"]["reason"] == "no_published_version"
    assert named.status_code == status.HTTP_201_CREATED, named.text
    assert named.json()["data"]["subject_version_id"] == version_id


@pytest.mark.asyncio
async def test_too_many_cases_and_an_unknown_agent_are_refused_before_anything_runs(
    async_client, async_db, ctx, llm
) -> None:
    agent_id, _ = await _agent(async_client, "support")
    for name in ("one", "two", "three"):
        await _case(async_db, ctx, agent_id, name, ["x"])

    too_many = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id, "max_cases": 2})
    unknown = await async_client.post("/api/v1/evaluations/run", json={"subject_id": "agt_nope"})
    empty = await async_client.post("/api/v1/evaluations/run", json={"subject_id": agent_id, "dataset": "none"})

    assert too_many.status_code == status.HTTP_400_BAD_REQUEST
    assert too_many.json()["details"] == {"case_count": 3, "max_cases": 2}
    assert unknown.status_code == status.HTTP_404_NOT_FOUND
    assert empty.status_code == status.HTTP_400_BAD_REQUEST
    assert llm.models == []
