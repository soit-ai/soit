BEGIN;

INSERT INTO tenants (id, name, plan, created_at, updated_at)
VALUES ('tenant_n1_release', 'N1 Release Tenant', 'free', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO workspaces (id, tenant_id, name, created_at, updated_at)
VALUES ('workspace_n1_release', 'tenant_n1_release', 'N1 Release Workspace', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO users (id, email, password_hash, name, is_active, created_at, updated_at)
VALUES ('user_n1_release', 'n1-release@example.invalid', 'not-a-login-hash', 'N1 Release User', TRUE, '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO tenant_memberships (tenant_id, user_id, role, created_at)
VALUES ('tenant_n1_release', 'user_n1_release', 'Owner', '2026-07-18 14:00:00');

INSERT INTO workspace_memberships (tenant_id, workspace_id, user_id, role, created_at)
VALUES ('tenant_n1_release', 'workspace_n1_release', 'user_n1_release', 'Owner', '2026-07-18 14:00:00');

INSERT INTO secrets (id, tenant_id, workspace_id, name, secret_ref, created_by, updated_by, created_at, updated_at)
VALUES ('sec_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'N1 Release Secret', 'secret:sec_n1_release', 'user_n1_release', 'user_n1_release', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO workflows (id, tenant_id, workspace_id, name, status, visibility, owner_user_id, current_version_id, created_by, updated_by, created_at, updated_at)
VALUES ('wf_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'N1 Release Workflow', 'active', 'private', 'user_n1_release', 'wfv_n1_release', 'user_n1_release', 'user_n1_release', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO workflow_versions (id, tenant_id, workspace_id, workflow_id, version, status, spec_schema, spec_json, created_by, created_at)
VALUES ('wfv_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'wf_n1_release', 1, 'draft', 'workflow.v1', '{"schema":"workflow.v1","nodes":[],"edges":[],"configs":{"api":{"secret_ref":"secret:sec_n1_release"}}}', 'user_n1_release', '2026-07-18 14:00:00');

INSERT INTO agents (id, tenant_id, workspace_id, name, status, visibility, is_public, featured, downloads_count, reviews_count, current_version_id, created_by, updated_by, created_at, updated_at)
VALUES ('agent_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'N1 Release Agent', 'active', 'private', FALSE, FALSE, 0, 0, 'agentv_n1_release', 'user_n1_release', 'user_n1_release', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO agent_versions (id, tenant_id, workspace_id, agent_id, version, status, spec_schema, spec_json, created_by, created_at)
VALUES ('agentv_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'agent_n1_release', 1, 'draft', 'agent.v1', '{"schema":"agent.v1","bindings":{"models":[],"knowledge":[],"workflows":[],"tools":[]},"configs":{"api":{"secret_ref":"secret:sec_n1_release"}}}', 'user_n1_release', '2026-07-18 14:00:00');

INSERT INTO knowledge (id, tenant_id, workspace_id, name, type, status, visibility, doc_count, chunk_count, created_by, updated_by, created_at, updated_at)
VALUES ('kb_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'N1 Release Knowledge', 'document', 'active', 'private', 1, 0, 'user_n1_release', 'user_n1_release', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO knowledge_documents (id, tenant_id, workspace_id, knowledge_id, doc_key, version, is_latest, source_kind, filename, status, retry_count, raw_text_artifact_key, created_by, updated_by, created_at, updated_at)
VALUES ('doc_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'kb_n1_release', 'release-candidate', 1, TRUE, 'upload', 'release-candidate.txt', 'indexed', 0, 'n1/minio/release-candidate.txt', 'user_n1_release', 'user_n1_release', '2026-07-18 14:00:00', '2026-07-18 14:00:00');

INSERT INTO runs (id, tenant_id, workspace_id, user_id, trace_id, request_id, attempt_no, mode, kind, subject_kind, subject_id, status, input_summary, output_summary, started_at, ended_at, created_at, updated_at)
VALUES ('run_n1_release', 'tenant_n1_release', 'workspace_n1_release', 'user_n1_release', 'trace_n1_release', 'request_n1_release', 1, 'sync', 'workflow', 'workflow', 'wf_n1_release', 'succeeded', 'n1-input-sentinel', 'n1-output-sentinel', '2026-07-18 14:00:00', '2026-07-18 14:00:01', '2026-07-18 14:00:00', '2026-07-18 14:00:01');

INSERT INTO event_outbox (id, event_id, event_type, event_version, tenant_id, workspace_id, idempotency_key, subject_type, subject_id, run_id, producer, payload_json, status, available_at, attempt_count, occurred_at, created_at)
VALUES ('outbox_n1_release', 'evt_n1_release', 'run.completed', '1', 'tenant_n1_release', 'workspace_n1_release', 'n1-release-event', 'run', 'run_n1_release', 'run_n1_release', 'n1-fixture', '{"sentinel":"n1-outbox-preserved"}', 'pending', '2026-07-18 14:00:01', 0, '2026-07-18 14:00:01', '2026-07-18 14:00:01');

COMMIT;
