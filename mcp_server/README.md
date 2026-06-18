# clab-mcp Server

An MCP (Model Context Protocol) server that lets **Claude Desktop** (on a
Macbook) read and safely change the configuration of the ContainerLab nodes
running on **ks-server** — AOS-CX (`vr-aoscx`) and vJunos-switch
(`juniper_vjunosswitch`).

It must run **on ks-server**, because the node management IPs (`172.20.20.x`)
live on a Docker bridge reachable only from the host. The Macbook talks to this
server over the LAN via **Streamable HTTP** (no tunnel needed).

This server is **independent of the GUI** (`backend/`, port 8888). It only
*reuses* the SSH helpers in `backend/drivers/util.py`; it does not modify the
GUI and runs as its own process/service.

```
Macbook (Claude Desktop) ──HTTP:8765──▶ ks-server: clab-mcp ──┬─REST/SSH──▶ AOS-CX  172.20.20.x
   (LAN 172.31.204.250)                                          └─NETCONF/SSH▶ vJunos  172.20.20.x
```

## Tools

| Tool | Args | What it does |
|------|------|--------------|
| `get_node_facts` | `mgmt_ip`, `kind` | hostname / model / version |
| `get_node_config` | `mgmt_ip`, `kind` | current config (AOS-CX = running CLI, vJunos = `set`) |
| `run_show` | `mgmt_ip`, `kind`, `command` | run a read-only `show ...` command |
| `apply_config` | `mgmt_ip`, `kind`, `config`, `dry_run=true` | apply config (safe by default) |
| `rollback` | `mgmt_ip`, `command=1` | vJunos only: undo the last commit |

`mgmt_ip` and `kind` for each node are printed in the **Lab Export Markdown**
(GUI → *Export for MCP*), in the "サマリ" table. Attach that file to the chat.

### Safety model
- **`apply_config` defaults to `dry_run=true`.**
  - **vJunos**: loads the candidate, returns the commit **diff**, then discards
    it without committing — the device is untouched. Set `dry_run=false` to
    commit; undo with `rollback`.
  - **AOS-CX**: has no native diff. `dry_run=true` returns the exact lines that
    *would* be sent and does **not** touch the device — call `get_node_config`
    first to capture the current state, then re-run with `dry_run=false`.
- Config-change tools return a `diff`/`summary` so Claude can explain the change.
- Errors are structured: `error_kind` is one of
  `connect` / `auth` / `config` / `commit` / `rpc` / `bad_request`.

### Credentials / API paths (per 07_api_feasibility)
- AOS-CX: REST (Cookie login, `verify=False`), version auto-discovered
  (probes `v10.16` first); `show`/running-config/conf-t over SSH. `admin/admin`.
- vJunos: NETCONF 830 via PyEZ (`junos-eznc`). `admin/admin@123`.

---

## 1. Run the server

### Dependencies
Reuses the Phase-07 venv at `~/work/api-test-venv` (already has `junos-eznc`,
`ncclient`, `paramiko`). Add the two new deps:

```bash
~/work/api-test-venv/bin/pip install -r ~/work/container-lab/mcp_server/requirements.txt
```

### Configure
```bash
cd ~/work/container-lab/mcp_server
cp .env.example .env          # then edit .env
# generate a token:
~/work/api-test-venv/bin/python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Set `MCP_TOKEN` in `.env` to that value. (`.env` is gitignored.)

### Manual start (for testing)
```bash
cd ~/work/container-lab/mcp_server
~/work/api-test-venv/bin/python server.py
# -> clab-mcp listening on http://0.0.0.0:8765/mcp  (auth: on)
```

### Run as a service (systemd)
```bash
sudo cp ~/work/container-lab/mcp_server/clab-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now clab-mcp     # enable = start at boot
systemctl status clab-mcp
journalctl -u clab-mcp -f                 # follow logs
```
This service is separate from the GUI; restarting one does not affect the other.

### Quick local check
```bash
# from ks-server, using the venv's FastMCP client:
cd ~/work/container-lab/mcp_server
MCP_TOKEN_VAL=$(grep ^MCP_TOKEN= .env | cut -d= -f2-) \
~/work/api-test-venv/bin/python - <<'PY'
import asyncio, os
from fastmcp import Client
async def main():
    async with Client("http://127.0.0.1:8765/mcp", auth=os.environ["MCP_TOKEN_VAL"]) as c:
        print([t.name for t in await c.list_tools()])
        r = await c.call_tool("get_node_facts", {"mgmt_ip":"172.20.20.3","kind":"vr-aoscx"})
        print(r.data)
asyncio.run(main())
PY
```

---

## 2. Connect Claude Desktop (remote MCP over Streamable HTTP)

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Use the server's LAN address and the **same token** as in `.env`:

```json
{
  "mcpServers": {
    "clab-mcp": {
      "type": "http",
      "url": "http://172.31.204.250:8765/mcp",
      "headers": {
        "Authorization": "Bearer PASTE_THE_SAME_MCP_TOKEN_HERE"
      }
    }
  }
}
```

Notes:
- `172.31.204.250` is ks-server on the LAN; `8765` / `/mcp` match `.env`.
- If your Claude Desktop build doesn't support `"type": "http"` directly, bridge
  it with `mcp-remote`:
  ```json
  {
    "mcpServers": {
      "clab-mcp": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "http://172.31.204.250:8765/mcp",
                 "--header", "Authorization: Bearer PASTE_THE_SAME_MCP_TOKEN_HERE"]
      }
    }
  }
  ```
- Restart Claude Desktop. `clab-mcp` and its 5 tools should appear.

---

## 3. Usage flow

1. **GUI** → open the running lab → click **⬇ Export for MCP** → download
   `<lab>-mcp-export.md`.
2. In **Claude Desktop**, attach that `.md` to the chat (it carries each node's
   `mgmt_ip`, `kind`, API info and current config).
3. Ask in natural language, e.g.:
   - *「vsw1 の OSPF ネイバーを確認して」* → `run_show` (`show ospf neighbor`)
   - *「sw01 に VLAN 20 (name USERS) を追加して」* → `apply_config` (dry-run first,
     then apply on your OK)
   - *「さっきの vsw1 の変更を取り消して」* → `rollback`

Claude reads `mgmt_ip` / `kind` from the attached Markdown and picks the right
tool. For changes it will show the dry-run diff first; confirm before it
re-runs with `dry_run=false`.
