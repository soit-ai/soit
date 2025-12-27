""" test_spec_validation

Spec validation tests - verify JSON Schema validation.
"""

import pytest
import json
from app.kernel.specs.loader import load_spec
from app.kernel.specs.validator import validate_spec


def test_workflow_spec_validation():
    """Test workflow spec validation."""
    # Load workflow spec schema
    schema = load_spec("workflow_spec")
    
    # Valid workflow spec
    valid_spec = {
        "version": "1.0",
        "nodes": [
            {
                "id": "node1",
                "type": "llm",
                "config": {
                    "model": "model:openai:gpt-4",
                    "prompt": "Hello {{ inputs.name }}",
                }
            }
        ],
        "edges": [],
    }
    
    # Should validate successfully
    assert validate_spec(valid_spec, schema) is True
    
    # Invalid workflow spec (missing required fields)
    invalid_spec = {
        "version": "1.0",
        # Missing nodes
    }
    
    # Should fail validation
    with pytest.raises(Exception):
        validate_spec(invalid_spec, schema)


def test_tool_spec_validation():
    """Test tool spec validation."""
    schema = load_spec("tool_spec")
    
    # Valid tool spec
    valid_spec = {
        "name": "http_get",
        "type": "http",
        "description": "HTTP GET request",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    }
    
    assert validate_spec(valid_spec, schema) is True
    
    # Invalid tool spec
    invalid_spec = {
        "name": "http_get",
        # Missing type
    }
    
    with pytest.raises(Exception):
        validate_spec(invalid_spec, schema)


def test_dataset_spec_validation():
    """Test dataset spec validation."""
    schema = load_spec("dataset_spec")
    
    # Valid dataset spec
    valid_spec = {
        "name": "test_dataset",
        "description": "Test dataset",
        "index_config": {
            "embedding_model": "model:openai:text-embedding-ada-002",
            "chunk_size": 1000,
        },
    }
    
    assert validate_spec(valid_spec, schema) is True

