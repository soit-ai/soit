# Editions, licenses and extension packages

SOIT Community needs no license: without one the runtime runs every
Community feature, as it always has. SOIT Enterprise is Community plus an
extension package and a signed license file; the license is what turns the
extension's features on.

## Applying a license

Mount the license file and the Ed25519 public key that verifies it, and point
the runtime at both:

```bash
ENTERPRISE_LICENSE_PATH=/etc/soit/license.json
ENTERPRISE_LICENSE_PUBLIC_KEY_PATH=/etc/soit/license.pub
```

The runtime reads them once when it starts, before any extension package
mounts:

| License | Edition | Entitlements |
| ------- | ------- | ------------ |
| none configured | as `PLATFORM_EDITION` says (`community` by default) | as `PLATFORM_ENTITLEMENTS` says |
| verifies, not expired | `enterprise` | the license's feature keys that an installed package defines |
| expired | `community` | none |
| signature does not match, file unreadable, malformed, not valid yet, or no public key configured | `community` | none |

A license that grants nothing does not stop the runtime: it runs as
Community and logs why at `ERROR`. A feature key the license grants that no
installed package defines (an Enterprise feature whose package is not
installed) is ignored and logged.

**Diagnostics.** `GET /api/v1/diagnostics` (workspace owners) and
**Settings › About** show the edition, the license's status, id, customer and
expiry with days left, why a configured license grants nothing, the enabled
feature keys, the ignored ones and the extension packages mounted.

**Heartbeat.** While a license is configured, the API process re-reads it
once a day and logs a `license.heartbeat` record: its status, id, customer,
expiry and days left, and the deployment's metering for the month so far
(`metered_calls`, `active_principals`, `active_api_keys`, from the daily
usage aggregates). The record is a `WARNING` when the license is not active
or expires within 30 days. A license that lapses while the runtime is up
drops it to Community at that heartbeat; a renewed file is picked up the same
way. Nothing is sent anywhere: the heartbeat is a log line.

## The license file

```json
{
  "alg": "Ed25519",
  "payload": {
    "license_id": "lic_example",
    "customer_id": "example",
    "issued_at": "2026-10-01T00:00:00+00:00",
    "expires_at": "2027-10-01T00:00:00+00:00",
    "entitlements": ["security.sso", "deployment.offline_license"]
  },
  "signature": "<base64 Ed25519 signature>"
}
```

The signature covers the payload serialized as canonical JSON: keys sorted,
no whitespace (`json.dumps(payload, sort_keys=True, separators=(",", ":"))`).
The public key file is PEM (`-----BEGIN PUBLIC KEY-----`) or the raw 32-byte
key in base64. Timestamps without an offset are read as UTC; an `issued_at`
more than five minutes ahead of the host's clock is not valid yet.

## Writing an extension package

An extension package declares two entry points in its `pyproject.toml`:

```toml
[project.entry-points."soit.feature_registries"]
example = "example_extension:feature_registry_path"

[project.entry-points."soit.extensions"]
example = "example_extension:mount"
```

- `soit.feature_registries` names a path, or a callable returning one, to a
  feature registry file in the shape of
  `server/app/kernel/entitlements/features.community.json`. Its keys become
  valid entitlements.
- `soit.extensions` names a callable `mount(app, settings)`, called once
  after Community's routes are registered and the license is applied. It can
  add routes and register providers, and should check
  `settings.platform_entitlements` for the feature keys it serves. A package
  that raises while mounting is logged and reported as `failed` in
  diagnostics; the rest of the application still starts.
