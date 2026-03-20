"""run_all

Run smoke tests for SOIT-Pro demo scenarios.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


DEFAULT_BASE_URL = "http://localhost:9200/api/v1"


@dataclass
class SmokeContext:
    """Shared context for smoke tests."""

    base_url: str
    token: str
    tenant_id: str
    workspace_id: str
    user_id: str
    strict: bool
    timeout_seconds: int
    poll_interval: float
    embedding_model_ref: str
    response_model_ref: str
    inline_ingest_worker: bool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SOIT-Pro smoke tests.")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--admin-email", default=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument("--admin-password", default=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "changeme123"))
    parser.add_argument("--workspace-id", default=os.getenv("WORKSPACE_ID"))
    parser.add_argument("--token", default=os.getenv("ACCESS_TOKEN"))
    parser.add_argument("--strict", action="store_true", help="Fail on skipped steps.")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("SMOKE_TIMEOUT", "300")))
    parser.add_argument("--poll-interval", type=float, default=float(os.getenv("SMOKE_POLL_INTERVAL", "2.0")))
    parser.add_argument(
        "--embedding-model-ref",
        default=os.getenv("DEFAULT_EMBEDDING_MODEL_REF", "model:openai:text-embedding-3-small"),
    )
    parser.add_argument(
        "--response-model-ref",
        default=os.getenv("DEFAULT_LLM_MODEL_REF", "model:openai:gpt-5.1"),
    )
    parser.add_argument(
        "--inline-ingest-worker",
        action="store_true",
        help="Run one local knowledge ingest worker pass after upload for local smoke runs.",
    )
    return parser.parse_args()


def _log(message: str) -> None:
    print(message, flush=True)


def _request(
    ctx: SmokeContext,
    method: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    **kwargs: Any,
) -> Dict[str, Any]:
    url = ctx.base_url.rstrip("/") + path
    merged_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {ctx.token}",
        "X-Workspace-Id": ctx.workspace_id,
    }
    if headers:
        merged_headers.update(headers)
    response = requests.request(method, url, headers=merged_headers, timeout=timeout, **kwargs)
    try:
        payload = response.json()
    except Exception as exc:  # pragma: no cover - diagnostics only
        raise RuntimeError(f"Invalid JSON response from {url}: {response.text}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {payload}")
    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError(f"{method} {url} failed: {payload}")
    return payload.get("data", payload)


def _login(base_url: str, email: str, password: str) -> Tuple[str, str]:
    url = base_url.rstrip("/") + "/login"
    response = requests.post(
        url,
        json={"email": email, "password": password},
        timeout=30,
        headers={"Accept": "application/json"},
    )
    payload = response.json()
    if response.status_code >= 400 or payload.get("success") is False:
        raise RuntimeError(f"Login failed: {payload}")
    data = payload.get("data", {})
    token = data.get("access_token")
    workspace_id = data.get("workspace_id")
    if not token or not workspace_id:
        raise RuntimeError(f"Login response missing token/workspace_id: {payload}")
    return token, workspace_id


def _get_current_actor(ctx: SmokeContext) -> Tuple[str, str]:
    data = _request(ctx, "GET", "/me")
    user_id = data.get("id")
    tenant_id = data.get("tenant_id")
    if not user_id or not tenant_id:
        raise RuntimeError("Failed to resolve current user or tenant context.")
    return user_id, tenant_id


def _run_inline_ingest_worker(ctx: SmokeContext) -> None:
    from app.infra.db.session import get_db_sync
    from app.kernel.contracts.context import RequestContext
    from app.modules.knowledge.runtime.ingest_worker import KnowledgeIngestWorker
    from app.wiring.services import build_knowledge_service

    db = get_db_sync()
    try:
        worker_ctx = RequestContext(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            tenant_role="Owner",
            workspace_role="Owner",
        )
        service = build_knowledge_service(db=db, ctx=worker_ctx)
        worker = KnowledgeIngestWorker(service)
        import asyncio

        asyncio.run(worker.run_once())
    finally:
        db.close()


def _ensure_llm_ready(strict: bool, label: str) -> bool:
    if os.getenv("OPENAI_API_KEY"):
        return True
    if strict:
        raise RuntimeError(f"{label} requires OPENAI_API_KEY but it is not set.")
    _log(f"[SKIP] {label}: OPENAI_API_KEY is not set.")
    return False


def demo_workflow(ctx: SmokeContext) -> None:
    _log("[RUN] Demo-1 workflow create/publish/run")
    workflow = _request(
        ctx,
        "POST",
        "/workflows",
        json={"name": f"smoke-workflow-{uuid.uuid4().hex[:8]}", "description": "smoke test"},
    )
    workflow_id = workflow.get("id")
    if not workflow_id:
        raise RuntimeError("Workflow creation did not return id.")

    spec = {
        "name": "Smoke Workflow",
        "inputs_schema": {"type": "object", "properties": {}},
        "outputs_schema": {"type": "object", "properties": {"value": {"type": "boolean"}}},
        "graph": {
            "nodes": [
                {"id": "set1", "type": "set_var", "params": {"set": {"value": True}}},
                {"id": "out1", "type": "output", "params": {"value": "{{ steps.set1.output.value }}"}},
            ],
            "edges": [{"id": "e1", "from": "set1", "to": "out1"}],
        },
    }
    version = _request(
        ctx,
        "POST",
        f"/workflows/{workflow_id}/versions",
        json={"graph_json": spec, "created_by": ctx.user_id},
    )
    version_id = version.get("id")
    if not version_id:
        raise RuntimeError("Workflow version creation did not return id.")

    _request(
        ctx,
        "POST",
        f"/workflows/{workflow_id}/publish",
        json={"version_id": version_id, "preflight": False},
    )

    result = _request(ctx, "POST", f"/workflows/{workflow_id}/execute", json={})
    run_id = result.get("run_id")
    if not run_id:
        raise RuntimeError("Workflow execution did not return run_id.")
    _log(f"[OK] Demo-1 workflow run_id={run_id}")


def demo_knowledge(ctx: SmokeContext) -> str:
    _log("[RUN] Demo-2 knowledge upload/ingest/query")

    knowledge = _request(
        ctx,
        "POST",
        "/knowledge",
        json={
            "name": f"smoke-knowledge-{uuid.uuid4().hex[:8]}",
            "knowledge_type": "document",
            "visibility": "workspace",
            "description": "smoke test knowledge base",
        },
    )
    knowledge_id = knowledge.get("id")
    if not knowledge_id:
        raise RuntimeError("Knowledge creation did not return id.")

    index = _request(
        ctx,
        "POST",
        f"/knowledge/{knowledge_id}/indexes",
        json={
            "name": "primary",
            "provider": "milvus",
            "embedding_model_ref": ctx.embedding_model_ref,
            "dimension": 0,
            "metric_type": "cosine",
            "is_primary": True,
        },
    )
    if not index.get("id"):
        raise RuntimeError("Index creation failed.")

    sample_text = "SOIT smoke test document. This text is used for knowledge ingestion."
    files = {"file": ("smoke.txt", sample_text.encode("utf-8"), "text/plain")}
    data = {
        "doc_key": "smoke-doc",
        "source_type": "upload",
        "async_ingest": "true",
        "max_retries": "1",
    }
    document = _request(
        ctx,
        "POST",
        f"/knowledge/{knowledge_id}/documents",
        files=files,
        data=data,
    )
    document_id = document.get("id")
    if not document_id:
        raise RuntimeError("Document upload did not return id.")

    if ctx.inline_ingest_worker:
        _log("[RUN] Demo-2 inline ingest worker pass")
        _run_inline_ingest_worker(ctx)

    deadline = time.time() + ctx.timeout_seconds
    task_status = None
    last_error = None
    while time.time() < deadline:
        tasks = _request(
            ctx,
            "GET",
            f"/knowledge/{knowledge_id}/ingest-tasks",
            params={"limit": 20, "offset": 0},
        )
        task = next((item for item in tasks if item.get("document_id") == document_id), None)
        if not task:
            time.sleep(ctx.poll_interval)
            continue
        task_status = task.get("status")
        last_error = (task.get("error_code"), task.get("error_message"))
        if task_status in {"succeeded", "failed", "canceled"}:
            break
        time.sleep(ctx.poll_interval)

    if task_status != "succeeded":
        raise RuntimeError(f"Ingest task failed: status={task_status}, error={last_error}")

    query = _request(
        ctx,
        "POST",
        f"/knowledge/{knowledge_id}/query",
        json={"query": "smoke test document", "top_k": 3, "strategy": "keyword", "include_snippets": True},
    )
    if not query.get("results"):
        raise RuntimeError("Knowledge query returned no results.")
    _log(f"[OK] Demo-2 knowledge_id={knowledge_id}")
    return knowledge_id


def demo_chat_runtime(ctx: SmokeContext, knowledge_id: str) -> None:
    _log("[RUN] Demo-3 responses runtime via thread")
    thread = _request(
        ctx,
        "POST",
        "/threads",
        json={
            "title": f"smoke-thread-{uuid.uuid4().hex[:8]}",
            "thread_type": "chat",
            "default_model_ref": ctx.response_model_ref,
            "knowledge_config_json": {
                "knowledge_ids": [knowledge_id],
                "top_k": 3,
                "strategy": "keyword",
            },
            "metadata_json": {
                "source": "smoke",
                "knowledge_id": knowledge_id,
            },
        },
    )
    thread_id = thread.get("id")
    if not thread_id:
        raise RuntimeError("Thread creation did not return id.")

    response = _request(
        ctx,
        "POST",
        "/responses",
        json={
            "thread_id": thread_id,
            "model": ctx.response_model_ref,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": "Summarize the smoke runtime in one short sentence.",
                        "metadata": {"knowledge_id": knowledge_id},
                    }
                ]
            },
            "metadata": {
                "source": "smoke.responses",
                "knowledge_id": knowledge_id,
            },
        },
    )
    response_id = response.get("id")
    run_id = response.get("run_id")
    output = response.get("output_json") or {}
    if not response_id or not run_id:
        raise RuntimeError("Response execution did not return response_id/run_id.")
    if not output.get("text"):
        raise RuntimeError("Response output is empty.")

    thread_detail = _request(ctx, "GET", f"/threads/{thread_id}")
    messages = thread_detail.get("messages") or []
    if not any(item.get("role") == "assistant" and item.get("response_id") == response_id for item in messages):
        raise RuntimeError("Thread detail is missing the assistant response message.")

    timeline = _request(ctx, "GET", f"/responses/by-run/{run_id}")
    if not timeline.get("items"):
        raise RuntimeError("Response timeline returned no items for the run.")

    _log(f"[OK] Demo-3 response_id={response_id}")


def demo_secrets(ctx: SmokeContext) -> None:
    _log("[RUN] Demo-4 secret_ref resolution")
    secret_payload = {
        "name": f"smoke-secret-{uuid.uuid4().hex[:8]}",
        "description": "smoke test secret",
        "value": f"token-{uuid.uuid4().hex}",
    }
    secret = _request(ctx, "POST", "/secrets", json=secret_payload)
    secret_id = secret.get("id")
    if not secret_id:
        raise RuntimeError("Secret creation did not return id.")
    if "value" in secret:
        raise RuntimeError("Secret value leaked in response.")

    test = _request(ctx, "POST", f"/secrets/{secret_id}/test")
    if not test.get("ok"):
        raise RuntimeError(f"Secret test failed: {test}")
    _log("[OK] Demo-4 secret_ref test passed")


def main() -> int:
    args = _parse_args()

    token = args.token
    workspace_id = args.workspace_id
    if not token or not workspace_id:
        token, workspace_id = _login(args.base_url, args.admin_email, args.admin_password)
        _log("[OK] Logged in with bootstrap admin.")

    ctx = SmokeContext(
        base_url=args.base_url,
        token=token,
        tenant_id="",
        workspace_id=workspace_id,
        user_id="",
        strict=args.strict,
        timeout_seconds=args.timeout,
        poll_interval=args.poll_interval,
        embedding_model_ref=args.embedding_model_ref,
        response_model_ref=args.response_model_ref,
        inline_ingest_worker=args.inline_ingest_worker,
    )
    ctx.user_id, ctx.tenant_id = _get_current_actor(ctx)

    failures = 0
    try:
        demo_workflow(ctx)
    except Exception as exc:
        failures += 1
        _log(f"[FAIL] Demo-1 workflow: {exc}")

    knowledge_id = None
    if _ensure_llm_ready(ctx.strict, "Demo-2 knowledge ingest"):
        try:
            knowledge_id = demo_knowledge(ctx)
        except Exception as exc:
            failures += 1
            _log(f"[FAIL] Demo-2 knowledge: {exc}")

    if knowledge_id and _ensure_llm_ready(ctx.strict, "Demo-3 responses runtime"):
        try:
            demo_chat_runtime(ctx, knowledge_id)
        except Exception as exc:
            failures += 1
            _log(f"[FAIL] Demo-3 chat: {exc}")

    try:
        demo_secrets(ctx)
    except Exception as exc:
        failures += 1
        _log(f"[FAIL] Demo-4 secrets: {exc}")

    if failures:
        _log(f"[DONE] Smoke tests completed with {failures} failures.")
        return 1
    _log("[DONE] Smoke tests succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
