# SOIT-Pro Roadmap

For the detailed Phase 0 and Phase 1 execution plan, see [Phase 0/1 Delivery Plan](./phase-0-1-delivery-plan.md).

## P0: Contract Repair And Quality Gate

- Fix Agent execution drift by separating public execute payloads from internal runtime requests.
- Keep published Agent version bindings as the only source for model, tool, and knowledge execution configuration.
- Restore backend tests, unblock the frontend TypeScript 6 deprecation gate, fix Docker worker startup, and add CI quality gates.

## MVP: Stable Enterprise Agent Loop

- Deliver a complete Agent path: create, version, publish, execute, stream, response, thread, task, run trace, and tool call detail.
- Deliver a complete Knowledge path: upload, ingest, chunk, index, query, and citation.
- Connect observability dashboards to real run, task, response, tool, cost, and approval data.

## Beta: Governed Multi-Capability Platform

- Add evaluation and regression checks for Agent, Knowledge, and Workflow behavior.
- Harden Plugin and MCP execution with allowlists, audit, approval, and secret boundaries.
- Package production deployment profiles, health checks, backup/restore guidance, and model provider diagnostics.
