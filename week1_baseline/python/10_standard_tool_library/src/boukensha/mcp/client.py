from __future__ import annotations

import itertools
import json
import os
import subprocess
from typing import Any, Dict, List, Optional


class Client:
    """A minimal MCP-over-stdio client: it spawns an MCP server as a
    subprocess, performs the initialize handshake, and lets you discover and
    call the tools it advertises. It knows nothing about any particular
    server — command, args, and env are the standard stdio transport config.

        client = boukensha.mcp.client.Client.spawn(command="mud-manager", args=["--mcp"])
        for t in client.tools:
            print(t["name"])
        print(client.call_tool("look")["text"])
        client.close()
    """

    class Error(RuntimeError):
        pass

    PROTOCOL_VERSION = "2025-06-18"

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        cmd = [str(command), *[str(a) for a in (args or [])]]
        merged_env = {**os.environ, **{str(k): str(v) for k, v in (env or {}).items()}}

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            text=True,
            bufsize=1,
        )
        self._id_counter = itertools.count(1)
        self.server_info: Optional[Dict[str, Any]] = None
        self.tools: List[Dict[str, Any]] = []
        self._handshake()
        self.tools = self._fetch_tools()

    @classmethod
    def spawn(
        cls,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> "Client":
        return cls(command=command, args=args, env=env)

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a tool. Returns {"text": str, "error": bool}."""
        res = self._request("tools/call", {"name": str(name), "arguments": arguments or {}})
        result = res.get("result")
        if result is None:
            raise self.Error(f"tools/call error: {res.get('error')!r}")
        text = "\n".join(
            c["text"] for c in (result.get("content") or []) if c.get("text") is not None
        )
        return {"text": text, "error": bool(result.get("isError"))}

    def close(self) -> None:
        try:
            self._process.stdin.close()
        except Exception:
            pass
        self._process.wait()
        try:
            self._process.stdout.close()
        except Exception:
            pass
        try:
            self._process.stderr.close()
        except Exception:
            pass

    # ---------- internal --------------------------------------------------

    def _handshake(self) -> None:
        import boukensha as _boukensha  # deferred: avoids a circular import at load time

        res = self._request(
            "initialize",
            {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "boukensha", "version": _boukensha.__version__},
            },
        )
        self.server_info = (res.get("result") or {}).get("serverInfo")
        self._notify("notifications/initialized")

    def _fetch_tools(self) -> List[Dict[str, Any]]:
        res = self._request("tools/list")
        return (res.get("result") or {}).get("tools") or []

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req_id = next(self._id_counter)
        self._write({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        return self._read_until(req_id)

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _write(self, obj: Dict[str, Any]) -> None:
        self._process.stdin.write(json.dumps(obj) + "\n")
        self._process.stdin.flush()

    def _read_until(self, req_id: int) -> Dict[str, Any]:
        while True:
            line = self._process.stdout.readline()
            if line == "":
                raise self.Error("server closed the connection")
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if msg.get("id") == req_id:
                return msg
            # ignore server-initiated notifications / mismatched ids
