"""Smoke test for the optional LiteLLM runtime dependency."""

from importlib.metadata import version

import pytest


def test_litellm_optional_dependency_exposes_required_async_apis():
    litellm = pytest.importorskip("litellm")

    assert version("litellm") == "1.91.1"
    assert callable(litellm.acompletion)
    assert callable(litellm.aembedding)
    assert callable(litellm.arerank)
