# SOIT Architecture Principles

Use these rules as the active architecture baseline.

## Core Rules

1. `Agent` is the primary user-facing intelligent capability.
2. `Workflow`, `Knowledge`, `Memory`, `Plugin`, and `MCP` are capability layers.
3. `Run / Task / Trace / Artifact` form the unified execution ledger.
4. Runtime behavior is routed through shared kernel/runtime and kernel/trace surfaces.

## Dependency Boundaries

1. `kernel/` does not depend on `modules/`.
2. `adapters/` contains integration code, not business logic.
3. `api/` stays thin and orchestrates only.
4. New runtime code must depend on current kernel contracts, not retired platform families.

## Delivery Rules

1. Data model changes land before API migrations.
2. API migrations land before page migrations.
3. Public contracts must use active product terminology.
4. Transitional aliases are temporary and must carry an explicit removal plan.

## Explicitly Forbidden

1. New primary models or APIs built around retired platform terminology.
2. New module-owned executors that bypass shared runtime orchestration.
3. Direct provider-specific protocols in frontend state or UI.
