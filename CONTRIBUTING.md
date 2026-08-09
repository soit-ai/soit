# Contributing to SOIT

Thank you for contributing to SOIT. This repository contains the open-source
Community core: the agent runtime, workflow runtime, knowledge pipeline,
plugin/MCP basics, run/task ledger, model management, and local deployment
assets.

## Docs-only changes

You can contribute documentation without a full local stack.

**You can skip:** `uv sync`, `npm install`, and Docker services.

**Still required:**

- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for commit messages / PR titles
- DCO sign-off on every commit (`git commit -s`)
- When you change a documented command, path, or release template, keep the doc-contract tests green — especially `server/tests/unit/test_phase1_release_docs.py` for quickstart/README command text

**Preview Markdown locally:** open the file in your editor or any Markdown previewer (no build step). For site-specific rendering, use whatever docs tooling the tree already documents in `docs/`.

To open a docs PR:

1. Edit files under `docs/`, `README.md`, or other Markdown you are fixing.
2. Commit with a `docs:` type message.
3. Open the PR. All CI jobs (quality / security / commit-style) still run and must pass — docs-only means you do not need a local dev stack to author the change, not that failing checks are OK.

---

## Development Setup

Install backend dependencies from `server/`:

```powershell
uv sync
```

Install frontend dependencies from `web/`:

```powershell
npm install
```

For a local environment with supporting services, use the Docker quickstart in
[docs/quickstart.md](docs/quickstart.md). For hot reload development, see
[docs/development.md](docs/development.md).

## Quality Checks

Run focused checks first, then broaden to the relevant gate before opening a
pull request.

Backend checks from `server/`:

```powershell
uv run pytest
uv run lint-imports --config importlinter.ini
uv run ruff check app tests
uv run pyright
```

Frontend checks from `web/`:

```powershell
npm run typecheck
npm run build
npm run test:e2e
```

## Documentation

Public documentation belongs in `docs/`, `server/docs/`, or `web/docs/`.
Keep local planning notes, private release evidence, and operator-specific
records out of this repository.

When changing a documented command, path, or release template, update the
corresponding tests under `server/tests/unit/` if they validate that artifact.

## Commit Messages

Commits and pull request titles must follow
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) and are
enforced in CI by `.github/workflows/commit-style.yml` via
[commitlint](https://commitlint.js.org/) with the configuration in
`commitlint.config.mjs`.

Format: `type(scope): subject`, written in English, lowercase subject, no
trailing period, header at most 100 characters.

Allowed types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `style`,
`build`, `perf`, `ci`, `security`, `hardening`, `revert`.

Use `security` for changes that close a security gap and `hardening` for
defense-in-depth improvements without a known vulnerability. Mark breaking
changes with `!` after the type or scope (for example `feat(api)!: ...`) and
describe the migration in the commit body.

To check locally before pushing:

```powershell
npx --package @commitlint/cli --package @commitlint/config-conventional commitlint --from origin/main --verbose
```

## License of Contributions

SOIT is released under the [Apache License 2.0](LICENSE) with additional
usage conditions stated in the [README](README.md#license). By contributing
you agree that your contributed code may be used commercially by SOIT LLC,
including in its cloud business operations, and that SOIT LLC may adjust the
project's licensing terms as deemed necessary.

## Developer Certificate of Origin

Every commit must be signed off to certify that you have the right to submit
the contribution under the project license, per the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```powershell
git commit -s -m "feat(scope): subject"
```

This appends a `Signed-off-by: Your Name <your@email>` line to the commit
message, which CI verifies on every pull request. To fix a branch that is
missing sign-offs:

```powershell
git rebase --signoff origin/main
```

## Changelog

User-facing changes (features, fixes, security changes, deprecations) should
add an entry to the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md) in
the same pull request. Internal refactors, test-only, and CI-only changes do
not need an entry.

## Pull Requests

Before opening a pull request:

1. Keep changes scoped to one feature, fix, or documentation update.
2. Include tests or verification output for behavior changes.
3. Update public documentation when user-facing behavior changes.
4. Avoid committing secrets, local credentials, generated build output, or
   machine-specific evidence files.
5. Review dependency and license changes and update public behavior or operations
   documentation when the change affects compatibility, security, or recovery.

Report suspected vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not in a public issue.
