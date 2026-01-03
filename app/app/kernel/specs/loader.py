""" loader

Load JSON Schemas from kernel/specs.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


_SCHEMA_CACHE: Dict[str, Dict[str, Any]] = {}


def get_specs_dir() -> Path:
    """Get specs directory path.
    
    Returns:
        Path to specs directory.
    """
    return Path(__file__).parent / "v1"


def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load JSON schema by name.
    
    Args:
        schema_name: Schema name (e.g., "workflow_spec", "tool_spec").
        
    Returns:
        Schema dictionary.
        
    Raises:
        FileNotFoundError: If schema file not found.
    """
    # Check cache
    if schema_name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[schema_name]
    
    # Load from file
    specs_dir = get_specs_dir()
    schema_file = specs_dir / f"{schema_name}.schema.json"
    
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema not found: {schema_name}")
    
    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    # Cache it
    _SCHEMA_CACHE[schema_name] = schema
    return schema


def list_schemas() -> list[str]:
    """List available schema names.
    
    Returns:
        List of schema names.
    """
    specs_dir = get_specs_dir()
    schemas = []
    for schema_file in specs_dir.glob("*.schema.json"):
        schema_name = schema_file.stem.replace(".schema", "")
        schemas.append(schema_name)
    return schemas
