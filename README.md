[日本語版 / Japanese](README.ja.md)

# clab — Multi-Vendor ContainerLab Management GUI + MCP Server

A web GUI and a Claude MCP server for building, deploying, and operating
**multi-vendor** network topologies on [ContainerLab](https://containerlab.dev/).
It supports Aruba/HPE **AOS-CX** (`vr-aoscx`) and Juniper **vJunos-switch**
(`juniper_vjunosswitch`) side by side.

The project ships two front ends:

- **clab (GUI)** — operate labs from your browser.
- **clab-mcp (MCP server)** — read and safely change node configs from
  **Claude Desktop** over the LAN.

> ⚠️ This is a lab tool. It ships **no real credentials or secrets**. The
> factory-default `admin/admin` (AOS-CX) and `admin/admin@123` (vJunos) logins
> and a placeholder RADIUS shared secret are the only credentials referenced;
> the real `.env` and RADIUS config are git-ignored. **Change these before any
> non-lab use.**

## Features

### GUI (clab)
- **Lab management** — deploy / destroy / status, with a running-lab selector.
- **Apply Config / Preview Config** — push a template's config set to the nodes
  of the loaded lab in one click. The matching template is auto-selected when a
  lab is loaded (by name or by node-set match), so even generic lab names work.
- **Topology view** — YAML-driven link drawing on an interactive Cytoscape.js
  canvas.
- **Per-node terminals** — WebSocket-backed `xterm.js` consoles to each node.
- **Node detail panel** — live information pulled over SSH / API from the
  selected node.
- **Export for MCP** — generate a `.md` describing the lab (including the live
  network state of attached PCs) to attach in Claude Desktop.
- **YAML import / export** — round-trip topology files.

### MCP server (clab-mcp)
Exposed over Streamable HTTP on `:8765` and usable from Claude Desktop via
`mcp-remote`. Tools:

- `get_node_facts` — basic facts for a node.
- `get_node_config` — running config.
- `run_show` — run a read-only `show` command.
- `apply_config` — apply config (`dry_run` by default).
- `rollback` — roll back the last change.

## Architecture

- **backend/** — FastAPI app with a `NodeDriver` abstraction
  (`drivers/aoscx.py`, `drivers/vjunos_switch.py`, `drivers/linux.py`),
  dispatched by ContainerLab `kind`.
- **frontend/** — Vanilla JS single-page UI (`app.js`) using Cytoscape.js +
  xterm.js.
- **mcp_server/** — FastMCP server (Streamable HTTP, port 8765).
- **ContainerLab** manages the labs using `vrnetlab/vr-aoscx` and
  `vrnetlab/juniper_vjunos-switch`.

Device access paths:

- **AOS-CX** — REST API v10.16 (cookie login) for facts; SSH for
  `show` / `running-config` / `configure terminal`.
- **vJunos** — NETCONF (port 830) + PyEZ (`junos-eznc`); config is
  load → diff → commit with rollback support.

## Templates (`configs/defaults/`)

| Category | Templates |
| --- | --- |
| AOS-CX standard | `simple-l2`, `spine-leaf`, `vsx-mclag`, `auth-verify-radius` |
| vJunos | `junos-p2p` |
| Multi-vendor (CX × Junos) | `cx-junos-interop`, `cx-junos-p2p-l2`, `cx-junos-p2p-ospf`, `cx-junos-ospf-pc-demo` |
| EVPN-VXLAN (all AOS-CX) | `evpn-allcx-dynamic`, `vxlan-allcx-static`, `allcx-underlay-demo` |
| EVPN-VXLAN (multi-vendor) | `evpn-mv-dynamic`, `evpn-mv-underlay-demo` |

## EVPN-VXLAN notes

- **`vr-aoscx` 10.16.1006 runs EVPN Dynamic VTEP.** The key is configuring
  **`send-community extended`** on the BGP neighbor — EVPN route-targets are
  carried as Extended Communities, and without this the VTEPs are never created.
- Verify with `show interface vxlan vteps`: look for **Origin = evpn** and
  **Status = operational**.
- A multi-vendor design with a **vJunos Spine as the EVPN Route Reflector** and
  **AOS-CX Leaves as VTEPs** has been verified to bring up Dynamic VTEPs.

## Requirements

- A Linux host running ContainerLab (KVM-capable recommended).
- Docker.
- Container images imported into your local Docker:
  - `vrnetlab/vr-aoscx:10.16.1006`
  - `vrnetlab/juniper_vjunos-switch:25.4R1.12`
- Python 3.11+.
- Node.js (for `mcp-remote`, used by Claude Desktop).

> Appliance images (`.ova` / `.qcow2`) are **not** included in this repo.

## Quick start

### GUI

```bash
cp .env.example .env        # adjust credentials
docker compose up -d --build
# open http://<host>:8888
```

### MCP server

```bash
systemctl start clab-mcp     # Streamable HTTP on <host>:8765/mcp
```

Then point Claude Desktop at it via `mcp-remote` (key `clab-mcp`):

```json
{
  "mcpServers": {
    "clab-mcp": {
      "command": "npx",
      "args": ["mcp-remote", "http://<host>:8765/mcp", "--allow-http"]
    }
  }
}
```

Typical flow: in the GUI choose **Export for MCP**, attach the generated `.md`
to Claude Desktop, then operate the nodes in natural language.

> Lab data and runtime configs live under `~/claude/cx-clab/` (`labs/` and
> `configs/`) and are **not** tracked by git.

## Layout

```
backend/           FastAPI app + NodeDriver abstraction
frontend/          Browser GUI (Cytoscape.js + xterm.js)
mcp_server/        Claude MCP server (FastMCP)
configs/defaults/  Template config sets
Dockerfile         Builds the GUI image (bundles containerlab + docker CLI)
docker-compose.yml
```

## Security

- Real secrets are **never** committed. `.gitignore` excludes the real `.env`,
  `labs/` runtime artifacts, the vendored `vrnetlab/`, and large appliance
  images.
- The bundled `configs/` are **lab defaults**: the RADIUS shared secret is a
  placeholder and the logins are the vendor factory defaults
  (`admin/admin`, `admin/admin@123`). **Change these before any non-lab use.**
- Lab-internal IPs are kept as-is for out-of-the-box reproducibility.

## License

For internal lab use.
