"""Smoke test for the LiteLLM runtime dependency."""

from importlib.metadata import version

import litellm


def test_litellm_dependency_exposes_required_async_apis():
    assert version("litellm") == "1.91.1"
    assert callable(litellm.acompletion)
    assert callable(litellm.aembedding)
    assert callable(litellm.arerank)
