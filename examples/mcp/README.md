# Connecting MCP clients to SOIT

SOIT serves a workspace's tools as an MCP server at `/mcp` (streamable HTTP,
stateless). Any MCP client that can send a bearer header connects with a SOIT
API key; the key decides the workspace and which tools are offered. Every
tool call becomes a governed run in SOIT. See [`docs/mcp.md`](../../docs/mcp.md).

| Setting | Value |
| ------- | ----- |
| URL | your SOIT address plus `/mcp`, e.g. `http://localhost:9200/mcp` |
| Header | `Authorization: Bearer sk_…`, a SOIT API key with the `write` scope |

Each example reads the key from `SOIT_API_KEY`; keep it out of files you
commit.

## Claude Code

```bash
claude mcp add --transport http soit http://localhost:9200/mcp \
  --header "Authorization: Bearer $SOIT_API_KEY"
```

Or share it with a project in [`.mcp.json`](claude-code.mcp.json), which
Claude Code reads from the project root and expands `${SOIT_API_KEY}` in.

## Cursor

Put [`cursor-mcp.json`](cursor-mcp.json) in `.cursor/mcp.json` (one project)
or `~/.cursor/mcp.json` (every project). Cursor expands `${env:SOIT_API_KEY}`.

## Python

[`python_client.py`](python_client.py) uses the official MCP Python SDK
(`pip install mcp`) to list the tools and call one:

```bash
export SOIT_MCP_URL=http://localhost:9200/mcp
export SOIT_API_KEY=sk_...
python python_client.py
```
