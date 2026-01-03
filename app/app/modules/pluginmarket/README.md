# modules/pluginmarket

Marketplace + installation for SOIT plugins.

## Structure

- `domain/`
  - `models.py`: SQLModel tables (`plugins`, `plugin_installations`)
- `application/`
  - `service.py`: use-cases (publish/list/install/enable/disable)
  - `schemas.py`: request/response DTOs (Pydantic)
  - `ports.py`: repository ports (Protocols)
- `infra/`
  - `repository.py`: SQL-backed repositories (scope-aware)
  - `installer.py`: filesystem installer (package validation + extract + runtime registry)

## Plugin package format (current)

A plugin package is a **zip** file containing at least:

- `plugin.json` (or `plugin.toml`)
  - should include `spec` (a `plugin_spec` JSON object) OR ship `spec.json`

Optional:
- `spec.json`
- any runtime files (code/assets) — extracted under `var/plugins/installed/<tenant>/<workspace>/<name>/<version>/files/`

## Installation flow

1. Upload package via API: `POST /v1/pluginmarket/{plugin_id}/install-package`
2. `installer.py`:
   - checks sha256 (optional)
   - safe-extracts zip (blocks path traversal)
   - validates `plugin_spec` via `kernel/specs`
   - stores normalized `manifest.json` and `spec.json`
   - registers the plugin into in-process `kernel.registry`

## Enable/disable

No DB schema changes:
- enable/disable state is stored in `PluginInstallation.config_json.enabled`.

## Next steps (planned)

- signature verification (ed25519/rsa)
- dependency resolution between plugins
- a concrete `PluginRuntimePort` adapter (http/subprocess/container)
