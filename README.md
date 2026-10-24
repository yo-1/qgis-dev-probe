# qgis-dev-probe

QGIS プラグイン開発者向けの**開発専用**ツール。AI クライアント（Claude Desktop / Claude Code / Codex）から、実機の QGIS を観察・操作して**実機検証**できるようにします。

- QGIS 側: 開発用プラグイン `qgis_dev_probe`（localhost のみで待受。**既定は停止**）
- AI 側: stdio の MCP サーバー `qgis-dev-probe-mcp`

> **ステータス: 0.1.0 / 一部実機検証済み。** Windows 11 + QGIS 3.44.13 + Claude Desktop で主要ツールを確認済み。Claude Code も接続確認済みです。Codex・他の QGIS バージョン・他の OS は未確認です。確認項目は [docs/VERIFY.md](docs/VERIFY.md)。

## できること

| 区分 | ツール | 必要な権限 |
|---|---|---|
| observe | ping, get_info, list_windows, dump_widgets, list_actions, screenshot, list_layers, inspect_layer, list_algorithms, get_algorithm_params, list_plugins, read_log, list_recipes | 常時（readonly） |
| act | set_widget, click_widget, trigger_action, close_window, add_layer, remove_layer, run_algorithm, reload_plugin, run_recipe | モード `interactive` |
| exec | execute_code | `interactive` + セッション限りの許可チェック |
| local | wait（MCP 側のみ） | - |

画面を開いて確認する手順（`trigger_action` → `list_windows` → `dump_widgets` → `screenshot` → `close_window`）は [docs/SCENARIOS.md](docs/SCENARIOS.md)。

検証対象プラグイン固有の手順は、そのプラグインのリポジトリに置く **recipe**（`def run(ctx, args)` の Python ファイル）を `run_recipe` で呼びます。このツール自体は特定プラグインに依存しません。

## 前提

- QGIS 3.44（Qt5）想定。他バージョンは未確認。`metadata.txt` の qgisMinimumVersion も 3.44 としています。
- MCP 側: Python 3.10+、`mcp>=2.3,<3`（v1 系 `FastMCP` とは非互換）。
- 対応クライアント: stdio で MCP サーバーを起動できるもの。**ChatGPT の Web/アプリは対象外**（リモート HTTPS コネクタのみのため）。詳細は [docs/CLIENTS.md](docs/CLIENTS.md)。

## セットアップ（PowerShell 7 / Windows 例）

```powershell
# 1. プラグインの zip を作る
python scripts/package_plugin.py      # dist/qgis_dev_probe-<version>.zip
# 2. QGIS: プラグイン > プラグインの管理とインストール > ZIP からインストール
# 3. MCP サーバーを入れる（仮想環境推奨）
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .
```

QGIS のメニュー「プラグイン → QGIS Dev Probe（開発用・AI実機検証）」を開き、「サーバー起動 / Start server」。モードは必要なときだけ `interactive` にします。
詳しい手順とトラブルシューティングは [docs/SETUP.md](docs/SETUP.md)、使い方は [docs/USAGE.md](docs/USAGE.md)、クライアント設定は [docs/CLIENTS.md](docs/CLIENTS.md)。

## 安全設計（要約）

- 127.0.0.1 / ::1 以外にはバインドしない。接続ごとにトークン検証（`endpoint.json`、POSIX では 0600）。
- 既定は停止 + readonly。`execute_code` の許可は保存されず、QGIS 再起動で失効。
- スクリーンショットの出力先は固定（呼び出し側はパス指定不可）。
- `exec()` の使用は 2 箇所のみで、いずれもこのプラグインの目的上必要な機能です。`execute_code`（セッションごとの明示許可制）と、ユーザーがローカルに置いたレシピファイルの読込です。This plugin contains two intentional `exec()` uses (the session-gated `execute_code` tool and local recipe loading), which are core to its purpose.
- **開発機専用。** 共有・本番の QGIS には入れないでください。脅威モデルは [SECURITY.md](SECURITY.md)。

## 開発

```bash
python -m unittest discover -s tests -t . -v
ruff check .
```

構成と設計判断: [docs/DESIGN.md](docs/DESIGN.md) / プロトコル: [docs/PROTOCOL.md](docs/PROTOCOL.md) / 貢献: [CONTRIBUTING.md](CONTRIBUTING.md)

## ライセンス

MIT（暫定。変更する場合は LICENSE と pyproject.toml を更新）
