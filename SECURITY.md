# Security Policy

## Supported Versions

Before the first public SOIT Community release is published, security fixes are
made on `main`. After public releases begin, the latest released minor version
and `main` receive security fixes. Older versions are unsupported unless their
release notes explicitly say otherwise.

## Reporting a Vulnerability

Use the repository's **Security** tab and GitHub private vulnerability reporting
when it is available. Do not open a public issue for an unpatched vulnerability
and do not include credentials, customer data, exploit payloads, or access tokens
in a public discussion.

If private vulnerability reporting is unavailable, contact a maintainer through
a private channel listed on the repository owner profile and ask for a secure
reporting channel. Share only enough information to establish contact until a
private channel is confirmed.

Please include:

- affected version or commit;
- affected component and configuration;
- reproduction steps with secrets and customer data removed;
- expected impact and any known mitigations.

Maintainers will acknowledge receipt, validate scope, coordinate a fix and
disclosure date, and credit the reporter when requested. Response times are goals,
not a contractual support SLA.

## Release Security Gates

Release candidates must pass repository-history secret scanning, dependency and
container scanning, license/source inventory generation, and the normal quality
gate. Critical or High dependency findings block release unless
`security/vulnerability-exceptions.json` contains a non-expired exception with an
owner and a concrete rationale.

Generated SBOMs and GitHub artifact attestations describe the released source and
container images. They do not by themselves establish compliance, safety, or
fitness for a particular deployment.
