# kernel/specs/v1/

Kernel v1 schemas:
- app_spec, workflow_spec, tool_spec, plugin_spec, runtrace_spec
- refs.schema.json (shared reference models)
- dataset schemas (if included)

Rules:
- Keep v1 stable.
- Add new optional fields only (minor versions).


### Dataset schemas

Dataset-related schemas are consolidated in `dataset_spec.schema.json` (legacy wrappers remain for compatibility).
