# kernel/specs/v1/

Kernel v1 schemas:
- app_spec, workflow_spec, tool_spec, node_spec, plugin_spec, runtrace_spec, memory_spec, notification_spec
- refs.schema.json (shared reference models)
- knowledge schemas (implemented on top of the legacy knowledge storage schema when needed)

Rules:
- Keep v1 stable.
- Add new optional fields only (minor versions).


### Knowledge schemas

Knowledge-related schemas are consolidated in `knowledge_spec.schema.json`.
