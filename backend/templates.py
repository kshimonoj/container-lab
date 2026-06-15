TEMPLATES = {
    "vsx-mclag": {
        "name": "VSX + MCLAG (Router-Core-Access-PC)",
        "group": "AOS-CX 標準",
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
        "group": "AOS-CX 標準",
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
        "group": "AOS-CX 標準",
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
        "group": "Juniper",
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
        "group": "マルチベンダー (CX × Junos)",
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
        "group": "AOS-CX 標準",
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
    },

    # ── [A] cx-junos-p2p (L2) ────────────────────────────────────
    "cx-junos-p2p-l2": {
        "name": "CX-Junos P2P (L2)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "AOS-CX cx1 (1/1/1) ↔ vJunos vsw1 (ge-0/0/0). 最小構成の L2 相互接続。"
                       "cx1 は VLAN10 をネイティブで運ぶトランク、vsw1 は untagged inet。"
                       "Apply Config 後、VLAN10 SVI/inet 10.0.10.0/30 で疎通確認。",
        "nodes": [
            {"id": "cx1",  "label": "CX1 (AOS-CX)", "kind": "vr-aoscx",             "x": 250, "y": 250},
            {"id": "vsw1", "label": "vsw1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 550, "y": 250},
        ],
        "links": [
            {"source": "cx1", "target": "vsw1", "src_if": "1/1/1", "dst_if": "ge-0/0/0", "label": "L2 VLAN10 10.0.10.0/30"},
        ]
    },

    # ── [B] cx-junos-p2p (L3/OSPF) ───────────────────────────────
    "cx-junos-p2p-ospf": {
        "name": "CX-Junos P2P (L3/OSPF)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "AOS-CX cx1 ↔ vJunos vsw1、OSPF area 0 で相互経路交換。"
                       "P2P 10.0.0.0/30、cx1 lo0 192.168.1.1/32 / vsw1 lo0 192.168.2.1/32 を広報。"
                       "「既存 Juniper コアに HPE エッジを追加」の最小 L3 デモ。",
        "nodes": [
            {"id": "cx1",  "label": "CX1 (AOS-CX)", "kind": "vr-aoscx",             "x": 250, "y": 250},
            {"id": "vsw1", "label": "vsw1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 550, "y": 250},
        ],
        "links": [
            {"source": "cx1", "target": "vsw1", "src_if": "1/1/1", "dst_if": "ge-0/0/0", "label": "OSPF 10.0.0.0/30"},
        ]
    },

    # ── [C] cx-junos-core (CX 2 + vJunos 2) ──────────────────────
    "cx-junos-core": {
        "name": "CX-Junos コア (4ノード)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "vJunos vsw1/vsw2 がコア、AOS-CX cx1/cx2 がエッジ。全ノード OSPF area 0。"
                       "「Juniper コアを維持しつつ HPE でエッジを刷新」する移行デモ。"
                       "完了条件: cx1 から cx2 の loopback (192.168.1.2) へ ping 疎通。"
                       "※ 2台目 AOS-CX (cx2) には startup-delay 120s を設定済み。",
        "nodes": [
            {"id": "vsw1", "label": "vsw1 (Core)",  "kind": "juniper_vjunosswitch", "x": 300, "y": 180},
            {"id": "vsw2", "label": "vsw2 (Core)",  "kind": "juniper_vjunosswitch", "x": 600, "y": 180},
            {"id": "cx1",  "label": "CX1 (Edge)",   "kind": "vr-aoscx",             "x": 300, "y": 420},
            {"id": "cx2",  "label": "CX2 (Edge)",   "kind": "vr-aoscx",             "x": 600, "y": 420,
             "startup_delay": 120},
        ],
        "links": [
            # core <-> core
            {"source": "vsw1", "target": "vsw2", "src_if": "ge-0/0/1", "dst_if": "ge-0/0/1", "label": "core 10.0.1.0/30"},
            # edge -> core
            {"source": "cx1",  "target": "vsw1", "src_if": "1/1/1",    "dst_if": "ge-0/0/0", "label": "10.0.2.0/30"},
            {"source": "cx2",  "target": "vsw2", "src_if": "1/1/1",    "dst_if": "ge-0/0/0", "label": "10.0.3.0/30"},
        ]
    },

    # ── [D] junos-to-cx-migration (L2, vJunos 2 + CX 1) ──────────
    "junos-to-cx-migration": {
        "name": "Junos→CX 移行デモ",
        "group": "マルチベンダー (CX × Junos)",
        "description": "vJunos vsw1/vsw2 がスパイン、AOS-CX cx1 が dual-homed リーフ (HPE 新規導入)。"
                       "VLAN 10/20 を L2 トランクで収容。"
                       "「リーフ層を Juniper から HPE に段階移行中」の状態を再現。"
                       "ループ防止のため RSTP / spanning-tree を有効化。",
        "nodes": [
            {"id": "vsw1", "label": "vsw1 (Spine1)", "kind": "juniper_vjunosswitch", "x": 300, "y": 180},
            {"id": "vsw2", "label": "vsw2 (Spine2)", "kind": "juniper_vjunosswitch", "x": 600, "y": 180},
            {"id": "cx1",  "label": "CX1 (Leaf/HPE)", "kind": "vr-aoscx",            "x": 450, "y": 420},
        ],
        "links": [
            # spine <-> spine
            {"source": "vsw1", "target": "vsw2", "src_if": "ge-0/0/1", "dst_if": "ge-0/0/1", "label": "core trunk 10/20"},
            # leaf dual-homed to both spines
            {"source": "cx1",  "target": "vsw1", "src_if": "1/1/1",    "dst_if": "ge-0/0/0", "label": "trunk 10/20"},
            {"source": "cx1",  "target": "vsw2", "src_if": "1/1/2",    "dst_if": "ge-0/0/0", "label": "trunk 10/20"},
        ]
    },

    # ── [E] cx-junos-l2-trunk (L2 multi-VLAN, CX 1 + vJunos 1) ───
    "cx-junos-l2-trunk": {
        "name": "CX-Junos L2 マルチVLAN",
        "group": "マルチベンダー (CX × Junos)",
        "description": "AOS-CX cx1 ↔ vJunos vsw1 を VLAN 10/20/30 のタグ付きトランクで接続。"
                       "各 VLAN に SVI/IRB を持たせ (10.0.10/20/30.0/30)、VLAN 移行デモ・L2 接続確認に使用。",
        "nodes": [
            {"id": "cx1",  "label": "CX1 (AOS-CX)", "kind": "vr-aoscx",             "x": 250, "y": 250},
            {"id": "vsw1", "label": "vsw1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 550, "y": 250},
        ],
        "links": [
            {"source": "cx1", "target": "vsw1", "src_if": "1/1/1", "dst_if": "ge-0/0/0", "label": "trunk VLAN 10/20/30"},
        ]
    },
}
