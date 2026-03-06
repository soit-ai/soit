# workflow.v1 (canonical)

This doc summarizes the canonical workflow spec, publish pipeline, and projection APIs.

## Canonical spec shape

Required top-level fields:
- name
- graph (nodes + edges)
- inputs_schema
- outputs_schema

Example (trimmed):

```json
{
  "name": "demo",
  "inputs_schema": { "type": "object" },
  "outputs_schema": { "type": "object" },
  "graph": {
    "nodes": [
      { "id": "n1", "type": "tool", "params": { "tool_ref": "tool:http:demo" } },
      { "id": "o1", "type": "output", "params": { "value": "{{ steps.n1.output }}" } }
    ],
    "edges": [
      { "id": "e1", "from": "n1", "to": "o1" }
    ]
  }
}
```

Node fields:
- id: node id (string)
- type: node type (string)
- params: node params payload (object)
- ui: optional UI metadata (object)

Edge fields:
- id: edge id (string)
- from/to: node ids
- from_port/to_port: optional port ids
- condition: optional expression

## Publish pipeline

Publish does:
1) validate spec_json against workflow.v1 schema
2) compute checksum (SHA256 of canonicalized JSON)
3) mark version published; deprecate older published versions for same app
4) build projections:
   - app_components (nodes projection)
   - app_component_edges (edges projection)
   - app_version_refs (external refs)

## Projection queries (AppCenter)

Endpoints:
- GET /api/v1/appcenter/{app_id}/versions/{version_id}/components
- GET /api/v1/appcenter/{app_id}/versions/{version_id}/edges
- GET /api/v1/appcenter/{app_id}/versions/{version_id}/refs
- GET /api/v1/appcenter/refs/impact?ref_type=tool&ref_key=tool:http:demo

## Workflow publish

Publish an existing version:
- POST /api/v1/workflows/{app_id}/publish (body: version_id, optional preflight=true)

Create + publish in one step:
- POST /api/v1/workflows/{app_id}/versions (body: graph_json, created_by, optional preflight)

## Rebuild projections

Script:
- python scripts/rebuild_projections.py --tenant-id ... --workspace-id ... --user-id ... --app-id ...
- python scripts/rebuild_projections.py --tenant-id ... --workspace-id ... --user-id ... --version-id ...
- python scripts/rebuild_projections.py --tenant-id ... --workspace-id ... --user-id ... --all
