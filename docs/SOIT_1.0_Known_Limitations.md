# SOIT 1.0 Known Limitations

Updated: March 11, 2026

## Scope Decisions Kept Out of 1.0

1. `Tasks` is currently treated as the runtime task surface for async execution work, not a separate planning or work-management product.
2. Advanced workflow builder semantics are intentionally narrowed to the current runtime-supported node set used by `workflow.v1`.
3. Non-P0 capability expansion for MCP, plugin marketplace depth, advanced security/audit, and onboarding remains outside the 1.0 release gate.

## Product Limitations

1. Workflow builder save currently serializes the supported execution subset and does not preserve every legacy builder-only node semantic one-to-one.
2. `Tasks` scope is still narrower than the other first-class objects and needs a dedicated product decision before any larger 1.x expansion.
3. Release readiness no longer depends on missing automation, but it still benefits from a short owner-led UI sweep across Models, Runs, Settings, and Tasks before public rollout.

## Deferred Backlog

1. Richer `Tasks` taxonomy, filtering, and ownership model.
2. Expanded workflow runtime compatibility across all visual builder node types.
3. Deeper observability dashboards beyond the current Runs-centric minimum loop.
4. Additional release hardening from the P1 backlog in [docs/SOIT_1.0_Task_Checklist_Consolidated.md](/f:/soit/soit-pro/docs/SOIT_1.0_Task_Checklist_Consolidated.md).
