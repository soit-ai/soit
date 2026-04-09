# Unified Versioning And Release

This document defines the target semantics and service contract for version control and release management across `agent`, `skill`, and `workflow`.

The goal is to unify business behavior without merging the existing physical tables.

## Goals

- Standardize draft, publish, rollback, preview, and live execution semantics.
- Eliminate duplicated version/release orchestration logic in each module.
- Keep `agent_*`, `skill_*`, and `workflow_*` tables separate for now.
- Make future versioned subjects reusable through one shared service contract.

## Non-goals

- Do not merge `*_versions` or `*_publishes` into generic shared tables in this phase.
- Do not redesign every domain-specific field on day one.
- Do not break current API paths immediately; migrate behavior behind stable handlers first.

## Current Problems

The current model already shows the same business concern repeated in three modules:

- root table with `current_version_id` and `published_version_id`
- immutable-ish version table
- publish ledger table

But the semantics are inconsistent:

- `agent.publish_version` and `skill.publish_version` publish an existing version.
- `workflow.publish_version` creates a new version and publishes it in one action.
- `workflow.rollback_version` moves pointers without writing a publish ledger record.
- `skill.create_version` does not advance `current_version_id`, while `agent` does.
- runtime selection often falls back to `published_version_id or current_version_id`, which mixes preview semantics and live semantics.

These inconsistencies are more important than the duplicated tables. The first priority is to unify behavior.

## Canonical Terms

- `Subject`: a versioned business object such as `agent`, `skill`, or `workflow`.
- `Head version`: the latest working version. This may be a draft. It maps to the existing `current_version_id`.
- `Live version`: the currently effective version for formal execution. It maps to the existing `published_version_id`.
- `Draft`: a version that exists but is not live yet.
- `Publish`: make a target version the live version and write a release ledger record.
- `Rollback`: change the live version to a previous version and write a release ledger record.
- `Preview`: explicitly run a draft or specified version, separate from normal live execution.

## Target Semantics

### Subject pointers

Each versioned subject keeps two pointers:

- `current_version_id`: unified meaning = head version
- `published_version_id`: unified meaning = live version

Rules:

- `create_draft` creates a new version and advances `current_version_id`.
- `publish(version_id)` does not create a version. It promotes an existing version to live and updates `published_version_id`.
- `rollback(version_id)` does not create a version. It points `published_version_id` back to a previous version and records the rollback.
- `published_version_id` may be null if the subject has never been published.
- `current_version_id` should normally point to the newest known version.

### Runtime behavior

- formal execution uses `published_version_id` only
- preview or debug execution may use:
  - explicit `version_id`
  - otherwise `current_version_id`

This removes ambiguity. A live request must not silently consume drafts.

### Immutability

Version rows are immutable snapshots after creation.

Allowed mutable fields after creation should be limited to lifecycle metadata such as:

- `status`
- optional release annotations

`spec_json` must not be updated in place after the version row is created.

## Shared Service Contract

Introduce a shared service under a dedicated module such as:

- `app/modules/versioning/application/service.py`

The shared service owns orchestration only. Domain validation and side effects stay in each module via adapters.

### Proposed interface

```python
class VersionControlService:
    def create_draft(
        self,
        subject_kind: str,
        subject_id: str,
        spec_json: dict,
        *,
        spec_schema: str,
        based_on_version_id: str | None = None,
        metadata: dict | None = None,
    ) -> object: ...

    def publish(
        self,
        subject_kind: str,
        subject_id: str,
        version_id: str,
        *,
        scope: str = "workspace",
        notes: str | None = None,
    ) -> object: ...

    def rollback(
        self,
        subject_kind: str,
        subject_id: str,
        target_version_id: str,
        *,
        scope: str = "workspace",
        notes: str | None = None,
    ) -> object: ...

    def get_head_version(self, subject_kind: str, subject_id: str) -> object | None: ...
    def get_live_version(self, subject_kind: str, subject_id: str) -> object | None: ...
    def list_versions(self, subject_kind: str, subject_id: str, *, limit: int, offset: int) -> list[object]: ...
    def list_releases(self, subject_kind: str, subject_id: str, *, limit: int, offset: int) -> list[object]: ...
```

## Public API Surface

Release ledger must be queryable through stable read endpoints so frontend code can render publish history and rollback provenance directly.

- `GET /api/v1/agents/{agent_id}/releases`
- `GET /api/v1/skills/{skill_id}/releases`
- `GET /api/v1/workflows/{workflow_id}/releases`

Returned items should expose:

- release id
- subject id
- version id
- action
- scope
- status
- from_version_id
- to_version_id
- notes
- rollback_of_publish_id
- created_by
- created_at
- updated_at

## Adapter Contract

Each versioned module provides a subject adapter instead of implementing publish logic directly.

Suggested location:

- `app/modules/agent/application/versioning_adapter.py`
- `app/modules/skill/application/versioning_adapter.py`
- `app/modules/workflow/application/versioning_adapter.py`

### Adapter responsibilities

- load and verify subject ownership/scope
- compute next version number
- create version row in the module-specific table
- load version row and verify it belongs to the subject
- update subject pointers
- create publish ledger row in the module-specific table
- perform domain validation before publish
- perform domain-specific side effects after publish/rollback

### Adapter shape

```python
class VersioningAdapter(Protocol):
    subject_kind: str

    def get_subject(self, subject_id: str) -> object: ...
    def get_version(self, version_id: str) -> object | None: ...
    def next_version_number(self, subject_id: str) -> int: ...

    def create_version(
        self,
        subject_id: str,
        *,
        version_no: int,
        spec_schema: str,
        spec_json: dict,
        based_on_version_id: str | None,
        metadata: dict | None,
    ) -> object: ...

    def update_head(self, subject: object, version_id: str) -> object: ...
    def update_live(self, subject: object, version_id: str) -> object: ...

    def create_release(
        self,
        subject: object,
        *,
        action: str,
        from_version_id: str | None,
        to_version_id: str,
        scope: str,
        notes: str | None,
        rollback_of_publish_id: str | None = None,
    ) -> object: ...

    def validate_for_publish(self, subject: object, version: object) -> None: ...
    def after_publish(self, subject: object, version: object) -> None: ...
    def after_rollback(self, subject: object, version: object) -> None: ...
```

## Standard Lifecycle

### Version status

Recommended normalized status set:

- `draft`
- `published`
- `superseded`
- `archived`

Optional future state:

- `validated`

Minimal rules:

- newly created version starts as `draft`
- publishing a version marks that version as `published`
- older published versions may remain `published` historically, or be moved to `superseded`
- only one version is live through the subject pointer, not through the status field alone

### Release actions

Recommended normalized release actions:

- `publish`
- `rollback`
- `unpublish`

Recommended release record status:

- `succeeded`
- `failed`

Optional future state:

- `pending`

## Persistence Strategy

Physical tables stay separate in this phase:

- `agent_versions`, `agent_publishes`
- `skill_versions`, `skill_publishes`
- `workflow_versions`, `workflow_publishes`

But schemas should converge on a minimum common contract.

### Version tables: recommended common fields

- `id`
- `tenant_id`
- `workspace_id`
- subject foreign key
- `version`
- `status`
- `spec_schema`
- `spec_json`
- `checksum`
- `created_from_version_id`
- `changelog`
- `created_by`
- `created_at`

Notes:

- `agent_versions` is already close.
- `workflow_versions` should add `checksum` and `changelog`.
- `skill_versions` should add `checksum`, `created_from_version_id`, and `changelog`.

### Publish tables: recommended common fields

- `id`
- `tenant_id`
- `workspace_id`
- subject foreign key
- target version foreign key
- `action`
- `scope`
- `status`
- `from_version_id`
- `to_version_id`
- `notes`
- `rollback_of_publish_id`
- `created_by`
- `created_at`
- `updated_at`

Notes:

- `agent_publishes` already contains `notes` and `rollback_of_publish_id`.
- `workflow_publishes` should add `action`, `from_version_id`, `to_version_id`, and `rollback_of_publish_id`.
- `skill_publishes` should add the same fields plus `notes`.

## Module-specific Integration

### Agent

- keep domain-specific spec building and checksum generation in the agent module
- keep binding synchronization as a post-version or post-publish side effect
- formal execution should resolve from `published_version_id` only
- add explicit preview execution if draft execution is still needed

### Skill

- `create_version` should advance `current_version_id`
- `publish_version` should stop doing ad-hoc pointer management and delegate to the shared service
- keep skill-specific validation in the skill adapter

### Workflow

- split the current `publish_version` behavior into:
  - `create_draft`
  - `publish(existing_version_id)`
- `rollback_version` must write a release ledger record
- publish validation should keep compile and spec validation in the workflow adapter
- formal execution should use live version only

## API Compatibility Strategy

Existing endpoints may stay initially, but their behavior should be redirected to the unified service.

Recommended normalization:

- create/edit endpoints operate on head versions
- publish endpoint only publishes an existing version
- rollback endpoint only rolls back to an existing version
- execution endpoint defaults to live version
- preview endpoint accepts explicit `version_id`

This allows external API stability while removing internal semantic drift.

## Implementation Plan

### Phase 1: unify semantics

- add shared `versioning` service and adapter protocol
- move publish/rollback orchestration into the shared service
- keep module tables unchanged

### Phase 2: align module behavior

- make `skill.create_version` update head pointer
- split workflow create-vs-publish behavior
- ensure rollback always writes release ledger
- ensure formal execution reads live version only

### Phase 3: align schema

- add missing common columns to `skill_*` and `workflow_*` tables
- backfill fields where possible
- add indexes for release history queries if needed

### Phase 4: clean up legacy paths

- remove duplicated module-specific publish orchestration
- keep only domain-specific adapter logic in each module

## Risks And Controls

- Risk: existing callers may rely on draft fallback during execution.
  - Control: preserve preview behavior through explicit preview endpoints or explicit `version_id`.

- Risk: release history is incomplete today, especially for workflow rollback.
  - Control: after the new service lands, treat release ledger as authoritative and stop pointer-only rollback.

- Risk: slight schema differences may tempt module-specific shortcuts.
  - Control: define adapter contract first and reject behaviors outside the shared lifecycle.

## Acceptance Criteria

- draft, publish, rollback, and live execution semantics are consistent for `agent`, `skill`, and `workflow`
- all publish and rollback actions create release ledger records
- live execution resolves from `published_version_id` only
- module services delegate orchestration to a shared versioning service
- module-specific logic is limited to validation and domain side effects
