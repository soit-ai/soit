"""Ticket triage workflow template."""

from typing import Any


def build_ticket_triage_template() -> dict[str, Any]:
    return {
        "name": "Ticket triage",
        "description": "Classify a customer issue, prepare review, create a ticket, and return a response.",
        "inputs_schema": {
            "type": "object",
            "required": ["customer_message", "customer_id", "priority"],
            "properties": {
                "customer_message": {"type": "string"},
                "customer_id": {"type": "string"},
                "priority": {"type": "string"},
                "knowledge_collection": {"type": "string"},
                "embedding_model": {"type": "string"},
                "model_ref": {"type": "string"},
            },
        },
        "outputs_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "status": {"type": "string"},
                "response": {"type": "string"},
                "citations": {"type": "array"},
            },
        },
        "policy": {
            "registry_only_tools": True,
            "default_timeout_ms": 30000,
        },
        "graph": {
            "nodes": [
                {
                    "id": "start",
                    "type": "set_var",
                    "params": {
                        "set": {
                            "customer_message": "{{ inputs.customer_message }}",
                            "customer_id": "{{ inputs.customer_id }}",
                            "priority": "{{ inputs.priority }}",
                        }
                    },
                },
                {
                    "id": "knowledge_search",
                    "type": "retrieve",
                    "params": {
                        "query": "{{ steps.start.output.customer_message }}",
                        "collection": "{{ inputs.knowledge_collection }}",
                        "embedding_model": "{{ inputs.embedding_model }}",
                        "top_k": 3,
                    },
                },
                {
                    "id": "classify",
                    "type": "llm",
                    "params": {
                        "model": "{{ inputs.model_ref }}",
                        "system": "Classify support tickets using the retrieved policy context.",
                        "prompt": (
                            "Customer: {{ steps.start.output.customer_message }}\n"
                            "Priority: {{ steps.start.output.priority }}\n"
                            "Policy context: {{ steps.knowledge_search.output.context }}\n"
                            "Return a concise classification and recommended handling."
                        ),
                    },
                },
                {
                    "id": "approval",
                    "type": "condition",
                    "params": {
                        "condition": '{{ inputs.priority }} != "low"',
                        "classification": "{{ steps.classify.output.text }}",
                    },
                },
                {
                    "id": "ticket_tool",
                    "type": "tool",
                    "params": {
                        "tool_ref": "builtin.ticket.create_review_ticket",
                        "url": "https://tickets.example.local/reviews",
                        "customer_id": "{{ steps.start.output.customer_id }}",
                        "priority": "{{ steps.start.output.priority }}",
                        "message": "{{ steps.start.output.customer_message }}",
                        "classification": "{{ steps.classify.output.text }}",
                        "api_token": "secret:ticket_api_key",
                    },
                },
                {
                    "id": "response",
                    "type": "output",
                    "params": {
                        "ticket_id": "{{ steps.ticket_tool.output.result.ticket_id }}",
                        "status": "{{ steps.ticket_tool.output.result.status }}",
                        "response": "{{ steps.classify.output.text }}",
                        "citations": "{{ steps.knowledge_search.output.citations }}",
                    },
                },
                {
                    "id": "reject",
                    "type": "output",
                    "params": {
                        "ticket_id": "",
                        "status": "rejected",
                        "response": "Ticket creation skipped because the approval condition was not met.",
                        "citations": "{{ steps.knowledge_search.output.citations }}",
                    },
                },
            ],
            "edges": [
                {"id": "e_start_knowledge", "from": "start", "to": "knowledge_search"},
                {"id": "e_knowledge_classify", "from": "knowledge_search", "to": "classify"},
                {"id": "e_classify_approval", "from": "classify", "to": "approval"},
                {
                    "id": "e_approval_ticket",
                    "from": "approval",
                    "to": "ticket_tool",
                    "condition": "{{ steps.approval.output.result }}",
                },
                {
                    "id": "e_approval_reject",
                    "from": "approval",
                    "to": "reject",
                    "condition": "{{ steps.approval.output.result }} == false",
                },
                {"id": "e_ticket_response", "from": "ticket_tool", "to": "response"},
            ],
        },
    }
