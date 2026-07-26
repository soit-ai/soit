# Independent Release Acceptance

This gate is performed by two or three people who did not author code in the
release candidate. Each reviewer uses a separate clean environment and the same
immutable commit. Development-team smoke tests and CI results do not count as
independent acceptance.

## Reviewer procedure

1. Record the operating system, container runtime, CPU architecture, available
   memory, checkout URL, release tag, and full commit in an environment evidence
   file. Start from a clean checkout and empty data volumes.
2. Follow the public quickstart without unpublished assistance. Record start and
   finish timestamps and retain the complete command output.
3. In the new empty workspace, create Knowledge and an Agent, publish and execute
   the Agent, and inspect its real run in Observe.
4. Create, publish, and execute a Workflow in the same workspace.
5. Record completion percentage, every blocking issue, total duration, and the
   evidence locations. A passing record requires 100% completion and no blocker.
6. Sign the reviewer record. The release owner signs the consolidated decision
   only after all reviewer records pass.

Copy `independent-release-acceptance.example.json` into the private/local release
evidence repository. Never commit local machine paths, participant identities, or
private acceptance output to the Community source repository.

Validate the draft structure from `server/`:

```bash
uv run python scripts/verify_independent_release_acceptance.py \
  ../docs/deployment/independent-release-acceptance.example.json
```

For final sign-off, point `--evidence-root` at the directory containing every
relative environment, run, and signature reference:

```bash
uv run python scripts/verify_independent_release_acceptance.py \
  /path/to/independent-release-acceptance.json \
  --evidence-root /path/to/private-release-evidence
```

The strict command must pass before the independent acceptance gate can be
reported as complete. This internal acceptance does not replace later external
design-partner or market validation.
