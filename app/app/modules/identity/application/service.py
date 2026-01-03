""" service

Identity domain business logic.
"""

from typing import Optional, Callable
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.auth import JWTManager
from app.kernel.commons.errors import NotFoundError, ValidationError, UnauthorizedError
from app.kernel.commons.time import utcnow as utc_now
from app.modules.identity.domain.models import (
    User,
    Tenant,
    Workspace,
    TenantMembership,
    WorkspaceMembership,
)
from app.modules.identity.application.ports import (
    UserRepositoryPort,
    TenantRepositoryPort,
    TenantMembershipRepositoryPort,
    WorkspaceRepositoryPort,
    WorkspaceMembershipRepositoryPort,
)
from app.modules.identity.application.schemas import (
    UserCreate,
    TenantCreate,
    WorkspaceCreate,
    MembershipCreate,
)
from app.kernel.identity.rbac import (
    TENANT_ROLE_OWNER,
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_MAINTAINER,
    WORKSPACE_ROLE_READER,
)


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class IdentityService:
    """Service for identity management."""
    
    def __init__(
        self,
        db: Session,
        jwt_manager: JWTManager,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        tenant_membership_repo: TenantMembershipRepositoryPort,
        workspace_repo_factory: Callable[[RequestContext], WorkspaceRepositoryPort],
        workspace_membership_repo_factory: Callable[[RequestContext], WorkspaceMembershipRepositoryPort],
    ):
        """Initialize identity service.
        
        Args:
            db: Database session.
            jwt_manager: JWT manager instance.
        """
        self.db = db
        self.jwt_manager = jwt_manager
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.tenant_membership_repo = tenant_membership_repo
        self.workspace_repo_factory = workspace_repo_factory
        self.workspace_membership_repo_factory = workspace_membership_repo_factory

    def register_user(
        self,
        user_data: UserCreate,
        tenant_name: Optional[str] = None,
    ) -> tuple[User, Tenant, str]:
        """Register a new user and optionally create a tenant.
        
        Args:
            user_data: User creation data.
            tenant_name: Optional tenant name (creates tenant if provided).
            
        Returns:
            Tuple of (User, Tenant, access_token).
            
        Raises:
            ValidationError: If user already exists or validation fails.
        """
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise ValidationError("User with this email already exists")
        
        # Create user
        password_hash = pwd_context.hash(user_data.password)
        user = User(
            email=user_data.email,
            password_hash=password_hash,
            name=user_data.name,
        )
        user = self.user_repo.create(user)
        
        # Create tenant if name provided
        tenant = None
        if tenant_name:
            tenant = Tenant(name=tenant_name)
            tenant = self.tenant_repo.create(tenant)
            
            # Create owner membership
            membership = TenantMembership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=TENANT_ROLE_OWNER,
            )
            self.tenant_membership_repo.create(membership)
        
        # Generate access token
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant.id if tenant else "",
            tenant_role=TENANT_ROLE_OWNER if tenant else None,
        )
        
        return user, tenant, access_token
    
    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> tuple[User, str]:
        """Authenticate a user.
        
        Args:
            email: User email.
            password: User password.
            
        Returns:
            Tuple of (User, access_token).
            
        Raises:
            UnauthorizedError: If authentication fails.
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedError("Invalid email or password")
        
        if not user.is_active:
            raise UnauthorizedError("User account is inactive")
        
        if not pwd_context.verify(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        
        # Get user's primary tenant (first membership)
        memberships = self.tenant_membership_repo.get_by_user(user.id)
        tenant_id = memberships[0].tenant_id if memberships else ""
        tenant_role = memberships[0].role if memberships else None
        
        # Generate access token
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant_id,
            tenant_role=tenant_role,
        )
        
        return user, access_token
    
    def create_tenant(
        self,
        tenant_data: TenantCreate,
        user_id: str,
    ) -> Tenant:
        """Create a new tenant.
        
        Args:
            tenant_data: Tenant creation data.
            user_id: User ID of the creator (becomes owner).
            
        Returns:
            Created Tenant instance.
        """
        # Check if tenant name already exists
        existing = self.tenant_repo.get_by_name(tenant_data.name)
        if existing:
            raise ValidationError("Tenant with this name already exists")
        
        # Create tenant
        tenant = Tenant(
            name=tenant_data.name,
            plan=tenant_data.plan,
        )
        tenant = self.tenant_repo.create(tenant)
        
        # Create owner membership
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user_id,
            role=TENANT_ROLE_OWNER,
        )
        self.tenant_membership_repo.create(membership)
        
        return tenant
    
    def create_workspace(
        self,
        workspace_data: WorkspaceCreate,
        ctx: RequestContext,
    ) -> Workspace:
        """Create a new workspace.
        
        Args:
            workspace_data: Workspace creation data.
            ctx: Request context.
            
        Returns:
            Created Workspace instance.
        """
        workspace_repo = self.workspace_repo_factory(ctx)
        
        # Check if workspace name already exists in tenant
        existing = workspace_repo.get_by_name(workspace_data.name)
        if existing:
            raise ValidationError("Workspace with this name already exists")
        
        # Create workspace
        workspace = Workspace(
            tenant_id=ctx.tenant_id,
            name=workspace_data.name,
            description=workspace_data.description,
        )
        workspace = workspace_repo.create(workspace)
        
        # Create owner membership
        membership_repo = self.workspace_membership_repo_factory(ctx)
        membership = WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.id,
            user_id=ctx.user_id,
            role=WORKSPACE_ROLE_OWNER,
        )
        membership_repo.create(membership)
        
        return workspace
    
    def add_tenant_member(
        self,
        tenant_id: str,
        membership_data: MembershipCreate,
        ctx: RequestContext,
    ) -> TenantMembership:
        """Add a member to a tenant.
        
        Args:
            tenant_id: Tenant ID.
            membership_data: Membership creation data.
            ctx: Request context.
            
        Returns:
            Created TenantMembership instance.
            
        Raises:
            ForbiddenError: If user doesn't have permission.
            NotFoundError: If tenant or user not found.
        """
        # Check permission (only tenant admin/owner can add members)
        if ctx.tenant_id != tenant_id:
            raise ValidationError("Cannot add members to different tenant")
        
        if not ctx.is_tenant_admin():
            raise ValidationError("Tenant admin role required")
        
        # Verify tenant exists
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundError("Tenant not found")
        
        # Verify user exists
        user = self.user_repo.get_by_id(membership_data.user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Check if membership already exists
        existing = self.tenant_membership_repo.get(tenant_id, membership_data.user_id)
        if existing:
            raise ValidationError("User is already a member of this tenant")
        
        # Create membership
        membership = TenantMembership(
            tenant_id=tenant_id,
            user_id=membership_data.user_id,
            role=membership_data.role,
        )
        return self.tenant_membership_repo.create(membership)
    
    def add_workspace_member(
        self,
        workspace_id: str,
        membership_data: MembershipCreate,
        ctx: RequestContext,
    ) -> WorkspaceMembership:
        """Add a member to a workspace.
        
        Args:
            workspace_id: Workspace ID.
            membership_data: Membership creation data.
            ctx: Request context.
            
        Returns:
            Created WorkspaceMembership instance.
            
        Raises:
            ForbiddenError: If user doesn't have permission.
            NotFoundError: If workspace or user not found.
        """
        # Check permission (only workspace owner/maintainer can add members)
        workspace_repo = self.workspace_repo_factory(ctx)
        workspace = workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        
        if not ctx.can_write():
            raise ValidationError("Workspace write permission required")
        
        # Verify user exists
        user = self.user_repo.get_by_id(membership_data.user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Verify user is member of tenant
        tenant_membership = self.tenant_membership_repo.get(ctx.tenant_id, membership_data.user_id)
        if not tenant_membership:
            raise ValidationError("User must be a member of the tenant first")
        
        # Check if membership already exists
        membership_repo = self.workspace_membership_repo_factory(ctx)
        existing = membership_repo.get(workspace_id, membership_data.user_id)
        if existing:
            raise ValidationError("User is already a member of this workspace")
        
        # Create membership
        membership = WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace_id,
            user_id=membership_data.user_id,
            role=membership_data.role,
        )
        return membership_repo.create(membership)
    
    def get_user_workspace_role(
        self,
        workspace_id: str,
        user_id: str,
        ctx: RequestContext,
    ) -> Optional[str]:
        """Get user's role in a workspace.
        
        Args:
            workspace_id: Workspace ID.
            user_id: User ID.
            ctx: Request context.
            
        Returns:
            Role string or None if not a member.
        """
        membership_repo = self.workspace_membership_repo_factory(ctx)
        membership = membership_repo.get(workspace_id, user_id)
        return membership.role if membership else None
    
    def get_user_tenant_role(
        self,
        tenant_id: str,
        user_id: str,
    ) -> Optional[str]:
        """Get user's role in a tenant.
        
        Args:
            tenant_id: Tenant ID.
            user_id: User ID.
            
        Returns:
            Role string or None if not a member.
        """
        membership = self.tenant_membership_repo.get(tenant_id, user_id)
        return membership.role if membership else None

