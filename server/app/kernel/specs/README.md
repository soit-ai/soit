# kernel/specs/

JSON Schemas for spec-first development.
`v1/` contains kernel v1 schemas and reference models.

Rules:
- Schemas are the source of truth.
- Backward compatibility is required for minor updates.


Implementation notes:
- Validation uses JSON Schema Draft 2020-12.
- Cross-file `$ref` (e.g. `refs.schema.json#/$defs/...`) is resolved via an in-memory `referencing.Registry` built from all schemas in the version folder.
