# 画面確認のシナリオ（自作プラグインの検証手順）

画面を開く操作（`trigger_action` / `click_widget`）は**遅延実行**で、結果は少し遅れて現れる。
`run_recipe` は同期実行なのでこれを待てない。そのため、画面を伴う確認は **クライアント（AI）が 1 手ずつ**進める。
同期で完結する検査（起動口の存在確認など）だけを recipe にする。

各プラグイン固有のシナリオは、そのプラグイン自身のリポジトリ（`docs/` など）に置くことを推奨する。
このファイルは汎用の型と、実機で確認済みの例（MORIZON Reloaded）を示す。

## 型

| 手順 | ツール | 確認すること |
|---|---|---|
| 1. 起動口の確認 | `run_recipe check_plugin_entrypoints` | プラグインが有効で、起動口の項目が 1 件ずつ有効 |
| 2. 画面を開く | `trigger_action`（項目の表示テキスト、または `object_name`） | 応答が即時に返る（`deferred: true`） |
| 3. 待つ | `wait` 1〜2 秒 | - |
| 4. 開いたか | `list_windows` | 期待するクラス名・タイトルのウィンドウがある |
| 5. 中身 | `dump_widgets`（`only_named: true` が見やすい） | タブ名・主要部品が期待どおり |
| 6. 見た目 | `screenshot` | 表示崩れ・文字化け・エラー表示がない |
| 7. 操作 | `set_widget` / `click_widget` | 値の反映、押した結果 |
| 8. 後始末 | `close_window`、または「キャンセル」を `click_widget` | モーダルが残っていない（`list_windows` で確認） |
| 9. ログ | `read_log`（`level: warning`） | 手順中に新しい warning 以上がない |

注意:
- 同じ名前の項目が複数ある場合（サブメニューとボタンなど）、`trigger_action` は候補付きでエラーを返す。`index` か `object_name` で指定する。サブメニューは実行できない。
- 再読込の直後は QAction の数が落ち着かない。`reload_plugin` → 2 秒待つ → `list_actions` の順で確認する。
- 設定ダイアログの値を変えて確認する場合は、最後に必ず「キャンセル」で閉じる（保存しない）。

## 例: MORIZON Reloaded（実機確認済み 2026-10-24 / QGIS 3.44.13 / rc6）

1. `run_recipe check_plugin_entrypoints` に `{"plugin": "MORIZON", "actions": ["MORIZON Reloaded を起動", "MORIZON Reloaded 設定"]}`
2. `trigger_action` に `text: "MORIZON Reloaded を起動"` → メインダイアログが開いた
3. `list_windows` → クラス `ForestZoningMainDialog`、タイトル `MORIZON Reloaded`（非モーダル）
4. `dump_widgets` → `tabWidget` のタブ: 要素計算 / スコアリング / ゾーニング / 集計 / 印刷。ヘッダの `reloadedBuild` にバージョン表示
5. `screenshot` → 入力欄・チェックボックス・「実行」ボタン（必須入力が未設定のため無効）が表示
6. `close_window` で閉じた

※ 手順 1 の recipe も実機で実行済み（正常、存在しない項目、存在しないプラグインの 3 ケースで期待どおり）。

## 例: 森林資源メッシュ用国土基本図図郭作成（forest_map_sheet_generator 0.1.0-rc3 / プローブ rc7 で実機確認 2026-10-24）

前提: 対象プラグイン側のダイアログ入力に objectName が付いていること（rc3 で付与。無いと `dump_widgets` で名前なしの部品として並ぶだけで、狙って操作できない）。

0. ZIP を入れ替えた直後は、再起動する前に `run_recipe check_plugin_metadata` に `{"plugin": "forest_map_sheet_generator"}`。`metadata.txt` の必須項目（特に `description`）が欠けていると、手動の読み込みでは動くのに、再起動後に自動で読み込まれない（rc3 で実機確認。rc4 で修正）
1. `run_recipe check_plugin_entrypoints` に `{"plugin": "forest_map_sheet_generator", "actions": ["森林資源メッシュ用国土基本図図郭作成"]}`（再起動後に `active:false` だった場合は、起動ログ（QGIS の「ログメッセージ → プラグイン」）にメタデータのエラーが出ていないか確認する）
2. `trigger_action` に `text: "森林資源メッシュ用国土基本図図郭作成"` → モーダルダイアログ（`forestMapSheetGeneratorDialog`）が開く
3. `run_recipe check_dialog_widgets` に `{"window": "forestMapSheetGeneratorDialog", "widgets": ["targetMethodCombo", "mapCodeEdit", "gridTypeCombo", "zoneModeCombo", "manualZonesEdit", "zoneLayerCombo", "zoneDataVersionEdit", "outputGpkgFile", "buttonBox"]}`（ページ切替で隠れている部品も `visible_only=false` で確認する）
4. `set_widget`: `mapCodeEdit = "04HE"`、`gridTypeCombo = "森林用4分割"`、`zoneModeCombo = "手動（1～19、カンマ区切り）"`、`manualZonesEdit = 4`（数値でも文字列でも入る。rc7 以降）
5. `zoneModeCombo = "適用区域レイヤで自動判定"` → 下のページが「適用区域レイヤ」のコンボに切り替わる。`screenshot` で確認
6. `close_window` で閉じる。**OK（`buttonBox`）は押さない**: 押すと図郭の生成・GeoPackage への書き込みが走る

注意: 生成まで確認する場合は、出力先を使い捨ての `.gpkg` にし、事前にユーザーの許可を得ること。

