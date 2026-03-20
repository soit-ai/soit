# SOIT 1.0 Release Handoff Note

Updated: March 11, 2026

## Status

SOIT 1.0 is ready for release-candidate handoff.

Engineering completion is done. The remaining release gate is:

1. Release owner sign-off.
2. A short UI spot-check using [docs/SOIT_1.0_Owner_UI_Spotcheck.md](/f:/soit/soit-pro/docs/SOIT_1.0_Owner_UI_Spotcheck.md).

## Included in 1.0

- Unified workspace navigation and legacy redirects.
- ModelHub provider management and catalog sync surface.
- Knowledge create, document ingest, query, and runtime entry chain.
- Agent create, version, publish, and execution chain.
- Chat agent selection with response/run linkage.
- Workflow builder save-to-version and execution minimum loop.
- Runs filtering, detail inspection, and linked navigation.
- Settings overview with Team, API, Secrets, and Security entry points.
- Runtime Tasks list/detail visibility.

## Validation Completed

### Frontend

- `web -> npm run build` passed on March 10, 2026.

### Backend

- Targeted pytest coverage passed on March 10-11, 2026.
- Smoke flow passed on March 11, 2026:
  - Workflow create / publish / execute
  - Knowledge upload / ingest / query
  - Thread + responses runtime execution
  - Secret create / test

Primary evidence is summarized in [docs/SOIT_1.0_Release_Signoff_Summary.md](/f:/soit/soit-pro/docs/SOIT_1.0_Release_Signoff_Summary.md).

## Known Constraints

- `Tasks` remains a runtime task surface, not a broader work-management module.
- Workflow builder is aligned to the currently supported `workflow.v1` runtime subset.
- A short owner-led UI sweep is still recommended before public rollout.

Details remain in [docs/SOIT_1.0_Known_Limitations.md](/f:/soit/soit-pro/docs/SOIT_1.0_Known_Limitations.md).

## Recommended Release Sequence

1. Owner runs the UI sweep in [docs/SOIT_1.0_Owner_UI_Spotcheck.md](/f:/soit/soit-pro/docs/SOIT_1.0_Owner_UI_Spotcheck.md).
2. Owner confirms sign-off against [docs/SOIT_1.0_Release_Checklist.md](/f:/soit/soit-pro/docs/SOIT_1.0_Release_Checklist.md).
3. Team communicates deferred scope using [docs/SOIT_1.0_Known_Limitations.md](/f:/soit/soit-pro/docs/SOIT_1.0_Known_Limitations.md).

## Suggested Internal Announcement

SOIT 1.0 has completed engineering validation and smoke verification as of March 11, 2026. The build, targeted backend contract tests, and local end-to-end smoke chain are passing. Remaining release work is limited to release-owner UI sign-off and standard rollout coordination; deferred items remain documented and excluded from 1.0 scope.
