""" repository

Identity repositories using scope-aware base.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.identity.domain.models import (
    User,
    Tenant,
    Workspace,
    TenantMembership,
    WorkspaceMembership,
)


class UserRepository:
    """Repository for User model (global scope)."""
    
    def __init__(self, db: Session):
        """Initialize user repository.
        
        Args:
            db: Database session.
        """
        self.db = db
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User ID.
            
        Returns:
            User instance or None if not found.
        """
        return self.db.get(User, user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: User email.
            
        Returns:
            User instance or None if not found.
        """
        query = select(User).where(User.email == email)
        return self.db.exec(query).first()
    
    def create(self, user: User) -> User:
        """Create a new user.
        
        Args:
            user: User instance to create.
            
        Returns:
            Created user instance.
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update(self, user: User) -> User:
        """Update an existing user.
        
        Args:
            user: User instance to update.
            
        Returns:
            Updated user instance.
        """
        self.db.commit()
        self.db.refresh(user)
        return user


class TenantRepository:
    """Repository for Tenant model (global scope)."""
    
    def __init__(self, db: Session):
        """Initialize tenant repository.
        
        Args:
            db: Database session.
        """
        self.db = db
    
    def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID.
        
        Args:
            tenant_id: Tenant ID.
            
        Returns:
            Tenant instance or None if not found.
        """
        return self.db.get(Tenant, tenant_id)
    
    def get_by_name(self, name: str) -> Optional[Tenant]:
        """Get tenant by name.
        
        Args:
            name: Tenant name.
            
        Returns:
            Tenant instance or None if not found.
        """
        query = select(Tenant).where(Tenant.name == name)
        return self.db.exec(query).first()
    
    def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant.
        
        Args:
            tenant: Tenant instance to create.
            
        Returns:
            Created tenant instance.
        """
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
    
    def update(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant.
        
        Args:
            tenant: Tenant instance to update.
            
        Returns:
            Updated tenant instance.
        """
        self.db.commit()
        self.db.refresh(tenant)
        return tenant


class WorkspaceRepository(Repository[Workspace]):
    """Repository for Workspace model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workspace repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Workspace, db, ctx)
    
    def get_by_name(self, name: str) -> Optional[Workspace]:
        """Get workspace by name.
        
        Args:
            name: Workspace name.
            
        Returns:
            Workspace instance or None if not found.
        """
        query = select(Workspace).where(
            and_(
                Workspace.tenant_id == self.ctx.tenant_id,
                Workspace.name == name,
            )
        )
        return self.db.exec(query).first()
    
    def list_by_tenant(self) -> List[Workspace]:
        """List all workspaces in tenant.
        
        Returns:
            List of Workspace instances.
        """
        query = select(Workspace).where(
            Workspace.tenant_id == self.ctx.tenant_id
        ).order_by(Workspace.created_at.desc())
        return list(self.db.exec(query).all())


class TenantMembershipRepository:
    """Repository for TenantMembership model."""
    
    def __init__(self, db: Session):
        """Initialize tenant membership repository.
        
        Args:
            db: Database session.
        """
        self.db = db
    
    def get(self, tenant_id: str, user_id: str) -> Optional[TenantMembership]:
        """Get membership.
        
        Args:
            tenant_id: Tenant ID.
            user_id: User ID.
            
        Returns:
            TenantMembership instance or None if not found.
        """
        return self.db.get(TenantMembership, (tenant_id, user_id))
    
    def get_by_user(self, user_id: str) -> List[TenantMembership]:
        """Get all memberships for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.user_id == user_id
        )
        return list(self.db.exec(query).all())
    
    def get_by_tenant(self, tenant_id: str) -> List[TenantMembership]:
        """Get all memberships for a tenant.
        
        Args:
            tenant_id: Tenant ID.
            
        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id
        )
        return list(self.db.exec(query).all())
    
    def create(self, membership: TenantMembership) -> TenantMembership:
        """Create a new membership.
        
        Args:
            membership: Membership instance to create.
            
        Returns:
            Created membership instance.
        """
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership
    
    def update(self, membership: TenantMembership) -> TenantMembership:
        """Update an existing membership.
        
        Args:
            membership: Membership instance to update.
            
        Returns:
            Updated membership instance.
        """
        self.db.commit()
        self.db.refresh(membership)
        return membership
    
    def delete(self, tenant_id: str, user_id: str) -> bool:
        """Delete a membership.
        
        Args:
            tenant_id: Tenant ID.
            user_id: User ID.
            
        Returns:
            True if deleted, False if not found.
        """
        membership = self.get(tenant_id, user_id)
        if not membership:
            return False
        
        self.db.delete(membership)
        self.db.commit()
        return True


class WorkspaceMembershipRepository:
    """Repository for WorkspaceMembership model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workspace membership repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
    
    def get(self, workspace_id: str, user_id: str) -> Optional[WorkspaceMembership]:
        """Get membership.
        
        Args:
            workspace_id: Workspace ID.
            user_id: User ID.
            
        Returns:
            WorkspaceMembership instance or None if not found.
        """
        return self.db.get(
            WorkspaceMembership,
            (self.ctx.tenant_id, workspace_id, user_id)
        )
    
    def get_by_workspace(self, workspace_id: str) -> List[WorkspaceMembership]:
        """Get all memberships for a workspace.
        
        Args:
            workspace_id: Workspace ID.
            
        Returns:
            List of WorkspaceMembership instances.
        """
        query = select(WorkspaceMembership).where(
            and_(
                WorkspaceMembership.tenant_id == self.ctx.tenant_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        return list(self.db.exec(query).all())
    
    def get_by_user(self, user_id: str) -> List[WorkspaceMembership]:
        """Get all workspace memberships for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            List of WorkspaceMembership instances.
        """
        query = select(WorkspaceMembership).where(
            and_(
                WorkspaceMembership.tenant_id == self.ctx.tenant_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        return list(self.db.exec(query).all())
    
    def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Create a new membership.
        
        Args:
            membership: Membership instance to create.
            
        Returns:
            Created membership instance.
        """
        # Ensure tenant_id matches context
        membership.tenant_id = self.ctx.tenant_id
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership
    
    def update(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Update an existing membership.
        
        Args:
            membership: Membership instance to update.
            
        Returns:
            Updated membership instance.
        """
        self.db.commit()
        self.db.refresh(membership)
        return membership
    
    def delete(self, workspace_id: str, user_id: str) -> bool:
        """Delete a membership.
        
        Args:
            workspace_id: Workspace ID.
            user_id: User ID.
            
        Returns:
            True if deleted, False if not found.
        """
        membership = self.get(workspace_id, user_id)
        if not membership:
            return False
        
        self.db.delete(membership)
        self.db.commit()
        return True

