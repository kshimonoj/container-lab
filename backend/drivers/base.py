# drivers/base.py
"""NodeDriver base class.

A driver encapsulates everything vendor/kind-specific about a node:
  - how it maps to a containerlab node definition (kind + default image)
  - SSH credentials and how to disable CLI paging
  - boot-completion detection
  - which "show" commands the detail panel runs and how to parse them
  - how to push configuration

lab_manager stays vendor-neutral and routes every per-node operation through
the driver resolved from the node's containerlab kind.
"""
from . import util


class NodeDriver:
    # ── identity / clab mapping ────────────────────────────
    kind: str = ""              # containerlab kind == DRIVER_REGISTRY key
    display_name: str = ""
    image: str = ""             # default image when the node carries none
    is_vm: bool = True          # True => SSH terminal; False => docker exec terminal

    # ── access ─────────────────────────────────────────────
    default_username: str = ""
    default_password: str = ""
    ssh_port: int = 22
    paging_cmds: list = []      # commands to disable CLI paging at session start

    # ── capacity / boot ────────────────────────────────────
    boot_timeout_sec: int = 300
    ram_gib: float = 1.0        # planning estimate (QEMU allocation per node)
    boot_hint: str = ""         # short UI text shown while a node is booting

    # ── containerlab node definition ───────────────────────
    def build_node_def(self, node: dict, labels: dict) -> dict:
        """Return the containerlab node mapping for this node."""
        node_def = {
            "kind": self.kind,
            "image": node.get("image") or self.image,
            "labels": labels,
        }
        binds = node.get("binds")
        if binds:
            node_def["binds"] = list(binds)
        # Optional containerlab node-level startup-delay (seconds). Used to stagger
        # boot of multiple slow VMs (e.g. several AOS-CX) so they don't thrash and
        # flip to unhealthy on a busy host.
        delay = node.get("startup_delay")
        if delay:
            node_def["startup-delay"] = int(delay)
        return node_def

    # ── access ─────────────────────────────────────────────
    def ssh_info(self, host: str) -> dict:
        return {"host": host, "port": self.ssh_port,
                "username": self.default_username, "password": self.default_password}

    # ── boot detection ─────────────────────────────────────
    def is_booted(self, container_logs: str) -> bool:
        """Log-pattern fallback for boot completion. The primary signal is the
        Docker healthcheck (see lab_manager status); override per vendor."""
        return False

    # ── detail panel: commands + parsing ───────────────────
    def detail_commands(self) -> dict:
        """{key: cli_command} run over a single SSH session for the detail panel."""
        return {}

    def parse_detail(self, key: str, raw_output: str):
        """Parse one command's raw output into structured rows. Override per vendor."""
        return []

    # ── high-level live info (detail panel "Refresh") ──────
    def live_info(self, lab_name: str, node_id: str) -> dict:
        """Default implementation for VM/network-OS nodes: resolve the mgmt IP,
        run detail_commands over one SSH session, and parse each output.
        Returns a result dict consumed by the frontend renderLive()."""
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

        cmds = self.detail_commands()
        raw = util.run_show_commands(
            host, self.ssh_port, self.default_username, self.default_password,
            self.paging_cmds, cmds,
        )
        result["raw"] = raw
        for key in cmds:
            parsed = self.parse_detail(key, raw.get(key, ""))
            if key in result and isinstance(result.get(key), list):
                result[key] = parsed
            elif key == "version":
                result["version"] = parsed if isinstance(parsed, str) else result["version"]
        return result

    # ── config push ────────────────────────────────────────
    def apply_config(self, lab_name: str, node_id: str, config_text: str) -> dict:
        """Push config_text to the node. Returns
        {ok, applied_lines, errors, output_tail}. Override per vendor."""
        raise NotImplementedError

    # ── MCP export support ─────────────────────────────────
    # Short API/auth descriptor + config dialect used by the "Export for MCP"
    # report (lab_manager.export_mcp_markdown). config_command is the single
    # show command whose output is the node's current running config.
    mcp_api_name: str = ""          # e.g. "REST API v10.16 (https)"
    mcp_config_format: str = ""     # config dialect label, e.g. "CLI" / "set"
    config_command: str = ""        # show command returning the running config

    def mcp_api_lines(self, host: str) -> list:
        """Markdown bullet lines describing how MCP reaches this node's API.
        Default: SSH/CLI access. Override per vendor for REST/NETCONF detail."""
        return [
            f"- API: {self.mcp_api_name or 'SSH/CLI'}",
            f"  - ssh: {self.default_username}@{host}:{self.ssh_port} / "
            f"pass: {self.default_password}",
        ]

    def get_running_config(self, lab_name: str, node_id: str) -> dict:
        """Best-effort retrieval of the node's current running config for export.
        Returns {ok, format, text, error}. Failures are non-fatal — the caller
        keeps the export going and just notes the error.

        Default implementation: for VM/network-OS nodes with a config_command,
        open one SSH session and capture that command's output (proven path,
        reused from the detail panel). Other nodes report 'not supported'."""
        fmt = self.mcp_config_format
        if not self.is_vm or not self.config_command:
            return {"ok": False, "format": fmt, "text": "",
                    "error": "no running-config retrieval for this kind"}
        host = util.get_container_ip(lab_name, node_id)
        if not host:
            return {"ok": False, "format": fmt, "text": "",
                    "error": f"no mgmt IP for {node_id}"}
        raw = util.run_show_commands(
            host, self.ssh_port, self.default_username, self.default_password,
            self.paging_cmds, {"cfg": self.config_command}, timeout=25,
        )
        text = util.strip_ansi(raw.get("cfg", ""))
        if text.lstrip().startswith("[SSH error"):
            return {"ok": False, "format": fmt, "text": "", "error": text.strip()}
        return {"ok": True, "format": fmt,
                "text": util.clean_config_output(text, self.config_command),
                "error": ""}
