"""app.kernel.specs.validator

Validate JSON documents against SOIT JSON Schemas.

- Uses JSON Schema Draft 2020-12 (as declared in schemas).
- Resolves $ref across sibling schema files (refs.schema.json etc) via referencing.Registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Union

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from app.kernel.commons.errors import ValidationError
from app.kernel.specs.loader import load_schema, build_registry

JsonDict = Dict[str, Any]

SPEC_SCHEMA_MAP = {
    "workflow.v1": "workflow_spec",
    "chat.v1": "chat_spec",
    "agent.v1": "agent_spec",
}


@dataclass
class SpecIssue:
    message: str
    instance_path: str
    schema_path: str


def _json_pointer(path_parts: List[Union[str, int]]) -> str:
    def esc(s: str) -> str:
        return s.replace("~", "~0").replace("/", "~1")

    if not path_parts:
        return ""
    out = ""
    for p in path_parts:
        if isinstance(p, int):
            out += f"/{p}"
        else:
            out += f"/{esc(p)}"
    return out


class SpecValidator:
    """Schema validator with rich error details."""

    def validate(
        self,
        schema_name: str,
        document: JsonDict,
        *,
        version: str = "v1",
        raise_on_error: bool = True,
    ) -> List[SpecIssue]:
        schema = load_schema(schema_name, version=version)
        registry = build_registry(version=version)

        try:
            v = Draft202012Validator(schema, registry=registry)
        except SchemaError as e:
            raise ValidationError(
                message=f"Invalid JSON Schema: {schema_name}",
                details={"spec": schema_name, "version": version, "error": str(e)},
            )

        errors = sorted(v.iter_errors(document), key=lambda e: list(e.absolute_path))

        issues: List[SpecIssue] = [
            SpecIssue(
                message=e.message,
                instance_path=_json_pointer(list(e.absolute_path)),
                schema_path=_json_pointer(list(e.absolute_schema_path)),
            )
            for e in errors
        ]

        if issues and raise_on_error:
            raise ValidationError(
                message=f"Spec validation failed: {schema_name}",
                details={
                    "spec": schema_name,
                    "version": version,
                    "error_count": len(issues),
                    "errors": [i.__dict__ for i in issues],
                },
            )
        return issues

    # Convenience wrappers
    def validate_workflow_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("workflow_spec", document, version=version)

    def validate_tool_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("tool_spec", document, version=version)

    def validate_node_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("node_spec", document, version=version)

    def validate_plugin_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("plugin_spec", document, version=version)

    def validate_runtrace_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("runtrace_spec", document, version=version)

    def validate_app_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("app_spec", document, version=version)

    def validate_memory_spec(self, document: JsonDict, *, version: str = "v1") -> List[SpecIssue]:
        return self.validate("memory_spec", document, version=version)


validator = SpecValidator()


def validate_runtime_spec(
    spec_schema: str,
    document: JsonDict,
    *,
    raise_on_error: bool = True,
) -> List[SpecIssue]:
    """Validate runtime spec by schema identifier (e.g., workflow.v1)."""
    if not spec_schema:
        raise ValidationError(message="Spec schema is required", details={"spec_schema": spec_schema})
    normalized = spec_schema.strip().lower()
    schema_name = SPEC_SCHEMA_MAP.get(normalized)
    if not schema_name:
        raise ValidationError(
            message="Unsupported spec schema",
            details={"spec_schema": spec_schema, "supported": sorted(SPEC_SCHEMA_MAP.keys())},
        )
    version = "v1"
    if "." in normalized:
        _, version = normalized.split(".", 1)
        version = version or "v1"
    return validator.validate(schema_name, document, version=version, raise_on_error=raise_on_error)


def validate_spec(document: JsonDict, schema: Union[str, JsonDict], *, version: str = "v1") -> bool:
    """Backward compatible helper: return True if valid, otherwise raise ValidationError."""
    if isinstance(schema, str):
        validator.validate(schema, document, version=version, raise_on_error=True)
        return True

    registry = build_registry(version=version)
    v = Draft202012Validator(schema, registry=registry)
    errors = sorted(v.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        raise ValidationError(
            message="Spec validation failed",
            details={
                "version": version,
                "error_count": len(errors),
                "errors": [
                    {
                        "message": e.message,
                        "instance_path": _json_pointer(list(e.absolute_path)),
                        "schema_path": _json_pointer(list(e.absolute_schema_path)),
                    }
                    for e in errors
                ],
            },
        )
    return True
