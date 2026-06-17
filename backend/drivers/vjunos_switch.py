# drivers/vjunos_switch.py
"""Juniper vJunos-switch driver.

Values come from the 02_vjunos_standalone verification:
  - kind        juniper_vjunosswitch
  - image       vrnetlab/juniper_vjunos-switch:25.4R1.12
  - creds       admin / admin@123  (j-super-user)
  - boot        ~2 min to SSH; Docker healthcheck flips to `healthy`
  - data ports  ge-0/0/X (0-based), mgmt fxp0
  - apply       configure -> set ... -> commit (set format works interactively)
"""
import re
import time

from .base import NodeDriver
from . import util


class VjunosSwitchDriver(NodeDriver):
    kind = "juniper_vjunosswitch"
    display_name = "vJunos-switch"
    image = "vrnetlab/juniper_vjunos-switch:25.4R1.12"
    is_vm = True

    default_username = "admin"
    default_password = "admin@123"
    ssh_port = 22
    paging_cmds = ["set cli screen-length 0", "set cli screen-width 0"]

    # boot is ~2 min in practice; allow generous margin (spec suggested ~1200s)
    boot_timeout_sec = 1200
    ram_gib = 5.0                      # vrnetlab vjunos allocates 5120 MB
    boot_hint = "vJunos boots in ~2-3 min (first boot can take longer)"

    # ── MCP export (see 07_api_feasibility: NETCONF 830 / PyEZ) ──
    mcp_api_name = "NETCONF 830 (PyEZ)"
    mcp_config_format = "set"
    config_command = "show configuration | display set"

    def mcp_api_lines(self, host: str) -> list:
        return [
            "- API: NETCONF (port 830) / PyEZ",
            f"  - user: {self.default_username} / pass: {self.default_password}",
            f"  - connect: Device(host='{host}', user='{self.default_username}', "
            f"passwd='{self.default_password}', port=830)",
            "  - config 形式: set (変更は commit 前に diff 確認 / rollback 可)",
        ]

    # ── boot detection (log fallback; health is the primary signal) ──
    def is_booted(self, container_logs: str) -> bool:
        text = container_logs or ""
        return ("Startup complete" in text
                or "Login prompt found" in text
                or "VM started" in text)

    # ── detail panel commands ──────────────────────────────
    def detail_commands(self) -> dict:
        return {
            "version": "show version",
            "if": "show interfaces terse",
            "vlan": "show vlans",
            "lldp": "show lldp neighbors",
            "config": "show configuration | display set",
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
        result["version"] = self._parse_version(raw.get("version", ""))
        terse = self._parse_if_terse(raw.get("if", ""))
        result["interfaces"] = terse["interfaces"]
        result["ip_ifs"] = terse["ip_ifs"]
        result["vlans"] = self._parse_vlans(raw.get("vlan", ""))
        result["lldp"] = self._parse_lldp(raw.get("lldp", ""))
        return result

    def parse_detail(self, key: str, raw_output: str):
        if key == "version":
            return self._parse_version(raw_output)
        if key == "if":
            return self._parse_if_terse(raw_output)["interfaces"]
        if key == "vlan":
            return self._parse_vlans(raw_output)
        if key == "lldp":
            return self._parse_lldp(raw_output)
        return []

    # ── parsers ────────────────────────────────────────────
    @staticmethod
    def _parse_version(text: str) -> str:
        for ln in util.clean_lines(text):
            m = re.search(r"^\s*Junos:\s*(\S+)", ln)
            if m:
                return m.group(1)
        return ""

    # interface prefixes worth showing (data + mgmt + L3); the rest are vJunos
    # internal pseudo-interfaces (cbp/demux/dsc/jsrv/em1/...) and are hidden.
    _USER_IF = ("ge-", "xe-", "et-", "ae", "fxp0", "irb", "lo0", "vlan", "me")

    @classmethod
    def _is_user_iface(cls, name: str) -> bool:
        return name.startswith(cls._USER_IF)

    @classmethod
    def _parse_if_terse(cls, text: str) -> dict:
        """`show interfaces terse`:
        Interface   Admin Link Proto Local            Remote
        ge-0/0/0    up    up
        ge-0/0/0.0  up    up   inet  10.0.0.1/30
        """
        interfaces, ip_ifs = [], []
        for ln in util.clean_lines(text):
            s = ln.strip()
            if not s or s.startswith("Interface"):
                continue
            parts = s.split()
            # require the Admin column to be up/down: filters the echoed command
            # line ("show interfaces terse") and any wrapped junk.
            if len(parts) < 2 or parts[1].lower() not in ("up", "down"):
                continue
            name = parts[0]
            if not cls._is_user_iface(name):
                continue
            admin = parts[1].lower()
            link = parts[2].lower() if len(parts) > 2 and parts[2].lower() in ("up", "down") else ""
            status = link or admin
            ipm = re.search(r"\d+\.\d+\.\d+\.\d+/\d+", s)
            # physical (no unit) -> interface table; logical with inet IP -> ip table
            if "." not in name:
                interfaces.append({"port": name, "status": status,
                                   "detail": " ".join(parts[1:3])})
            if ipm:
                ip_ifs.append({"interface": name, "ip": ipm.group(0), "status": status})
        return {"interfaces": interfaces, "ip_ifs": ip_ifs}

    @staticmethod
    def _parse_vlans(text: str) -> list:
        """Best-effort parse of `show vlans`. Junos wraps interface lists across
        continuation lines; we attach trailing interface-only lines to the last
        VLAN. Raw output is always available in the UI as a fallback."""
        vlans = []
        for ln in util.clean_lines(text):
            s = ln.strip()
            if not s or s.lower().startswith("routing instance") or s.lower().startswith("vlan name"):
                continue
            parts = s.split()
            # a row with a numeric tag column => new VLAN
            tag_idx = next((i for i, p in enumerate(parts) if p.isdigit()), -1)
            if tag_idx >= 1:
                name = parts[tag_idx - 1]
                tag = parts[tag_idx]
                ifaces = " ".join(parts[tag_idx + 1:])
                vlans.append({"id": tag, "name": name, "status": "",
                              "reason": "", "type": "", "interfaces": ifaces})
            elif vlans and re.match(r"^[a-z]+-\d", s):
                # continuation interface line
                vlans[-1]["interfaces"] = (vlans[-1]["interfaces"] + " " + parts[0]).strip()
        return vlans

    @staticmethod
    def _parse_lldp(text: str) -> list:
        nbrs = []
        for ln in util.clean_lines(text):
            s = ln.strip()
            if not s or s.lower().startswith("local interface") or s.startswith("LLDP"):
                continue
            m = re.match(r"^((?:ge|xe|et|fxp|em)-?[\d/.]*\d|fxp0)\s+(.*)$", s)
            if not m:
                continue
            rest = m.group(2).split()
            neighbor = rest[-1] if rest else ""
            nbrs.append({"local_port": m.group(1), "neighbor": neighbor,
                         "detail": m.group(2).strip()})
        return nbrs

    # ── error detection + config push ──────────────────────
    @staticmethod
    def _detect_errors(text: str) -> list:
        errs = []
        for ln in text.replace("\r", "").split("\n"):
            s = ln.strip()
            if not s:
                continue
            low = s.lower()
            if (low.startswith("error:") or "syntax error" in low
                    or "unknown command" in low or "invalid" in low
                    or "missing argument" in low or "is ambiguous" in low):
                errs.append(s)
        return errs

    def apply_config(self, lab_name: str, node_id: str, config_text: str,
                     per_line_wait: float = 0.4, timeout: int = 180) -> dict:
        """configure -> push `set` lines -> commit and-quit. Detects CLI/commit
        errors and reports whether `commit complete` was seen."""
        host = util.get_container_ip(lab_name, node_id)
        if not host:
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"no mgmt IP for {node_id} (node not ready?)"],
                    "output_tail": ""}

        lines = []
        for raw in config_text.replace("\r", "").split("\n"):
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("!"):
                continue
            lines.append(s)

        ssh = None
        try:
            ssh, chan = util.open_shell(host, self.ssh_port,
                                        self.default_username, self.default_password)
            time.sleep(1.5)
            util.drain(chan)
            for pc in self.paging_cmds:
                chan.send(pc + "\n")
                time.sleep(0.4)
                util.drain(chan)

            # enter configuration mode
            chan.send("configure\n")
            time.sleep(1.0)
            util.drain(chan)

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

            # commit and leave configuration mode
            chan.send("commit and-quit\n")
            commit_deadline = time.time() + 60
            while time.time() < commit_deadline:
                if chan.recv_ready():
                    out += chan.recv(65535)
                    if b"commit complete" in out or b"commit failed" in out:
                        time.sleep(0.5)
                        while chan.recv_ready():
                            out += chan.recv(65535)
                        break
                else:
                    time.sleep(0.3)
            ssh.close()

            text = util.strip_ansi(out.decode("utf-8", errors="replace"))
            errors = self._detect_errors(text)
            committed = "commit complete" in text.lower()
            if not committed:
                errors.append("commit not confirmed (no 'commit complete')")
            tail = "\n".join(text.split("\n")[-40:]).strip()
            return {"ok": len(errors) == 0 and committed, "applied_lines": applied,
                    "errors": errors, "output_tail": tail}
        except Exception as e:
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass
            return {"ok": False, "applied_lines": 0,
                    "errors": [f"exception: {e}"], "output_tail": ""}
