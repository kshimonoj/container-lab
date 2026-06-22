# mcp_server/cx_client.py
"""AOS-CX client for the MCP server.

Routing of the API surface (see 07_api_feasibility_result.md):
  - facts / arbitrary reads  -> REST API (Cookie login, verify=False)
  - running-config / show     -> SSH CLI (REST has no generic CLI passthrough,
                                 and CLI text is far more useful to Claude than
                                 the declarative JSON config)
  - config change             -> SSH conf-t (CLI text is what the MCP tool
                                 receives; conf-t errors are detected & returned)

The low-level SSH plumbing is reused verbatim from the GUI backend
(backend/drivers/util.py) so behaviour matches the proven driver. Nothing in
the backend is modified.

Every public function returns a structured dict. Failures are never raised to
the caller: they come back as {"ok": False, "error_kind": ..., "error": ...}
so the MCP layer can explain *why* something failed (connect / auth / api).
"""
import os
import sys
import time

import paramiko
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── reuse the backend's vendor-neutral SSH helpers (no backend changes) ──
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
from drivers import util  # noqa: E402  (open_shell / run_show_commands / strip_ansi)

DEFAULT_USER = "admin"
DEFAULT_PASS = "admin"
SSH_PORT = 22
PAGING_CMDS = ["no page"]

# We do NOT hardcode a single REST version. At login time we probe these in
# order (newest first) and cache the first that authenticates per host. The
# device's `/rest/` index returns nginx 404 (see 07), so probing the login
# endpoint is the reliable discovery method.
_CANDIDATE_VERSIONS = [
    "v10.16", "v10.15", "v10.14", "v10.13",
    "v10.12", "v10.11", "v10.10", "v10.09", "v10.08", "v1",
]
_version_cache = {}  # ip -> rest version string that worked


def _err(kind, msg, **extra):
    out = {"ok": False, "error_kind": kind, "error": str(msg)}
    out.update(extra)
    return out


# ── SSH exec channel (read path: show / running-config) ────────────
# The interactive-shell path (util.run_show_commands / invoke_shell) relies on
# prompt/idle heuristics that hang on AOS-CX (long EULA banner shifts the buffer
# so the output terminator is never detected -> ~240s MCP timeout). The exec
# channel — `ssh host 'command'`, send one command and read stdout to EOF — is
# what the proven 0.5s direct-SSH test uses, so the read tools use it here.
# REST (get_node_facts) and the conf-t path (apply_config) are untouched.
_BANNER_MARKERS = (
    "Consistent with FAR",
    "standard commercial license",
    "RESTRICTED RIGHTS",
)


def _strip_login_banner(text: str) -> str:
    """AOS-CX prints an EULA/MOTD banner before command output on some images.
    Drop everything up to and including the last known banner-terminator line."""
    lines = text.splitlines()
    cut = 0
    for i, ln in enumerate(lines):
        if any(m in ln for m in _BANNER_MARKERS):
            cut = i + 1
    return "\n".join(lines[cut:]).strip("\n")


def _ssh_exec(ip, command, username=DEFAULT_USER, password=DEFAULT_PASS,
              connect_timeout=10, exec_timeout=25):
    """Run one command over a fresh SSH exec channel and return its stdout text.

    One command = one SSH session: no prompt/terminator detection, so it cannot
    hang the way the interactive shell does. On any failure raises so the caller
    can classify it — but never blocks past exec_timeout (no 4-minute hang)."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # host key changes on redeploy
    try:
        client.connect(
            hostname=ip, port=SSH_PORT,
            username=username, password=password,
            look_for_keys=False, allow_agent=False,   # force password auth, no key-probe hang
            timeout=connect_timeout, banner_timeout=15, auth_timeout=15,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=exec_timeout)
        stdout.channel.settimeout(exec_timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        text = out if out.strip() else err
        return _strip_login_banner(text)
    finally:
        try:
            client.close()
        except Exception:
            pass


def _classify_ssh_error(exc) -> str:
    """Map a paramiko/socket exception to the MCP error_kind vocabulary."""
    if isinstance(exc, paramiko.AuthenticationException):
        return "auth"
    return "connect"


# ── REST session ───────────────────────────────────────────────
class CxSession:
    """A logged-in AOS-CX REST session. Use as a context manager so logout
    always runs:  `with CxSession(ip) as s: s.get('/system')`."""

    def __init__(self, ip, username=DEFAULT_USER, password=DEFAULT_PASS, timeout=15):
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.version = None
        self.s = requests.Session()
        self.s.verify = False

    def base(self, version=None):
        return f"https://{self.ip}/rest/{version or self.version}"

    def login(self):
        """Probe candidate REST versions until one authenticates. Raises
        CxError-like via _LoginError carrying an error_kind for the caller."""
        # try the cached version first, then the rest
        order = []
        if self.ip in _version_cache:
            order.append(_version_cache[self.ip])
        order += [v for v in _CANDIDATE_VERSIONS if v not in order]

        last_status = None
        for ver in order:
            url = f"https://{self.ip}/rest/{ver}/login"
            try:
                r = self.s.post(
                    url, params={"username": self.username, "password": self.password},
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as e:
                # connection-level failure: no point trying other versions
                raise _LoginError("connect", f"cannot reach {self.ip}: {e}")
            if r.status_code == 200:
                self.version = ver
                _version_cache[self.ip] = ver
                return ver
            if r.status_code in (401, 403):
                # right endpoint, wrong credentials
                raise _LoginError(
                    "auth",
                    f"login rejected (HTTP {r.status_code}) for "
                    f"{self.username}@{self.ip}",
                )
            last_status = r.status_code  # usually 404: wrong version, try next
        raise _LoginError(
            "api",
            f"no usable REST version on {self.ip} "
            f"(last HTTP {last_status}; tried {', '.join(order)})",
        )

    def get(self, path, **params):
        r = self.s.get(self.base() + path, params=params or None, timeout=self.timeout)
        return r

    def logout(self):
        try:
            self.s.post(self.base() + "/logout", timeout=self.timeout)
        except requests.exceptions.RequestException:
            pass

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, *exc):
        self.logout()
        self.s.close()
        return False


class _LoginError(Exception):
    def __init__(self, kind, msg):
        self.kind = kind
        super().__init__(msg)


# ── public API ─────────────────────────────────────────────────
def get_system(ip, username=DEFAULT_USER, password=DEFAULT_PASS):
    """hostname / platform / software version via REST GET /system."""
    try:
        with CxSession(ip, username, password) as s:
            r = s.get("/system",
                      attributes="hostname,platform_name,software_version")
            if r.status_code != 200:
                return _err("api", f"GET /system -> HTTP {r.status_code}",
                            status=r.status_code)
            d = r.json()
            return {
                "ok": True,
                "kind": "vr-aoscx",
                "hostname": d.get("hostname", ""),
                "model": d.get("platform_name", ""),
                "version": d.get("software_version", ""),
                "rest_version": s.version,
                "mgmt_ip": ip,
            }
    except _LoginError as e:
        return _err(e.kind, e)
    except Exception as e:
        return _err("api", e)


def run_get(ip, path, username=DEFAULT_USER, password=DEFAULT_PASS):
    """Arbitrary REST GET (read-only). `path` is appended to the versioned base,
    e.g. '/system/vlans?depth=2'."""
    if not path.startswith("/"):
        path = "/" + path
    try:
        with CxSession(ip, username, password) as s:
            r = s.s.get(s.base() + path, timeout=s.timeout)
            body = None
            try:
                body = r.json()
            except ValueError:
                body = r.text
            return {"ok": r.status_code < 400, "status": r.status_code,
                    "path": path, "rest_version": s.version, "data": body}
    except _LoginError as e:
        return _err(e.kind, e)
    except Exception as e:
        return _err("api", e)


def get_running_config(ip, username=DEFAULT_USER, password=DEFAULT_PASS):
    """Full running-config as CLI text (SSH `show running-config`).

    Uses the exec channel (one command per session). exec mode is non-interactive
    so AOS-CX does not page the output — the full config is returned in one read.
    """
    cmd = "show running-config"
    try:
        text = _ssh_exec(ip, cmd, username, password)
    except Exception as e:
        return _err(_classify_ssh_error(e), f"{type(e).__name__}: {e}")
    return {"ok": True, "format": "cli", "command": cmd,
            "text": util.clean_config_output(text, cmd)}


def run_show(ip, command, username=DEFAULT_USER, password=DEFAULT_PASS):
    """Run an arbitrary `show ...` command over SSH and return its output."""
    try:
        text = _ssh_exec(ip, command, username, password)
    except Exception as e:
        return _err(_classify_ssh_error(e), f"{type(e).__name__}: {e}",
                    command=command)
    return {"ok": True, "command": command,
            "output": util.clean_config_output(text, command)}


# Mode-enter/leave commands we manage ourselves; drop them from user input so
# `configure terminal` isn't sent twice (which errors at the config prompt).
_MODE_CMDS = {"configure", "configure terminal", "conf t", "config",
              "config terminal", "end", "exit", "quit"}


def _normalise_config(config_text):
    lines = []
    for raw in config_text.replace("\r", "").split("\n"):
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue
        if s.lower() in _MODE_CMDS:
            continue
        lines.append(s)
    return lines


def _detect_errors(text):
    errs = []
    for ln in text.replace("\r", "").split("\n"):
        s = ln.strip()
        if not s:
            continue
        if (s.startswith("%") or "Invalid input" in s or "Unknown command" in s
                or "Incomplete command" in s or "Ambiguous command" in s):
            errs.append(s)
    return errs


def apply_config(ip, config_text, dry_run=True,
                 username=DEFAULT_USER, password=DEFAULT_PASS,
                 per_line_wait=0.5, timeout=150):
    """Push AOS-CX CLI config (conf-t style).

    AOS-CX has no native dry-run/diff. To stay safe (per the task spec), when
    dry_run=True we DO NOT touch the device: we return the normalised lines that
    *would* be sent plus a reminder to fetch the current config first. The
    device is only modified when dry_run=False.
    """
    lines = _normalise_config(config_text)
    if not lines:
        return _err("config", "no config lines to apply (input was empty)")

    if dry_run:
        return {
            "ok": True, "dry_run": True, "applied": False,
            "kind": "vr-aoscx",
            "planned_lines": lines,
            "summary": (f"DRY RUN: {len(lines)} line(s) would be sent to "
                        f"{ip} via conf-t. AOS-CX has no native diff; call "
                        f"get_node_config first to capture the current state, "
                        f"then re-run with dry_run=false to apply."),
            "note": "No change was made to the device.",
        }

    ssh = None
    try:
        ssh, chan = util.open_shell(ip, SSH_PORT, username, password)
        time.sleep(1.5)
        util.drain(chan)
        for pc in PAGING_CMDS:
            chan.send(pc + "\n")
            time.sleep(0.6)
            util.drain(chan)

        # enter config mode (AOS-CX requires `configure terminal` before
        # `vlan`/`interface`/... — the user's `config` text need not include it)
        chan.send("configure terminal\n")
        time.sleep(0.8)
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
        chan.send("end\n")  # leave config mode
        time.sleep(0.6)
        while chan.recv_ready():
            out += chan.recv(65535)
        ssh.close()

        text = util.strip_ansi(out.decode("utf-8", errors="replace"))
        errors = _detect_errors(text)
        tail = "\n".join(text.split("\n")[-40:]).strip()
        return {
            "ok": len(errors) == 0, "dry_run": False, "applied": True,
            "kind": "vr-aoscx", "applied_lines": applied,
            "planned_lines": lines, "errors": errors, "output_tail": tail,
            "summary": (f"Applied {applied} line(s) to {ip}; "
                        f"{len(errors)} CLI error(s)."),
        }
    except Exception as e:
        try:
            if ssh:
                ssh.close()
        except Exception:
            pass
        kind = "auth" if "auth" in str(e).lower() else "connect"
        return _err(kind, f"conf-t failed: {e}", applied=False)
