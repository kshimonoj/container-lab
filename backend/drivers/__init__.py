# drivers/__init__.py
"""Node driver registry.

Maps a containerlab `kind` string to the driver that knows how to talk to that
node type. lab_manager resolves a driver per node and routes every
kind-specific operation through it, so adding a vendor means adding a driver
module here — nothing else in the backend needs to know about it.
"""
from .base import NodeDriver
from .aoscx import AosCxDriver
from .linux import LinuxDriver
from .vjunos_switch import VjunosSwitchDriver

# Default kind for nodes that don't declare one (keeps existing AOS-CX behaviour).
DEFAULT_KIND = "vr-aoscx"

_DRIVERS = [AosCxDriver(), LinuxDriver(), VjunosSwitchDriver()]

DRIVER_REGISTRY = {d.kind: d for d in _DRIVERS}

# Accept alternate kind spellings that containerlab / users may use.
_ALIASES = {
    "aruba_aoscx": "vr-aoscx",
    "aoscx": "vr-aoscx",
    "juniper_vjunos-switch": "juniper_vjunosswitch",
    "vjunos": "juniper_vjunosswitch",
    "vjunos-switch": "juniper_vjunosswitch",
}
for alias, target in _ALIASES.items():
    if target in DRIVER_REGISTRY:
        DRIVER_REGISTRY[alias] = DRIVER_REGISTRY[target]


def get_driver(kind: str) -> NodeDriver:
    """Return the driver for a containerlab kind, falling back to the default
    (AOS-CX) so unknown/empty kinds behave as before."""
    if kind and kind in DRIVER_REGISTRY:
        return DRIVER_REGISTRY[kind]
    return DRIVER_REGISTRY[DEFAULT_KIND]


def list_drivers() -> list:
    """Metadata for the frontend (kinds available in the Add Node dialog)."""
    seen = []
    out = []
    for d in _DRIVERS:
        if d.kind in seen:
            continue
        seen.append(d.kind)
        out.append({
            "kind": d.kind,
            "display_name": d.display_name,
            "image": d.image,
            "is_vm": d.is_vm,
            "boot_timeout_sec": d.boot_timeout_sec,
            "ram_gib": d.ram_gib,
            "boot_hint": d.boot_hint,
        })
    return out
