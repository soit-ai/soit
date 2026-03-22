"""test_vault_secrets

Unit tests for the Vault secrets adapter.
"""

import pytest

pytest.importorskip("hvac")

from app.adapters.secrets.vault import VaultSecretsPort
from app.settings.settings import settings


def test_vault_adapter_imports():
    """Ensure the Vault adapter imports and initializes without URL."""
    original_url = settings.vault_url
    original_token = settings.vault_token
    settings.vault_url = None
    settings.vault_token = None
    try:
        adapter = VaultSecretsPort(url=None, token=None)
        assert adapter.client is None
    finally:
        settings.vault_url = original_url
        settings.vault_token = original_token
