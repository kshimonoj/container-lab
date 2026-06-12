# drivers/util.py
"""Vendor-neutral, low-level helpers shared by the node drivers.

Kept free of any device-specific logic so both lab_manager and the individual
drivers can import it without creating import cycles. Everything here talks to
the host (docker / nsenter / paramiko) and knows nothing about AOS-CX vs Junos.
"""
import json
import re
import subprocess
import time

import paramiko


def container_name(lab_name: str, node_id: str) -> str:
    return f"clab-{lab_name}-{node_id}"


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def clean_lines(text: str) -> list:
    """Strip ANSI + split into lines. Keep blank lines (the parser decides)."""
    return [ln.rstrip() for ln in strip_ansi(text).replace("\r", "").split("\n")]


# ── docker / container inspection ──────────────────────────────
def node_kind(lab_name: str, node_id: str) -> str:
    """Resolve a deployed node's containerlab kind from the container label
    `clab-node-kind`. Returns '' if the container is absent/unknown."""
    name = container_name(lab_name, node_id)
    try:
        r = subprocess.run(
            ["docker", "inspect", name,
             "--format", "{{ index .Config.Labels \"clab-node-kind\" }}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def deploy_state(lab_name: str, node_id: str) -> str:
    """Return '<status>|<health>' (health empty if the image has no healthcheck)."""
    name = container_name(lab_name, node_id)
    try:
        st = subprocess.run(
            ["docker", "inspect", name,
             "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"],
            capture_output=True, text=True, timeout=10
        )
        return st.stdout.strip() if st.returncode == 0 else "not found"
    except Exception:
        return "unknown"


def health_status(lab_name: str, node_id: str) -> str:
    """Just the Docker health string ('healthy'/'starting'/'') for boot judging."""
    name = container_name(lab_name, node_id)
    try:
        r = subprocess.run(
            ["docker", "inspect", name, "--format", "{{if .State.Health}}{{.State.Health.Status}}{{end}}"],
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def container_logs(lab_name: str, node_id: str, tail: int = 200) -> str:
    name = container_name(lab_name, node_id)
    try:
        r = subprocess.run(
            ["docker", "logs", "--tail", str(tail), name],
            capture_output=True, text=True, timeout=15
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def get_container_ip(lab_name: str, node_id: str) -> str:
    """Return a node's management IP (prefers the clab mgmt network)."""
    name = container_name(lab_name, node_id)
    result = subprocess.run(
        ["docker", "inspect", name, "--format", "{{json .NetworkSettings.Networks}}"],
        capture_output=True, text=True
    )
    try:
        networks = json.loads(result.stdout)
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress", "")
            if ip and "clab" in net_name.lower():
                return ip
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress", "")
            if ip:
                return ip
    except Exception:
        pass
    return ""


# ── linux node exec helpers (docker exec / nsenter) ────────────
def docker_exec(lab_name: str, node_id: str, cmd: str, timeout: int = 15) -> str:
    name = container_name(lab_name, node_id)
    try:
        r = subprocess.run(
            ["docker", "exec", name, "sh", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"[error: {e}]"


def container_pid(lab_name: str, node_id: str) -> str:
    name = container_name(lab_name, node_id)
    try:
        r = subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", name],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""


# ── SSH shell helpers (used by VM-based network OS drivers) ────
def open_shell(host: str, port: int, username: str, password: str,
               retries: int = 3, width: int = 220, height: int = 100):
    """Open an interactive SSH shell, retrying because vrnetlab VMs sometimes
    drop the session right after connect. Returns (ssh, channel). Raises on
    final failure."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last_err = None
    for _attempt in range(retries):
        try:
            ssh.connect(
                hostname=host, port=port, username=username, password=password,
                timeout=15, banner_timeout=30, auth_timeout=15,
                look_for_keys=False, allow_agent=False,
            )
            chan = ssh.invoke_shell(term="xterm", width=width, height=height)
            return ssh, chan
        except Exception as e:
            last_err = e
            try:
                ssh.close()
            except Exception:
                pass
            time.sleep(2)
    raise last_err or RuntimeError("SSH connect failed")


def drain(chan):
    """Read whatever is currently available on the channel (non-blocking)."""
    if chan.recv_ready():
        return chan.recv(65535)
    return b""


def run_show_commands(host: str, port: int, username: str, password: str,
                      paging_cmds: list, commands: dict, timeout: int = 12) -> dict:
    """Open one SSH shell, disable paging, run each command and capture output.
    Returns {key: raw_output}. On failure each value is an error string."""
    out = {}
    ssh = None
    try:
        ssh, chan = open_shell(host, port, username, password)
        time.sleep(1.5)
        drain(chan)
        for pc in paging_cmds:
            chan.send(pc + "\n")
            time.sleep(0.6)
            drain(chan)
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
            if ssh:
                ssh.close()
        except Exception:
            pass
        for key in commands:
            out.setdefault(key, f"[SSH error: {e}]")
    return out
