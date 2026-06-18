# clab — ContainerLab GUI

A web GUI for building, deploying, and operating multi-vendor topologies on
[ContainerLab](https://containerlab.dev/) — Aruba/HPE **AOS-CX** (`vr-aoscx`) and
Juniper **vJunos-switch** (`juniper_vjunosswitch`). Built with **FastAPI** (backend),
and **Cytoscape.js** + **xterm.js** (frontend).

The optional **clab-mcp** server (see `mcp_server/`) lets Claude Desktop read and
safely change node configs over the LAN.

> ⚠️ This is a lab tool. It ships **no real credentials or secrets**. The factory-default
> `admin/admin` AOS-CX login and a placeholder RADIUS shared secret are the only credentials
> referenced, and the real `.env` / RADIUS config are git-ignored. See **Security** below.

## Features

- **Lab management** — deploy / destroy / status, with a running-lab selector.
- **Topology view** — YAML-driven link drawing on an interactive Cytoscape.js canvas.
- **Terminals** — WebSocket-backed `xterm.js` consoles to each node.
- **Node detail panel** — live information pulled over SSH from the selected node.
- **Templates** — `simple-l2`, `spine-leaf`, `vsx-mclag`, `auth-verify-radius`, each with
  one-click **Apply Config**.

## Layout

```
backend/      FastAPI app (main.py, lab_manager.py, templates.py)
frontend/     Cytoscape.js + xterm.js single-page UI
Dockerfile    Builds the GUI image (bundles containerlab + docker CLI)
docker-compose.yml
```

## Requirements

- Docker (the GUI container needs the Docker socket and host networking).
- An AOS-CX container image imported into your local Docker (e.g. via `vrnetlab`).
- The AOS-CX `.ova` appliance image is **not** included in this repo.

## Quick start

```bash
cp .env.example .env        # adjust credentials
docker compose up -d --build
# open http://<host>:8888
```

## Security

- Real secrets are **never** committed. `.gitignore` excludes the real `.env`,
  `labs/` runtime artifacts, the vendored `vrnetlab/`, and the large `OVA/` appliance image.
- The bundled `configs/freeradius/` and `configs/defaults/` are **lab defaults**: the RADIUS
  shared secret is the placeholder value `labpassword` and the lab login is the AOS-CX factory
  `admin/admin`. **Change these before any non-lab use.**
- Lab-internal IPs (`10.1.x.x`) are kept as-is for out-of-the-box reproducibility.

## License

For internal lab use.
