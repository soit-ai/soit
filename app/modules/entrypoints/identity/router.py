""" router

Identity API router.
"""

from fastapi import APIRouter

from app.modules.entrypoints.identity import handlers


router = APIRouter()


# Auth endpoints
router.add_api_route(
    "/register",
    handlers.register,
    methods=["POST"],
    summary="Register a new user",
    tags=["auth"],
)

router.add_api_route(
    "/login",
    handlers.login,
    methods=["POST"],
    summary="Login user",
    tags=["auth"],
)

router.add_api_route(
    "/me",
    handlers.get_current_user,
    methods=["GET"],
    summary="Get current user",
    tags=["users"],
)

# Tenant endpoints
router.add_api_route(
    "/tenants",
    handlers.create_tenant,
    methods=["POST"],
    summary="Create a new tenant",
    tags=["tenants"],
)

router.add_api_route(
    "/tenants/{tenant_id}",
    handlers.get_tenant,
    methods=["GET"],
    summary="Get tenant by ID",
    tags=["tenants"],
)

router.add_api_route(
    "/tenants/{tenant_id}/members",
    handlers.add_tenant_member,
    methods=["POST"],
    summary="Add a member to tenant",
    tags=["tenants"],
)

# Workspace endpoints
router.add_api_route(
    "/workspaces",
    handlers.create_workspace,
    methods=["POST"],
    summary="Create a new workspace",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces",
    handlers.list_workspaces,
    methods=["GET"],
    summary="List workspaces",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}",
    handlers.get_workspace,
    methods=["GET"],
    summary="Get workspace by ID",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}/members",
    handlers.add_workspace_member,
    methods=["POST"],
    summary="Add a member to workspace",
    tags=["workspaces"],
)

