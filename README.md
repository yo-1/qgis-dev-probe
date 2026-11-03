# qgis-dev-probe

QGIS プラグイン開発者向けの**開発専用**ツール。AI クライアント（Claude Desktop / Claude Code / Codex）から、実機の QGIS を観察・操作して**実機検証**できるようにします。

- QGIS 側: 開発用プラグイン `qgis_dev_probe`（localhost のみで待受。**既定は停止**）
- AI 側: stdio の MCP サーバー `qgis-dev-probe-mcp`

> **ステータス: 0.1.3 / 実機検証済み。** 公式プラグインリポジトリで 0.1.2 を公開中。0.1.3 は 2026-11-01 に提出し、手動レビュー待ち。Windows 11 + QGIS 3.44.13 で、Claude Desktop・Claude Code・Codex（デスクトップ）の接続、GUI の観察・操作、スクリーンショット、Processing 実行、プラグイン再読込、コード実行の許可ゲートまで実機で確認済みです。他の QGIS バージョン・macOS は未確認です。確認項目は [docs/VERIFY.md](docs/VERIFY.md)。

English summary: [English](#english).

## English

**QGIS Dev Probe** is a **development-only** bridge that lets an AI client (Claude Desktop / Claude Code / Codex) inspect and operate a real, running QGIS over MCP, so the AI can verify on the actual machine that the plugin it built really works.

- QGIS side: the `qgis_dev_probe` plugin (listens on localhost only, **stopped by default**)
- AI side: a stdio MCP server, `qgis-dev-probe-mcp`

> **Status: 0.1.3 / verified on a real machine.** Version 0.1.2 is published on the QGIS plugin repository; 0.1.3 was submitted on 2026-11-01 and is awaiting manual review. Verified on Windows 11 + QGIS 3.44.13 with Claude Desktop, Claude Code, and Codex (desktop): connection, GUI inspection and operation, screenshots, Processing runs, plugin reload, and the permission gates for code execution. Other QGIS versions and macOS are untested. See [docs/VERIFY.md](docs/VERIFY.md).

### What it does

| Class | Tools | Required permission |
|---|---|---|
| observe | ping, get_info, list_windows, dump_widgets, list_actions, screenshot, list_layers, inspect_layer, list_algorithms, get_algorithm_params, list_plugins, read_log, list_recipes | Always (readonly) |
| act | set_widget, click_widget, trigger_action, close_window, add_layer, remove_layer, run_algorithm, reload_plugin | `interactive` mode |
| exec | execute_code, run_recipe | `interactive` + per-session opt-in |
| local | wait (MCP side only) | - |

A typical check — open a dialog, inspect its widgets, take a screenshot, close it — is described in [docs/SCENARIOS.md](docs/SCENARIOS.md). Plugin-specific checks are written as **recipes** (Python files with `def run(ctx, args)`) kept in the target plugin's own repository and run with `run_recipe`; this tool does not depend on any specific plugin.

### Requirements

- QGIS 3.44 (`qgisMinimumVersion` is 3.44). Other versions are untested.
- MCP side: Python 3.10+, `mcp>=2.3,<3` (not compatible with the v1 `FastMCP` line).
- A client that can launch a local stdio MCP server. Browser and smartphone clients cannot use this bridge (they only accept remote HTTPS connectors, and the bridge is localhost-only by design). Which client forms work is summarized at the top of [docs/CLIENTS.md](docs/CLIENTS.md).

### Setup (short version)

1. Install the plugin from the QGIS plugin repository (Plugins → Manage and Install Plugins → search "QGIS Dev Probe"), or build the ZIP with `python scripts/package_plugin.py` and install from ZIP.
2. Install the MCP server in a clone of this repository: `python -m venv .venv`, then `pip install -e .`
3. Register the server in your client (see [docs/CLIENTS.md](docs/CLIENTS.md)), start QGIS, open "Plugins → QGIS Dev Probe" and press "Start server". Use `interactive` mode only when needed.

Full instructions and troubleshooting: [docs/SETUP.md](docs/SETUP.md) (in Japanese). Usage: [docs/USAGE.md](docs/USAGE.md) (in Japanese).

### Safety design (summary)

- Binds to 127.0.0.1 / ::1 only. A per-start token in `endpoint.json` (0600 on POSIX) is verified on every connection.
- Stopped and `readonly` by default. The `execute_code` opt-in is never persisted and resets when QGIS restarts.
- Screenshot output paths are fixed; callers cannot choose them.
- This plugin contains two intentional `exec()` uses (the session-gated `execute_code` tool and local recipe loading), which are core to its purpose.
- **Development machines only.** Do not install on shared or production QGIS setups. Threat model: [SECURITY.md](SECURITY.md).

### License

MIT (provisional).

## できること

| 区分 | ツール | 必要な権限 |
|---|---|---|
| observe | ping, get_info, list_windows, dump_widgets, list_actions, screenshot, list_layers, inspect_layer, list_algorithms, get_algorithm_params, list_plugins, read_log, list_recipes | 常時（readonly） |
| act | set_widget, click_widget, trigger_action, close_window, add_layer, remove_layer, run_algorithm, reload_plugin | モード `interactive` |
| exec | execute_code, run_recipe | `interactive` + セッション限りの許可チェック |
| local | wait（MCP 側のみ） | - |

画面を開いて確認する手順（`trigger_action` → `list_windows` → `dump_widgets` → `screenshot` → `close_window`）は [docs/SCENARIOS.md](docs/SCENARIOS.md)。

検証対象プラグイン固有の手順は、そのプラグインのリポジトリに置く **recipe**（`def run(ctx, args)` の Python ファイル）を `run_recipe` で呼びます。このツール自体は特定プラグインに依存しません。

## 前提

- QGIS 3.44 想定。他バージョンは未確認。`metadata.txt` の qgisMinimumVersion も 3.44 としています。
- MCP 側: Python 3.10+、`mcp>=2.3,<3`（v1 系 `FastMCP` とは非互換）。
- 対応クライアント: stdio で MCP サーバーを起動できるもの。**ChatGPT の Web/アプリは対象外**（リモート HTTPS コネクタのみのため）。詳細は [docs/CLIENTS.md](docs/CLIENTS.md)。

## セットアップ（概要）

1. プラグイン: QGIS のプラグイン管理で「QGIS Dev Probe」を検索してインストールします（公式プラグインリポジトリ）。開発用は `python scripts/package_plugin.py` で ZIP を作り、「ZIP からインストール」でも入れられます。
2. MCP サーバー: このリポジトリを clone し、仮想環境に `pip install -e .` で入れます。
3. クライアントに MCP サーバーを登録し（[docs/CLIENTS.md](docs/CLIENTS.md)）、QGIS のメニュー「プラグイン → QGIS Dev Probe（開発用・AI実機検証）」から「サーバー起動 / Start server」を押します。モードは必要なときだけ `interactive` にします。

詳しい手順とトラブルシューティングは [docs/SETUP.md](docs/SETUP.md)、使い方は [docs/USAGE.md](docs/USAGE.md)。

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
