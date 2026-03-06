"""app.kernel.specs

Spec-first JSON Schema support.

Public API:
- load_schema / load_spec
- list_schemas
- build_registry (for $ref resolution)
- validate_spec
- validator (SpecValidator)
"""

from .loader import get_specs_dir, list_schemas, load_schema, load_spec, build_registry
from .validator import validate_spec, validate_runtime_spec, validator, SpecValidator, SpecIssue

__all__ = [
    "get_specs_dir",
    "list_schemas",
    "load_schema",
    "load_spec",
    "build_registry",
    "validate_spec",
    "validate_runtime_spec",
    "validator",
    "SpecValidator",
    "SpecIssue",
]
