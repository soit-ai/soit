"""Feature key registry and entitlement resolution."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import Any

FEATURE_REGISTRY_VERSION = 1
VALID_EDITIONS = frozenset({"community", "enterprise", "cloud"})
DEFAULT_FEATURE_FILE = Path(__file__).with_name("features.community.json")


class FeatureKind(str, Enum):
    """Common feature ownership categories."""

    PRODUCT = "product"
    DEPLOYMENT = "deployment"
    SAAS_OPS = "saas_ops"


@dataclass(frozen=True)
class FeatureDefinition:
    """Registered SOIT feature key metadata."""

    key: str
    editions: frozenset[str]
    kind: str


class FeatureRegistry:
    """In-memory registry for edition-scoped feature keys."""

    def __init__(self, definitions: Iterable[FeatureDefinition]) -> None:
        normalized: dict[str, FeatureDefinition] = {}
        for definition in definitions:
            if definition.key in normalized:
                raise ValueError(f"Duplicate feature key: {definition.key}")
            normalized[definition.key] = definition
        self._definitions = normalized

    @classmethod
    def default(
        cls,
        *,
        extra_files: Iterable[str | PathLike[str]] | None = None,
    ) -> FeatureRegistry:
        files: list[str | PathLike[str]] = [DEFAULT_FEATURE_FILE]
        files.extend(extra_files or [])
        return cls.from_json_files(files)

    @classmethod
    def from_json_file(cls, path: str | PathLike[str]) -> FeatureRegistry:
        return cls(_load_feature_definitions(Path(path)))

    @classmethod
    def from_json_files(cls, paths: Iterable[str | PathLike[str]]) -> FeatureRegistry:
        definitions: list[FeatureDefinition] = []
        for path in paths:
            definitions.extend(_load_feature_definitions(Path(path)))
        return cls(definitions)

    def get(self, key: str) -> FeatureDefinition:
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise ValueError(f"Unknown feature key: {key}") from exc

    def keys_for_edition(self, edition: str) -> frozenset[str]:
        normalized = _normalize_edition(edition)
        return frozenset(
            definition.key
            for definition in self._definitions.values()
            if normalized in definition.editions
        )

    def validate_keys(self, keys: Iterable[str]) -> frozenset[str]:
        normalized: set[str] = set()
        for key in keys:
            value = str(key).strip()
            if not value:
                continue
            self.get(value)
            normalized.add(value)
        return frozenset(normalized)


def _load_feature_definitions(path: Path) -> tuple[FeatureDefinition, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid feature registry JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid feature registry shape in {path}")

    _reject_unknown_keys(
        payload,
        allowed={"version", "owner", "features"},
        label=f"feature registry {path}",
    )

    if payload.get("version") != FEATURE_REGISTRY_VERSION:
        raise ValueError(
            f"Invalid feature registry version in {path}: "
            f"expected {FEATURE_REGISTRY_VERSION}"
        )

    owner = payload.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError(f"Invalid feature registry owner in {path}")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError(f"Invalid feature registry features in {path}")

    definitions: list[FeatureDefinition] = []
    for index, raw_feature in enumerate(features):
        definitions.append(_parse_feature_definition(raw_feature, path=path, index=index))
    return tuple(definitions)


def _parse_feature_definition(
    value: Any,
    *,
    path: Path,
    index: int,
) -> FeatureDefinition:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid feature definition at {path} features[{index}]")
    _reject_unknown_keys(
        value,
        allowed={"key", "editions", "kind"},
        label=f"feature definition {path} features[{index}]",
    )

    key = value.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"Invalid feature key at {path} features[{index}]")

    kind = value.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError(f"Invalid feature kind at {path} features[{index}]")
    normalized_kind = kind.strip().lower()
    try:
        FeatureKind(normalized_kind)
    except ValueError as exc:
        raise ValueError(f"Unknown feature kind: {kind}") from exc

    editions = value.get("editions")
    if not isinstance(editions, list) or not editions:
        raise ValueError(f"Invalid feature editions at {path} features[{index}]")

    normalized_editions: set[str] = set()
    for edition in editions:
        if not isinstance(edition, str) or not edition.strip():
            raise ValueError(f"Invalid feature edition at {path} features[{index}]")
        normalized_edition = edition.strip().lower()
        if normalized_edition not in VALID_EDITIONS:
            raise ValueError(f"Unknown feature edition: {edition}")
        normalized_editions.add(normalized_edition)

    return FeatureDefinition(
        key=key.strip(),
        editions=frozenset(normalized_editions),
        kind=normalized_kind,
    )


def _reject_unknown_keys(value: dict[str, Any], *, allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {label}: {', '.join(unknown)}")


def _normalize_edition(edition: str) -> str:
    normalized = edition.strip().lower()
    if normalized not in VALID_EDITIONS:
        raise ValueError(f"Unknown platform edition: {edition}")
    return normalized


def resolve_enabled_features(
    *,
    edition: str = "community",
    entitlement_keys: Iterable[str] | None = None,
    registry: FeatureRegistry | None = None,
) -> frozenset[str]:
    """Resolve enabled features for an edition plus explicit entitlements."""

    active_registry = registry or FeatureRegistry.default()
    normalized_edition = _normalize_edition(edition)
    base = set(active_registry.keys_for_edition("community"))
    if normalized_edition == "community":
        return frozenset(base)

    entitlements = active_registry.validate_keys(entitlement_keys or [])
    allowed_for_edition = active_registry.keys_for_edition(normalized_edition)
    return frozenset(base | (set(entitlements) & set(allowed_for_edition)))
