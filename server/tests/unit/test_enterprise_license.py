"""The Community runtime reads a signed Enterprise license and falls back to Community."""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.kernel.entitlements import edition as edition_state
from app.kernel.entitlements.edition import current_edition
from app.kernel.entitlements.license import (
    LicenseStatus,
    canonical_payload,
    load_license,
    verify_license,
)
from app.kernel.runtime.db.models.usage import UsageDailyAggregate
from app.wiring import edition as edition_wiring
from app.wiring import extensions as extension_wiring
from app.wiring.edition import (
    license_heartbeat,
    metering_month_to_date,
    resolve_edition,
)
from app.wiring.extensions import mount_extensions

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
SIGNER = Ed25519PrivateKey.generate()


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "license_id": "lic_acme_2026",
        "customer_id": "acme",
        "issued_at": (NOW - timedelta(days=1)).isoformat(),
        "expires_at": (NOW + timedelta(days=365)).isoformat(),
        "entitlements": ["security.sso", "deployment.offline_license"],
    }
    payload.update(overrides)
    return payload


def _envelope(payload: dict[str, Any], signer: Ed25519PrivateKey = SIGNER) -> str:
    # The Enterprise issuer's format: sorted keys, canonical payload signed.
    signature = signer.sign(canonical_payload(payload))
    return json.dumps(
        {"alg": "Ed25519", "payload": payload, "signature": base64.b64encode(signature).decode()},
        sort_keys=True,
    )


def _pem(signer: Ed25519PrivateKey = SIGNER) -> bytes:
    return signer.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


def _raw_b64(signer: Ed25519PrivateKey = SIGNER) -> bytes:
    return base64.b64encode(signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def _files(tmp_path: Path, envelope: str, key: bytes | None = None) -> tuple[str, str]:
    license_file = tmp_path / "license.json"
    license_file.write_text(envelope, encoding="utf-8")
    key_file = tmp_path / "license.pub"
    key_file.write_bytes(key if key is not None else _pem())
    return str(license_file), str(key_file)


@pytest.fixture(autouse=True)
def _fresh_edition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edition_state, "_current", None)


class TestVerification:
    def test_no_license_is_community(self) -> None:
        state = load_license(None, None, now=NOW)
        assert state.status is LicenseStatus.ABSENT
        assert state.edition == "community"

    @pytest.mark.parametrize("key", [_pem(), _raw_b64()], ids=["pem", "raw-base64"])
    def test_a_signed_current_license_is_active(self, tmp_path: Path, key: bytes) -> None:
        state = load_license(*_files(tmp_path, _envelope(_payload()), key), now=NOW)

        assert state.status is LicenseStatus.ACTIVE
        assert state.edition == "enterprise"
        assert state.license is not None and state.license.customer_id == "acme"
        assert state.entitlements == {"security.sso", "deployment.offline_license"}
        assert state.days_left(NOW) == 365

    def test_an_expired_license_grants_nothing(self, tmp_path: Path) -> None:
        payload = _payload(expires_at=(NOW - timedelta(seconds=1)).isoformat())
        state = load_license(*_files(tmp_path, _envelope(payload)), now=NOW)

        assert state.status is LicenseStatus.EXPIRED
        assert state.edition == "community"
        assert state.entitlements == frozenset()
        assert state.license is not None and state.license.license_id == "lic_acme_2026"

    def test_a_changed_payload_fails_its_signature(self, tmp_path: Path) -> None:
        envelope = json.loads(_envelope(_payload()))
        envelope["payload"]["entitlements"].append("security.scim")
        state = load_license(*_files(tmp_path, json.dumps(envelope)), now=NOW)

        assert state.status is LicenseStatus.INVALID
        assert "signature" in (state.reason or "")
        assert state.entitlements == frozenset()

    def test_another_issuers_key_does_not_verify(self, tmp_path: Path) -> None:
        state = load_license(*_files(tmp_path, _envelope(_payload()), _pem(Ed25519PrivateKey.generate())), now=NOW)
        assert state.status is LicenseStatus.INVALID

    def test_a_license_from_the_future_is_not_valid_yet(self, tmp_path: Path) -> None:
        payload = _payload(issued_at=(NOW + timedelta(days=2)).isoformat())
        state = load_license(*_files(tmp_path, _envelope(payload)), now=NOW)
        assert state.status is LicenseStatus.INVALID
        assert state.reason == "the license is not valid yet"

    @pytest.mark.parametrize(
        "envelope",
        [
            "not json",
            json.dumps({"alg": "HS256", "payload": {}, "signature": ""}),
            json.dumps({"alg": "Ed25519", "payload": "x", "signature": ""}),
            json.dumps({"alg": "Ed25519", "payload": {}, "signature": "***"}),
        ],
        ids=["not-json", "other-alg", "payload-not-object", "signature-not-base64"],
    )
    def test_a_malformed_file_is_invalid_not_an_error(self, tmp_path: Path, envelope: str) -> None:
        state = load_license(*_files(tmp_path, envelope), now=NOW)
        assert state.status is LicenseStatus.INVALID
        assert state.reason

    def test_a_payload_missing_a_field_is_invalid(self, tmp_path: Path) -> None:
        payload = _payload()
        del payload["customer_id"]
        state = load_license(*_files(tmp_path, _envelope(payload)), now=NOW)
        assert state.status is LicenseStatus.INVALID
        assert "customer_id" in (state.reason or "")

    def test_a_license_without_its_public_key_cannot_be_verified(self, tmp_path: Path) -> None:
        license_path, _ = _files(tmp_path, _envelope(_payload()))
        state = load_license(license_path, None, now=NOW)
        assert state.status is LicenseStatus.INVALID
        assert "ENTERPRISE_LICENSE_PUBLIC_KEY_PATH" in (state.reason or "")

    def test_a_missing_file_is_named(self, tmp_path: Path) -> None:
        state = load_license(str(tmp_path / "gone.json"), str(tmp_path / "gone.pub"), now=NOW)
        assert state.status is LicenseStatus.INVALID
        assert "gone.json" in (state.reason or "")

    def test_the_enterprise_issuers_envelope_verifies(self) -> None:
        # soit_enterprise.licensing.Ed25519LicenseIssuer writes exactly this.
        payload = _payload()
        issued = json.dumps(
            {
                "alg": "Ed25519",
                "payload": payload,
                "signature": base64.b64encode(
                    SIGNER.sign(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                ).decode("ascii"),
            },
            sort_keys=True,
        )
        assert verify_license(issued, _pem(), now=NOW).status is LicenseStatus.ACTIVE


def _settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "platform_edition": "community",
        "platform_entitlements": [],
        "enterprise_license_path": None,
        "enterprise_license_public_key_path": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _enterprise_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "features.enterprise.json"
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "owner": "enterprise",
                "features": [
                    {"key": "security.sso", "editions": ["enterprise", "cloud"], "kind": "product"},
                    {"key": "deployment.offline_license", "editions": ["enterprise"], "kind": "deployment"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry


class TestEdition:
    def test_without_a_license_the_settings_are_left_alone(self) -> None:
        settings = _settings()
        state = resolve_edition(settings)

        assert (settings.platform_edition, settings.platform_entitlements) == ("community", [])
        assert state.edition == "community"
        assert "agent.runtime" in state.enabled_features
        assert current_edition() is state

    def test_an_active_license_turns_on_the_features_an_extension_defines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(edition_wiring, "extension_feature_files", lambda: [_enterprise_registry(tmp_path)])
        license_path, key_path = _files(tmp_path, _envelope(_payload(entitlements=["security.sso", "security.scim"])))
        settings = _settings(enterprise_license_path=license_path, enterprise_license_public_key_path=key_path)

        state = resolve_edition(settings)

        assert settings.platform_edition == "enterprise"
        assert settings.platform_entitlements == ["security.sso"]
        assert "security.sso" in state.enabled_features
        # No installed package defines it: reported, not fatal.
        assert state.ignored_entitlements == {"security.scim"}

    def test_a_license_without_the_extension_installed_grants_only_community(self, tmp_path: Path) -> None:
        license_path, key_path = _files(tmp_path, _envelope(_payload()))
        settings = _settings(enterprise_license_path=license_path, enterprise_license_public_key_path=key_path)

        state = resolve_edition(settings)

        assert settings.platform_edition == "enterprise"
        assert settings.platform_entitlements == []
        assert state.ignored_entitlements == {"security.sso", "deployment.offline_license"}

    def test_a_configured_license_that_fails_drops_to_community(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        license_path, key_path = _files(tmp_path, _envelope(_payload(expires_at="2020-01-01T00:00:00+00:00")))
        settings = _settings(
            platform_edition="enterprise",
            platform_entitlements=["security.sso"],
            enterprise_license_path=license_path,
            enterprise_license_public_key_path=key_path,
        )

        with caplog.at_level(logging.ERROR, logger="app.wiring.edition"):
            state = resolve_edition(settings)

        assert (settings.platform_edition, settings.platform_entitlements) == ("community", [])
        assert state.license.status is LicenseStatus.EXPIRED
        assert "running as Community" in caplog.text


class TestExtensions:
    def test_an_installed_extension_is_mounted_and_a_broken_one_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def mount(app: FastAPI, settings: Any) -> None:
            router = APIRouter()

            @router.get("/api/v1/enterprise/ping")
            def ping() -> dict[str, str]:
                return {"edition": settings.platform_edition}

            app.include_router(router)

        def broken(_app: FastAPI, _settings: Any) -> None:
            raise RuntimeError("missing dependency")

        entries = [
            SimpleNamespace(name="enterprise", load=lambda: mount),
            SimpleNamespace(name="broken", load=lambda: broken),
        ]
        monkeypatch.setattr(
            "importlib.metadata.entry_points",
            lambda group: entries if group == extension_wiring.EXTENSION_GROUP else [],
        )
        app = FastAPI()

        mounts = mount_extensions(app, _settings(platform_edition="enterprise"))

        assert [(m.name, m.status) for m in mounts] == [("enterprise", "mounted"), ("broken", "failed")]
        assert "missing dependency" in (mounts[1].error or "")
        assert TestClient(app).get("/api/v1/enterprise/ping").json() == {"edition": "enterprise"}


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_it_reads_the_months_metering(self, async_db) -> None:
        today = datetime.now(UTC).date()
        for user, key, calls in (("u1", "k1", 3), ("u1", "", 2), ("u2", "k2", 5)):
            async_db.add(
                UsageDailyAggregate(
                    tenant_id="t", workspace_id="w", day=today, user_id=user, api_key_id=key, call_count=calls
                )
            )
        await async_db.commit()

        metering = await metering_month_to_date(async_sessionmaker(bind=async_db.bind), today)

        assert metering == {"metered_calls": 10, "active_principals": 2, "active_api_keys": 2}

    @pytest.mark.asyncio
    async def test_a_license_that_lapses_while_running_drops_the_edition(
        self, tmp_path: Path, async_db, caplog: pytest.LogCaptureFixture
    ) -> None:
        license_path, key_path = _files(tmp_path, _envelope(_payload()))
        settings = _settings(enterprise_license_path=license_path, enterprise_license_public_key_path=key_path)
        resolve_edition(settings)
        assert settings.platform_edition == "enterprise"

        Path(license_path).write_text(
            _envelope(_payload(expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat())),
            encoding="utf-8",
        )
        with caplog.at_level(logging.INFO, logger="app.wiring.edition"):
            state = await license_heartbeat(settings, async_sessionmaker(bind=async_db.bind))

        assert state.edition == "community"
        assert settings.platform_edition == "community"
        assert current_edition().license.status is LicenseStatus.EXPIRED
        beat = next(record for record in caplog.records if getattr(record, "event", None) == "license.heartbeat")
        assert beat.levelno == logging.WARNING
        assert beat.license_status == "expired"
        assert beat.metered_calls == 0
