""" ids

ULID/UUID helpers.
"""

import uuid
from typing import Optional


def generate_ulid() -> str:
    """Generate a ULID-like sortable ID.
    
    For now, we use UUID4 with prefix. In production, consider using
    python-ulid or similar library for true ULID generation.
    
    Returns:
        A string ID prefixed with type indicator.
    """
    return f"id_{uuid.uuid4().hex}"


def generate_run_id() -> str:
    """Generate a run ID.
    
    Returns:
        A run ID string (e.g., "run_01H...").
    """
    return f"run_{uuid.uuid4().hex}"


def generate_step_id() -> str:
    """Generate a step ID.
    
    Returns:
        A step ID string (e.g., "st_01H...").
    """
    return f"st_{uuid.uuid4().hex}"


def generate_tenant_id() -> str:
    """Generate a tenant ID.
    
    Returns:
        A tenant ID string (e.g., "t_01H...").
    """
    return f"t_{uuid.uuid4().hex}"


def generate_workspace_id() -> str:
    """Generate a workspace ID.
    
    Returns:
        A workspace ID string (e.g., "w_01H...").
    """
    return f"w_{uuid.uuid4().hex}"


def generate_user_id() -> str:
    """Generate a user ID.
    
    Returns:
        A user ID string (e.g., "u_01H...").
    """
    return f"u_{uuid.uuid4().hex}"


def generate_artifact_id() -> str:
    """Generate an artifact ID.
    
    Returns:
        An artifact ID string (e.g., "art_01H...").
    """
    return f"art_{uuid.uuid4().hex}"


def generate_workflow_id() -> str:
    """Generate a workflow ID.
    
    Returns:
        A workflow ID string (e.g., "wf_01H...").
    """
    return f"wf_{uuid.uuid4().hex}"


def generate_workflow_version_id() -> str:
    """Generate a workflow version ID.
    
    Returns:
        A workflow version ID string (e.g., "wfv_01H...").
    """
    return f"wfv_{uuid.uuid4().hex}"


def parse_id(id_str: str) -> Optional[str]:
    """Parse and validate an ID string.
    
    Args:
        id_str: The ID string to parse.
        
    Returns:
        The ID string if valid, None otherwise.
    """
    if not id_str or not isinstance(id_str, str):
        return None
    if len(id_str) < 3:
        return None
    return id_str
