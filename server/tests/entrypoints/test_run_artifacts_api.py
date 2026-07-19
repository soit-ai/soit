"""Entry-point contracts for governed Run artifact downloads."""

import hashlib

from fastapi import status

from app.api.v1.run.dependencies import get_run_artifact_storage
from app.kernel.runtime.runs.writer import TraceWriter
from app.main import app


class _ArtifactStorage:
    async def get(self, key: str, **kwargs):
        del kwargs
        assert key.endswith("/report.csv")
        return b"name,value\nSOIT,1\n"


def test_run_artifact_download_is_scoped_and_does_not_expose_storage_key(client, db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent", kind="agent")
    content = b"name,value\nSOIT,1\n"
    artifact = writer.create_artifact(
        run.id,
        "file",
        (
            f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/"
            f"runs/{run.id}/report.csv"
        ),
        meta={"name": "report.csv"},
        mime="text/csv",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    db.commit()
    app.dependency_overrides[get_run_artifact_storage] = lambda: _ArtifactStorage()
    try:
        response = client.get(f"/api/v1/runs/{run.id}/artifacts/{artifact.id}/content")
    finally:
        app.dependency_overrides.pop(get_run_artifact_storage, None)

    assert response.status_code == status.HTTP_200_OK
    assert response.content == content
    assert response.headers["content-type"].startswith("text/csv")
    assert "report.csv" in response.headers["content-disposition"]
    assert artifact.storage_key not in response.text

