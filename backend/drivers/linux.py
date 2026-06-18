# drivers/linux.py
"""Linux/host node driver (PCs, FreeRADIUS, etc.).

These nodes are plain containers, not VMs: their terminal is a `docker exec`
shell, live info comes from busybox `ip`, and config is applied as a shell
script run inside the node's network namespace via nsenter (works even for
images without an `ip` binary)."""
import re
import subprocess

from .base import NodeDriver
from . import util


class LinuxDriver(NodeDriver):
    kind = "linux"
    display_name = "PC (linux)"
    image = "alpine:latest"
    is_vm = False                  # terminal uses docker exec, not SSH

    boot_timeout_sec = 60
    ram_gib = 0.25
    boot_hint = "container starts instantly"

    def is_booted(self, container_logs: str) -> bool:
        return True  # plain containers are up as soon as they run

    # ── MCP export ─────────────────────────────────────────
    mcp_api_name = "docker exec (読み取り可)"
    # plain containers have no running-config; we export their live net state
    mcp_config_label = "現在のネットワーク状態"

    def mcp_api_lines(self, host: str) -> list:
        return [
            "- API: なし (plain container)",
            f"  - shell: docker exec -it clab-<lab>-<node> /bin/sh  (mgmt_ip {host})",
            "  - 操作: 読み取りは docker exec で ip/ping 等を実行可能 "
            "(MCP の run_show 相当は未対応。現状は GUI の exec-terminal もしくは "
            "手動 docker exec を使用)",
        ]

    def get_running_config(self, lab_name: str, node_id: str) -> dict:
        """Plain containers have no running-config; instead capture the node's
        current live network state (read-only) via docker exec so the MCP
        export reflects each PC's real IPs and routes. Failures (e.g. container
        not running) are non-fatal: returns ok=False and the caller notes it."""
        # (display header, shell command). `-br` is iproute2-only; BusyBox/alpine
        # prints a usage blurb instead, so fall back to plain `ip addr` there.
        cmds = [
            ("ip -br addr", "ip -br addr 2>/dev/null || ip addr"),
            ("ip route", "ip route"),
        ]
        sections = []
        any_ok = False
        for header, cmd in cmds:
            out = util.docker_exec(lab_name, node_id, cmd).rstrip()
            if out and not self._looks_like_exec_error(out):
                any_ok = True
            sections.append(f"# {header}\n{out}" if out else f"# {header}\n(出力なし)")
        text = "\n".join(sections)
        if not any_ok:
            return {"ok": False, "format": "", "text": "",
                    "error": "docker exec で状態取得できませんでした "
                             "(コンテナ未起動の可能性)"}
        return {"ok": True, "format": "", "text": text, "error": ""}

    @staticmethod
    def _looks_like_exec_error(out: str) -> bool:
        markers = ("[error:", "No such container", "is not running",
                   "Error response from daemon", "multi-call binary")
        return any(m in out for m in markers)

    # ── live info via docker exec (busybox ip) ─────────────
    def live_info(self, lab_name: str, node_id: str) -> dict:
        result = {
            "lab_name": lab_name, "node_id": node_id, "kind": self.kind,
            "display_name": self.display_name,
            "deploy_state": util.deploy_state(lab_name, node_id),
            "vlans": [], "ip_ifs": [], "interfaces": [], "lldp": [],
            "version": "", "raw": {},
        }
        raw = {
            "ip_addr": util.docker_exec(lab_name, node_id, "ip addr"),
            "ip_link": util.docker_exec(lab_name, node_id, "ip link"),
        }
        result["raw"] = raw
        result["ip_ifs"] = self._parse_ip_addr(raw.get("ip_addr", ""))
        result["interfaces"] = self._parse_link(raw.get("ip_link", ""))
        return result

    @staticmethod
    def _parse_ip_addr(text: str) -> list:
        ifs = []
        cur, cur_state = None, ""
        for ln in util.clean_lines(text):
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

    @staticmethod
    def _parse_link(text: str) -> list:
        ifs = []
        for ln in util.clean_lines(text):
            m = re.match(r"^\d+:\s+([^:@]+)[@:].*?\bstate\s+(\S+)", ln)
            if m:
                ifs.append({"port": m.group(1).strip(),
                            "status": m.group(2).lower(), "detail": ""})
        return ifs

    # ── config via nsenter into the node netns ─────────────
    def apply_config(self, lab_name: str, node_id: str, config_text: str) -> dict:
        pid = util.container_pid(lab_name, node_id)
        if not pid or pid == "0":
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"{util.container_name(lab_name, node_id)} not running"],
                    "output_tail": ""}

        applied = 0
        errors = []
        out_lines = []
        for raw in config_text.replace("\r", "").split("\n"):
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
                idempotent = ("File exists" in o or "already" in o.lower())
                if rr.returncode != 0 and not idempotent:
                    errors.append(f"{s} -> {o}")
            except Exception as e:
                errors.append(f"{s} -> {e}")
        return {"ok": len(errors) == 0, "applied_lines": applied,
                "errors": errors, "output_tail": "\n".join(out_lines[-20:])}
