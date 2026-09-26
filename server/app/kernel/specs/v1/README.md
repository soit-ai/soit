# kernel/specs/v1/

Kernel v1 schemas:
- workflow_spec, chat_spec, agent_spec, tool_spec, node_spec, plugin_spec, runtrace_spec, run_step_tool_call_spec, memory_spec, notification_spec
- refs.schema.json (shared reference models)
- knowledge schemas
- ledger_spec: the runtime ledger as it leaves SOIT (runs, run steps, cost
  entries, audit entries, outbox events), written by
  `app/kernel/runtime/runs/ledger.py` for exports and run evidence bundles

Rules:
- Keep v1 stable.
- Add new optional fields only (minor versions).


### Knowledge schemas

Knowledge-related schemas are consolidated in `knowledge_spec.schema.json`.

### Ledger contract changes

`ledger_spec` carries its own `schema_version`, and every exported record
names it. `tests/unit/test_ledger_contract.py` fails when a ledger model gains
a column that neither the contract nor its list of internal columns accounts
for, so a change to what leaves the runtime is always a reviewed change:
adding an optional field bumps the minor version; removing, renaming or
retyping one needs a new major version.
