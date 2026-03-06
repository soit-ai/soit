"""test_tool_secret_injection

Unit tests for tool secret injection and redaction.
"""

import pytest
from sqlalchemy import select

from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.trace.writer import TraceWriter
from app.kernel.trace.models import RunStep


class DummySecretsPort(SecretsPort):
    """Secrets port stub for tool policy tests."""

    async def get_secret(self, secret_ref: str, **kwargs):
        return "supersecret"

    async def set_secret(self, secret_ref: str, value: str, **kwargs):
        raise RuntimeError("Not implemented")

    async def delete_secret(self, secret_ref: str, **kwargs):
        raise RuntimeError("Not implemented")


class DummyToolPort(ToolPort):
    """Tool port stub capturing parameters."""

    def __init__(self):
        self.last_parameters = None

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs):
        self.last_parameters = parameters
        return ToolResponse(result={"ok": True}, success=True, metadata={})


@pytest.mark.asyncio
async def test_tool_policy_injects_and_redacts_secrets(db, ctx):
    """Secret refs are injected for execution and redacted in audit logs."""
    dummy_tool = DummyToolPort()
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        app_id="app_workflow",
        app_version_id="ver_workflow",
        app_type="workflow",
    )

    gateway = ToolPolicyGateway(
        gateway=dummy_tool,
        ctx=ctx,
        trace_writer=trace_writer,
        secrets_port=DummySecretsPort(),
    )

    parameters = {
        "headers": {"Authorization": {"secret_ref": "secret:test_token"}},
        "query": {"token": {"secret_ref": "secret:test_token"}},
        "body": {"payload": {"secret_ref": "secret:test_token"}},
    }

    await gateway.invoke(
        tool_ref="tool:http:demo",
        parameters=parameters,
        run_id=run.id,
    )

    assert dummy_tool.last_parameters["headers"]["Authorization"] == "supersecret"
    assert dummy_tool.last_parameters["query"]["token"] == "supersecret"
    assert dummy_tool.last_parameters["body"]["payload"] == "supersecret"

    result = db.exec(select(RunStep).where(RunStep.run_id == run.id)).first()
    if result is None:
        assert False, "Expected run step for tool invocation"
    if not isinstance(result, RunStep):
        if isinstance(result, (list, tuple)):
            result = result[0]
        elif hasattr(result, "_mapping"):
            result = result[0]
    step = result

    audit_json = (step.metrics_json or {}).get("audit_json", "")
    assert "supersecret" not in audit_json
    assert "secret:test_token" in audit_json
