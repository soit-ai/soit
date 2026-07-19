export default [
  {
    "id": "H01", "editable": false,
    "node": { "id": "H01", "type": "transform", "name": "Text Input", "params": { "mapping": { "text": "" } }, "ui": { "builder_type": "text-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Text Input", "content": "" } } },
    "edges": [{ "id": "H01-output", "from": "H01", "to": "H01-target", "from_port": "output", "to_port": "input", "condition": null }]
  },
  {
    "id": "H02", "editable": false,
    "node": { "id": "H02", "type": "transform", "name": "Prompt", "params": { "mapping": { "prompt": "" } }, "ui": { "builder_type": "prompt-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Prompt", "template": "", "variables": [] } } },
    "edges": [{ "id": "H02-output", "from": "H02", "to": "H02-target", "from_port": "output", "to_port": "input", "condition": null }]
  },
  {
    "id": "H03", "editable": true,
    "node": { "id": "H03", "type": "llm", "name": "LLM", "params": { "prompt": "{{ steps.H03-source.output.text }}", "model": "gpt-3.5-turbo", "temperature": 0.7, "max_tokens": 1000 }, "ui": { "builder_type": "llm-node", "position": { "x": 80, "y": 80 }, "data": { "label": "LLM", "modelName": "gpt-3.5-turbo", "temperature": 0.7, "maxTokens": 1000, "topP": 1, "systemPrompt": "" } } },
    "edges": [
      { "id": "H03-incoming", "from": "H03-source", "to": "H03", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H03-output", "from": "H03", "to": "H03-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H04", "editable": false,
    "node": { "id": "H04", "type": "tool", "name": "Tool Call", "params": { "tool_ref": "", "arguments": {}, "input": "{{ steps.H04-source.output }}" }, "ui": { "builder_type": "tool-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Tool Call", "toolName": "", "description": "", "parameters": {} } } },
    "edges": [
      { "id": "H04-incoming", "from": "H04-source", "to": "H04", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H04-output", "from": "H04", "to": "H04-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H05", "editable": false,
    "node": { "id": "H05", "type": "transform", "name": "Data Source", "params": { "mapping": { "value": "" } }, "ui": { "builder_type": "data-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Data Source", "dataType": "document", "source": "", "cache": false } } },
    "edges": [{ "id": "H05-output", "from": "H05", "to": "H05-target", "from_port": "output", "to_port": "input", "condition": null }]
  },
  {
    "id": "H06", "editable": true,
    "node": { "id": "H06", "type": "output", "name": "Output", "params": { "value": "{{ steps.H06-source.output }}" }, "ui": { "builder_type": "output-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Output", "format": "text", "destination": "ui", "saveHistory": true, "streaming": false } } },
    "edges": [{ "id": "H06-incoming", "from": "H06-source", "to": "H06", "from_port": "output", "to_port": "input", "condition": null }]
  },
  {
    "id": "H07", "editable": false,
    "node": { "id": "H07", "type": "retrieve", "name": "Knowledge Search", "params": { "query": "{{ steps.H07-source.output.text }}", "collection": "knowledge_base", "top_k": 3, "embedding_model": "model:openai:text-embedding-3-small" }, "ui": { "builder_type": "knowledge-search-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Knowledge Search", "dataSource": "knowledge_base", "topK": 3, "similarityThreshold": 0.7, "rerank": false, "filters": [] } } },
    "edges": [
      { "id": "H07-incoming", "from": "H07-source", "to": "H07", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H07-output", "from": "H07", "to": "H07-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H08", "editable": false,
    "node": { "id": "H08", "type": "node", "name": "Agent", "params": { "node_ref": "", "input": "{{ steps.H08-source.output }}" }, "ui": { "builder_type": "agent-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Agent", "agentType": "react", "model": "gpt-4", "systemPrompt": "", "tools": [], "verbose": false, "memory": true } } },
    "edges": [
      { "id": "H08-incoming", "from": "H08-source", "to": "H08", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H08-output", "from": "H08", "to": "H08-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H09", "editable": false,
    "node": { "id": "H09", "type": "llm", "name": "Question Classifier", "params": { "mapping": { "value": "{{ steps.H09-source.output }}" } }, "ui": { "builder_type": "question-classifier-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Question Classifier", "classifierType": "llm", "model": "gpt-3.5-turbo", "prompt": "", "categories": [], "fallback": true, "fallbackMessage": "Unclassified question" } } },
    "edges": [
      { "id": "H09-incoming", "from": "H09-source", "to": "H09", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H09-output", "from": "H09", "to": "H09-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H10", "editable": false,
    "node": { "id": "H10", "type": "condition", "name": "Logic", "params": { "condition": "true", "value": "{{ steps.H10-source.output }}" }, "ui": { "builder_type": "logic-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Logic", "operation": "AND", "conditions": [] } } },
    "edges": [
      { "id": "H10-incoming", "from": "H10-source", "to": "H10", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H10-output", "from": "H10", "to": "H10-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H11", "editable": false,
    "node": { "id": "H11", "type": "condition", "name": "Conditional", "params": { "condition": "true", "value": "{{ steps.H11-source.output }}" }, "ui": { "builder_type": "conditional-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Conditional", "conditions": [], "defaultPath": "" } } },
    "edges": [
      { "id": "H11-incoming", "from": "H11-source", "to": "H11", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H11-output-true", "from": "H11", "to": "H11-target", "from_port": "output-true", "to_port": "input", "condition": "true" },
      { "id": "H11-output-false", "from": "H11", "to": "H11-target", "from_port": "output-false", "to_port": "input", "condition": "false" }
    ]
  },
  {
    "id": "H12", "editable": false,
    "node": { "id": "H12", "type": "transform", "name": "Delivery", "params": { "mapping": { "value": "{{ steps.H12-source.output }}" } }, "ui": { "builder_type": "delivery-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Delivery", "message": "", "deliveryType": "direct" } } },
    "edges": [
      { "id": "H12-incoming", "from": "H12-source", "to": "H12", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H12-output", "from": "H12", "to": "H12-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H13", "editable": false,
    "node": { "id": "H13", "type": "condition", "name": "Loop", "params": { "mapping": { "value": "{{ steps.H13-source.output }}" } }, "ui": { "builder_type": "loop-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Loop", "iterationVariable": "", "maxIterations": 10, "exitCondition": "" } } },
    "edges": [
      { "id": "H13-incoming", "from": "H13-source", "to": "H13", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H13-loop-body", "from": "H13", "to": "H13-target", "from_port": "loop-body", "to_port": "input", "condition": null },
      { "id": "H13-output", "from": "H13", "to": "H13-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H14", "editable": true,
    "node": { "id": "H14", "type": "transform", "name": "Transform", "params": { "mapping": { "value": "{{ steps.H14-source.output }}" } }, "ui": { "builder_type": "transform-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Transform", "transformType": "json", "inputFormat": "", "outputFormat": "", "script": "" } } },
    "edges": [
      { "id": "H14-incoming", "from": "H14-source", "to": "H14", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H14-output", "from": "H14", "to": "H14-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H15", "editable": false,
    "node": { "id": "H15", "type": "transform", "name": "Code", "params": { "mapping": { "value": "{{ steps.H15-source.output }}" } }, "ui": { "builder_type": "code-execution-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Code", "language": "javascript", "code": "", "timeout": 30000 } } },
    "edges": [
      { "id": "H15-incoming", "from": "H15-source", "to": "H15", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H15-output", "from": "H15", "to": "H15-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H16", "editable": false,
    "node": { "id": "H16", "type": "transform", "name": "Template", "params": { "mapping": { "value": "{{ steps.H16-source.output }}" } }, "ui": { "builder_type": "template-transform-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Template", "template": "", "inputFormat": "", "outputFormat": "" } } },
    "edges": [
      { "id": "H16-incoming", "from": "H16-source", "to": "H16", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H16-output", "from": "H16", "to": "H16-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H17", "editable": false,
    "node": { "id": "H17", "type": "transform", "name": "Variable Aggregator", "params": { "mapping": { "value": "{{ steps.H17-source.output }}" } }, "ui": { "builder_type": "variable-aggregator-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Variable Aggregator", "structure": "object", "variables": [], "outputVariable": "" } } },
    "edges": [
      { "id": "H17-incoming", "from": "H17-source", "to": "H17", "from_port": "output", "to_port": "input-1", "condition": null },
      { "id": "H17-incoming-2", "from": "H17-source-2", "to": "H17", "from_port": "output", "to_port": "input-2", "condition": null },
      { "id": "H17-output", "from": "H17", "to": "H17-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H18", "editable": false,
    "node": { "id": "H18", "type": "transform", "name": "Document Extractor", "params": { "mapping": { "value": "{{ steps.H18-source.output }}" } }, "ui": { "builder_type": "document-extractor-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Document Extractor", "documentId": "", "extractionType": "text", "outputFormat": "json", "extractionRules": [] } } },
    "edges": [
      { "id": "H18-incoming", "from": "H18-source", "to": "H18", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H18-output", "from": "H18", "to": "H18-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H19", "editable": true,
    "node": { "id": "H19", "type": "set_var", "name": "Variable Assignment", "params": { "key": "value", "value": "{{ steps.H19-source.output }}" }, "ui": { "builder_type": "variable-assignment-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Variable Assignment", "variableName": "", "variableValue": "", "valueType": "string" } } },
    "edges": [
      { "id": "H19-incoming", "from": "H19-source", "to": "H19", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H19-output", "from": "H19", "to": "H19-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H20", "editable": false,
    "node": { "id": "H20", "type": "transform", "name": "Parameter Extractor", "params": { "mapping": { "value": "{{ steps.H20-source.output }}" } }, "ui": { "builder_type": "parameter-extractor-node", "position": { "x": 80, "y": 80 }, "data": { "label": "Parameter Extractor", "parameters": [], "defaultValues": {} } } },
    "edges": [
      { "id": "H20-incoming", "from": "H20-source", "to": "H20", "from_port": "output", "to_port": "input", "condition": null },
      { "id": "H20-output", "from": "H20", "to": "H20-target", "from_port": "output", "to_port": "input", "condition": null }
    ]
  },
  {
    "id": "H21", "editable": false,
    "node": { "id": "H21", "type": "output", "name": "End", "params": { "value": "{{ steps.H21-source.output }}" }, "ui": { "builder_type": "end-node", "position": { "x": 80, "y": 80 }, "data": { "label": "End", "status": "success", "message": "" } } },
    "edges": [{ "id": "H21-incoming", "from": "H21-source", "to": "H21", "from_port": "output", "to_port": "input", "condition": null }]
  }
] as const
