"""MCP server exposing memory tools on top of the self-hosted mem0 REST API.

Runs inside the mem0 compose cluster and proxies tool calls to the mem0 API
service over the internal network. Configure with:

    MEM0_API_URL          base URL of the mem0 API (default http://mem0:8000)
    MEM0_API_KEY          bearer token accepted by the mem0 API (admin key or user key)
    MEM0_DEFAULT_USER_ID  optional fallback scope when a tool call omits user_id
"""

import json
import os
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

MEM0_API_URL = os.environ.get("MEM0_API_URL", "http://mem0:8000").rstrip("/")
MEM0_API_KEY = os.environ.get("MEM0_API_KEY", "")
MEM0_DEFAULT_USER_ID = os.environ.get("MEM0_DEFAULT_USER_ID") or None
# Comma-separated Host header values the MCP endpoint accepts, e.g.
# "networkapp:8890" or "networkapp:*". Port wildcards
# are supported. With the variable unset, DNS-rebinding protection is off
# entirely; when set, only listed hosts are accepted.
MCP_ALLOWED_HOSTS = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]

mcp = MCPServer(
    name="mem0",
    instructions=(
        "Long-term memory for this user. Add durable facts, preferences, and "
        "decisions with add_memory; recall context with search_memories or "
        "get_memories before answering questions the user has answered before."
    ),
)

_client = httpx.Client(
    base_url=MEM0_API_URL,
    headers={"Authorization": f"Bearer {MEM0_API_KEY}"} if MEM0_API_KEY else {},
    timeout=120.0,
)


def _call(method: str, path: str, **kwargs: Any) -> str:
    response = _client.request(method, path, **kwargs)
    if response.status_code >= 400:
        detail = response.json().get("detail", response.text) if response.headers.get("content-type", "").startswith("application/json") else response.text
        raise RuntimeError(f"mem0 API {method} {path} failed ({response.status_code}): {detail}")
    return json.dumps(response.json(), default=str)


def _scope(user_id: Optional[str], agent_id: Optional[str], run_id: Optional[str]) -> dict[str, Any]:
    scope = {"user_id": user_id or MEM0_DEFAULT_USER_ID, "agent_id": agent_id, "run_id": run_id}
    if not any(scope.values()):
        raise ValueError("Provide at least one of user_id, agent_id, run_id (or set MEM0_DEFAULT_USER_ID).")
    return {k: v for k, v in scope.items() if v}


@mcp.tool()
def add_memory(
    text: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Store new memories extracted from the given text for a user, agent, or run."""
    body = _scope(user_id, agent_id, run_id)
    body["messages"] = [{"role": "user", "content": text}]
    if metadata:
        body["metadata"] = metadata
    return _call("POST", "/memories", json=body)


@mcp.tool()
def search_memories(
    query: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Semantic search over stored memories. Use this to recall what you know about the user."""
    filters = _scope(user_id, agent_id, run_id)
    return _call("POST", "/search", json={"query": query, "filters": filters, "top_k": limit})


@mcp.tool()
def get_memories(
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
) -> str:
    """List stored memories for a user, agent, or run. Search instead when a specific fact is needed."""
    params = _scope(user_id, agent_id, run_id)
    params["top_k"] = limit
    return _call("GET", "/memories", params=params)


@mcp.tool()
def get_memory(memory_id: str) -> str:
    """Retrieve a single memory by its ID."""
    return _call("GET", f"/memories/{memory_id}")


@mcp.tool()
def update_memory(memory_id: str, text: str) -> str:
    """Overwrite a memory's text. Get user confirmation for the change first."""
    return _call("PUT", f"/memories/{memory_id}", json={"text": text})


@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a single memory by its ID. Get user confirmation for the deletion first."""
    return _call("DELETE", f"/memories/{memory_id}")


_transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
if MCP_ALLOWED_HOSTS:
    _transport_security = TransportSecuritySettings(
        allowed_hosts=MCP_ALLOWED_HOSTS,
        # Same-origin clients (curl, native MCP clients) send no Origin header,
        # which the middleware accepts. Listed hosts cover browser-based clients.
        allowed_origins=[f"http://{h}" for h in MCP_ALLOWED_HOSTS],
    )
else:
    print("MCP_ALLOWED_HOSTS is unset - accepting requests with any Host header", flush=True)

app = mcp.streamable_http_app(transport_security=_transport_security)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8000")))
