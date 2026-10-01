"""The line format datasets are imported from and exported to.

One case per line of a JSONL file, each line an object validated against the
``dataset_case_spec`` schema. The same document is what a dataset version
snapshot holds, so an export, a snapshot and an import all speak one shape.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.specs import validator

CASE_SCHEMA = "dataset_case_spec"
MAX_IMPORT_LINES = 1000
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_REPORTED_ERRORS = 100


@dataclass(frozen=True)
class DatasetCaseDocument:
    """One case as a dataset holds it, before it becomes a row."""

    name: str
    input: str | dict[str, Any]
    expected_features: dict[str, Any]

    @property
    def input_snapshot(self) -> dict[str, Any]:
        return input_to_snapshot(self.input)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input": self.input,
            "expected_features": self.expected_features,
        }


def input_to_snapshot(value: str | dict[str, Any]) -> dict[str, Any]:
    """The ``input_snapshot_json`` a case stores for an imported ``input``.

    Text becomes ``{"input": text}``, which the agent runner sends as it is; an
    object is kept whole, since it may carry ``messages`` or ``input_summary``.
    """
    if isinstance(value, str):
        return {"input": value}
    return dict(value)


def snapshot_to_input(snapshot: dict[str, Any] | None) -> str | dict[str, Any]:
    """Inverse of :func:`input_to_snapshot`, so an export imports back unchanged."""
    snapshot = dict(snapshot or {})
    if set(snapshot) == {"input"} and isinstance(snapshot["input"], str):
        return snapshot["input"]
    return snapshot


def case_document(
    name: str, input_snapshot: dict[str, Any] | None, expected_features: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "name": name,
        "input": snapshot_to_input(input_snapshot),
        "expected_features": dict(expected_features or {}),
    }


def schema_errors(document: Any) -> list[str]:
    """Why a case document does not satisfy the schema, one message per problem."""
    if not isinstance(document, dict):
        return ["each case must be a JSON object"]
    issues = validator.validate(CASE_SCHEMA, document, raise_on_error=False)
    return [f"{issue.instance_path or '/'}: {issue.message}" for issue in issues]


def validate_case(document: dict[str, Any]) -> DatasetCaseDocument:
    """Check one case given through the API and return it, or refuse it with why."""
    errors = schema_errors(document)
    if errors:
        raise ValidationError(
            "The case does not match the dataset case format",
            details={"errors": [{"message": message} for message in errors]},
        )
    return DatasetCaseDocument(
        name=document["name"].strip(),
        input=document["input"],
        expected_features=dict(document["expected_features"]),
    )


def parse_jsonl(content: str) -> list[DatasetCaseDocument]:
    """Parse an imported file, all or nothing.

    Every line is checked before anything is refused, so one upload reports
    all of its problems rather than one per attempt. Blank lines are skipped
    and line numbers count from 1 over the whole file, blanks included.
    """
    if len(content.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ValidationError(
            f"The import is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB",
            details={"max_bytes": MAX_IMPORT_BYTES},
        )
    lines = [
        (number, text)
        for number, text in enumerate(content.splitlines(), start=1)
        if text.strip()
    ]
    if not lines:
        raise ValidationError("The import has no cases")
    if len(lines) > MAX_IMPORT_LINES:
        raise ValidationError(
            f"The import has {len(lines)} cases; the limit is {MAX_IMPORT_LINES}",
            details={"max_lines": MAX_IMPORT_LINES},
        )

    cases: list[DatasetCaseDocument] = []
    errors: list[dict[str, Any]] = []
    first_line_of: dict[str, int] = {}
    for number, text in lines:
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append({"line": number, "message": f"not valid JSON: {exc.msg}"})
            continue
        problems = schema_errors(document)
        if problems:
            errors.extend({"line": number, "message": message} for message in problems)
            continue
        name = document["name"].strip()
        if name in first_line_of:
            errors.append(
                {
                    "line": number,
                    "message": f"duplicate case name '{name}' (first on line {first_line_of[name]})",
                }
            )
            continue
        first_line_of[name] = number
        cases.append(
            DatasetCaseDocument(
                name=name,
                input=document["input"],
                expected_features=dict(document["expected_features"]),
            )
        )
    if errors:
        raise ValidationError(
            f"{len({item['line'] for item in errors})} of {len(lines)} lines are not valid cases; nothing was imported",
            details={"error_count": len(errors), "errors": errors[:MAX_REPORTED_ERRORS]},
        )
    return cases


def render_jsonl(documents: list[dict[str, Any]]) -> str:
    """Serialise case documents, one per line, the way :func:`parse_jsonl` reads them."""
    return "".join(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
        for document in documents
    )


def content_hash(snapshot: list[dict[str, Any]]) -> str:
    """SHA-256 of a snapshot's content, the same whatever order its cases are in."""
    ordered = sorted(snapshot, key=lambda item: str(item.get("name")))
    canonical = json.dumps(
        ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def diff_snapshots(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> dict[str, int]:
    """Cases added, removed and changed between two snapshots, matched by name."""
    before = {str(item["name"]): item for item in previous}
    after = {str(item["name"]): item for item in current}
    return {
        "added": len(after.keys() - before.keys()),
        "removed": len(before.keys() - after.keys()),
        "changed": sum(
            1 for name in after.keys() & before.keys() if after[name] != before[name]
        ),
    }
