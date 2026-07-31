"""Build a plugin package fixture, optionally signed.

The real-backend end-to-end suite needs a package it can install against a live
server. Generating it here rather than committing a binary keeps the fixture
readable and lets the signing key be produced per run, so no private key is
ever stored in the repository.

Usage:
    uv run python scripts/build_plugin_fixture.py --out /tmp/fixture
Writes ``plugin.zip`` plus ``keys.json`` holding the base64 public key and the
package digest, which the caller feeds to the server as trusted configuration.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from app.kernel.registry.signature import payload_digest, sha256_hex

TOOL_REF = "tool:http:e2e_echo"


def build_package(name: str, version: str) -> tuple[bytes, dict[str, Any]]:
    """Return the unsigned package bytes and the manifest it contains."""
    spec: dict[str, Any] = {
        "name": name,
        "publisher": "soit",
        "version": version,
        "plugin_type": "tool",
        "runtime_level": "L0",
        "capabilities": ["tools"],
        "exports": {"tools": [TOOL_REF]},
        "artifacts": {"tools": {TOOL_REF: "tools/e2e_echo.json"}},
        "permissions": {"network": ["example.com"]},
        # Filled in below once the payload exists.
        "integrity": {"digest": ""},
    }
    manifest = {
        "name": name,
        "version": version,
        "runtime": {"type": "http", "base_url": "https://example.com"},
        "spec": spec,
    }
    # The payload digest excludes the manifest, so recording it does not
    # change what it describes; one extra pass is enough to make it accurate.
    manifest["spec"]["integrity"]["digest"] = f"sha256:{payload_digest(_zip(manifest))}"
    return _zip(manifest), manifest


def _zip(manifest: dict[str, Any]) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plugin.json", json.dumps(manifest))
        archive.writestr(
            "tools/e2e_echo.json",
            json.dumps(
                {
                    "name": "e2e_echo",
                    "adapter": "http",
                    "description": "Echo tool installed by the real-backend suite.",
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object"},
                    "http": {"url": "https://example.com/echo", "method": "POST"},
                    "policy": {"audit_level": "basic"},
                }
            ),
        )
    return mem.getvalue()


def sign(package: bytes, manifest: dict[str, Any]) -> tuple[bytes, str]:
    """Re-emit the package with a valid signature over its own digest.

    Returns the signed bytes and the base64 public key that verifies them.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    public_key_b64 = base64.b64encode(public_bytes).decode()

    # build_package already recorded the payload digest; signing only adds a
    # signature over that value, leaving the payload untouched.
    declared = manifest["spec"]["integrity"]["digest"]
    assert declared == f"sha256:{payload_digest(package)}"
    signature = private_key.sign(declared.encode("utf-8"))
    manifest["spec"]["integrity"]["signature"] = base64.b64encode(signature).decode()

    return _zip(manifest), public_key_b64


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Directory to write into")
    parser.add_argument("--name", default="e2e-tool-plugin")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument(
        "--unsigned",
        action="store_true",
        help="Emit without a signature, to exercise refusal paths",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    package, manifest = build_package(args.name, args.version)
    public_key = ""
    if not args.unsigned:
        package, public_key = sign(package, manifest)

    (out / "plugin.zip").write_bytes(package)
    (out / "keys.json").write_text(
        json.dumps(
            {
                "public_key_b64": public_key,
                "digest": f"sha256:{sha256_hex(package)}",
                "name": args.name,
                "version": args.version,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out / 'plugin.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
