"""app.kernel.specs.loader

Utilities to load JSON Schemas used by SOIT's spec-first development.

Design goals
- Stable and explicit: schemas live under app/kernel/specs/<version>/
- Fast: in-process cache
- Correct: $ref across sibling schema files (e.g. refs.schema.json#/$defs/...) must resolve
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from referencing import Registry, Resource

SchemaDict = dict[str, Any]


@dataclass(frozen=True)
class SchemaKey:
    version: str
    name: str


# Cache: (version, name) -> schema dict
_SCHEMA_CACHE: dict[SchemaKey, SchemaDict] = {}
# Cache: version -> referencing.Registry
_REGISTRY_CACHE: dict[str, Registry] = {}


def _specs_root() -> Path:
    # app/kernel/specs
    return Path(__file__).resolve().parent


def get_specs_dir(version: str = "v1") -> Path:
    """Return the specs directory for a given version (default: v1)."""
    p = _specs_root() / version
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"Specs directory not found: {p}")
    return p


def _schema_path(name: str, version: str = "v1") -> Path:
    p = get_specs_dir(version) / f"{name}.schema.json"
    if not p.exists():
        raise FileNotFoundError(f"Schema not found: {name} (version={version}) at {p}")
    return p


def list_schemas(version: str = "v1") -> list[str]:
    """List available schema names for a given version."""
    specs_dir = get_specs_dir(version)
    out: list[str] = []
    for schema_file in sorted(specs_dir.glob("*.schema.json")):
        name = schema_file.name.replace(".schema.json", "")
        out.append(name)
    return out


def _load_json(path: Path) -> SchemaDict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(name: str, version: str = "v1") -> SchemaDict:
    """Load a schema dict (cached)."""
    key = SchemaKey(version=version, name=name)
    if key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[key]

    schema_path = _schema_path(name, version)
    schema = _load_json(schema_path)

    # Ensure a stable base URI for relative $ref.
    # We use file:// URI so "refs.schema.json" resolves to file:///.../refs.schema.json
    if isinstance(schema, dict) and "$id" not in schema:
        schema["$id"] = schema_path.resolve().as_uri()

    _SCHEMA_CACHE[key] = schema
    return schema


def build_registry(version: str = "v1") -> Registry:
    """Build a referencing.Registry for resolving $ref across sibling schema files."""
    if version in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[version]

    reg = Registry()
    specs_dir = get_specs_dir(version)

    # Register every schema under its file:// URI (derived from its path).
    for schema_file in sorted(specs_dir.glob("*.schema.json")):
        name = schema_file.name.replace(".schema.json", "")
        schema = load_schema(name, version=version)
        uri = schema_file.resolve().as_uri()
        reg = reg.with_resource(uri, Resource.from_contents(schema))

    _REGISTRY_CACHE[version] = reg
    return reg
