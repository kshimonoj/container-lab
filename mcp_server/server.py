# mcp_server/server.py
"""CX-CLAB MCP server (FastMCP, Streamable HTTP).

Exposes read + safe config-change tools for the ContainerLab nodes (AOS-CX and
vJunos-switch) running on ks-server. Claude Desktop connects over the LAN and
operates the lab using the mgmt_ip / kind values that appear in the "Export for
MCP" Markdown attached to the chat.

Run:  python server.py        (reads .env for bind + token)
Auth: a single fixed bearer token (MCP_TOKEN) checked on every HTTP request.
"""
import os

from starlette.middleware import Middleware

from fastmcp import FastMCP

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

import cx_client
import junos_client

# ── config (env) ────────────────────────────────────────────────
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8765"))
PATH = os.environ.get("MCP_PATH", "/mcp")
TOKEN = os.environ.get("MCP_TOKEN", "").strip()

# kind -> client module. Aliases mirror backend/drivers/__init__.py so the kind
# strings from the Lab Export Markdown resolve regardless of spelling.
_CX_KINDS = {"vr-aoscx", "aruba_aoscx", "aoscx"}
_JUNOS_KINDS = {"juniper_vjunosswitch", "juniper_vjunos-switch",
                "vjunos", "vjunos-switch"}


def _route(kind):
    """Map a containerlab kind to its client module, or (None, error-dict)."""
    k = (kind or "").strip()
    if k in _CX_KINDS:
        return cx_client, None
    if k in _JUNOS_KINDS:
        return junos_client, None
    return None, {
        "ok": False, "error_kind": "bad_request",
        "error": (f"unknown kind {kind!r}. Use one of: "
                  f"vr-aoscx (AOS-CX) or juniper_vjunosswitch (vJunos). "
                  f"The kind is listed in the Lab Export Markdown."),
    }


mcp = FastMCP("cx-clab-mcp")


# ── tools ───────────────────────────────────────────────────────
@mcp.tool
def get_node_facts(mgmt_ip: str, kind: str) -> dict:
    """Get a node's identity: hostname, model, and OS version.

    mgmt_ip and kind come from the attached Lab Export Markdown (the "サマリ"
    table). kind is 'vr-aoscx' for AOS-CX or 'juniper_vjunosswitch' for vJunos.

    AOS-CX is read via REST GET /system; vJunos via NETCONF/PyEZ facts.
    Returns {ok, hostname, model, version, ...} or {ok:false, error_kind, error}.
    """
    client, bad = _route(kind)
    if bad:
        return bad
    if client is cx_client:
        return cx_client.get_system(mgmt_ip)
    return junos_client.get_facts(mgmt_ip)


@mcp.tool
def get_node_config(mgmt_ip: str, kind: str) -> dict:
    """Get a node's current configuration.

    AOS-CX returns CLI running-config text (format 'cli'); vJunos returns the
    configuration in `set` format. Use this BEFORE apply_config so you can
    describe and verify what will change.

    mgmt_ip and kind come from the attached Lab Export Markdown.
    Returns {ok, format, text} or {ok:false, error_kind, error}.
    """
    client, bad = _route(kind)
    if bad:
        return bad
    if client is cx_client:
        return cx_client.get_running_config(mgmt_ip)
    return junos_client.get_config(mgmt_ip, fmt="set")


@mcp.tool
def run_show(mgmt_ip: str, kind: str, command: str) -> dict:
    """Run a read-only operational 'show ...' command and return its output.

    Examples: AOS-CX 'show vlan', 'show ip interface brief'; vJunos
    'show interfaces terse', 'show ospf neighbor'. This never changes config.

    mgmt_ip and kind come from the attached Lab Export Markdown.
    Returns {ok, command, output} or {ok:false, error_kind, error}.
    """
    client, bad = _route(kind)
    if bad:
        return bad
    return client.run_show(mgmt_ip, command)


@mcp.tool
def apply_config(mgmt_ip: str, kind: str, config: str,
                 dry_run: bool = True) -> dict:
    """Apply a configuration change. SAFE BY DEFAULT (dry_run=True).

    Provide `config` in the node's native CLI form:
      - AOS-CX: conf-t style lines, e.g. 'vlan 20\\n    name USERS'
      - vJunos: `set` format lines, e.g. 'set vlans USERS vlan-id 20'

    dry_run=True (default):
      - vJunos: loads the candidate and returns the commit DIFF, then discards
        it WITHOUT committing (device unchanged).
      - AOS-CX: returns the exact lines that would be sent (no native diff);
        the device is NOT touched. Call get_node_config first for current state.
    dry_run=False: actually applies (AOS-CX conf-t / vJunos commit). For vJunos
    you can undo with the rollback tool.

    Always review the returned diff/summary before re-running with dry_run=false.
    mgmt_ip and kind come from the attached Lab Export Markdown.
    """
    client, bad = _route(kind)
    if bad:
        return bad
    return client.apply_config(mgmt_ip, config, dry_run=dry_run)


@mcp.tool
def rollback(mgmt_ip: str, command: int = 1) -> dict:
    """Roll back the most recent committed change on a vJunos node.

    vJunos ONLY (AOS-CX has no NETCONF rollback; undo it with apply_config).
    `command` is the rollback id: 1 = undo the last commit (default). Returns
    the diff that was applied. mgmt_ip comes from the Lab Export Markdown.
    """
    return junos_client.rollback(mgmt_ip, n=command)


# ── auth middleware (single fixed bearer token over the LAN) ─────
class TokenAuthMiddleware:
    def __init__(self, app, token):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.token:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"authorization", b"").decode()
        if provided != f"Bearer {self.token}":
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body",
                        "body": b'{"error":"unauthorized: missing/invalid bearer token"}'})
            return
        await self.app(scope, receive, send)


def build_app():
    mw = []
    if TOKEN:
        mw.append(Middleware(TokenAuthMiddleware, token=TOKEN))
    return mcp.http_app(path=PATH, middleware=mw)


app = build_app()


if __name__ == "__main__":
    import uvicorn
    if not TOKEN:
        print("WARNING: MCP_TOKEN is empty - the server is UNAUTHENTICATED. "
              "Set MCP_TOKEN in .env.")
    print(f"cx-clab-mcp listening on http://{HOST}:{PORT}{PATH}  "
          f"(auth: {'on' if TOKEN else 'OFF'})")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
