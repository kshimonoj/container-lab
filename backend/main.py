# main.py
import asyncio
import json
import os
import subprocess
import threading

import paramiko
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lab_manager import (
    apply_default_config, deploy_lab, destroy_lab, estimate_resources,
    exec_command, export_topology_yaml, get_lab_status, get_node_live_info,
    get_node_ssh_info, get_radius_summary, import_topology_yaml, list_drivers,
    list_labs, list_running_labs,
)
from templates import TEMPLATES

app = FastAPI(title="CX ContainerLab GUI")
app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/app/frontend/index.html") as f:
        return f.read()


# ── Templates ──────────────────────────────────────────────────
@app.get("/api/templates")
async def get_templates():
    return {"templates": [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in TEMPLATES.items()
    ]}

@app.get("/api/templates/{template_id}")
async def get_template(template_id: str):
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")
    return TEMPLATES[template_id]


# ── Drivers (node kinds the GUI can place) ─────────────────────
@app.get("/api/drivers")
async def get_drivers():
    return {"drivers": list_drivers()}


# ── Resource estimate (pre-deploy guard) ───────────────────────
class EstimateRequest(BaseModel):
    topology: dict

@app.post("/api/resources/estimate")
async def resources_estimate(req: EstimateRequest):
    return estimate_resources(req.topology)


# ── Labs ───────────────────────────────────────────────────────
@app.get("/api/labs")
async def get_labs():
    return {"labs": list_labs()}

@app.get("/api/labs/running")
def api_list_running_labs():
    """List running containerlab labs (from inspect --all)."""
    return {"labs": list_running_labs()}

@app.get("/api/labs/{lab_name}/nodes/{node_id}/live")
def api_node_live(lab_name: str, node_id: str, kind: str = ""):
    """Node live info (for the Refresh button). The driver is resolved from the
    live container kind; `kind` is only a hint used if the container is gone."""
    return get_node_live_info(lab_name, node_id, kind)

@app.get("/api/labs/{lab_name}/topology")
async def get_lab_topology(lab_name: str):
    """Return a deployed lab's clab YAML as a GUI topology."""
    from pathlib import Path

    yaml_path = Path(f"/home/kshimono/claude/cx-clab/labs/{lab_name}/{lab_name}.clab.yml")
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="Lab topology file not found")

    content = yaml_path.read_text()
    result = import_topology_yaml(content)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "parse error"))

    # check whether it is deployed (containers exist)
    status = get_lab_status(lab_name)
    is_deployed = len(status.get("containers", [])) > 0

    return {
        "lab_name": lab_name,
        "topology": result["topology"],
        "is_deployed": is_deployed,
    }

class DeployRequest(BaseModel):
    lab_name: str
    topology: dict

@app.post("/api/labs/deploy")
async def deploy(req: DeployRequest):
    result = deploy_lab(req.topology, req.lab_name)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return result

@app.delete("/api/labs/{lab_name}")
async def destroy(lab_name: str):
    result = destroy_lab(lab_name)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", result.get("stderr")))
    return result

@app.delete("/api/labs/{lab_name}/files")
async def delete_lab_files(lab_name: str):
    """Remove only the lab's YAML files/directory (does not destroy containers)."""
    from pathlib import Path
    import shutil
    lab_dir = Path(f"/home/kshimono/claude/cx-clab/labs/{lab_name}")
    if lab_dir.exists():
        try:
            shutil.rmtree(lab_dir)
            return {"success": True, "message": f"Removed {lab_dir}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "message": "No files to remove"}

@app.get("/api/labs/{lab_name}/status")
async def status(lab_name: str):
    return get_lab_status(lab_name)


# ── Apply Config (per-template default config sets) ────────────
@app.post("/api/labs/{lab_name}/apply-config")
def api_apply_config(lab_name: str, payload: dict):
    """Push the default config set for the given template to a running lab.
    payload: {"template_id": "..."}"""
    template_id = (payload or {}).get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")
    return apply_default_config(lab_name, template_id)


# ── RADIUS summary (detail panel) ──────────────────────────────
@app.get("/api/radius/summary")
def api_radius_summary():
    """Return a static summary of the mounted FreeRADIUS templates."""
    return get_radius_summary()


# ── Node exec ──────────────────────────────────────────────────
class ExecRequest(BaseModel):
    command: str

@app.post("/api/labs/{lab_name}/nodes/{node_id}/exec")
async def node_exec(lab_name: str, node_id: str, req: ExecRequest):
    return exec_command(lab_name, node_id, req.command)


# ── YAML export/import ─────────────────────────────────────────
class ExportRequest(BaseModel):
    lab_name: str
    topology: dict

@app.post("/api/topology/export")
async def topology_export(req: ExportRequest):
    yaml_str = export_topology_yaml(req.topology, req.lab_name)
    return PlainTextResponse(yaml_str, media_type="text/plain")

class ImportRequest(BaseModel):
    yaml_content: str

@app.post("/api/topology/import")
async def topology_import(req: ImportRequest):
    return import_topology_yaml(req.yaml_content)


# ── SSH info ───────────────────────────────────────────────────
@app.get("/api/labs/{lab_name}/nodes/{node_id}/ssh-info")
async def ssh_info_endpoint(lab_name: str, node_id: str):
    info = get_node_ssh_info(lab_name, node_id)
    if not info:
        raise HTTPException(status_code=404, detail="No IP found")
    return info


# ── WebSocket: SSH Terminal (CX switches) ──────────────────────
@app.websocket("/ws/terminal/{lab_name}/{node_id}")
async def terminal_ws(websocket: WebSocket, lab_name: str, node_id: str):
    await websocket.accept()
    await websocket.send_text(f"\r\nConnecting to {lab_name}/{node_id} ...\r\n")

    # wait up to 30s for an IP (handles just-started containers)
    ssh_info = None
    for attempt in range(6):
        ssh_info = get_node_ssh_info(lab_name, node_id)
        if ssh_info:
            break
        await websocket.send_text(f"\r\n[Waiting for container IP... {attempt+1}/6]\r\n")
        await asyncio.sleep(5)

    if not ssh_info:
        await websocket.send_text("\r\n[ERROR] Node not found or no IP address.\r\n")
        await websocket.close()
        return

    await websocket.send_text(f"\r\n[Connecting SSH to {ssh_info['host']}...]\r\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH connect retry (CX takes a while to boot)
    channel = None
    for attempt in range(10):
        try:
            ssh.connect(
                hostname=ssh_info["host"],
                port=ssh_info["port"],
                username=ssh_info["username"],
                password=ssh_info["password"],
                timeout=10,
                banner_timeout=30,
                auth_timeout=15,
                look_for_keys=False,
                allow_agent=False,
            )
            channel = ssh.invoke_shell(term="xterm", width=220, height=50)
            channel.setblocking(False)
            await websocket.send_text("\r\n[SSH connected]\r\n")
            break
        except Exception as e:
            await websocket.send_text(f"\r\n[SSH attempt {attempt+1}/10 failed: {e}]\r\n")
            if attempt < 9:
                await asyncio.sleep(15)

    if channel is None:
        await websocket.send_text("\r\n[ERROR] SSH connection failed after 10 attempts.\r\n")
        await websocket.close()
        return

    stop_event = threading.Event()

    def _read_ssh(ch):
        try:
            if ch.recv_ready():
                return ch.recv(4096)
        except Exception:
            pass
        return b""

    async def send_output():
        loop = asyncio.get_event_loop()
        while not stop_event.is_set():
            try:
                data = await loop.run_in_executor(None, _read_ssh, channel)
                if data:
                    await websocket.send_text(data.decode("utf-8", errors="replace"))
            except Exception:
                break
            await asyncio.sleep(0.05)

    output_task = asyncio.create_task(send_output())
    try:
        while True:
            data = await websocket.receive_text()
            channel.send(data)
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        output_task.cancel()
        try: channel.close()
        except: pass
        try: ssh.close()
        except: pass


# ── WebSocket: docker exec Terminal (linux nodes) ──────────────
@app.websocket("/ws/exec-terminal/{lab_name}/{node_id}")
async def exec_terminal_ws(websocket: WebSocket, lab_name: str, node_id: str):
    """For linux-kind nodes: provide a shell via docker exec (uses a PTY)."""
    await websocket.accept()
    container_name = f"clab-{lab_name}-{node_id}"
    await websocket.send_text(f"\r\nConnecting to {container_name}...\r\n")

    # confirm the container is running
    check = subprocess.run(
        ["docker", "inspect", container_name, "--format", "{{.State.Running}}"],
        capture_output=True, text=True
    )
    if check.stdout.strip() != "true":
        await websocket.send_text(f"\r\n[ERROR] Container {container_name} is not running.\r\n")
        await websocket.close()
        return

    # start docker exec with a PTY (for an interactive shell)
    import pty
    import fcntl
    import termios
    import struct

    master_fd, slave_fd = pty.openpty()

    # set terminal size
    winsize = struct.pack("HHHH", 50, 200, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", "-it", container_name, "/bin/sh",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
    )
    os.close(slave_fd)

    await websocket.send_text("\r\n[Connected]\r\n")

    loop = asyncio.get_event_loop()
    stop_event = threading.Event()

    # make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _read_fd(fd):
        try:
            return os.read(fd, 4096)
        except BlockingIOError:
            return b""
        except OSError:
            return None

    async def read_output():
        while not stop_event.is_set():
            try:
                data = await loop.run_in_executor(None, _read_fd, master_fd)
                if data:
                    await websocket.send_text(data.decode("utf-8", errors="replace"))
                elif data is None:
                    break
            except Exception:
                break
            await asyncio.sleep(0.05)

    output_task = asyncio.create_task(read_output())
    try:
        while True:
            data = await websocket.receive_text()
            os.write(master_fd, data.encode())
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        output_task.cancel()
        try: proc.terminate()
        except: pass
        try: os.close(master_fd)
        except: pass
