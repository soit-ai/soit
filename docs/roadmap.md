# SOIT Roadmap

SOIT is an open-source governed agent runtime for teams that need self-hosted,
model-neutral execution with observable and auditable agent behavior.

## Shipped

- **SOIT Gateway** (v1.2 to v1.4): an OpenAI-compatible entry point
  (`/v1/chat/completions`, `/v1/models`, embeddings and images) so any OpenAI
  SDK client runs through SOIT's per-key limits, budgets, content safety and
  cost ledger, with virtual models that fail over across providers, native
  Anthropic and Gemini adapters, a metadata-only capture mode, standalone
  gateway processes (`SOIT_ROLE=gateway`) and model servers on private
  networks.
- **Budgets** (v1.2): workspace, agent and principal budgets with threshold
  alerts and hard stops, atomic holds and daily usage aggregates.
- **Governed tools for agents that run elsewhere** (v1.3): a tool invocation
  API and SOIT as an MCP server, on the same policy chain as SOIT's own
  agents.
- **Evidence you can take away** (v1.3): a per-run evidence package with a
  hash manifest, audit and cost exports, and a versioned ledger schema.
- **Model upgrades without regressions** (v1.3): replay every regression set
  against a new model and compare pass rate, cost and latency.
- **Editions** (v1.4): signed Enterprise licenses, extension packages mounted
  through entry points, and opt-in anonymous telemetry, off by default.

## Current Focus

- Keep SOIT quick to try and hard to break: the five-container lite profile,
  a green main branch, release evidence anyone can verify, and the CLI on a
  package index.
- Make every console screen read what the runtime records, and nothing else:
  the remaining prototype fixtures are being replaced or removed.
- Real-provider evidence for the gateway and the native adapters, beyond the
  unit and mock coverage each one ships with.

## Next Milestones

- **Agents as files**: export an agent's specification as YAML and import it
  back, so agents move between workspaces and live in version control.
- **Evaluation API**: run an evaluation from the API, with datasets as
  versioned objects rather than one regression set per agent.
- **Cost-aware routing**: virtual model policies that weigh price and latency,
  not only availability.
- **Durable agents**: checkpoints that let a long-running agent resume after
  a restart, cancellation that takes effect at once, and retention policies
  for run records.
- **Connectors**: a framework for external systems (ticketing, chat, storage)
  that agents reach through governed tools.
- **Enterprise**: single sign-on, principal-level quotas and compliance
  exports, as an extension package on the same runtime.

## Contributing

Track concrete implementation work through the
[issue tracker](https://github.com/soit-ai/soit/issues), and use the
[contributing guide](../CONTRIBUTING.md) for local setup, quality checks and
pull request expectations. Roadmap items describe product direction and
contributor-facing work, not private planning notes or local release evidence.
