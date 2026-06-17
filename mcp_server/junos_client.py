# mcp_server/junos_client.py
"""vJunos-switch client for the MCP server (NETCONF 830 / PyEZ).

See 07_api_feasibility_result.md: PyEZ handles read and write. Config changes
go load -> diff -> (commit | discard); rollback is `rollback n` -> commit.

Safety: apply_config defaults to dry_run=True. In dry-run we load the candidate,
capture the diff, then roll the candidate back WITHOUT committing, so the device
is never changed. Only dry_run=False commits.

Every public function returns a structured dict; failures come back as
{"ok": False, "error_kind": connect|auth|config|commit|rpc, "error": ...}.
"""
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import (
    ConnectError, ConnectAuthError, ConnectRefusedError, ConnectTimeoutError,
    ConfigLoadError, CommitError, LockError, RpcError, UnlockError,
)

DEFAULT_USER = "admin"
DEFAULT_PASS = "admin@123"
NETCONF_PORT = 830
CONNECT_TIMEOUT = 30


def _err(kind, msg, **extra):
    out = {"ok": False, "error_kind": kind, "error": str(msg)}
    out.update(extra)
    return out


def _open(ip, username, password):
    """Open a PyEZ Device or raise a (kind, message) via _ConnError."""
    dev = Device(host=ip, user=username, passwd=password,
                 port=NETCONF_PORT, conn_open_timeout=CONNECT_TIMEOUT,
                 gather_facts=False)
    try:
        dev.open()
    except ConnectAuthError as e:
        raise _ConnError("auth", f"NETCONF auth failed for {username}@{ip}: {e}")
    except (ConnectRefusedError, ConnectTimeoutError, ConnectError) as e:
        raise _ConnError("connect", f"cannot reach {ip}:{NETCONF_PORT}: {e}")
    return dev


class _ConnError(Exception):
    def __init__(self, kind, msg):
        self.kind = kind
        super().__init__(msg)


# ── reads ───────────────────────────────────────────────────────
def get_facts(ip, username=DEFAULT_USER, password=DEFAULT_PASS):
    try:
        dev = _open(ip, username, password)
    except _ConnError as e:
        return _err(e.kind, e)
    try:
        dev.facts_refresh()
        f = dev.facts
        return {
            "ok": True, "kind": "juniper_vjunosswitch",
            "hostname": f.get("hostname", ""),
            "model": f.get("model", ""),
            "version": f.get("version", ""),
            "serial": f.get("serialnumber", ""),
            "mgmt_ip": ip,
        }
    except Exception as e:
        return _err("rpc", e)
    finally:
        dev.close()


def get_config(ip, fmt="set", username=DEFAULT_USER, password=DEFAULT_PASS):
    """Current configuration. fmt in {'set','text','xml'} (default 'set')."""
    fmt = (fmt or "set").lower()
    if fmt not in ("set", "text", "xml"):
        return _err("rpc", f"unsupported format {fmt!r} (use set/text/xml)")
    try:
        dev = _open(ip, username, password)
    except _ConnError as e:
        return _err(e.kind, e)
    try:
        rpc = dev.rpc.get_config(options={"format": fmt})
        text = rpc.text if hasattr(rpc, "text") and fmt != "xml" else None
        if text is None:
            from lxml import etree
            text = etree.tostring(rpc, encoding="unicode", pretty_print=True)
        return {"ok": True, "format": fmt, "text": text.strip()}
    except RpcError as e:
        return _err("rpc", e)
    except Exception as e:
        return _err("rpc", e)
    finally:
        dev.close()


def run_show(ip, command, username=DEFAULT_USER, password=DEFAULT_PASS):
    """Run an arbitrary operational command (e.g. 'show interfaces terse')."""
    try:
        dev = _open(ip, username, password)
    except _ConnError as e:
        return _err(e.kind, e, command=command)
    try:
        out = dev.cli(command, format="text", warning=False)
        return {"ok": True, "command": command, "output": (out or "").strip()}
    except RpcError as e:
        return _err("rpc", e, command=command)
    except Exception as e:
        return _err("rpc", e, command=command)
    finally:
        dev.close()


# ── writes ──────────────────────────────────────────────────────
def apply_config(ip, config_set, dry_run=True,
                 username=DEFAULT_USER, password=DEFAULT_PASS,
                 comment="cx-clab-mcp"):
    """Load `set`-format config, return the diff. dry_run=True discards the
    candidate (no commit); dry_run=False commits it."""
    if not (config_set or "").strip():
        return _err("config", "no config to apply (input was empty)")
    try:
        dev = _open(ip, username, password)
    except _ConnError as e:
        return _err(e.kind, e)
    try:
        with Config(dev, mode="exclusive") as cu:
            try:
                cu.load(config_set, format="set")
            except ConfigLoadError as e:
                cu.rollback()
                return _err("config", f"load failed: {e}", dry_run=dry_run,
                            applied=False)
            diff = cu.diff()
            if diff is None:
                cu.rollback()
                return {"ok": True, "dry_run": dry_run, "applied": False,
                        "kind": "juniper_vjunosswitch", "diff": "",
                        "summary": "No change: candidate matches running config."}
            if dry_run:
                cu.rollback()  # discard candidate -> device untouched
                return {"ok": True, "dry_run": True, "applied": False,
                        "kind": "juniper_vjunosswitch", "diff": diff,
                        "summary": ("DRY RUN: the diff above would be committed. "
                                    "Re-run with dry_run=false to apply. "
                                    "Nothing was committed.")}
            # real commit
            try:
                cu.commit(comment=comment, timeout=120)
            except CommitError as e:
                cu.rollback()
                return _err("commit", f"commit failed (rolled back): {e}",
                            dry_run=False, applied=False, diff=diff)
            return {"ok": True, "dry_run": False, "applied": True,
                    "kind": "juniper_vjunosswitch", "diff": diff,
                    "summary": "Committed. Use rollback to undo (rollback 1)."}
    except LockError as e:
        return _err("config", f"could not lock config (in use?): {e}")
    except (UnlockError, RpcError) as e:
        return _err("rpc", e)
    except Exception as e:
        return _err("rpc", e)
    finally:
        dev.close()


def rollback(ip, n=1, username=DEFAULT_USER, password=DEFAULT_PASS,
             comment="cx-clab-mcp rollback"):
    """Roll back to a previous commit (n=1 = undo the last commit) and commit
    the rollback. Returns the diff that was applied."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return _err("config", f"rollback id must be an integer, got {n!r}")
    try:
        dev = _open(ip, username, password)
    except _ConnError as e:
        return _err(e.kind, e)
    try:
        with Config(dev, mode="exclusive") as cu:
            cu.rollback(rb_id=n)
            diff = cu.diff()
            if diff is None:
                cu.rollback()
                return {"ok": True, "applied": False,
                        "kind": "juniper_vjunosswitch", "diff": "",
                        "summary": f"rollback {n} produced no change."}
            try:
                cu.commit(comment=comment, timeout=120)
            except CommitError as e:
                cu.rollback()
                return _err("commit", f"rollback commit failed: {e}", diff=diff)
            return {"ok": True, "applied": True,
                    "kind": "juniper_vjunosswitch", "diff": diff,
                    "summary": f"Rolled back to commit {n} and committed."}
    except (LockError, UnlockError, RpcError) as e:
        return _err("rpc", e)
    except Exception as e:
        return _err("rpc", e)
    finally:
        dev.close()
