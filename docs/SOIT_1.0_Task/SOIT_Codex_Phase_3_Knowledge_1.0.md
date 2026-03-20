# SOIT Codex Phase 3 - Knowledge 1.0

## Goal
打通 Knowledge 主链路，让知识库真正具备上传、处理、索引、查询、被 Agent 使用的完整能力。

## Scope
- Knowledge / Document / Chunk / Ingest Task
- Upload pipeline state flow
- Retry and re-index controls
- Query testing
- Usage relations

## Must Follow
- 只做 1.0 闭环能力
- 不做复杂权限体系和高级分析
- 不做过度检索策略扩展

## Tasks
1. Normalize knowledge, document, chunk, ingest task models.
2. Finalize document lifecycle states: uploaded, parsing, chunking, embedding, indexed, failed.
3. Implement or refine ingest task query APIs.
4. Support retry, re-index, and delete document actions.
5. Provide basic knowledge query test endpoint.
6. Expose usage relation query for Agent / Workflow references.
7. Build Knowledge list page.
8. Build Knowledge detail page with documents, statuses, counts, ingest state.
9. Add upload flow and progress state rendering.
10. Add retry UI for failed documents.
11. Add basic query testing UI.

## Deliverables
- Complete ingest state flow
- Knowledge list/detail pages
- Query testing capability
- Relation visibility to Agent / Workflow

## Acceptance Criteria
- User can create a knowledge base
- User can upload documents and see processing state
- Failed documents can be retried
- Indexed knowledge can be bound to Agent

## Suggested Commit
feat(knowledge): complete 1.0 ingest and retrieval workflow
