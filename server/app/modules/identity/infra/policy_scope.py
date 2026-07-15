"""Identity policy scope adapter for security application consumers."""

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.modules.identity.domain.models import Tenant, Workspace
from app.modules.identity.infra.repository import TenantRepository, WorkspaceRepository


class DatabaseIdentityPolicyScopePort:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.tenant_repo = TenantRepository(db)
        self.workspace_repo = WorkspaceRepository(db, ctx)

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        return self.tenant_repo.get_by_id(tenant_id)

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self.workspace_repo.get_by_id(workspace_id)
