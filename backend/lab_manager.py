# lab_manager.py
import subprocess
import yaml
import os
import json
import re
import time
import paramiko
from pathlib import Path
from datetime import datetime

LABS_DIR = Path("/home/kshimono/claude/cx-clab/labs")
LABS_DIR.mkdir(parents=True, exist_ok=True)

CX_IMAGE = "vrnetlab/vr-aoscx:10.16.1006"

# Per-template default config sets pushed by the "Apply Config" action.
DEFAULTS_DIR = Path("/home/kshimono/claude/cx-clab/configs/defaults")
# Mounted FreeRADIUS templates used by get_radius_summary().
FREERADIUS_DIR = Path("/home/kshimono/claude/cx-clab/configs/freeradius")


def topology_to_clab_yaml(topology: dict, lab_name: str) -> str:
    """Convert the GUI topology definition to ContainerLab YAML.
    Node coordinates are embedded in labels so they can be restored."""
    nodes = {}
    for node in topology.get("nodes", []):
        kind = node.get("kind", "vr-aoscx")
        # store coordinates in labels (as strings)
        labels = {
            "clab-gui-x": str(int(node.get("x", 300))),
            "clab-gui-y": str(int(node.get("y", 250))),
            "clab-gui-label": str(node.get("label", node["id"])),
        }
        if kind == "linux":
            node_def = {
                "kind": "linux",
                "image": node.get("image") or "alpine:latest",
                "labels": labels,
            }
        else:
            node_def = {
                "kind": "vr-aoscx",
                "image": node.get("image") or CX_IMAGE,
                "labels": labels,
            }
        # optional mounts (e.g. RADIUS). emit binds only for nodes that have them (backward compatible)
        binds = node.get("binds")
        if binds:
            node_def["binds"] = list(binds)
        nodes[node["id"]] = node_def

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
        capture_output=True, text=True, timeout=300
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
            capture_output=True, text=True, timeout=120
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
    # containerlab does not add a "clab-node-lab-name" label.
    # filter by the node container name prefix clab-<lab_name>-.
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
                # fetch the health status individually
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


def exec_command(lab_name: str, node_id: str, command: str) -> dict:
    """Run a command on a node.

    AOS-CX runs inside a QEMU VM within the vrnetlab container, so a host-side
    `docker exec` cannot reach the CLI. We open an interactive SSH shell,
    disable paging, and run the command.
    """
    ssh_info = get_node_ssh_info(lab_name, node_id)
    if not ssh_info:
        return {"success": False, "output": f"Node {node_id} not found or has no IP yet"}

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            hostname=ssh_info["host"],
            port=ssh_info["port"],
            username=ssh_info["username"],
            password=ssh_info["password"],
            timeout=15,
            banner_timeout=30,
            auth_timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        chan = ssh.invoke_shell(term="xterm", width=220, height=100)
        time.sleep(1.5)
        if chan.recv_ready():
            chan.recv(65535)
        # AOS-CX: disable output paging
        chan.send("no page\n")
        time.sleep(0.8)
        if chan.recv_ready():
            chan.recv(65535)
        chan.send(command + "\n")
        time.sleep(2.0)

        out = b""
        deadline = time.time() + 15
        while time.time() < deadline:
            if chan.recv_ready():
                out += chan.recv(65535)
            else:
                time.sleep(0.3)
                if not chan.recv_ready():
                    break
        ssh.close()
        return {"success": True, "output": out.decode("utf-8", errors="replace")}
    except Exception as e:
        try:
            ssh.close()
        except Exception:
            pass
        return {"success": False, "output": f"SSH exec failed: {e}"}


def get_node_ssh_info(lab_name: str, node_id: str) -> dict:
    """Get a node's SSH connection info."""
    container_name = f"clab-{lab_name}-{node_id}"
    result = subprocess.run(
        ["docker", "inspect", container_name,
         "--format", "{{json .NetworkSettings.Networks}}"],
        capture_output=True, text=True
    )
    try:
        networks = json.loads(result.stdout)
        # prefer the clab management network (172.20.20.x)
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress", "")
            if ip and "clab" in net_name.lower():
                return {"host": ip, "port": 22, "username": "admin", "password": "admin"}
        # fall back to any network that has an IP, even without a clab- prefix
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress", "")
            if ip:
                return {"host": ip, "port": 22, "username": "admin", "password": "admin"}
    except Exception:
        pass
    return {}


# ── Running labs (containerlab inspect --all) ──────────────────
def list_running_labs() -> list:
    """Run `containerlab inspect --all` as JSON and group by lab name.
    Returns: [{"name", "node_count", "nodes":[{"name","kind","image","mgmt_ip","state","status"}]}]
    Defensively handles containerlab version differences ({"<lab>":[...]} / {"containers":[...]} / [...]).
    """
    try:
        result = subprocess.run(
            ["containerlab", "inspect", "--all", "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
    except Exception:
        return []

    # extract the row (container) list
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


# ── Live node info (show fetch + lightweight parse) ────────────
def _cx_exec_multi(lab_name: str, node_id: str, commands: dict, timeout: int = 12) -> dict:
    """Run multiple show commands over a single SSH session, return {key: output}.
    Avoids repeated logins for speed/robustness. On failure each value is an error string."""
    ssh_info = get_node_ssh_info(lab_name, node_id)
    if not ssh_info:
        return {k: f"[no IP for {node_id}]" for k in commands}

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    out = {}
    try:
        # CX SSH intermittently drops the session right after connect, so retry
        chan = None
        last_err = None
        for attempt in range(3):
            try:
                ssh.connect(
                    hostname=ssh_info["host"], port=ssh_info["port"],
                    username=ssh_info["username"], password=ssh_info["password"],
                    timeout=15, banner_timeout=30, auth_timeout=15,
                    look_for_keys=False, allow_agent=False,
                )
                chan = ssh.invoke_shell(term="xterm", width=220, height=100)
                break
            except Exception as e:
                last_err = e
                try:
                    ssh.close()
                except Exception:
                    pass
                time.sleep(2)
        if chan is None:
            raise last_err or RuntimeError("SSH connect failed")
        time.sleep(1.5)
        if chan.recv_ready():
            chan.recv(65535)
        chan.send("no page\n")
        time.sleep(0.6)
        if chan.recv_ready():
            chan.recv(65535)
        for key, cmd in commands.items():
            chan.send(cmd + "\n")
            time.sleep(1.0)
            buf = b""
            deadline = time.time() + timeout
            idle = 0
            while time.time() < deadline:
                if chan.recv_ready():
                    buf += chan.recv(65535)
                    idle = 0
                else:
                    # keep waiting (do not break) until real output beyond the echo arrives
                    # (slow nodes can take several seconds to produce first output)
                    decoded = buf.decode("utf-8", errors="replace")
                    got_output = len(decoded.strip()) > len(cmd) + 3
                    time.sleep(0.3)
                    if not chan.recv_ready():
                        idle += 1
                        if got_output and idle >= 2:
                            break
            out[key] = buf.decode("utf-8", errors="replace")
        ssh.close()
    except Exception as e:
        try:
            ssh.close()
        except Exception:
            pass
        for key in commands:
            out.setdefault(key, f"[SSH error: {e}]")
    return out


def _clean_lines(text: str) -> list:
    """Strip ANSI + split into lines. Keep blank lines (the parser decides)."""
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")
    return [ln.rstrip() for ln in text.replace("\r", "").split("\n")]


def _parse_cx_vlan(text: str) -> list:
    vlans = []
    for ln in _clean_lines(text):
        m = re.match(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$", ln)
        if m:
            vlans.append({
                "id": m.group(1), "name": m.group(2), "status": m.group(3),
                "reason": m.group(4), "type": m.group(5),
                "interfaces": m.group(6).strip(),
            })
    return vlans


def _parse_cx_ip_brief(text: str) -> list:
    ifs = []
    for ln in _clean_lines(text):
        if not ln.strip() or ln.lstrip().startswith("Interface") or set(ln.strip()) <= set("-"):
            continue
        parts = ln.split()
        if len(parts) < 2:
            continue
        ipm = re.search(r"\d+\.\d+\.\d+\.\d+(?:/\d+)?", ln)
        if not ipm:
            continue
        status = ""
        for tok in parts:
            if tok.lower() in ("up", "down"):
                status = tok.lower()
                break
        ifs.append({"interface": parts[0], "ip": ipm.group(0), "status": status})
    return ifs


def _parse_cx_if_brief(text: str) -> list:
    ifs = []
    for ln in _clean_lines(text):
        m = re.match(r"^\s*((?:\d+/\d+/\d+)|(?:lag\d+)|(?:vlan\d+))\s+(.*)$", ln)
        if not m:
            continue
        rest = m.group(2)
        status = ""
        sm = re.search(r"\b(up|down)\b", rest, re.IGNORECASE)
        if sm:
            status = sm.group(1).lower()
        ifs.append({"port": m.group(1), "status": status, "detail": rest.strip()})
    return ifs


def _parse_cx_lldp(text: str) -> list:
    nbrs = []
    for ln in _clean_lines(text):
        m = re.match(r"^\s*(\d+/\d+/\d+)\s+(.*)$", ln)
        if not m:
            continue
        rest = m.group(2).split()
        neighbor = rest[-1] if rest else ""
        nbrs.append({"local_port": m.group(1), "neighbor": neighbor,
                     "detail": m.group(2).strip()})
    return nbrs


def _parse_linux_ip_addr(text: str) -> list:
    """Parse busybox `ip addr` (multi-line). Return interfaces that have an IP."""
    ifs = []
    cur, cur_state = None, ""
    for ln in _clean_lines(text):
        m = re.match(r"^\d+:\s+([^:@]+)[@:]", ln)
        if m:
            cur = m.group(1).strip()
            fm = re.search(r"<([^>]*)>", ln)
            flags = fm.group(1).split(",") if fm else []
            cur_state = "up" if "UP" in flags else "down"
            continue
        im = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", ln)
        if im and cur:
            ifs.append({"interface": cur, "ip": im.group(1), "status": cur_state})
    return ifs


def _parse_linux_link(text: str) -> list:
    """Parse busybox `ip link` (multi-line)."""
    ifs = []
    for ln in _clean_lines(text):
        m = re.match(r"^\d+:\s+([^:@]+)[@:].*?\bstate\s+(\S+)", ln)
        if m:
            ifs.append({"port": m.group(1).strip(),
                        "status": m.group(2).lower(), "detail": ""})
    return ifs


def get_node_live_info(lab_name: str, node_id: str, kind: str = "aruba_aoscx") -> dict:
    """Live info for the Refresh button. Switches commands by kind.
    Returns raw output even on parse failure. Never hangs the UI on timeout."""
    result = {
        "lab_name": lab_name, "node_id": node_id, "kind": kind,
        "deploy_state": "", "vlans": [], "ip_ifs": [],
        "interfaces": [], "lldp": [], "raw": {},
    }

    container = f"clab-{lab_name}-{node_id}"
    try:
        st = subprocess.run(
            ["docker", "inspect", container,
             "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"],
            capture_output=True, text=True, timeout=10
        )
        result["deploy_state"] = st.stdout.strip() if st.returncode == 0 else "not found"
    except Exception:
        result["deploy_state"] = "unknown"

    if kind == "linux":
        raw = {}
        for key, cmd in (("ip_addr", "ip addr"), ("ip_link", "ip link")):
            try:
                r = subprocess.run(
                    ["docker", "exec", container, "sh", "-c", cmd],
                    capture_output=True, text=True, timeout=15
                )
                raw[key] = (r.stdout or "") + (r.stderr or "")
            except Exception as e:
                raw[key] = f"[error: {e}]"
        result["raw"] = raw
        result["ip_ifs"] = _parse_linux_ip_addr(raw.get("ip_addr", ""))
        result["interfaces"] = _parse_linux_link(raw.get("ip_link", ""))
        return result

    # AOS-CX
    cmds = {
        "vlan": "show vlan",
        "ip_int": "show ip interface brief",
        "if": "show interface brief",
        "lldp": "show lldp neighbor-info",
    }
    raw = _cx_exec_multi(lab_name, node_id, cmds)
    result["raw"] = raw
    result["vlans"] = _parse_cx_vlan(raw.get("vlan", ""))
    result["ip_ifs"] = _parse_cx_ip_brief(raw.get("ip_int", ""))
    result["interfaces"] = _parse_cx_if_brief(raw.get("if", ""))
    result["lldp"] = _parse_cx_lldp(raw.get("lldp", ""))
    return result


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


def _detect_cx_errors(text: str) -> list:
    """Extract AOS-CX CLI error lines from captured output."""
    errs = []
    for ln in text.replace("\r", "").split("\n"):
        s = ln.strip()
        if not s:
            continue
        if (s.startswith("%") or "Invalid input" in s or "Unknown command" in s
                or "Incomplete command" in s or "Ambiguous command" in s):
            errs.append(s)
    return errs


def _push_cx_config(lab_name: str, node_id: str, config_text: str,
                    per_line_wait: float = 0.5, timeout: int = 150) -> dict:
    """Open a single SSH session and push AOS-CX config lines in order.
    Returns {ok, applied_lines, errors, output_tail}. Bounded by timeout so a
    slow/unready node never hangs the whole apply run."""
    ssh_info = get_node_ssh_info(lab_name, node_id)
    if not ssh_info:
        return {"ok": False, "applied_lines": 0,
                "errors": [f"no mgmt IP for {node_id} (node not ready?)"],
                "output_tail": ""}

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    chan = None
    last_err = None
    try:
        # readiness/retry: CX SSH can drop the session right after connect
        for _attempt in range(3):
            try:
                ssh.connect(
                    hostname=ssh_info["host"], port=ssh_info["port"],
                    username=ssh_info["username"], password=ssh_info["password"],
                    timeout=15, banner_timeout=30, auth_timeout=15,
                    look_for_keys=False, allow_agent=False,
                )
                chan = ssh.invoke_shell(term="xterm", width=220, height=100)
                break
            except Exception as e:
                last_err = e
                try:
                    ssh.close()
                except Exception:
                    pass
                time.sleep(3)
        if chan is None:
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"SSH connect failed: {last_err}"], "output_tail": ""}

        time.sleep(1.5)
        if chan.recv_ready():
            chan.recv(65535)
        chan.send("no page\n")
        time.sleep(0.6)
        if chan.recv_ready():
            chan.recv(65535)

        lines = []
        for raw in config_text.replace("\r", "").split("\n"):
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("!"):
                continue
            lines.append(s)

        out = b""
        applied = 0
        start = time.time()
        for s in lines:
            if time.time() - start > timeout:
                break
            chan.send(s + "\n")
            applied += 1
            time.sleep(per_line_wait)
            deadline = time.time() + 4
            while time.time() < deadline:
                if chan.recv_ready():
                    out += chan.recv(65535)
                else:
                    time.sleep(0.1)
                    if not chan.recv_ready():
                        break
        time.sleep(0.6)
        while chan.recv_ready():
            out += chan.recv(65535)
        ssh.close()

        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out.decode("utf-8", errors="replace"))
        errors = _detect_cx_errors(text)
        tail = "\n".join(text.split("\n")[-40:]).strip()
        return {"ok": len(errors) == 0, "applied_lines": applied,
                "errors": errors, "output_tail": tail}
    except Exception as e:
        try:
            ssh.close()
        except Exception:
            pass
        return {"ok": False, "applied_lines": 0,
                "errors": [f"exception: {e}"], "output_tail": ""}


def _apply_linux_node(lab_name: str, node_id: str, script_text: str) -> dict:
    """Apply linux-node setup commands inside the node netns via nsenter.
    Works even for images without an `ip` binary (e.g. freeradius), because the
    GUI container's own iproute2 runs in the target network namespace."""
    container = f"clab-{lab_name}-{node_id}"
    try:
        r = subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", container],
                           capture_output=True, text=True, timeout=10)
        pid = r.stdout.strip()
        if not pid or pid == "0":
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"{container} not running"],
                    "output_tail": (r.stderr or "").strip()}
    except Exception as e:
        return {"ok": False, "applied_lines": 0,
                "errors": [f"inspect failed: {e}"], "output_tail": ""}

    applied = 0
    errors = []
    out_lines = []
    for raw in script_text.replace("\r", "").split("\n"):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        cmd = ["nsenter", "-t", pid, "-n"] + s.split()
        try:
            rr = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            applied += 1
            o = ((rr.stdout or "") + (rr.stderr or "")).strip()
            if o:
                out_lines.append(o)
            # address already present = idempotent re-run; treat as non-fatal
            idempotent = ("File exists" in o or "already" in o.lower())
            if rr.returncode != 0 and not idempotent:
                errors.append(f"{s} -> {o}")
        except Exception as e:
            errors.append(f"{s} -> {e}")
    return {"ok": len(errors) == 0, "applied_lines": applied,
            "errors": errors, "output_tail": "\n".join(out_lines[-20:])}


def apply_default_config(lab_name: str, template_id: str) -> dict:
    """Push per-node default config sets for the given template to running nodes.
    Reads configs/defaults/<template_id>/<node_id>.cfg (AOS-CX) or .sh (linux),
    in the order given by _order.txt (e.g. VSX before MCLAG). Per-node failures
    are recorded and the run continues. Returns per-node {ok, applied_lines,
    errors, output_tail}."""
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
            nodes[node_id] = _push_cx_config(lab_name, node_id, cfg.read_text())
        elif sh.exists():
            nodes[node_id] = _apply_linux_node(lab_name, node_id, sh.read_text())
        else:
            continue
        time.sleep(1.5)

    success = bool(nodes) and all(v.get("ok") for v in nodes.values())
    return {"success": success, "template_id": template_id,
            "lab_name": lab_name, "nodes": nodes}


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
            kind = node_def.get("kind", "vr-aoscx")
            labels = node_def.get("labels", {}) or {}
            # use coordinates from labels if present, otherwise auto-place
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
            # keep image/binds (round-trip for custom nodes like RADIUS; backward compatible)
            img = node_def.get("image")
            if img:
                node_entry["image"] = img
            binds = node_def.get("binds")
            if binds:
                node_entry["binds"] = binds
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
