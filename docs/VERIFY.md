# 実機確認チェックリスト（QGIS 3.44）

✅ = 自動テスト済み（偽物ではなく実ソケット/実 MCP）。⬜ = 実機で未確認。**⬜ が残る間は「動作確認済み」と書かないこと。**

## 自動テストで確認済み
- ✅ プロトコル、トークン検証、ポリシー、JobQueue、dispatcher、ソケットサーバー（loopback 限定・サイズ上限）
- ✅ widgets のロジック（偽ウィジェット）、recipes、config/endpoint、MCP クライアント、MCP stdio e2e（偽ハンドラ）

## 実機確認の結果（2026-10-24 / Windows 11 / QGIS 3.44.13 / Qt 5.15.13 / QGIS 内 Python 3.12.13）

| # | 項目 | 結果 |
|---|---|---|
| 1 | ロード・メニュー登録 | ✅ ロード・メニュー表示。再読込でも QAction が重複しない（行21） |
| 2 | Start/Stop、`endpoint.json` | ✅ |
| 3 | **モーダル表示中に応答する** | ✅ オプション/プロジェクトプロパティ表示中に `list_windows` 等が応答 |
| 4 | `click_widget` が開くモーダルの後続操作 | ✅ ボタンクリック→モーダル→`screenshot`→`キャンセル`クリック→閉じる、まで通った |
| 5 | `dump_widgets` / `set_widget` | ✅ QgsDoubleSpinBox・QCheckBox の set と復元。rc4: QLineEdit / QgsFilterLineEdit（日本語）・QgsSpinBox・QTabWidget（タブ名指定）・QComboBox（表示名指定、存在しない項目はエラーで候補を返す）・無効ウィジェットの拒否・QRadioButton の click で後続コンボが有効化、を確認。rc7: チェック付き `QgsCollapsibleGroupBox`（オプション → ネットワークの `grpProxy`）をオン→オフに切替でき、中の入力が連動して有効化されることを確認（保存せず Cancel で閉じた）。数字だけの文字列（"4"）も QLineEdit に入る（rc7 で修正） |
| 6 | `screenshot` | ✅ ウィンドウ/モーダル。Claude Desktop 上で画像が表示された。⬜ HiDPI 別環境 |
| 7 | `run_algorithm` | ✅ 成功（`native:creategrid`）・失敗（`algorithm_failed` + ログ）。⬜ 入力レイヤ付きの実行 |
| 8 | `reload_plugin` | ✅ `db_manager` で unload→load→start が成功。コード変更の反映は行18で確認。`qgis_dev_probe` 自身は設計どおり拒否 |
| 9 | `QgsProcessingFeedback` サブクラス | ✅ ログ収集は動作。⬜ `Qgis.ProcessingParameterFlag.Optional` の分岐（`optional` が返ることは確認） |
| 10 | メッセージログ連携 | ✅ `read_log` に QGIS のメッセージ・Python 警告が入る |
| 11 | 設定保存・`allow_exec` 非保存 | ✅ モード・レシピフォルダ等の設定は再起動後も維持（rc4）。`allow_exec`: 許可にチェック → QGIS を再起動 → 設定ダイアログでチェックが外れていることを確認（rc7、利用者の目視報告。再起動後はサーバー停止のため `policy_denied` の応答までは未確認） |
| 12 | クライアント接続 | ✅ Claude Desktop（`ping`/`list_windows`/`screenshot`/`list_actions`/`trigger_action`）。Claude Code（v2.1.310）: `claude mcp add` → `claude mcp list` で Connected、`/login` 後に `list_actions` を実行し 10 件取得を確認（rc6）。⬜ Codex |
| 13 | GitHub Actions CI | ✅ 10 回連続で成功（rc6 時点、利用者の画面で確認）。以降の push 分は未確認 |
| 14 | Stop→Start 後の応答 | ✅（修正後）。修正前は全ツールがタイムアウトした不具合を発見・修正 |
| 15 | メニュー項目/QAction の操作 | `click_widget` は QAction 非対応（仕様）。rc6 で `list_actions` / `trigger_action` を追加。✅ 実機確認: `list_actions` で MORIZON / Dev Probe の項目を取得、`trigger_action` で「MORIZON Reloaded を起動」→ メインダイアログが開き、`screenshot` / `dump_widgets` / `close_window` まで通った |
| 21 | 再読込で QAction（メニュー/ツールバー）が重複しない | ✅ MORIZON を再読込しても、落ち着いた状態では 3 件のまま（2 回確認）。**同期の直後に数えると 2〜5 件とぶれる**（Qt の遅延削除・遅延生成）ため、手順は「`list_actions` → `reload_plugin` → 2 秒待つ → `list_actions`」。同期 recipe で数える設計は誤検出したので採用しない |
| 16 | `run_recipe` | ✅ `smoke_test`・`reload_and_check`（正常/引数不足/存在しない recipe のエラー）。rc2 |
| 17 | `execute_code` | ✅ 既定は `policy_denied`、ダイアログで許可すると実行でき、外すと再び拒否（rc2、rc7 でも再確認: 読み取りだけのコードで QGIS/Python のバージョンを取得 → チェックを外すと `policy_denied`）。`qgis.utils.unloadPlugin` のソース取得にも使用 |
| 18 | `reload_and_check` で自作プラグインの**コード変更が反映される**か | ✅ 最小デモ（`__init__.py` のみ）で、`VERSION A`→`VERSION B` 編集後に再起動なしで反映を確認（0.1.0-rc2, QGIS 3.44.13）。さらに実プラグイン（morizon_next、サブモジュール多数）の `constants.py` に追記→反映、復元→消えることも確認。`modules_purged` は 0 のままだが反映される。理由は、QGIS 3.44.13 の `unloadPlugin` が `_unloadPluginModules(packageName)` を呼ぶため（`execute_code` + `inspect.getsource` で確認）。自前パージは保険として維持 |
| 19 | `dump_widgets` が `QScrollArea` の中を返す | ✅ rc3 では 15 件（中身ゼロ）→ rc4 で 42 件（オプション画面の部品が見えた）。原因は `qt_scrollarea_viewport` の一律除外 |
| 20 | 日本語併記ダイアログ（rc4）・日本語名（rc5） | ✅ rc4 の表示を確認（右パネル、モード日本語併記、再起動後も設定維持）。rc5: プラグイン管理の一覧・詳細に日本語名（`QGIS Dev Probe（開発用・AI実機検証ブリッジ）`）と説明が表示されることを確認 |
| 22 | recipe `check_plugin_entrypoints` | ✅ MORIZON で正常（ok）、存在しない項目（`action not found`）、存在しないプラグイン（`plugin is not installed`）を確認（rc6）。画面を開く手順は [SCENARIOS.md](SCENARIOS.md) |
| 23 | 他人のプラグインのダイアログ操作（森林資源メッシュ用国土基本図図郭作成 0.1.0-rc3） | ✅ `trigger_action` でモーダルを開き、`dump_widgets` で objectName 付き入力を取得、`set_widget` でコード入力・コンボ切替（stacked page 連動）・`screenshot`・`close_window` まで確認（rc6）。❗ 数字だけの文字列（"4"）が数値化されて拒否される不具合を発見 → rc7 で修正し、✅ rc7 で `系番号 = 4` の入力と「適用区域レイヤで自動判定」ページへの切替を実機確認。再起動後に対象プラグインが無効（active:false）のままだったため `reload_plugin` で読み込んだ（原因は未調査） |
| 24 | recipe `check_plugin_metadata` | ✅ 実機: 森林プラグイン rc4・MORIZON・qgis_dev_probe は ok、存在しないプラグインは `metadata not readable` で ok:false。⬜ 「項目が欠けた実物」での検出は未確認（単体テストのみ: 偽の `qgis.utils` で description 欠落・空値を検出）。背景の実機所見: `description` が無い 0.1.0-rc3 は、ZIP 直後は動くが再起動後は自動で読み込まれず、起動ログに「メタデータを読み込み中にエラー」。rc4 で追加して解消（再起動で確認済み） |

## 実機で見つかった不具合（単体テストでは検出できなかったもの）
- rc2: Stop→Start 後に全ツールがタイムアウト（修正済み）。
- rc3: `QgsFilterLineEdit` が `setValue` を持つためスピンボックス扱いされ、`set_widget` が文字列を拒否（修正済み）。
- rc4: `QScrollArea` の中身が `dump_widgets` / `find_widget` から見えない（修正済み）。

## 既知の課題
- MCP サーバー側（`src/qgis_dev_probe_mcp`）のコードを更新したら、クライアント（Claude Desktop など）を完全に終了して再起動する。起動済みのサーバープロセスは古いコードのまま動き続け、新しいツールが見えない。
- QGIS 本体の `dump_widgets` は非表示が大量。`visible_only`（既定 true）で対処済み。
- `LocatorWidget` など `set_value` 非対応のクラスは明示エラーになる。

## API 確認表（handlers.py が使用）
`Qgis.version/versionInt`, `QgsApplication.qgisSettingsDirPath/processingRegistry/messageLog`, `QgsProject.mapLayer/mapLayersByName/addMapLayer/removeMapLayer`, `QgsVectorLayer.featureCount/getFeatures/subsetString`, `QgsRasterLayer.dataProvider().sourceHasNoDataValue/sourceNoDataValue`, `QgsWkbTypes.geometryDisplayString/displayString`, `qgis.utils.available_plugins/active_plugins/pluginMetadata/loadPlugin/unloadPlugin/startPlugin`。公式 API ドキュメントで 3.44 の存在・署名を確認すること。
