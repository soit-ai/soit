# kernel/specs/v1/

Kernel v1 schemas:
- workflow_spec, chat_spec, agent_spec, tool_spec, node_spec, plugin_spec, runtrace_spec, run_step_tool_call_spec, memory_spec, notification_spec
- refs.schema.json (shared reference models)
- knowledge schemas

Rules:
- Keep v1 stable.
- Add new optional fields only (minor versions).


### Knowledge schemas

Knowledge-related schemas are consolidated in `knowledge_spec.schema.json`.
