"""test_registry_scope

Registry must isolate artifacts by tenant/workspace.
"""

from app.kernel.registry.deps import get_registry


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
