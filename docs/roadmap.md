# SOIT Roadmap

SOIT is an open-source governed agent runtime for teams that need self-hosted,
model-neutral execution with observable and auditable agent behavior.

## Current Focus

- Make SOIT quick to try and hard to break: the five-container lite profile, a
  green main branch, and release evidence that anyone can verify.
- Close the gaps between what the platform declares and what it enforces:
  knowledge visibility, workflow run limits, approvals that resume runs on
  their own, and a credit ledger that stays exact under concurrency.

## Next Milestones

- **SOIT Gateway**: an OpenAI-compatible entry point (/v1/chat/completions,
  /v1/models, embeddings and images) so any OpenAI SDK client runs through
  SOIT's per-key limits, budgets, content safety and cost ledger, with
  cross-provider failover, native Anthropic tool calling and a metadata-only
  capture mode.
- **Budgets**: workspace, agent and principal budgets with threshold alerts
  and hard stops, and daily usage aggregates.
- **Governed tools for agents that run elsewhere**: a tool invocation API and
  SOIT as an MCP server, both on the same policy chain as SOIT's own agents.
- **Evidence you can take away**: a per-run evidence package with a hash
  manifest, audit and cost exports, and a versioned ledger schema.
- **Model upgrades without regressions**: replay every regression set against
  a new model and compare pass rate, cost and latency.

## Contributing

Track concrete implementation work through the public issue tracker once it is
enabled. Until then, use the repository [contributing guide](../CONTRIBUTING.md)
for local setup, quality checks, and pull request expectations.
Public roadmap items should describe product direction and contributor-facing
work, not private planning notes or local release evidence.