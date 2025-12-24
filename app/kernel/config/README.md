# kernel/config/

Configuration management: settings, env parsing, feature flags.

Rules:
- No external calls.
- Secrets are references only (resolved via secrets gateway).
