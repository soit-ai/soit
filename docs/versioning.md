# Versioning and Support Policy

SOIT Community follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
Releases are tagged `vMAJOR.MINOR.PATCH` and produced through the process in
[release-process.md](release-process.md).

## What a version number promises

- **MAJOR** — incompatible changes to the public API (`/api/v1`), the spec
  schemas under `server/app/kernel/specs/`, or the supported upgrade path.
- **MINOR** — backwards-compatible features. New endpoints, new node types,
  new configuration with safe defaults, additive schema fields.
- **PATCH** — backwards-compatible bug and security fixes only.

## Compatibility surface

The following are the compatibility surface covered by SemVer:

- HTTP API routes and payloads under `/api/v1`.
- Primitive spec schemas under `server/app/kernel/specs/v1/`.
- Database migration chain: every release supports a fresh install and an
  upgrade from the previous minor release (N-1). Skipping minors requires
  stepping through intermediate releases. Details per release are recorded in
  [`docs/releases/`](releases/).
- Environment variables and Docker topology documented in
  [quickstart.md](quickstart.md).

Anything not listed above — internal Python modules, database table layout,
undocumented endpoints, UI internals — may change in any release.

## Deprecation policy

Deprecated functionality is announced in `CHANGELOG.md` and the release notes,
kept working for at least one minor release, and removed no earlier than the
next major or explicitly announced minor release. Breaking changes always ship
with migration guidance in the release notes.

## Supported versions

- Before the first public release: fixes land on `main` only.
- After public releases begin: the latest released minor and `main` receive
  bug and security fixes. Older versions are unsupported unless their release
  notes say otherwise.

Security-specific handling is defined in [SECURITY.md](../SECURITY.md).
