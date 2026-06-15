# lab_manager.py
"""Vendor-neutral lab orchestration.

Device/kind-specific behaviour (credentials, show commands, parsing, config
push, boot detection, capacity) lives in backend/drivers/*. This module only
knows how to drive containerlab and route per-node operations to the driver
resolved from each node's containerlab kind.
"""
import subprocess
import yaml
import os
import json
import re
import time
from pathlib import Path
from datetime import datetime

from drivers import get_driver, DEFAULT_KIND, list_drivers
from drivers import util

LABS_DIR = Path("/home/kshimono/claude/cx-clab/labs")
LABS_DIR.mkdir(parents=True, exist_ok=True)

# Per-template default config sets pushed by the "Apply Config" action.
DEFAULTS_DIR = Path("/home/kshimono/claude/cx-clab/configs/defaults")
# Mounted FreeRADIUS templates used by get_radius_summary().
FREERADIUS_DIR = Path("/home/kshimono/claude/cx-clab/configs/freeradius")


def topology_to_clab_yaml(topology: dict, lab_name: str) -> str:
    """Convert the GUI topology definition to ContainerLab YAML.
    Each node's clab definition is produced by its driver; node coordinates are
    embedded in labels so they can be restored."""
    nodes = {}
    for node in topology.get("nodes", []):
        kind = node.get("kind") or DEFAULT_KIND
        labels = {
            "clab-gui-x": str(int(node.get("x", 300))),
            "clab-gui-y": str(int(node.get("y", 250))),
            "clab-gui-label": str(node.get("label", node["id"])),
        }
        driver = get_driver(kind)
        nodes[node["id"]] = driver.build_node_def(node, labels)

    links = []
    for link in topology.get("links", []):
        src_if = link.get("src_if", "1/1/1")
        dst_if = link.get("dst_if", "1/1/1")
        links.append({
            "endpoints": [
                f"{link['source']}:{src_if}",
                f"{link['target']}:{dst_if}",
            ]
        })

    clab_def = {
        "name": lab_name,
        "topology": {
            "nodes": nodes,
            "links": links,
        }
    }
    return yaml.dump(clab_def, default_flow_style=False, allow_unicode=True)


def get_lab_path(lab_name: str) -> Path:
    return LABS_DIR / lab_name


def deploy_lab(topology: dict, lab_name: str) -> dict:
    """Deploy a lab."""
    lab_dir = get_lab_path(lab_name)
    lab_dir.mkdir(parents=True, exist_ok=True)

    yaml_content = topology_to_clab_yaml(topology, lab_name)
    yaml_path = lab_dir / f"{lab_name}.clab.yml"
    yaml_path.write_text(yaml_content)

    result = subprocess.run(
        ["containerlab", "deploy", "-t", str(yaml_path), "--reconfigure"],
        capture_output=True, text=True, timeout=600
    )

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "yaml_path": str(yaml_path),
        "yaml_content": yaml_content,
    }


def destroy_lab(lab_name: str, remove_files: bool = True) -> dict:
    lab_dir = get_lab_path(lab_name)
    yaml_path = lab_dir / f"{lab_name}.clab.yml"

    result_stdout = ""
    result_stderr = ""
    success = True

    if yaml_path.exists():
        result = subprocess.run(
            ["containerlab", "destroy", "-t", str(yaml_path), "--cleanup"],
            capture_output=True, text=True, timeout=180
        )
        result_stdout = result.stdout
        result_stderr = result.stderr
        success = result.returncode == 0

    # fully remove the lab files/directory
    if remove_files and lab_dir.exists():
        import shutil
        try:
            shutil.rmtree(lab_dir)
            result_stdout += f"\nRemoved lab directory: {lab_dir}"
        except Exception as e:
            result_stderr += f"\nFailed to remove dir: {e}"

    return {
        "success": success,
        "stdout": result_stdout,
        "stderr": result_stderr,
    }


def get_lab_status(lab_name: str) -> dict:
    """Get the container state of a lab."""
    result = subprocess.run(
        ["docker", "ps", "-a",
         "--filter", f"name=clab-{lab_name}-",
         "--format", "{{json .}}"],
        capture_output=True, text=True
    )

    containers = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                c = json.loads(line)
                node_name = c.get("Names", "").lstrip("/")
                health_result = subprocess.run(
                    ["docker", "inspect", node_name,
                     "--format", "{{.State.Health.Status}}"],
                    capture_output=True, text=True
                )
                health = health_result.stdout.strip()
                c["Health"] = health if health else "none"
                containers.append(c)
            except json.JSONDecodeError:
                pass

    return {"lab_name": lab_name, "containers": containers}


def list_labs() -> list:
    """List deployed labs."""
    if not LABS_DIR.exists():
        return []
    labs = []
    for lab_dir in LABS_DIR.iterdir():
        if lab_dir.is_dir():
            yaml_files = list(lab_dir.glob("*.clab.yml"))
            if yaml_files:
                labs.append({
                    "name": lab_dir.name,
                    "yaml_path": str(yaml_files[0]),
                    "modified": datetime.fromtimestamp(
                        yaml_files[0].stat().st_mtime
                    ).isoformat()
                })
    return labs


# ── per-node driver resolution ─────────────────────────────────
def _resolve_driver(lab_name: str, node_id: str, hint_kind: str = ""):
    """Pick the driver for a deployed node: prefer the live container's
    clab-node-kind label, fall back to a caller-supplied kind, then default."""
    kind = util.node_kind(lab_name, node_id) or hint_kind or DEFAULT_KIND
    return get_driver(kind), kind


def get_node_ssh_info(lab_name: str, node_id: str) -> dict:
    """Get a node's SSH connection info (host + driver credentials)."""
    host = util.get_container_ip(lab_name, node_id)
    if not host:
        return {}
    driver, _ = _resolve_driver(lab_name, node_id)
    return driver.ssh_info(host)


def exec_command(lab_name: str, node_id: str, command: str) -> dict:
    """Run a single command on a node, routed through its driver."""
    driver, kind = _resolve_driver(lab_name, node_id)

    if not driver.is_vm:
        out = util.docker_exec(lab_name, node_id, command)
        return {"success": True, "output": out}

    host = util.get_container_ip(lab_name, node_id)
    if not host:
        return {"success": False, "output": f"Node {node_id} not found or has no IP yet"}
    raw = util.run_show_commands(
        host, driver.ssh_port, driver.default_username, driver.default_password,
        driver.paging_cmds, {"cmd": command}, timeout=15,
    )
    out = raw.get("cmd", "")
    failed = out.startswith("[SSH error")
    return {"success": not failed, "output": out}


# ── Running labs (containerlab inspect --all) ──────────────────
def list_running_labs() -> list:
    """Run `containerlab inspect --all` as JSON and group by lab name."""
    try:
        result = subprocess.run(
            ["containerlab", "inspect", "--all", "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
    except Exception:
        return []

    rows = []
    if isinstance(data, dict):
        if isinstance(data.get("containers"), list):
            rows = data["containers"]
        else:
            for _lab, items in data.items():
                if isinstance(items, list):
                    rows.extend(items)
    elif isinstance(data, list):
        rows = data

    labs = {}
    for c in rows:
        if not isinstance(c, dict):
            continue
        lab = c.get("lab_name") or c.get("labName") or c.get("lab") or ""
        full_name = c.get("name", "")
        node_id = full_name
        prefix = f"clab-{lab}-"
        if lab and full_name.startswith(prefix):
            node_id = full_name[len(prefix):]
        mgmt = (c.get("ipv4_address") or c.get("mgmt-ipv4-address")
                or c.get("mgmt_ipv4_address") or "")
        if mgmt and "/" in mgmt:
            mgmt = mgmt.split("/")[0]
        if mgmt in ("N/A", "<nil>"):
            mgmt = ""
        node = {
            "name": node_id,
            "kind": c.get("kind", ""),
            "image": c.get("image", ""),
            "mgmt_ip": mgmt,
            "state": c.get("state", ""),
            "status": c.get("status", ""),
        }
        labs.setdefault(lab, []).append(node)

    out = []
    for lab, nodes in labs.items():
        if not lab:
            continue
        nodes.sort(key=lambda n: n["name"])
        out.append({"name": lab, "node_count": len(nodes), "nodes": nodes})
    out.sort(key=lambda l: l["name"])
    return out


# ── Live node info (delegated to the driver) ───────────────────
def get_node_live_info(lab_name: str, node_id: str, kind: str = "") -> dict:
    """Live info for the Refresh button, produced by the node's driver.
    Returns raw output even on parse failure; never hangs the UI on timeout."""
    driver, resolved = _resolve_driver(lab_name, node_id, hint_kind=kind)
    try:
        return driver.live_info(lab_name, node_id)
    except Exception as e:
        return {
            "lab_name": lab_name, "node_id": node_id, "kind": resolved,
            "deploy_state": util.deploy_state(lab_name, node_id),
            "vlans": [], "ip_ifs": [], "interfaces": [], "lldp": [],
            "version": "", "raw": {"error": f"[live_info error: {e}]"},
        }


# ── Apply Config (per-template default config sets) ────────────
def _node_order(template_id: str, tdir: Path) -> list:
    """Return the node push order. Honors an optional _order.txt (one node id
    per line); otherwise falls back to sorted config/script stems."""
    order_file = tdir / "_order.txt"
    if order_file.exists():
        ids = [ln.strip() for ln in order_file.read_text().splitlines()
               if ln.strip() and not ln.strip().startswith("#")]
        if ids:
            return ids
    stems = {p.stem for p in tdir.glob("*.cfg")} | {p.stem for p in tdir.glob("*.sh")}
    return sorted(stems)


def apply_default_config(lab_name: str, template_id: str) -> dict:
    """Push per-node default config sets for the given template to running nodes.
    Reads configs/defaults/<template_id>/<node_id>.cfg (network OS) or .sh
    (linux), in the order given by _order.txt. Each node is routed to its driver
    (AOS-CX conf-t / Junos commit / linux nsenter). Per-node failures are
    recorded and the run continues."""
    tdir = DEFAULTS_DIR / template_id
    if not tdir.is_dir():
        return {"success": False,
                "error": f"No default config set for template '{template_id}'",
                "nodes": {}}

    nodes = {}
    for node_id in _node_order(template_id, tdir):
        cfg = tdir / f"{node_id}.cfg"
        sh = tdir / f"{node_id}.sh"
        if cfg.exists():
            driver, _ = _resolve_driver(lab_name, node_id)
            nodes[node_id] = driver.apply_config(lab_name, node_id, cfg.read_text())
        elif sh.exists():
            # shell scripts are always applied via the linux driver (nsenter)
            nodes[node_id] = get_driver("linux").apply_config(
                lab_name, node_id, sh.read_text())
        else:
            continue
        time.sleep(1.5)

    success = bool(nodes) and all(v.get("ok") for v in nodes.values())
    return {"success": success, "template_id": template_id,
            "lab_name": lab_name, "nodes": nodes}


def _gui_labels(lab_name: str) -> dict:
    """Map node_id -> GUI label from a deployed lab's clab YAML (best-effort).
    Returns an empty dict if the lab file is missing or unparsable."""
    out = {}
    yaml_path = get_lab_path(lab_name) / f"{lab_name}.clab.yml"
    if not yaml_path.exists():
        return out
    try:
        clab = yaml.safe_load(yaml_path.read_text())
        for nid, ndef in (clab.get("topology", {}).get("nodes", {}) or {}).items():
            labels = (ndef or {}).get("labels", {}) or {}
            out[nid] = labels.get("clab-gui-label", nid)
    except Exception:
        pass
    return out


def preview_default_config(lab_name: str, template_id: str) -> dict:
    """Read (but do NOT apply) the per-node default config set for a template.

    Mirrors apply_default_config's file resolution (configs/defaults/<template_id>/
    <node_id>.cfg|.sh in _order.txt order) but only reads files — no device access.
    Nodes listed in _order.txt without a matching file are returned with
    content=None so the UI can show "設定なし". Used by the Preview Config UI."""
    tdir = DEFAULTS_DIR / template_id
    if not tdir.is_dir():
        return {"success": False,
                "error": f"No default config set for template '{template_id}'",
                "lab_name": lab_name, "template_id": template_id, "nodes": []}

    labels = _gui_labels(lab_name)
    nodes = []
    for node_id in _node_order(template_id, tdir):
        cfg = tdir / f"{node_id}.cfg"
        sh = tdir / f"{node_id}.sh"
        if cfg.exists():
            content, fname, ftype = cfg.read_text(), cfg.name, "cfg"
        elif sh.exists():
            content, fname, ftype = sh.read_text(), sh.name, "sh"
        else:
            content, fname, ftype = None, None, None
        # kind from the live container when available (same resolution apply uses)
        kind = util.node_kind(lab_name, node_id) or ""
        nodes.append({
            "node_id": node_id,
            "kind": kind,
            "label": labels.get(node_id, node_id),
            "config_file": fname,
            "type": ftype,
            "content": content,
        })
    return {"success": True, "lab_name": lab_name,
            "template_id": template_id, "nodes": nodes}


# ── Resource guard ─────────────────────────────────────────────
def _mem_available_gib() -> float:
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            if ln.startswith("MemAvailable:"):
                kb = int(ln.split()[1])
                return round(kb / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0


def estimate_resources(topology: dict) -> dict:
    """Estimate RAM required by a topology (per-driver node unit) and compare it
    to host MemAvailable. Used to warn before deploy."""
    breakdown = {}
    required = 0.0
    for node in topology.get("nodes", []):
        kind = node.get("kind") or DEFAULT_KIND
        driver = get_driver(kind)
        required += driver.ram_gib
        b = breakdown.setdefault(driver.display_name, {"count": 0, "ram_gib": 0.0})
        b["count"] += 1
        b["ram_gib"] = round(b["ram_gib"] + driver.ram_gib, 2)

    available = _mem_available_gib()
    required = round(required, 1)
    # keep a safety headroom so the host doesn't go to zero
    headroom = 2.0
    ok = (required + headroom) <= available if available else True
    warning = ""
    if available and not ok:
        warning = (f"Estimated {required} GiB required, only {available} GiB "
                   f"available (incl. {headroom} GiB headroom). Deploy may fail "
                   f"or thrash.")
    return {
        "required_gib": required,
        "available_gib": available,
        "headroom_gib": headroom,
        "ok": ok,
        "warning": warning,
        "breakdown": breakdown,
    }


# ── RADIUS summary (static read of mounted FreeRADIUS templates) ─
def get_radius_summary() -> dict:
    """Return a summary of the mounted FreeRADIUS templates for the detail panel.
    Static read only; no device access. Reflects configs/freeradius/* on disk."""
    summary = {"mac_auth": "unknown", "dot1x_user": None, "secret": None, "clients": []}

    authz = FREERADIUS_DIR / "authorize"
    if authz.exists():
        try:
            txt = authz.read_text()
            if re.search(r"^\s*DEFAULT\s+Auth-Type\s*:=\s*Accept", txt, re.MULTILINE):
                summary["mac_auth"] = "accept-all"
            m = re.search(r"^\s*(\w+)\s+Cleartext-Password", txt, re.MULTILINE)
            if m:
                summary["dot1x_user"] = m.group(1)
        except Exception:
            pass

    clients = FREERADIUS_DIR / "clients.conf"
    if clients.exists():
        try:
            txt = clients.read_text()
            for m in re.finditer(r"client\s+(\S+)\s*\{([^}]*)\}", txt, re.DOTALL):
                name, body = m.group(1), m.group(2)
                ip = re.search(r"ipaddr\s*=\s*(\S+)", body)
                sec = re.search(r"secret\s*=\s*(\S+)", body)
                summary["clients"].append({
                    "name": name,
                    "ipaddr": ip.group(1) if ip else "",
                    "secret": sec.group(1) if sec else "",
                })
                if sec and not summary["secret"]:
                    summary["secret"] = sec.group(1)
        except Exception:
            pass

    return summary


def export_topology_yaml(topology: dict, lab_name: str) -> str:
    """Export the topology as ContainerLab YAML."""
    return topology_to_clab_yaml(topology, lab_name)


def import_topology_yaml(yaml_content: str) -> dict:
    """Convert ContainerLab YAML to a GUI topology."""
    try:
        clab = yaml.safe_load(yaml_content)
        lab_name = clab.get("name", "imported")
        topo = clab.get("topology", {})

        nodes = []
        for i, (node_id, node_def) in enumerate(topo.get("nodes", {}).items()):
            kind = node_def.get("kind", DEFAULT_KIND)
            labels = node_def.get("labels", {}) or {}
            if "clab-gui-x" in labels and "clab-gui-y" in labels:
                x = int(labels.get("clab-gui-x", 300))
                y = int(labels.get("clab-gui-y", 250))
            else:
                x = 150 + (i % 3) * 280
                y = 150 + (i // 3) * 280
            label = labels.get("clab-gui-label", node_id)
            node_entry = {
                "id": node_id, "label": label, "kind": kind, "x": x, "y": y,
            }
            img = node_def.get("image")
            if img:
                node_entry["image"] = img
            binds = node_def.get("binds")
            if binds:
                node_entry["binds"] = binds
            delay = node_def.get("startup-delay")
            if delay:
                node_entry["startup_delay"] = delay
            nodes.append(node_entry)

        links = []
        for link in topo.get("links", []):
            eps = link.get("endpoints", [])
            if len(eps) == 2:
                src_node, src_if = eps[0].split(":", 1)
                dst_node, dst_if = eps[1].split(":", 1)
                links.append({
                    "source": src_node, "target": dst_node,
                    "src_if": src_if, "dst_if": dst_if,
                    "label": f"{src_if}↔{dst_if}",
                })

        return {"success": True, "lab_name": lab_name, "topology": {"nodes": nodes, "links": links}}
    except Exception as e:
        return {"success": False, "error": str(e)}
