# scripts/

Developer and ops scripts (one-off tasks).

Rules:
- Must be safe and clearly documented.
- Prefer idempotent scripts.

Available:
- `ingest_worker.py`: run knowledge ingestion tasks.
- `bootstrap_admin.py`: create a default admin user/tenant/workspace.
- `bootstrap_enterprise_mvp.py`: idempotent Phase 1 demo bootstrap that creates a sample Provider, sample Knowledge, sample Agent, and sample Workflow for the support-ticket path.
- `seed_enterprise_mvp_scenarios.py`: idempotent scenario seed for richer Run, Task, Observe, approval, failure, citation, cost, and audit demos.
- `verify_governance_demo.py`: deterministic Phase 1.5 governance demo verifier for permissions, secrets, audits, cost attribution, run replay, and regression evidence.
- `verify_phase15_governance_differentiation.py`: validate the Phase 1.5 governance differentiation evidence across Plugin-first governance, Observe governance surfaces, regression-as-release-gate, architecture review, and the customer demo story.
- `verify_phase1_release.py`: validate the SOIT 1.0 release evidence before publishing the `v1.0.0` tag and release notes; pass `--repo-root` for final release evidence so local evidence refs and the release tag are checked.
- `verify_phase1_manual_acceptance.py`: validate the SOIT 1.0 owner UI and Chain A/B manual acceptance evidence; pass `--repo-root` for final evidence so screenshot, signed-record, and Chain A/B evidence refs must exist locally.
- `verify_model_provider_spotcheck.py`: validate live ModelHub provider spot-check evidence; pass `--repo-root` for final evidence so diagnostic, chat completion, and cost attribution evidence refs must exist locally.
- `verify_phase1_user_feedback.py`: validate 1 to 3 non-developer Chain A feedback records before signing the SOIT 1.0 release gate; pass `--repo-root` for final evidence so participant feedback, release decision, and known limitations refs must exist locally.
- `verify_governance_release.py`: validate the SOIT 1.1 governance release evidence before publishing the `v1.1.0` tag and release notes.
- `migrate.sh`: apply database migrations (alembic upgrade head).
- `migrate_mcp_artifacts.py`: dry-run by default; pass `--apply` to move legacy MCP credentials to Vault and rewrite artifacts for the official SDK.
- `verify_release_migration_paths.py`: validate the SOIT 1.0 empty-database and development-database migration evidence JSON before signing the release gate.
- `smoke/run_all.py`: run release smoke tests (workflow/knowledge/responses/secrets).
