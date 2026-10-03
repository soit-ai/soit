"""How a resumed workflow node treats the decision on its tool call."""

APPROVAL_REJECTED = "APPROVAL_REJECTED"
"""Error code of a node whose tool call was rejected, canceled or expired."""


class WorkflowApprovalDeclined(Exception):
    """A resumed tool call whose approval was not granted.

    The node fails without calling the tool and is never retried: the
    decision is final, and only ``approved`` lets a waiting call run.
    """

    def __init__(self, *, node_id: str, status: str | None) -> None:
        self.node_id = node_id
        self.status = status or "missing"
        super().__init__(f"Tool call of node {node_id} was not approved ({self.status})")
