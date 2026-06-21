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

    # ── [G2a] evpn-allcx-dynamic (All-CX EVPN-VXLAN, DYNAMIC VTEP) ──────────
    # 全ノード AOS-CX (Spine2 + Leaf3 + PC4)。underlay=OSPF area0、overlay=iBGP EVPN
    # (Spine=RR)。各 Leaf/Spine の EVPN neighbor に send-community extended を入れることで
    # RT(Extended Community) が運ばれ、vtep-peer 無しでも動的に VTEP を学習する (Origin=evpn)。
    # vxlan-allcx-static / allcx-underlay-demo と同一トポロジ。3版で Static/Dynamic/Underlay を比較。
    "evpn-allcx-dynamic": {
        "name": "EVPN-VXLAN All-CX Dynamic VTEP (OSPF + iBGP RR)",
        "group": "AOS-CX EVPN",
        "description": "AOS-CX Spine×2 + AOS-CX Leaf×3 + PC×4 (全ノード AOS-CX)。"
                       "underlay=OSPF area0、overlay=iBGP EVPN AS65000 (Spine=Route Reflector)。"
                       "★Dynamic VTEP: 各 Leaf に vtep-peer を一切書かず、EVPN で動的学習させる。"
                       "鍵は Spine/Leaf 双方の EVPN neighbor に send-community extended を入れること。"
                       "これが無いと RT(BGP Extended Community) が運ばれず、Type-3 を受け取っても "
                       "VTEP を生成できない (前回これを誤解して dynamic が動かないと判断していた)。"
                       "Group1=VLAN10/VNI10010 (PC1@leaf1+PC3@leaf3)、Group2=VLAN20/VNI10020 "
                       "(PC2@leaf2+PC4@leaf3)。確認: show interface vxlan vteps で Origin=evpn / operational。"
                       "AOS-CX 5台は startup-delay (0/30/60/90/120s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (AOS-CX)", "kind": "vr-aoscx", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (AOS-CX)", "kind": "vr-aoscx", "x": 560, "y": 120, "startup_delay": 30},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340, "startup_delay": 60},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 90},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 120},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            # Spine1 -> Leaves (10.0.1.x/31). Spine も AOS-CX なので 1/1/X 表記。
            {"source": "spine1", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            # Spine2 -> Leaves (10.0.2.x/31)
            {"source": "spine2", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            # Leaves -> PCs (L3: access vlan 収容)
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": "G2/vlan20"},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf3", "target": "pc4", "src_if": "1/1/4", "dst_if": "eth1", "label": "G2/vlan20"},
        ]
    },

    # ── [G2a-mv] evpn-mv-dynamic (Multivendor EVPN-VXLAN, vJunos RR + CX Dynamic VTEP) ──
    # evpn-allcx-dynamic と同一設計思想のマルチベンダー版。Spine だけ vJunos に置換。
    # vJunos Spine×2 = EVPN Route Reflector (VTEP にならず EVPN 経路を反射するだけ)、
    # AOS-CX Leaf×3 = RR クライアント兼 Dynamic VTEP。全ノード iBGP 単一 AS65000、underlay=OSPF。
    # 鍵は send-community extended (RT=Extended Community が運ばれ vtep-peer 無しで動的学習)。
    # vJunos boot が遅いため Spine を先に・Leaf を後に段階起動 (0/30/90/120/150s)。
    "evpn-mv-dynamic": {
        "name": "EVPN-VXLAN Multivendor Dynamic (vJunos RR + CX VTEP)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "vJunos Spine×2 + AOS-CX Leaf×3 + PC×4。underlay=OSPF area0、"
                       "overlay=iBGP EVPN AS65000。★vJunos Spine が EVPN Route Reflector、"
                       "AOS-CX Leaf が RR クライアント兼 Dynamic VTEP。Spine は VTEP にならず "
                       "EVPN Type-2/3 を反射するだけ (VXLAN encap/decap しない)。"
                       "★Dynamic VTEP: Leaf に vtep-peer を一切書かず、send-community extended で "
                       "運ばれる RT(BGP Extended Community) を使って動的に VTEP を学習する。"
                       "Group1=VLAN10/VNI10010 (PC1@leaf1+PC3@leaf3)、Group2=VLAN20/VNI10020 "
                       "(PC2@leaf2+PC4@leaf3)。確認: show interface vxlan vteps で Origin=evpn / operational。"
                       "vJunos RR 経由で AOS-CX 由来の EVPN 経路 (RT/Extended-community) が正しく反射されるかが "
                       "マルチベンダー相互運用の確認ポイント。All-CX Dynamic 版 (evpn-allcx-dynamic) と設計思想が揃う。"
                       "vJunos boot が遅いため startup-delay (0/30/90/120/150s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (vJunos RR)", "kind": "juniper_vjunosswitch", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (vJunos RR)", "kind": "juniper_vjunosswitch", "x": 560, "y": 120, "startup_delay": 30},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340, "startup_delay": 90},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 120},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 150},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            # Spine1 (vJunos) -> Leaves (10.0.1.x/31). Spine は vJunos なので ge-0/0/X 表記。
            {"source": "spine1", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            # Spine2 (vJunos) -> Leaves (10.0.2.x/31)
            {"source": "spine2", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            # Leaves -> PCs (L3: access vlan 収容)
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": "G2/vlan20"},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf3", "target": "pc4", "src_if": "1/1/4", "dst_if": "eth1", "label": "G2/vlan20"},
        ]
    },

    # ── [G2a-mv-u] evpn-mv-underlay-demo (Multivendor, underlay only; overlay via MCP later) ──
    # evpn-mv-dynamic と同一トポロジ (vJunos Spine×2 + AOS-CX Leaf×3 + PC×4)。
    # OSPF underlay だけを先に作り、overlay (iBGP EVPN / VXLAN / EVPN instance) は未設定の
    # before-state。PC 間は不通。デモでは MCP apply_config で overlay (dynamic VTEP 版) を
    # 後から投入して開通する様子を見せる (allcx-underlay-demo のマルチベンダー版)。
    "evpn-mv-underlay-demo": {
        "name": "EVPN Multivendor Underlay only (demo, overlay via MCP later)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "vJunos Spine×2 + AOS-CX Leaf×3 + PC×4。★Underlay のみ: OSPF area0 で "
                       "loopback 到達性まで。VXLAN/EVPN/iBGP overlay は未設定 (before-state)。"
                       "Leaf のアクセスポート (1/1/3,1/1/4) も VLAN/VXLAN が無いため設定せず、"
                       "Leaf 跨ぎは不通 (PC1->PC3 は通らない)。デモでは MCP apply_config で "
                       "dynamic VTEP overlay (vJunos=EVPN RR / AOS-CX=RR クライアント兼 Dynamic VTEP) を "
                       "後から投入し、PC 間が開通する様子を見せる。投入する overlay 設定は "
                       "evpn-mv-underlay-demo-answerkey.md に用意 (鍵は send-community extended)。"
                       "evpn-mv-dynamic と同一トポロジ・同一 underlay の before 版。"
                       "vJunos boot が遅いため startup-delay (0/30/90/120/150s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (vJunos)", "kind": "juniper_vjunosswitch", "x": 560, "y": 120, "startup_delay": 30},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340, "startup_delay": 90},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 120},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 150},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            # Spine1 (vJunos) -> Leaves (10.0.1.x/31). Spine は vJunos なので ge-0/0/X 表記。
            {"source": "spine1", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            # Spine2 (vJunos) -> Leaves (10.0.2.x/31)
            {"source": "spine2", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            # Leaves -> PCs (underlay only: アクセス VLAN/VXLAN は overlay 投入時に追加)
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": "(G1/vlan10 後付け)"},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": "(G2/vlan20 後付け)"},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": "(G1/vlan10 後付け)"},
            {"source": "leaf3", "target": "pc4", "src_if": "1/1/4", "dst_if": "eth1", "label": "(G2/vlan20 後付け)"},
        ]
    },

    # ── [G2b] vxlan-allcx-static (All-CX VXLAN, STATIC VTEP, no BGP) ────────
    # 同一トポロジ。BGP/EVPN を完全に削除し、Leaf の VXLAN に vtep-peer を明示する静的方式。
    "vxlan-allcx-static": {
        "name": "VXLAN All-CX Static VTEP (OSPF underlay, no BGP)",
        "group": "AOS-CX EVPN",
        "description": "AOS-CX Spine×2 + AOS-CX Leaf×3 + PC×4 (全ノード AOS-CX)。"
                       "★Static VTEP: BGP/EVPN を一切使わず (router bgp 無し)、underlay=OSPF area0 のみ。"
                       "各 Leaf の interface vxlan 1 配下に vtep-peer (対向 Leaf loopback) を明示して "
                       "VXLAN データプレーンを張る。leaf1<->leaf3 が VNI10010、leaf2<->leaf3 が VNI10020。"
                       "Group1=VLAN10/VNI10010 (PC1+PC3)、Group2=VLAN20/VNI10020 (PC2+PC4)。"
                       "確認: show interface vxlan vteps で Origin=static / operational、router bgp が無いこと。"
                       "AOS-CX 5台は startup-delay (0/30/60/90/120s) で段階起動。"
                       "Dynamic 版 (evpn-allcx-dynamic) との制御プレーン有無の比較教材。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (AOS-CX)", "kind": "vr-aoscx", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (AOS-CX)", "kind": "vr-aoscx", "x": 560, "y": 120, "startup_delay": 30},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340, "startup_delay": 60},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 90},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 120},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            {"source": "spine1", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            {"source": "spine2", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": "G2/vlan20"},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf3", "target": "pc4", "src_if": "1/1/4", "dst_if": "eth1", "label": "G2/vlan20"},
        ]
    },

    # ── [G2c] allcx-underlay-demo (All-CX, underlay only; overlay via MCP later) ──
    # 同一トポロジ。OSPF underlay だけを先に作り、overlay (VXLAN/EVPN/BGP) は未設定の
    # before-state。PC 間は不通。後から MCP の apply_config で dynamic か static の overlay を
    # 投入して開通する様子を見せるデモ用 (cx-junos-ospf-pc-demo と同じ「後付け」方式)。
    "allcx-underlay-demo": {
        "name": "All-CX Underlay only (demo, overlay via MCP later)",
        "group": "AOS-CX EVPN",
        "description": "AOS-CX Spine×2 + AOS-CX Leaf×3 + PC×4 (全ノード AOS-CX)。"
                       "★Underlay のみ: OSPF area0 で loopback 到達性まで。VXLAN/EVPN/BGP overlay は未設定。"
                       "Leaf の 1/1/3,1/1/4 は VLAN access まで設定するが、VNI が無いため Leaf 跨ぎは不通 "
                       "(PC1->PC3 は通らない before-state)。デモでは MCP apply_config で overlay "
                       "(dynamic か static のどちらか) を後から投入し、PC 間が開通する様子を見せる。"
                       "投入する overlay 設定は allcx-underlay-demo-answerkey.md に dynamic/static 両方を用意。"
                       "AOS-CX 5台は startup-delay (0/30/60/90/120s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (AOS-CX)", "kind": "vr-aoscx", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (AOS-CX)", "kind": "vr-aoscx", "x": 560, "y": 120, "startup_delay": 30},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340, "startup_delay": 60},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 90},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 120},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            {"source": "spine1", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            {"source": "spine2", "target": "leaf1", "src_if": "1/1/1", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "1/1/2", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "1/1/3", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": "G2/vlan20"},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": "G1/vlan10"},
            {"source": "leaf3", "target": "pc4", "src_if": "1/1/4", "dst_if": "eth1", "label": "G2/vlan20"},
        ]
    },

    # ── [H] cx-junos-ospf-pc-demo (OSPF PC-to-PC demo; before = NO OSPF) ──
    "cx-junos-ospf-pc-demo": {
        "name": "OSPF PC-to-PC demo (CX × Junos)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "PC1 — sw01(AOS-CX) ==OSPF area0== sw02(vJunos) — PC2。"
                       "初期 config は OSPF 無しの「before」状態のため、PC1→PC2 (10.0.2.10) は "
                       "不通。デモ中に Apply Config / MCP で OSPF を追加すると疎通する。"
                       "P2P 10.1.1.0/30、PC側 10.0.1.0/24 (gw .1) / 10.0.2.0/24 (gw .1)、"
                       "lo0 sw01=1.1.1.1 / sw02=2.2.2.2。OSPF 追加手順は ospf-demo-answerkey.md。",
        "nodes": [
            {"id": "pc1",  "label": "PC1",           "kind": "linux",                "x": 120, "y": 300},
            {"id": "sw01", "label": "sw01 (AOS-CX)", "kind": "vr-aoscx",             "x": 340, "y": 300},
            {"id": "sw02", "label": "sw02 (vJunos)", "kind": "juniper_vjunosswitch", "x": 560, "y": 300},
            {"id": "pc2",  "label": "PC2",           "kind": "linux",                "x": 780, "y": 300},
        ],
        "links": [
            # PC1 -> sw01 (data link; PC uses eth1, eth0 is clab mgmt)
            {"source": "pc1",  "target": "sw01", "src_if": "eth1",     "dst_if": "1/1/1",    "label": "10.0.1.0/24"},
            # sw01 -> sw02 (OSPF area-0 P2P)
            {"source": "sw01", "target": "sw02", "src_if": "1/1/2",    "dst_if": "ge-0/0/0", "label": "OSPF 10.1.1.0/30"},
            # sw02 -> PC2
            {"source": "sw02", "target": "pc2",  "src_if": "ge-0/0/1", "dst_if": "eth1",     "label": "10.0.2.0/24"},
        ]
    },
}
