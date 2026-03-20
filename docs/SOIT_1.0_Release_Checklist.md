# SOIT 1.0 Release Checklist

Updated: March 11, 2026

## Goal

Use this checklist as the release gate for the SOIT 1.0 P0 scope. It is intentionally limited to the main chain and does not expand the feature set.

## Core Flow Verification

- [ ] Verify `Models -> Provider healthcheck -> Catalog sync -> Model selection`.
- [x] Verify `Knowledge -> Create -> Upload document -> Ingest visibility -> Query test`.
- [x] Verify `Agent -> Create -> Draft version -> Publish`.
- [ ] Verify `Chat -> Select agent -> Start thread -> Receive response -> Open related run`.
- [ ] Verify `Runs -> Filter by subject / workflow / status -> Open detail -> Inspect failure fields`.
- [ ] Verify `Workflow -> Build -> Save new version -> Execute -> View run log`.
- [ ] Verify `Settings -> Overview -> Team / API / Secrets / Security` entry chain.
- [ ] Verify `Tasks -> List -> Detail -> Retry / Resume / Cancel` for async runtime work where applicable.

## Failure Visibility

- [x] Main list/detail pages show explicit loading states.
- [x] Main list/detail pages show explicit empty states.
- [x] Main list/detail pages show explicit in-page error states with retry actions.
- [x] Knowledge document ingest failures show error details and retry entry.
- [x] Run detail and workflow log expose runtime failure message, code, and failed step.

## Navigation Consistency

- [x] Primary navigation matches `Dashboard / Agents / Workflows / Knowledge / Chat / Tasks / Runs / Models / Settings`.
- [x] `/observability` legacy paths redirect into `/runs`.
- [x] `/model`, `/plugin`, `/setting`, `/system` legacy paths redirect into current IA.
- [x] Cross-links from Knowledge, Agent, Chat, Workflow, and Runs open the expected destination.

## Validation Evidence

- [x] Frontend production build passes: `web -> npm run build` on March 10, 2026.
- [x] Targeted backend pytest coverage passes on March 10, 2026:
  - `tests/entrypoints/test_agent_api.py`
  - `tests/entrypoints/test_knowledge_api.py`
  - `tests/entrypoints/test_responses_api.py`
  - `tests/entrypoints/test_observability_api.py`
  - `tests/unit/test_runtime_core_service.py`
  - `tests/unit/test_workflow_executor.py`
  - `tests/integration/test_agent_publish_and_execute.py`
  - `tests/test_trace_emission.py`
- [x] Backend smoke tests executed successfully on March 11, 2026 from `app/scripts/smoke/run_all.py`.
  - Demo-1: workflow create / publish / execute
  - Demo-2: knowledge upload / ingest / query
  - Demo-3: thread + responses runtime execution
  - Demo-4: secret create / test
- [x] End-to-end verification recorded with seeded workspace data in [docs/SOIT_1.0_Release_Signoff_Summary.md](/f:/soit/soit-pro/docs/SOIT_1.0_Release_Signoff_Summary.md).

## Release Decision

- [x] No blocking broken route remains on the 1.0 main path.
- [x] No core page is unusable when backend returns empty data.
- [x] Deferred items are documented and explicitly excluded from 1.0 scope.
- [ ] Release owner sign-off completed.
