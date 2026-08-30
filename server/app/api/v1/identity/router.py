""" router

Identity API router.
"""

from fastapi import APIRouter

from app.api.v1.identity import handlers

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
    "/refresh",
    handlers.refresh_token,
    methods=["POST"],
    summary="Exchange a refresh token for a new access token",
    tags=["identity"],
)

router.add_api_route(
    "/login/mfa",
    handlers.complete_mfa_login,
    methods=["POST"],
    summary="Complete a sign-in with a second factor",
    tags=["identity"],
)

router.add_api_route(
    "/me/deletion-request",
    handlers.get_account_deletion_request,
    methods=["GET"],
    summary="Read the caller's pending account closure",
    tags=["identity"],
)

router.add_api_route(
    "/me/deletion-request",
    handlers.request_account_deletion,
    methods=["POST"],
    summary="Ask for the account to be closed",
    tags=["identity"],
)

router.add_api_route(
    "/me/deletion-request",
    handlers.cancel_account_deletion,
    methods=["DELETE"],
    summary="Withdraw a pending account closure",
    tags=["identity"],
)

router.add_api_route(
    "/me/mfa",
    handlers.get_mfa_status,
    methods=["GET"],
    summary="Report the caller's second-factor state",
    tags=["identity"],
)

router.add_api_route(
    "/me/mfa/setup",
    handlers.start_mfa_enrolment,
    methods=["POST"],
    summary="Begin second-factor enrolment",
    tags=["identity"],
)

router.add_api_route(
    "/me/mfa/confirm",
    handlers.confirm_mfa_enrolment,
    methods=["POST"],
    summary="Activate the second factor and return recovery codes",
    tags=["identity"],
)

router.add_api_route(
    "/me/mfa/recovery-codes",
    handlers.regenerate_mfa_recovery_codes,
    methods=["POST"],
    summary="Replace the recovery codes",
    tags=["identity"],
)

router.add_api_route(
    # POST rather than DELETE: turning this off carries a password, and a
    # password belongs in a body. A DELETE body is legal but widely dropped by
    # proxies, and putting it in the query string would log it.
    "/me/mfa/disable",
    handlers.disable_mfa,
    methods=["POST"],
    status_code=204,
    summary="Turn the second factor off",
    tags=["identity"],
)

router.add_api_route(
    "/me/views",
    handlers.list_saved_views,
    methods=["GET"],
    summary="List the caller's saved views",
    tags=["preferences"],
)

router.add_api_route(
    "/me/views",
    handlers.create_saved_view,
    methods=["POST"],
    summary="Save a view",
    tags=["preferences"],
)

router.add_api_route(
    "/me/views/{view_id}",
    handlers.update_saved_view,
    methods=["PATCH"],
    summary="Update a saved view",
    tags=["preferences"],
)

router.add_api_route(
    "/me/views/{view_id}",
    handlers.delete_saved_view,
    methods=["DELETE"],
    status_code=204,
    summary="Delete a saved view",
    tags=["preferences"],
)

router.add_api_route(
    "/me/pins",
    handlers.list_pins,
    methods=["GET"],
    summary="List the caller's pinned objects",
    tags=["preferences"],
)

router.add_api_route(
    "/me/pins",
    handlers.create_pin,
    methods=["POST"],
    summary="Pin an object",
    tags=["preferences"],
)

router.add_api_route(
    "/me/pins/{pin_id}",
    handlers.delete_pin,
    methods=["DELETE"],
    status_code=204,
    summary="Unpin an object",
    tags=["preferences"],
)

router.add_api_route(
    "/me/workspaces",
    handlers.list_my_workspaces,
    methods=["GET"],
    summary="List the caller's own workspaces",
    tags=["workspaces"],
)

router.add_api_route(
    "/me/sessions",
    handlers.list_sessions,
    methods=["GET"],
    summary="List the caller's sessions",
    tags=["identity"],
)

router.add_api_route(
    "/me/sessions/revoke-all",
    handlers.revoke_all_sessions,
    methods=["POST"],
    summary="Sign out of every session",
    tags=["identity"],
)

router.add_api_route(
    "/me/sessions/{session_id}",
    handlers.revoke_session,
    methods=["DELETE"],
    summary="End one session",
    tags=["identity"],
)

router.add_api_route(
    "/me",
    handlers.get_current_user,
    methods=["GET"],
    summary="Get current user",
    tags=["users"],
)

router.add_api_route(
    "/me",
    handlers.update_current_user,
    methods=["PATCH"],
    summary="Update current user profile",
    tags=["users"],
)

router.add_api_route(
    "/me/password",
    handlers.change_password,
    methods=["POST"],
    summary="Change current user password",
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
    "/workspaces/{workspace_id}",
    handlers.update_workspace,
    methods=["PATCH"],
    summary="Update workspace",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}/members",
    handlers.list_workspace_members,
    methods=["GET"],
    summary="List workspace members",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}/members",
    handlers.add_workspace_member,
    methods=["POST"],
    summary="Add a member to workspace",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}/members/{user_id}",
    handlers.update_workspace_member,
    methods=["PATCH"],
    summary="Update workspace member role",
    tags=["workspaces"],
)

router.add_api_route(
    "/workspaces/{workspace_id}/members/{user_id}",
    handlers.remove_workspace_member,
    methods=["DELETE"],
    summary="Remove workspace member",
    tags=["workspaces"],
)

# API key endpoints
router.add_api_route(
    "/api-keys",
    handlers.create_api_key,
    methods=["POST"],
    summary="Create API key",
    tags=["api_keys"],
)

router.add_api_route(
    "/api-keys",
    handlers.list_api_keys,
    methods=["GET"],
    summary="List API keys",
    tags=["api_keys"],
)

router.add_api_route(
    "/api-keys/{key_id}/revoke",
    handlers.revoke_api_key,
    methods=["POST"],
    summary="Revoke API key",
    tags=["api_keys"],
)

router.add_api_route(
    "/api-keys/{key_id}/rotate",
    handlers.rotate_api_key,
    methods=["POST"],
    summary="Rotate API key",
    tags=["api_keys"],
)

# Resource grant endpoints
router.add_api_route(
    "/resource-grants",
    handlers.create_resource_grant,
    methods=["POST"],
    summary="Create or update resource grant",
    tags=["resource_grants"],
)

router.add_api_route(
    "/resource-grants",
    handlers.list_resource_grants,
    methods=["GET"],
    summary="List resource grants for a resource",
    tags=["resource_grants"],
)

router.add_api_route(
    "/resource-grants/{resource_type}/{resource_id}/{user_id}",
    handlers.revoke_resource_grant,
    methods=["DELETE"],
    summary="Revoke resource grant",
    tags=["resource_grants"],
)
