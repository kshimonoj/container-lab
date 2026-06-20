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

    # ── [F] evpn-spine-leaf (EVPN-VXLAN L1 underlay + L2 EVPN CP) ────────
    "evpn-spine-leaf": {
        "name": "EVPN Spine-Leaf L2 (eBGP underlay + EVPN CP)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "JUNOS Spine×2 + AOS-CX Leaf×3 + PC×3. eBGP underlay (L1) + "
                       "Lean-Spine eBGP EVPN コントロールプレーン (L2)。各 Leaf は両 Spine と "
                       "underlay eBGP、Leaf 同士は loopback 間 multihop eBGP で l2vpn evpn を "
                       "フルメッシュ。Spine は EVPN 不参加 (underlay 中継のみ)。VXLAN/VNI は L3。"
                       "AOS-CX 3台は startup-delay (0/60/120s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (vJunos)", "kind": "juniper_vjunosswitch", "x": 560, "y": 120},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 60},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 120},
            {"id": "pc1",    "label": "PC1",             "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2",             "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3",             "kind": "linux", "x": 680, "y": 540},
        ],
        "links": [
            # Spine1 -> Leaves (10.0.1.x/31)
            {"source": "spine1", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            # Spine2 -> Leaves (10.0.2.x/31)
            {"source": "spine2", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/2", "label": "10.0.2.0/31"},
            {"source": "spine2", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/2", "label": "10.0.2.2/31"},
            {"source": "spine2", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/2", "label": "10.0.2.4/31"},
            # Leaves -> PCs (L1: access up only)
            {"source": "leaf1", "target": "pc1", "src_if": "1/1/3", "dst_if": "eth1", "label": ""},
            {"source": "leaf2", "target": "pc2", "src_if": "1/1/3", "dst_if": "eth1", "label": ""},
            {"source": "leaf3", "target": "pc3", "src_if": "1/1/3", "dst_if": "eth1", "label": ""},
        ]
    },

    # ── [G] evpn-spine-leaf-l3 (= [F] + VXLAN L2VNI データプレーン + Group 分離) ──
    # L2 テンプレート evpn-spine-leaf と同一トポロジ (8ノード/9リンク)。
    # config だけ VXLAN/VNI/RT/access-vlan/PC IP を追加した上位版。
    "evpn-spine-leaf-l3": {
        "name": "EVPN Spine-Leaf L3 (VXLAN + Group分離)",
        "group": "マルチベンダー (CX × Junos)",
        "description": "JUNOS Spine×2 + AOS-CX Leaf×3 + PC×4. eBGP underlay (L1) + "
                       "Lean-Spine eBGP EVPN コントロールプレーン (L2) + VXLAN L2VNI データプレーン (L3)。"
                       "Leaf 同士は loopback 間 multihop eBGP で l2vpn evpn をフルメッシュ、Spine は "
                       "EVPN 不参加 (underlay 中継のみ)。Group1=VLAN10/VNI10010 (PC1@leaf1+PC3@leaf3)、"
                       "Group2=VLAN20/VNI10020 (PC2@leaf2+PC4@leaf3)。同一 VNI のみ L2 疎通し別 Group は完全分離。"
                       "eBGP のため EVI ごとに手動 RT。VTEP source=loopback0。"
                       "vrnetlab vr-aoscx は EVPN 動的 VTEP 学習が効かないため、各 Leaf の VNI 配下に "
                       "static vtep-peer (対向 Leaf loopback) を補完して VXLAN データプレーンを疎通させる。"
                       "AOS-CX 3台は startup-delay (0/60/120s) で段階起動。",
        "nodes": [
            {"id": "spine1", "label": "Spine1 (vJunos)", "kind": "juniper_vjunosswitch", "x": 280, "y": 120},
            {"id": "spine2", "label": "Spine2 (vJunos)", "kind": "juniper_vjunosswitch", "x": 560, "y": 120},
            {"id": "leaf1",  "label": "Leaf1 (AOS-CX)",  "kind": "vr-aoscx", "x": 160, "y": 340},
            {"id": "leaf2",  "label": "Leaf2 (AOS-CX)",  "kind": "vr-aoscx", "x": 420, "y": 340, "startup_delay": 60},
            {"id": "leaf3",  "label": "Leaf3 (AOS-CX)",  "kind": "vr-aoscx", "x": 680, "y": 340, "startup_delay": 120},
            {"id": "pc1",    "label": "PC1 (G1)",        "kind": "linux", "x": 160, "y": 540},
            {"id": "pc2",    "label": "PC2 (G2)",        "kind": "linux", "x": 420, "y": 540},
            {"id": "pc3",    "label": "PC3 (G1)",        "kind": "linux", "x": 620, "y": 540},
            {"id": "pc4",    "label": "PC4 (G2)",        "kind": "linux", "x": 780, "y": 540},
        ],
        "links": [
            # Spine1 -> Leaves (10.0.1.x/31)
            {"source": "spine1", "target": "leaf1", "src_if": "ge-0/0/0", "dst_if": "1/1/1", "label": "10.0.1.0/31"},
            {"source": "spine1", "target": "leaf2", "src_if": "ge-0/0/1", "dst_if": "1/1/1", "label": "10.0.1.2/31"},
            {"source": "spine1", "target": "leaf3", "src_if": "ge-0/0/2", "dst_if": "1/1/1", "label": "10.0.1.4/31"},
            # Spine2 -> Leaves (10.0.2.x/31)
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

    # ── [G2] evpn-allcx (All-CX EVPN-VXLAN: OSPF underlay + iBGP EVPN RR) ──
    # evpn-spine-leaf-l3 と同一トポロジ・同一 Group 要件 (8ノード/9リンク) を全ノード
    # AOS-CX で構成。Aruba 公式リファレンス準拠で underlay=OSPF area0、overlay=iBGP
    # (Spine=Route Reflector)。マルチベンダー版 (eBGP/Lean Spine) との比較教材。
    "evpn-allcx": {
        "name": "EVPN-VXLAN All-CX (OSPF underlay + iBGP)",
        "group": "AOS-CX EVPN",
        "description": "AOS-CX Spine×2 + AOS-CX Leaf×3 + PC×3 (全ノード AOS-CX)。"
                       "Aruba 公式リファレンス準拠: underlay=OSPF area0 (loopback/VTEP 到達性)、"
                       "overlay=iBGP EVPN AS65000 で Spine が Route Reflector・Leaf が RR クライアント。"
                       "Spine は VXLAN 不参加 (RR に徹する)。VTEP は Leaf のみ (source=loopback0)。"
                       "iBGP のため route-target は auto。Group1=VLAN10/VNI10010 (PC1@leaf1+PC3@leaf3)、"
                       "Group2=VLAN20/VNI10020 (PC2@leaf2+PC4@leaf3)。同一 VNI のみ L2 疎通し別 Group は完全分離。"
                       "vrnetlab vr-aoscx は EVPN 動的 VTEP 学習が効かないため、各 Leaf の VNI 配下に "
                       "static vtep-peer (対向 Leaf loopback) を補完して VXLAN データプレーンを疎通させる。"
                       "AOS-CX 5台は startup-delay (0/30/60/90/120s) で段階起動。"
                       "マルチベンダー版 (eBGP/Lean Spine) との設計差を比較できる教材。",
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
