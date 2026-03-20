# SOIT Codex Phase 9 - 1.0 Stabilization and Release Gate

## Goal
对 SOIT 1.0 核心主链路进行联调、收尾、问题修复和发布前验收，确保可交付首批真实用户使用。

## Scope
- Integration cleanup
- Broken-link cleanup
- Basic empty/loading/error states
- Regression verification across main flows
- Release checklist

## Must Follow
- 只做稳定性和收尾，不新增功能扩展
- 不在本阶段引入新模块
- 发现非 1.0 范围需求时记录到 backlog，不直接实现

## Tasks
1. Run end-to-end verification for ModelHub -> Knowledge -> Agent -> Chat -> Runs.
2. Run end-to-end verification for Workflow -> Execute -> Runs.
3. Fix broken links, missing states, loading issues, obvious UI inconsistency.
4. Standardize empty, loading, error, and retry states on core pages.
5. Validate publish flows for Agent and Workflow.
6. Validate failure visibility for document ingest and runtime failures.
7. Review navigation consistency after all phases.
8. Produce 1.0 release checklist and known limitations list.
9. Keep deferred items explicitly out of scope and document them as backlog.

## Deliverables
- Stabilized 1.0 main flows
- Release checklist
- Known limitations / deferred scope list

## Acceptance Criteria
- Core flows pass manual end-to-end verification
- No blocking broken route or unusable main page remains
- Main failure scenarios are visible and actionable
- Deferred items are documented rather than partially implemented

## Suggested Commit
chore(release): stabilize 1.0 main flows and prepare release gate checklist
