# 設計

## 構成

```
AI クライアント ──stdio(MCP)──> qgis_dev_probe_mcp ──TCP(localhost, JSON 行)──> QGIS 内 qgis_dev_probe
                                  (src/)                                       (plugin/)
```

```
plugin/qgis_dev_probe/
  core/        純 Python（QGIS/Qt 非依存・単体テスト済み）: protocol, server, dispatcher, jobqueue, policy, registry, recipes ...
  qgis_side/   QGIS/Qt 依存: handlers（ツール実装）, widgets（ダック型 Qt 操作）, mainthread（QTimer ポンプ）
  plugin.py / dialog.py   ライフサイクル・UI
src/qgis_dev_probe_mcp/  client(同期ソケット), server(MCPServer)
```

## 主な判断

- **汎用 1 本 + recipe**: 検証対象プラグインごとにプローブを作らず、プラグイン固有手順は各リポジトリの recipe に置く。`ctx.call(tool, **kwargs)` で同じツールを組み合わせる。
- **スレッド**: ソケットはワーカースレッド。Qt/QGIS に触る処理は `JobQueue` に積み、メインスレッドの `QTimer` が処理する。`read_log` / `list_recipes` のみスレッド安全なので直接実行。
- **クリックは遅延実行**: `click_widget` と `trigger_action`（メニュー項目・ツールバーの QAction）は `QTimer.singleShot(0, ...)` でクリックを予約して即応答。モーダルダイアログを開くボタンでも応答がブロックされない。
- **widgets.py はダック型**: PyQt を import せず、偽ウィジェットで単体テストできる。無効・非表示・読み取り専用のウィジェットは操作拒否。
- **ポリシー**: observe / act / exec の 3 区分。`registry.py` が唯一の定義元で、MCP 側との一致は `tests/test_registry_sync.py` が検査。
- **recipe 読込**: `compile`/`exec`（`__pycache__` を作らない）。一覧は `ast` のみで実行しない。
- **MCP エラー**: mcp SDK は `ToolError` 以外の例外メッセージをモデルに隠すため、`ProbeClientError` を `ToolError` に変換して code/details を見せる（e2e テストで確認済み）。

## 検証対象プラグインの UI への推奨

`.ui`（Qt Designer）+ **すべての操作対象に安定した `objectName`**。プローブは objectName 指定を優先し、表示テキストはフォールバック。コードで UI を組む場合も `setObjectName` を付ける。プローブ自身の UI は小さく固定なのでコード構築。

## 非対象（現時点）

リモート接続 / HTTPS、複数 QGIS の同時制御、非同期 Processing（`run_algorithm` は同期で UI を止める）、QGIS 4 / Qt6。
