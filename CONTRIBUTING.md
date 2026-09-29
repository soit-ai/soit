# Contributing to SOIT

Thank you for contributing to SOIT. This repository contains the open-source
Community core: the agent runtime, workflow runtime, knowledge pipeline,
plugin/MCP basics, run/task ledger, model management, and local deployment
assets.

## Before your first pull request

The two checks that trip up most first-time contributors:

1. **Sign off every commit** with `git commit -s` (adds the `Signed-off-by:`
   line the [DCO check](#developer-certificate-of-origin) requires). Already
   committed without it? Fix a single commit with
   `git commit --amend -s --no-edit && git push --force-with-lease`, or a
   branch with `git rebase --signoff origin/main`.
2. **Use a Conventional Commit title** for commits and the PR, for example
   `docs: fix quickstart port table` — see
   [Commit Messages](#commit-messages).

## Docs-only changes

A change that only touches Markdown (`README.md`, `docs/`, `server/docs/`,
`web/docs/`, this file) needs none of the setup below: no `uv`, no `npm`, no
Docker. Edit, preview, commit, open the pull request.

What still applies:

- A Conventional Commit title with the `docs` type and a lowercase subject,
  for example `docs(quickstart): add the published-port table`, on every
  commit and on the pull request.
- The DCO sign-off on every commit: `git commit -s`.
- English only, outside the translation files (`README-cn.md`, `*.zh-CN.*`
  and `web/app/i18n/`). That covers documentation, code comments and commit
  messages.
- No `CHANGELOG.md` entry: documentation-only changes do not need one.
- Nothing local-only: no planning notes, evidence files or machine-specific
  paths (see [Documentation](#documentation)).

Documented commands and links are under test.
`server/tests/unit/test_phase1_release_docs.py` checks that every relative
Markdown link in the repository resolves, that `docs/quickstart.md` and
`docs/quickstart.zh-CN.md` still contain the documented quickstart commands
(the `docker compose` service list, the seed script, the smoke test,
`curl http://localhost:9200/health/ready`), that the migration runbook and
the model provider matrix keep their required terms, and that no public
document points at local-only workspaces. When you rename or move a file,
change a heading that a link points to, or change a documented command,
update that test in the same pull request. It needs the backend environment
once:

```powershell
cd server
uv sync
uv run pytest tests/unit/test_phase1_release_docs.py -q
```

You can also leave it to CI: the `quality` workflow has no path filter, so
every pull request runs the full backend and frontend gate, and a docs-only
change can only fail on this test. `commit-style` checks the commit titles,
the pull request title and the sign-offs.

To preview, use your editor's Markdown preview (in VS Code,
`Ctrl+Shift+V`), or GitHub's Preview tab in the file editor and the rendered
view on the pull request's Files changed tab; GitHub renders tables and
fenced code blocks as GitHub Flavored Markdown.

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

SOIT Community is released under the [Apache License 2.0](LICENSE). By
contributing, you agree that your contributions are licensed under the same
Apache License 2.0 that covers the project.

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
