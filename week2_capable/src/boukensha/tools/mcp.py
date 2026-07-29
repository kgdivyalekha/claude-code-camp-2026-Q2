from __future__ import annotations

import atexit
from typing import Any, Dict, List, Optional

from ..mcp.client import Client

SEPARATOR = "__"


class CollisionError(ValueError):
    """Two tools claiming one name. Always fatal, even for an optional server:
    this is a config contradiction, not a server being unreachable, and
    silently dropping the loser is the expensive failure."""


def register(
    registry: Any,
    command: str,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    prefix: Optional[str] = None,
) -> Client:
    """Mcp makes boukensha an MCP host: point it at any MCP server and every
    tool that server advertises becomes a boukensha tool. It knows nothing
    about any particular server — command/args/env is the standard stdio
    transport config, the same triple every other MCP host uses.

        tools.mcp.register(
            registry, command="mud-manager", args=["--mcp"],
            env={"MUD_HOST": "localhost"}, prefix="tbamud",
        )

    ``registry`` is anything with the ``tool``/``tool_names`` surface — a
    Registry or the RunDSL yielded to a run/repl callback.

    prefix: scopes the discovered names ("tbamud" -> tbamud__look). The
    prefix is a property of the server entry, supplied by config; this
    function applies whatever it is given. Names are only prefixed
    agent-side — the server still sees its own bare name on the wire.
    """
    client = Client.spawn(command=command, args=args, env=env)
    atexit.register(lambda: _safe_close(client))
    register_client(registry, client, prefix=prefix)
    return client


def register_client(registry: Any, client: Client, prefix: Optional[str] = None) -> int:
    """Register an already-spawned client's tools. Returns the count."""
    taken = list(registry.tool_names()) if hasattr(registry, "tool_names") else []

    for tool in client.tools:
        remote = tool["name"]
        local = prefixed(remote, prefix)

        if local in taken:
            raise CollisionError(
                f"boukensha: MCP tool name collision on '{local}' — a tool by that "
                "name is already registered. Give this server a distinct `prefix:` "
                "in mcp_servers."
            )
        taken.append(local)

        def _block(_remote: str = remote, **kwargs: Any) -> str:
            # Boukensha hands us string-keyed kwargs already; the server
            # wants strings too. Blank/omitted values are normalized
            # server-side.
            result = client.call_tool(_remote, {str(k): v for k, v in kwargs.items()})
            return f"error: {result['text']}" if result["error"] else result["text"]

        # Trim tool description to first sentence (§3.3 optimization)
        tool_desc = str(tool.get("description") or "")
        tool_desc = tool_desc.split(".")[0].strip()

        registry.tool(
            local,
            description=tool_desc,
            parameters=to_boukensha_params(tool.get("inputSchema")),
            block=_block,
        )

    return len(client.tools)


def prefixed(name: str, prefix: Optional[str]) -> str:
    p = (prefix or "").strip()
    return name if not p else f"{p}{SEPARATOR}{name}"


def to_boukensha_params(input_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert an MCP inputSchema into boukensha's ``parameters`` shape
    (``{name: {"type":, "description":, "required":}}``). Every property is listed so the
    model can supply optional ones too (servers treat blanks as absent). Descriptions are
    trimmed to reduce schema overhead (§3.3 optimization)."""
    props = (input_schema or {}).get("properties") or {}
    required_params = set((input_schema or {}).get("required") or [])
    out: Dict[str, Any] = {}
    for pname, schema in props.items():
        desc = str(schema.get("description") or "")
        # Trim description to first sentence only
        desc = desc.split(".")[0].strip()
        if schema.get("enum"):
            desc = f"{desc} (one of: {', '.join(str(e) for e in schema['enum'])})".strip()
        out[pname] = {
            "type": schema.get("type") or "string",
            "description": desc,
            "required": pname in required_params
        }
    return out


def _safe_close(client: Client) -> None:
    try:
        client.close()
    except Exception:
        pass
