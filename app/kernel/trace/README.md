# kernel/trace/

Unified execution trace:
- run/run_step/run_artifact/run_cost writers
- exporters to observability stack

Rules:
- Always record executables.
- Store only summaries in DB; large payloads as artifacts.
