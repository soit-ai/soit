# Workflow DSL (v1)

The Workflow DSL uses `workflow_spec.schema.json` as the source schema. Import/export supports `json` and `yaml` formats.

## 1. Structure Overview

Required fields:
- `name`: workflow name
- `inputs_schema`: input JSON Schema
- `nodes`: node list
- `edges`: edges between nodes
- `outputs`: output JSON Schema or mapping

Optional fields:
- `description`
- `semantics`: failure policy and concurrency
- `policy`: default timeouts/retries/tool limits

## 2. Variable References

Template syntax:
- `{{ inputs.<field> }}` reference input fields
- `{{ steps.<node_id>.output.<field> }}` reference step outputs

## 3. Node Types

Supported:
- `llm` / `retrieve` / `tool` / `http`
- `condition` / `transform` / `set_var`
- `output`
- `node`

Notes:
- `tool` nodes must include `tool_ref` or `tool` in input
- `retrieve` nodes must include `query` and either `collection` or `dataset`
- `llm` nodes must include `prompt` or `message` or `messages`
- `node` nodes must include `node_ref` (plugin node)
  - Example: `node:builtin:llm_chat` / `node:tool:health_check`

## 4. JSON Example

```json
{
  "name": "RAG Answer",
  "description": "Retrieve + LLM + output",
  "inputs_schema": {
    "type": "object",
    "properties": {
      "query": { "type": "string" }
    },
    "required": ["query"]
  },
  "nodes": [
    {
      "id": "r1",
      "type": "retrieve",
      "input": {
        "query": "{{ inputs.query }}",
        "dataset": "ds:kb_support"
      }
    },
    {
      "id": "m1",
      "type": "llm",
      "input": {
        "prompt": "Answer with citations.\n{{ steps.r1.output.context }}"
      }
    },
    {
      "id": "o1",
      "type": "output",
      "input": {
        "value": "{{ steps.m1.output.text }}",
        "citations": "{{ steps.r1.output.citations }}"
      }
    }
  ],
  "edges": [
    { "from": "r1", "to": "m1" },
    { "from": "m1", "to": "o1" }
  ],
  "outputs": {
    "type": "object",
    "properties": {
      "value": { "type": "string" },
      "citations": { "type": "array" }
    }
  },
  "semantics": {
    "on_error": "fail_fast",
    "concurrency": 2
  },
  "policy": {
    "registry_only_tools": true,
    "default_timeout_ms": 30000,
    "default_retry_policy": {
      "max_retries": 1,
      "backoff_ms": 500
    }
  }
}
```

## 5. YAML Example

```yaml
name: RAG Answer
description: Retrieve + LLM + output
inputs_schema:
  type: object
  properties:
    query:
      type: string
  required:
    - query
nodes:
  - id: r1
    type: retrieve
    input:
      query: "{{ inputs.query }}"
      dataset: ds:kb_support
  - id: m1
    type: llm
    input:
      prompt: "Answer with citations.\n{{ steps.r1.output.context }}"
  - id: o1
    type: output
    input:
      value: "{{ steps.m1.output.text }}"
      citations: "{{ steps.r1.output.citations }}"
edges:
  - from: r1
    to: m1
  - from: m1
    to: o1
outputs:
  type: object
  properties:
    value:
      type: string
    citations:
      type: array
semantics:
  on_error: fail_fast
  concurrency: 2
policy:
  registry_only_tools: true
  default_timeout_ms: 30000
  default_retry_policy:
    max_retries: 1
    backoff_ms: 500
```

## 6. API Usage

Export:
- `GET /api/v1/workflows/{workflow_id}/dsl?format=json|yaml&version_id=...`

Import:
- `POST /api/v1/workflows/{workflow_id}/dsl`
- Body:
  - `format`: `json` or `yaml`
  - `dsl`: JSON object or YAML string
  - `created_by`: user ID

## 7. Validation Rules

All DSL payloads are validated on the server with `workflow_spec.schema.json`. DSLs that do not match the schema are rejected.
