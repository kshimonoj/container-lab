TEMPLATES = {
    "vsx-mclag": {
        "name": "VSX + MCLAG (Router-Core-Access-PC)",
        "description": "Router SW04 → VSX Core (SW01+SW02) → MCLAG Access SW03 → PC",
        "nodes": [
            {"id": "sw04", "label": "Router SW04",  "kind": "vr-aoscx", "x": 400, "y": 80},
            {"id": "sw01", "label": "Core SW01",    "kind": "vr-aoscx", "x": 200, "y": 260},
            {"id": "sw02", "label": "Core SW02",    "kind": "vr-aoscx", "x": 600, "y": 260},
            {"id": "sw03", "label": "Access SW03",  "kind": "vr-aoscx", "x": 400, "y": 440},
            {"id": "pc1",  "label": "PC",           "kind": "linux",    "x": 400, "y": 600},
        ],
        "links": [
            # Uplink: Router → Core
            {"source": "sw04", "target": "sw01", "src_if": "1/1/1", "dst_if": "1/1/1", "label": "uplink"},
            {"source": "sw04", "target": "sw02", "src_if": "1/1/2", "dst_if": "1/1/1", "label": "uplink"},
            # VSX ISL
            {"source": "sw01", "target": "sw02", "src_if": "1/1/3", "dst_if": "1/1/3", "label": "VSX ISL"},
            # VSX Keepalive
            {"source": "sw01", "target": "sw02", "src_if": "1/1/4", "dst_if": "1/1/4", "label": "VSX KA"},
            # MCLAG: Core → Access
            {"source": "sw01", "target": "sw03", "src_if": "1/1/5", "dst_if": "1/1/1", "label": "MCLAG"},
            {"source": "sw02", "target": "sw03", "src_if": "1/1/5", "dst_if": "1/1/2", "label": "MCLAG"},
            # Access → PC
            {"source": "sw03", "target": "pc1",  "src_if": "1/1/6", "dst_if": "eth1",  "label": ""},
        ]
    },
    "simple-l2": {
        "name": "Simple L2 (2 switches)",
        "description": "Basic L2 connection between SW01 and SW02",
        "nodes": [
            {"id": "sw01", "label": "SW01", "kind": "vr-aoscx", "x": 200, "y": 250},
            {"id": "sw02", "label": "SW02", "kind": "vr-aoscx", "x": 500, "y": 250},
        ],
        "links": [
            {"source": "sw01", "target": "sw02", "src_if": "1/1/1", "dst_if": "1/1/1", "label": ""},
        ]
    },
    "spine-leaf": {
        "name": "Spine-Leaf (2+2)",
        "description": "2 spines x 2 leaves OSPF underlay",
        "nodes": [
            {"id": "spine01", "label": "Spine01", "kind": "vr-aoscx", "x": 200, "y": 150},
            {"id": "spine02", "label": "Spine02", "kind": "vr-aoscx", "x": 500, "y": 150},
            {"id": "leaf01",  "label": "Leaf01",  "kind": "vr-aoscx", "x": 150, "y": 380},
            {"id": "leaf02",  "label": "Leaf02",  "kind": "vr-aoscx", "x": 550, "y": 380},
        ],
        "links": [
            {"source": "spine01", "target": "leaf01",  "src_if": "1/1/1", "dst_if": "1/1/1", "label": ""},
            {"source": "spine01", "target": "leaf02",  "src_if": "1/1/2", "dst_if": "1/1/1", "label": ""},
            {"source": "spine02", "target": "leaf01",  "src_if": "1/1/1", "dst_if": "1/1/2", "label": ""},
            {"source": "spine02", "target": "leaf02",  "src_if": "1/1/2", "dst_if": "1/1/2", "label": ""},
        ]
    },
    "junos-p2p": {
        "name": "JUNOS P2P (2x vJunos-switch)",
        "description": "Two vJunos-switch back-to-back over ge-0/0/0 (same as the 02 verification). Apply Config sets 10.0.0.0/30 on each end.",
        "nodes": [
            {"id": "vsw1", "label": "vSW1", "kind": "juniper_vjunosswitch", "x": 250, "y": 250},
            {"id": "vsw2", "label": "vSW2", "kind": "juniper_vjunosswitch", "x": 550, "y": 250},
        ],
        "links": [
            {"source": "vsw1", "target": "vsw2", "src_if": "ge-0/0/0", "dst_if": "ge-0/0/0", "label": "P2P 10.0.0.0/30"},
        ]
    },
    "cx-junos-interop": {
        "name": "CX ↔ JUNOS Interop (AOS-CX + vJunos)",
        "description": "AOS-CX SW01 (1/1/1) ↔ vJunos vSW1 (ge-0/0/0). L3 P2P interop on 10.0.0.0/30.",
        "nodes": [
            {"id": "sw01", "label": "CX SW01", "kind": "vr-aoscx",            "x": 250, "y": 250},
            {"id": "vsw1", "label": "vSW1",    "kind": "juniper_vjunosswitch", "x": 550, "y": 250},
        ],
        "links": [
            {"source": "sw01", "target": "vsw1", "src_if": "1/1/1", "dst_if": "ge-0/0/0", "label": "interop 10.0.0.0/30"},
        ]
    },
    "auth-verify-radius": {
        "name": "Auth Verify (Access+Core+PC+RADIUS)",
        "description": "PC3 -> Access-1 -> Core-1 -> RADIUS. 802.1X/MAC-auth verification (accept-all template)",
        "nodes": [
            {"id": "pc3",     "label": "PC3",      "kind": "linux",    "x": 120, "y": 300},
            {"id": "access1", "label": "Access-1", "kind": "vr-aoscx", "x": 340, "y": 300},
            {"id": "core1",   "label": "Core-1",   "kind": "vr-aoscx", "x": 560, "y": 300},
            {"id": "radius",  "label": "RADIUS",   "kind": "linux",    "x": 780, "y": 300,
             "image": "freeradius/freeradius-server:latest",
             "binds": [
                 "/home/kshimono/claude/cx-clab/configs/freeradius/clients.conf:/etc/freeradius/clients.conf",
                 "/home/kshimono/claude/cx-clab/configs/freeradius/authorize:/etc/freeradius/mods-config/files/authorize",
             ]},
        ],
        "links": [
            # PC3 → Access-1 (user VLAN 11, access)
            {"source": "pc3",     "target": "access1", "src_if": "eth1",  "dst_if": "1/1/1", "label": "VLAN11"},
            # Access-1 → Core-1 (trunk: allowed 11,99 / native 1)
            {"source": "access1", "target": "core1",   "src_if": "1/1/2", "dst_if": "1/1/1", "label": "trunk"},
            # Core-1 → RADIUS (service VLAN 99, access)
            {"source": "core1",   "target": "radius",  "src_if": "1/1/2", "dst_if": "eth1",  "label": "VLAN99"},
        ]
    }
}
