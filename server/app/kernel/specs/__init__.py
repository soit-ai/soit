"""app.kernel.specs

Spec-first JSON Schema support.

Public API:
- load_schema
- list_schemas
- build_registry (for $ref resolution)
- validate_spec
- validator (SpecValidator)
"""

from .loader import build_registry, get_specs_dir, list_schemas, load_schema
from .validator import (
    SpecIssue,
    SpecValidator,
    validate_runtime_spec,
    validate_spec,
    validator,
)

__all__ = [
    "get_specs_dir",
    "list_schemas",
    "load_schema",
    "build_registry",
    "validate_spec",
    "validate_runtime_spec",
    "validator",
    "SpecValidator",
    "SpecIssue",
]
