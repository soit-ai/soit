"""The dataset case line format: validation, round trip and content hashing."""

from __future__ import annotations

import json

import pytest

from app.kernel.commons.errors import ValidationError
from app.modules.evaluation.application import dataset_format as fmt


def _line(**overrides) -> str:
    document = {
        "name": "refund-window",
        "input": "How long do refunds take?",
        "expected_features": {"minimum_output_terms": ["14 days"]},
    }
    document.update(overrides)
    return json.dumps(document)


def test_a_valid_file_parses_into_cases_in_order() -> None:
    content = "\n".join(
        [
            _line(name="a"),
            "",
            _line(name="b", input={"messages": [{"role": "user", "content": "hi"}]}),
        ]
    )

    cases = fmt.parse_jsonl(content)

    assert [case.name for case in cases] == ["a", "b"]
    assert cases[0].input_snapshot == {"input": "How long do refunds take?"}
    assert cases[1].input_snapshot == {"messages": [{"role": "user", "content": "hi"}]}


def test_every_bad_line_is_reported_with_its_number_and_nothing_parses() -> None:
    content = "\n".join(
        [
            _line(name="ok"),
            "{not json",
            _line(name="no-expectation", expected_features={}),
            "",
            _line(name="unknown-key", expected_features={"minimum_terms": ["x"]}),
            _line(name="ok"),
        ]
    )

    with pytest.raises(ValidationError) as caught:
        fmt.parse_jsonl(content)

    errors = caught.value.details["errors"]
    by_line = {}
    for item in errors:
        by_line.setdefault(item["line"], []).append(item["message"])
    assert set(by_line) == {2, 3, 5, 6}
    assert "not valid JSON" in by_line[2][0]
    assert "duplicate case name 'ok' (first on line 1)" in by_line[6][0]
    assert caught.value.details["error_count"] == len(errors)


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"input": ""},
        {"input": {}},
        {"input": 5},
        {"expected_features": {"max_latency_ms": 0}},
        {"expected_features": {"max_cost_amount": -1}},
        {"expected_features": {"minimum_output_terms": []}},
        {"expected_features": {"minimum_output_terms": [""]}},
        {"expected_features": {"llm_judge": {"min_score": 0.5}}},
        {"expected_features": {"llm_judge": {"rubric": "ok", "min_score": 2}}},
        {"extra": True},
    ],
)
def test_a_case_that_breaks_the_schema_is_refused(overrides) -> None:
    with pytest.raises(ValidationError):
        fmt.parse_jsonl(_line(**overrides))


def test_every_scorer_is_accepted() -> None:
    cases = fmt.parse_jsonl(
        _line(
            expected_features={
                "minimum_output_terms": ["a"],
                "max_latency_ms": 500,
                "max_cost_amount": 0.25,
                "llm_judge": {"rubric": "Is it polite?", "min_score": 0.8, "model": "model:x"},
            }
        )
    )

    assert len(cases) == 1


def test_size_and_line_limits_refuse_the_whole_file() -> None:
    with pytest.raises(ValidationError, match="no cases"):
        fmt.parse_jsonl("\n  \n")
    many = "\n".join(_line(name=f"c{i}") for i in range(fmt.MAX_IMPORT_LINES + 1))
    with pytest.raises(ValidationError, match="limit"):
        fmt.parse_jsonl(many)
    with pytest.raises(ValidationError, match="larger than"):
        fmt.parse_jsonl(_line(input="x" * (fmt.MAX_IMPORT_BYTES + 1)))


def test_text_and_object_inputs_round_trip_through_the_snapshot() -> None:
    assert fmt.snapshot_to_input({"input": "hello"}) == "hello"
    assert fmt.input_to_snapshot("hello") == {"input": "hello"}
    nested = {"input": {"a": 1}}
    assert fmt.snapshot_to_input(nested) == nested
    assert fmt.input_to_snapshot(fmt.snapshot_to_input(nested)) == nested
    messages = {"messages": [{"role": "user", "content": "hi"}], "input_summary": "hi"}
    assert fmt.input_to_snapshot(fmt.snapshot_to_input(messages)) == messages


def test_rendered_jsonl_parses_back_to_the_same_cases() -> None:
    documents = [
        fmt.case_document("a", {"input": "one"}, {"max_latency_ms": 5}),
        fmt.case_document("b", {"messages": [{"role": "user", "content": "café"}]}, {"minimum_output_terms": ["x"]}),
    ]

    parsed = fmt.parse_jsonl(fmt.render_jsonl(documents))

    assert [case.as_dict() for case in parsed] == documents


def test_the_content_hash_ignores_order_and_follows_content() -> None:
    first = fmt.case_document("a", {"input": "one"}, {"max_latency_ms": 5})
    second = fmt.case_document("b", {"input": "two"}, {"max_latency_ms": 5})
    changed = fmt.case_document("b", {"input": "two"}, {"max_latency_ms": 6})

    assert fmt.content_hash([first, second]) == fmt.content_hash([second, first])
    assert fmt.content_hash([first, second]) != fmt.content_hash([first, changed])
    assert len(fmt.content_hash([])) == 64


def test_snapshots_are_diffed_by_case_name() -> None:
    a = fmt.case_document("a", {"input": "one"}, {"max_latency_ms": 5})
    b = fmt.case_document("b", {"input": "two"}, {"max_latency_ms": 5})
    b2 = fmt.case_document("b", {"input": "two"}, {"max_latency_ms": 9})
    c = fmt.case_document("c", {"input": "three"}, {"max_latency_ms": 5})

    assert fmt.diff_snapshots([a, b], [b2, c]) == {"added": 1, "removed": 1, "changed": 1}
    assert fmt.diff_snapshots([], [a]) == {"added": 1, "removed": 0, "changed": 0}
