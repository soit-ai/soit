# SOIT Governance

SOIT Community is maintained by a small maintainer team. This document
describes how decisions are made and how to gain maintainer rights. It is
intentionally lightweight and will evolve as the community grows.

## Roles

**Users** run SOIT and report bugs, ideas, and experience through issues and
discussions.

**Contributors** submit pull requests, review changes, improve documentation,
or help triage. Anyone who follows [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md) can contribute.

**Maintainers** have merge rights. They triage issues, review and merge pull
requests, cut releases through the process in
[docs/release-process.md](docs/release-process.md), and are accountable for
the direction of the project. Current maintainers are listed in
[MAINTAINERS.md](MAINTAINERS.md).

## Decision Making

- Day-to-day decisions happen in issues and pull requests through lazy
  consensus: if no maintainer objects within a reasonable review window, the
  change can be merged by a maintainer.
- Substantial changes — new modules, public API changes, edition boundary
  changes, security-relevant architecture — should start as a design issue or
  discussion before implementation.
- When consensus is not reached, maintainers decide. If maintainers disagree,
  a simple majority of maintainers decides.
- Security response follows [SECURITY.md](SECURITY.md) and may bypass the
  normal review window when a coordinated fix requires it.

## Becoming a Maintainer

Contributors who show sustained, high-quality contributions — code, reviews,
triage, or documentation — over a period of months can be nominated by an
existing maintainer and confirmed by the maintainer team. Maintainers who are
inactive for an extended period may be moved to emeritus status after being
contacted.

## Changes to This Document

Changes to governance are proposed as pull requests and require approval from
the maintainer team.
