"""test_regression_sets

A regression suite that covers one scenario is a demo. These check that the
shipped sets are real sets -- distinct scenarios, well-formed cases, and a
runner that takes its answers from the case rather than knowing them.
"""

import json

import pytest

from scripts.evaluate_support_ticket_regression import (
    REGRESSION_SETS_DIR,
    SupportTicketGoldenCase,
    _load_cases,
)

SET_PATHS = sorted(REGRESSION_SETS_DIR.glob("*.json"))


def test_at_least_three_scenarios_are_shipped():
    scenarios = set()
    for path in SET_PATHS:
        scenarios.update(case["scenario"] for case in json.loads(path.read_text(encoding="utf-8")))

    assert len(scenarios) >= 3, scenarios


@pytest.mark.parametrize("path", SET_PATHS, ids=lambda path: path.stem)
def test_a_set_loads_into_cases(path):
    cases = _load_cases(path)

    assert cases
    assert all(isinstance(case, SupportTicketGoldenCase) for case in cases)


@pytest.mark.parametrize("path", SET_PATHS, ids=lambda path: path.stem)
def test_a_set_holds_one_scenario(path):
    """Two reports are only comparable when they ran the same set."""
    assert len({case.scenario for case in _load_cases(path)}) == 1


@pytest.mark.parametrize("path", SET_PATHS, ids=lambda path: path.stem)
def test_case_ids_are_unique_within_a_set(path):
    case_ids = [case.case_id for case in _load_cases(path)]

    assert len(case_ids) == len(set(case_ids))


@pytest.mark.parametrize("path", SET_PATHS, ids=lambda path: path.stem)
def test_every_case_asserts_something_about_the_answer(path):
    """A case with no expectation passes whatever the agent says."""
    for case in _load_cases(path):
        assert case.minimum_answer_terms, case.case_id
        assert case.expected_citation_source, case.case_id


@pytest.mark.parametrize("path", SET_PATHS, ids=lambda path: path.stem)
def test_a_cases_own_answer_satisfies_its_own_expectations(path):
    """Otherwise the set is unpassable and says nothing about a change."""
    for case in _load_cases(path):
        if case.answer is None:
            continue
        answer = case.answer.lower()
        for term in case.minimum_answer_terms:
            assert term.lower() in answer, f"{case.case_id}: {term}"


def test_the_scenarios_exercise_different_behaviour():
    """Three sets of the same shape would be one set copied three times."""
    shapes = set()
    for path in SET_PATHS:
        cases = _load_cases(path)
        shapes.add(
            (
                any(case.expect_tool_call for case in cases),
                any(case.expect_workflow_child_run for case in cases),
                all(not case.expect_tool_call for case in cases),
            )
        )

    assert len(shapes) >= 2


@pytest.mark.asyncio
async def test_the_runner_answers_with_the_cases_own_text():
    """A runner that knows the answer can only ever test one scenario."""
    from app.kernel.ports.llm.interface import ChatMessage
    from scripts.evaluate_support_ticket_regression import (
        SupportTicketEvaluationLLMPort,
    )

    case = SupportTicketGoldenCase(
        case_id="c1",
        prompt="anything",
        expected_citation_source="refund-policy.md",
        expect_tool_call=False,
        expect_workflow_child_run=False,
        expect_audit=False,
        answer="A scenario-specific reply.",
    )
    port = SupportTicketEvaluationLLMPort(case, workflow_ref="wf:x", workflow_inputs={})

    response = await port.chat([ChatMessage(role="user", content="hi")], model="model:test:primary")

    assert response.text == "A scenario-specific reply."
