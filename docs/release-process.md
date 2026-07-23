# SOIT Community Release Process

SOIT Community releases are created only from a clean, reviewed tag matching
`vMAJOR.MINOR.PATCH`. The tag version must match `server/pyproject.toml`,
`web/package.json`, runtime manifests, and release notes under `docs/releases/`.

The tag-triggered `.github/workflows/release.yml` reruns release checks and builds
three images used by the default topology: `server`, `knowledge-worker`, and
`web`. It publishes digest-addressable images, SPDX JSON SBOMs, GitHub/Sigstore
build provenance and SBOM attestations, a deterministic `git archive`, and
`SHA256SUMS`. The workflow creates the GitHub Release only after these steps pass.

Before pushing a tag:

1. Confirm the worktree and index are clean and the candidate commit is reviewed.
2. Confirm `quality.yml` and `security.yml` pass on that exact commit.
3. Complete fresh-install, N-1 migration, backup/restore, and independent product
   acceptance evidence outside the public repository.
4. Review release notes and known limitations. Do not label planned or locally
   simulated capabilities as available.
5. Create an annotated tag on the approved commit and push the tag only after
   release approval.

After publication, copy the real tag, commit, image digests, SBOM checksums, and
attestation URLs into an evidence document based on
`docs/deployment/release-artifacts.example.json`, then run:

```powershell
cd server
uv run python scripts/verify_release_artifacts.py `
  ../artifacts/release/release-artifacts.json
```

Consumers should verify downloaded files with `sha256sum -c SHA256SUMS` and verify
GitHub artifact attestations with `gh attestation verify`. The release is not
complete while any tag, commit, digest, checksum, SBOM, provenance record, or
release note points to a different build.
