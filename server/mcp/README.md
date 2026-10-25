# mem0 MCP server

Exposes the self-hosted mem0 API as MCP tools over streamable HTTP, so any
MCP client on your network (Claude Desktop, Claude Code, Cursor, ...) can use
your memories. Runs as the `mem0-mcp` service in the same compose cluster as
the mem0 API.

## Tools

| Tool              | Description                                        |
| ----------------- | -------------------------------------------------- |
| `add_memory`      | Store memories extracted from text for a user/agent/run. |
| `search_memories` | Semantic search with filters and limit.            |
| `get_memories`    | List memories for a user/agent/run.                |
| `get_memory`      | Fetch one memory by ID.                            |
| `update_memory`   | Overwrite a memory's text.                         |
| `delete_memory`   | Delete one memory by ID.                           |

`delete_all_memories`, `list_entities`, and `delete_entities` from the
deprecated `mem0-mcp` server are intentionally not exposed.

## Configuration

Environment variables (set in `server/.env`):

- `MEM0_API_URL` — mem0 API base URL inside the compose network (default `http://mem0:8000`).
- `MEM0_API_KEY` — bearer token the mem0 API accepts. Defaults to `ADMIN_API_KEY` in docker-compose; a dashboard-created user API key also works.
- `MEM0_DEFAULT_USER_ID` — optional scope used when a tool call omits `user_id`.

## Client setup

The service listens on host port 8890 at path `/mcp`:

```json
{
  "mcpServers": {
    "mem0": {
      "type": "http",
      "url": "http://nas.local.quavalent.io:8890/mcp"
    }
  }
}
```

For Claude Code: `claude mcp add --transport http mem0 http://nas.local.quavalent.io:8890/mcp`
