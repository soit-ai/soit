"""test_vault_secrets

Unit tests for the Vault secrets adapter.
"""

import threading
from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_vault_sdk_operations_run_outside_event_loop_thread():
    main_thread = threading.get_ident()
    call_threads: list[int] = []

    class _KVV2:
        def read_secret_version(self, *, path):
            call_threads.append(threading.get_ident())
            return {"data": {"data": {"value": "secret-value"}}}

        def create_or_update_secret(self, *, path, secret):
            call_threads.append(threading.get_ident())

        def delete_metadata_and_all_versions(self, *, path):
            call_threads.append(threading.get_ident())

    adapter = VaultSecretsPort(url=None, token=None)
    adapter.client = SimpleNamespace(
        secrets=SimpleNamespace(kv=SimpleNamespace(v2=_KVV2()))
    )

    assert await adapter.get_secret("secret:provider-key") == "secret-value"
    await adapter.set_secret("secret:provider-key", "new-value")
    await adapter.delete_secret("secret:provider-key")

    assert len(call_threads) == 3
    assert all(thread_id != main_thread for thread_id in call_threads)
