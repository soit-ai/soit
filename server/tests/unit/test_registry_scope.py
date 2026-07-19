"""test_registry_scope

Registry must isolate artifacts by tenant/workspace.
"""

from app.kernel.registry.deps import get_registry
from app.kernel.registry.registry import Registry


def test_registry_is_scoped_by_tenant_workspace():
    reg = get_registry()
    reg.clear_scope("t1", "w1")
    reg.clear_scope("t2", "w2")

    reg.register(kind="tool", tenant_id="t1", workspace_id="w1", name="tool:http:x", version="1", payload={"a": 1})
    reg.register(kind="tool", tenant_id="t2", workspace_id="w2", name="tool:http:x", version="1", payload={"a": 2})

    k1, p1 = reg.get(kind="tool", tenant_id="t1", workspace_id="w1", name="tool:http:x", version="1")
    k2, p2 = reg.get(kind="tool", tenant_id="t2", workspace_id="w2", name="tool:http:x", version="1")

    assert p1["a"] == 1
    assert p2["a"] == 2


def test_registry_latest_falls_back_to_lexicographic_when_any_version_is_invalid():
    registry = Registry()
    scope = {
        "kind": "tool",
        "tenant_id": "test-tenant",
        "workspace_id": "test-workspace",
        "name": "tool:function:registry-cache",
    }
    registry.register(**scope, version="1.0.0", payload={"label": "stable"})
    registry.register(
        **scope,
        version="registry-cache",
        payload={"label": "lexicographic"},
    )

    latest = registry.get_latest(**scope)

    assert latest is not None
    key, payload = latest
    assert key.version == "registry-cache"
    assert payload == {"label": "lexicographic"}
