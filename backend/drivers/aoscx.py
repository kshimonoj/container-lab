# drivers/aoscx.py
"""Aruba AOS-CX driver. Holds all CX-specific behaviour that used to live
inline in lab_manager: credentials, `no page` paging, the show-command set,
the output parsers and the conf-t style config push."""
import re
import time

from .base import NodeDriver
from . import util


class AosCxDriver(NodeDriver):
    kind = "vr-aoscx"                      # containerlab kind used by existing templates
    display_name = "AOS-CX"
    image = "vrnetlab/vr-aoscx:10.16.1006"
    is_vm = True

    default_username = "admin"
    default_password = "admin"
    ssh_port = 22
    paging_cmds = ["no page"]

    boot_timeout_sec = 300                 # ~1 min in practice; margin for safety
    ram_gib = 8.0                          # vrnetlab aoscx allocates 8192 MB
    boot_hint = "AOS-CX boots in ~1 min"

    # ── MCP export (see 07_api_feasibility: REST v10.16 Cookie login) ──
    mcp_api_name = "REST API v10.16 (https)"
    mcp_config_format = "CLI"
    config_command = "show running-config"

    def mcp_api_lines(self, host: str) -> list:
        base = f"https://{host}/rest/v10.16"
        return [
            "- API: REST API v10.16",
            f"  - base_url: {base}",
            f"  - login: POST /login?username={self.default_username}"
            f"&password={self.default_password} (Cookie 認証)",
            f"  - fallback: SSH {self.default_username}@{host}:{self.ssh_port} "
            f"(`show running-config`)",
        ]

    # ── boot detection (log fallback; health is the primary signal) ──
    def is_booted(self, container_logs: str) -> bool:
        text = container_logs or ""
        return ("Startup complete" in text
                or "completed write memory" in text
                or "Login incorrect" in text  # login prompt reachable
                or "vr-aoscx" in text and "QEMU" in text)

    # ── detail panel commands ──────────────────────────────
    def detail_commands(self) -> dict:
        return {
            "vlan": "show vlan",
            "ip_int": "show ip interface brief",
            "if": "show interface brief",
            "lldp": "show lldp neighbor-info",
            "version": "show version",
        }

    def live_info(self, lab_name: str, node_id: str) -> dict:
        result = {
            "lab_name": lab_name, "node_id": node_id, "kind": self.kind,
            "display_name": self.display_name,
            "deploy_state": util.deploy_state(lab_name, node_id),
            "vlans": [], "ip_ifs": [], "interfaces": [], "lldp": [],
            "version": "", "raw": {},
        }
        host = util.get_container_ip(lab_name, node_id)
        if not host:
            result["raw"] = {"error": f"[no mgmt IP for {node_id}]"}
            return result
        raw = util.run_show_commands(
            host, self.ssh_port, self.default_username, self.default_password,
            self.paging_cmds, self.detail_commands(),
        )
        result["raw"] = raw
        result["vlans"] = self._parse_vlan(raw.get("vlan", ""))
        result["ip_ifs"] = self._parse_ip_brief(raw.get("ip_int", ""))
        result["interfaces"] = self._parse_if_brief(raw.get("if", ""))
        result["lldp"] = self._parse_lldp(raw.get("lldp", ""))
        result["version"] = self._parse_version(raw.get("version", ""))
        return result

    def parse_detail(self, key: str, raw_output: str):
        return {
            "vlan": self._parse_vlan,
            "ip_int": self._parse_ip_brief,
            "if": self._parse_if_brief,
            "lldp": self._parse_lldp,
            "version": self._parse_version,
        }.get(key, lambda _t: [])(raw_output)

    # ── parsers (moved verbatim from lab_manager) ──────────
    @staticmethod
    def _parse_vlan(text: str) -> list:
        vlans = []
        for ln in util.clean_lines(text):
            m = re.match(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$", ln)
            if m:
                vlans.append({
                    "id": m.group(1), "name": m.group(2), "status": m.group(3),
                    "reason": m.group(4), "type": m.group(5),
                    "interfaces": m.group(6).strip(),
                })
        return vlans

    @staticmethod
    def _parse_ip_brief(text: str) -> list:
        ifs = []
        for ln in util.clean_lines(text):
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

    @staticmethod
    def _parse_if_brief(text: str) -> list:
        ifs = []
        for ln in util.clean_lines(text):
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

    @staticmethod
    def _parse_lldp(text: str) -> list:
        nbrs = []
        for ln in util.clean_lines(text):
            m = re.match(r"^\s*(\d+/\d+/\d+)\s+(.*)$", ln)
            if not m:
                continue
            rest = m.group(2).split()
            neighbor = rest[-1] if rest else ""
            nbrs.append({"local_port": m.group(1), "neighbor": neighbor,
                         "detail": m.group(2).strip()})
        return nbrs

    @staticmethod
    def _parse_version(text: str) -> str:
        for ln in util.clean_lines(text):
            m = re.search(r"Version\s*:?\s*(\S+)", ln, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    # ── error detection + config push ──────────────────────
    @staticmethod
    def _detect_errors(text: str) -> list:
        errs = []
        for ln in text.replace("\r", "").split("\n"):
            s = ln.strip()
            if not s:
                continue
            if (s.startswith("%") or "Invalid input" in s or "Unknown command" in s
                    or "Incomplete command" in s or "Ambiguous command" in s):
                errs.append(s)
        return errs

    def apply_config(self, lab_name: str, node_id: str, config_text: str,
                     per_line_wait: float = 0.5, timeout: int = 150) -> dict:
        host = util.get_container_ip(lab_name, node_id)
        if not host:
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"no mgmt IP for {node_id} (node not ready?)"],
                    "output_tail": ""}

        ssh = None
        try:
            ssh, chan = util.open_shell(host, self.ssh_port,
                                        self.default_username, self.default_password)
            time.sleep(1.5)
            util.drain(chan)
            for pc in self.paging_cmds:
                chan.send(pc + "\n")
                time.sleep(0.6)
                util.drain(chan)

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

            text = util.strip_ansi(out.decode("utf-8", errors="replace"))
            errors = self._detect_errors(text)
            tail = "\n".join(text.split("\n")[-40:]).strip()
            return {"ok": len(errors) == 0, "applied_lines": applied,
                    "errors": errors, "output_tail": tail}
        except Exception as e:
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"exception: {e}"], "output_tail": ""}
