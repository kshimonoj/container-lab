[English / 英語版](README.md)

# clab — マルチベンダー ContainerLab 管理 GUI + MCP サーバー

[ContainerLab](https://containerlab.dev/) 上で **マルチベンダー** のネットワーク
トポロジを構築・デプロイ・運用するための Web GUI と Claude 用 MCP サーバーです。
Aruba/HPE **AOS-CX** (`vr-aoscx`) と Juniper **vJunos-switch**
(`juniper_vjunosswitch`) を併用できます。

本プロジェクトは 2 つのフロントエンドを提供します。

- **clab (GUI)** — ブラウザからラボを操作する。
- **clab-mcp (MCP サーバー)** — **Claude Desktop** から LAN 経由でノード設定を
  読み取り、安全に変更する。

> ⚠️ これはラボ用ツールです。**実際の認証情報や秘密情報は一切含みません。**
> 参照される認証情報は工場出荷時の `admin/admin` (AOS-CX) と
> `admin/admin@123` (vJunos)、および RADIUS 共有シークレットのプレースホルダのみで、
> 実際の `.env` と RADIUS 設定は git 管理外です。**ラボ以外で使う前に必ず変更してください。**

## 機能

### GUI (clab)
- **ラボ管理** — deploy / destroy / status、起動中ラボのセレクタ付き。
- **Apply Config / Preview Config** — テンプレートの config セットを、ロード中
  ラボのノードへワンクリックで一括投入。ラボロード時に対応テンプレートが自動選択
  される（名前一致 or ノード集合一致）ため、汎用名のラボでも機能する。
- **トポロジ表示** — YAML 駆動のリンク描画をインタラクティブな Cytoscape.js
  キャンバス上で表示。
- **ノード別ターミナル** — WebSocket ベースの `xterm.js` コンソールを各ノードへ。
- **ノード詳細パネル** — 選択ノードから SSH / API 経由でライブ情報を取得。
- **Export for MCP** — ラボを記述した `.md`（接続 PC の実ネットワーク状態を含む）
  を生成し、Claude Desktop に添付できる。
- **YAML インポート / エクスポート** — トポロジファイルの相互変換。

### MCP サーバー (clab-mcp)
Streamable HTTP で `:8765` に公開され、`mcp-remote` 経由で Claude Desktop から
利用できます。ツール:

- `get_node_facts` — ノードの基本情報。
- `get_node_config` — running config。
- `run_show` — 読み取り専用の `show` コマンド実行。
- `apply_config` — 設定投入（既定で `dry_run`）。
- `rollback` — 直前の変更をロールバック。

## アーキテクチャ

- **backend/** — `NodeDriver` 抽象を持つ FastAPI アプリ
  (`drivers/aoscx.py`, `drivers/vjunos_switch.py`, `drivers/linux.py`)。
  ContainerLab の `kind` で振り分け。
- **frontend/** — Cytoscape.js + xterm.js を使う Vanilla JS の SPA (`app.js`)。
- **mcp_server/** — FastMCP サーバー（Streamable HTTP、ポート 8765）。
- **ContainerLab** が `vrnetlab/vr-aoscx` と `vrnetlab/juniper_vjunos-switch`
  でラボを管理。

デバイス操作経路:

- **AOS-CX** — 情報取得は REST API v10.16（Cookie ログイン）、
  `show` / `running-config` / `configure terminal` は SSH。
- **vJunos** — NETCONF（ポート 830）+ PyEZ (`junos-eznc`)。設定は
  load → diff → commit、rollback 可。

## テンプレート (`configs/defaults/`)

| カテゴリ | テンプレート |
| --- | --- |
| AOS-CX 標準 | `simple-l2`, `spine-leaf`, `vsx-mclag`, `auth-verify-radius` |
| vJunos | `junos-p2p` |
| マルチベンダー (CX × Junos) | `cx-junos-interop`, `cx-junos-p2p-l2`, `cx-junos-p2p-ospf`, `cx-junos-ospf-pc-demo` |
| EVPN-VXLAN (All-CX) | `evpn-allcx-dynamic`, `vxlan-allcx-static`, `allcx-underlay-demo` |
| EVPN-VXLAN (マルチベンダー) | `evpn-mv-dynamic`, `evpn-mv-underlay-demo` |

## EVPN-VXLAN の知見

- **`vr-aoscx` 10.16.1006 で EVPN Dynamic VTEP が動作する。** 鍵は BGP neighbor
  への **`send-community extended`** の設定。EVPN の route-target は Extended
  Community で運ばれるため、これが無いと VTEP が生成されない。
- 確認は `show interface vxlan vteps`: **Origin = evpn** / **Status =
  operational** を確認する。
- **vJunos Spine を EVPN Route Reflector**、**AOS-CX Leaf を VTEP** とする
  マルチベンダー構成で Dynamic VTEP が動作することを実証済み。

## 必要環境

- ContainerLab が動く Linux ホスト（KVM 対応推奨）。
- Docker。
- ローカル Docker にインポート済みのコンテナイメージ:
  - `vrnetlab/vr-aoscx:10.16.1006`
  - `vrnetlab/juniper_vjunos-switch:25.4R1.12`
- Python 3.11+。
- Node.js（Claude Desktop が使う `mcp-remote` 用）。

> アプライアンスイメージ（`.ova` / `.qcow2`）は本リポジトリに **含まれません**。

## クイックスタート

### GUI

```bash
cp .env.example .env        # 認証情報を調整
docker compose up -d --build
# http://<host>:8888 を開く
```

### MCP サーバー

```bash
systemctl start clab-mcp     # Streamable HTTP を <host>:8765/mcp で公開
```

その後、`mcp-remote` 経由で Claude Desktop から接続する（キー `clab-mcp`）:

```json
{
  "mcpServers": {
    "clab-mcp": {
      "command": "npx",
      "args": ["mcp-remote", "http://<host>:8765/mcp", "--allow-http"]
    }
  }
}
```

典型的な流れ: GUI で **Export for MCP** を選択 → 生成された `.md` を Claude
Desktop に添付 → 自然言語でノードを操作。

> ラボデータとランタイム config は `~/claude/cx-clab/`（`labs/` と `configs/`）
> 配下にあり、**git 管理外** です。

## ディレクトリ構成

```
backend/           FastAPI アプリ + NodeDriver 抽象
frontend/          ブラウザ GUI (Cytoscape.js + xterm.js)
mcp_server/        Claude MCP サーバー (FastMCP)
configs/defaults/  テンプレート config セット
Dockerfile         GUI イメージをビルド (containerlab + docker CLI を同梱)
docker-compose.yml
```

## セキュリティ

- 実際の秘密情報は **決してコミットしない**。`.gitignore` で実 `.env`、
  `labs/` ランタイム成果物、vendoring した `vrnetlab/`、大容量のアプライアンス
  イメージを除外している。
- 同梱の `configs/` は **ラボのデフォルト**: RADIUS 共有シークレットはプレース
  ホルダ、ログインはベンダー工場出荷値（`admin/admin`、`admin/admin@123`）。
  **ラボ以外で使う前に必ず変更すること。**
- ラボ内部 IP は、すぐに再現できるようそのまま残してある。

## ライセンス

社内ラボ用途。
