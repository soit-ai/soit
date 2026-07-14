"""OpenAPI must describe the response envelope and streaming media types."""


def test_openapi_success_schema_matches_response_middleware(client) -> None:
    schema = client.get("/api/v1/openapi.json").json()
    response_schema = schema["paths"]["/api/v1/agents"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    assert response_schema["properties"]["success"]["const"] is True
    assert response_schema["properties"]["code"]["type"] == "string"
    assert response_schema["properties"]["message"]["type"] == "string"
    assert response_schema["properties"]["data"]["$ref"].endswith(
        "/PaginatedResponse_AgentResponse_"
    )
    assert set(response_schema["required"]) >= {"success", "code", "message", "data"}


def test_openapi_sse_schema_is_not_json_enveloped(client) -> None:
    schema = client.get("/api/v1/openapi.json").json()
    content = schema["paths"]["/api/v1/responses/{response_id}/stream"]["get"][
        "responses"
    ]["200"]["content"]

    assert "text/event-stream" in content
    assert "application/json" not in content
