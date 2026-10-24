# Changelog

形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、バージョンは [SemVer](https://semver.org/lang/ja/) に従います。

## [Unreleased]

### Added
- docs/SETUP.md（セットアップマニュアル）、docs/USAGE.md（取扱説明書）。

## [0.1.0] - 2026-10-24

初回リリース。rc1〜rc7 の変更をまとめたもの（個別の経緯は下の rc 項を参照）。コードは rc7 と同じで、バージョン表記のみ 0.1.0 に更新。

### 検証範囲
- 実機検証済み: Windows 11 / QGIS 3.44.13 / Claude Desktop・Claude Code。結果は `docs/VERIFY.md`。
- 未確認: Codex、他の QGIS バージョン、他の OS、HiDPI の別環境。

### Added
- recipe `check_plugin_metadata`: インストール済みプラグインの metadata.txt の必須項目を、再起動せずに確認（description 欠落で再起動後に自動読み込みされなかった実例の再発防止）。
- recipe `check_dialog_widgets`: 開いているダイアログに必須の objectName が揃い、有効かを確認（読み取りのみ）。
- docs/SCENARIOS.md に「森林資源メッシュ用国土基本図図郭作成」の操作手順を追加。

## [0.1.0-rc7] - 2026-10-24

### Fixed
- `set_widget`: テキスト入力（QLineEdit 系・QPlainTextEdit）へ数値を渡すと `value must be a string` で拒否されていた。MCP クライアントが `"4"` を数値 `4` に変換して送るため、「系番号 4」のような入力ができなかった（森林資源メッシュ用国土基本図図郭作成のダイアログで実機確認）。bool・配列・null は引き続き拒否。

## [0.1.0-rc6] - 2026-10-24

### Added
- `list_actions` / `trigger_action`: メニュー項目・ツールバーなどの QAction を一覧・実行（プラグインの起動口は QAction のため、`click_widget` では押せなかった）。実行は遅延し、モーダルを開いても応答が止まらない。サブメニューと無効な項目は拒否。

## [0.1.0-rc5] - 2026-10-24

### Changed
- プラグイン名・説明・メニュー項目に日本語を併記（プラグイン管理で用途が分かるように）。内部名・objectName は不変。

## [0.1.0-rc4] - 2026-10-24

### Added
- ダイアログを日本語＋英語併記にし、右側にバージョン・用途・モード説明・接続情報の場所を表示。表示文言は `core/ui_text.py`（Qt 非依存でテスト可能）。

### Fixed
- `dump_widgets` / `find_widget`: `QScrollArea` の中の部品（`qt_scrollarea_viewport` の子）が見えない問題を修正。オプション画面などで操作できなかった（実機で発見）。

### Changed
- モードのコンボボックスは表示を日本語併記にし、内部値（readonly / interactive）はアイテムデータで保持。`set_widget` は従来どおり内部値でも選べる。

## [0.1.0-rc3] - 2026-10-24

### Fixed
- `set_widget`: `QgsFilterLineEdit` など `setValue` を持つ入力欄がスピンボックス扱いされ、文字列が「数値でなければならない」と拒否される問題を修正（実機で発見）。

## [0.1.0-rc2] - 2026-10-24

### Added
- 同梱 recipe: `smoke_test`（疎通確認）、`reload_and_check`（再読込＋新規エラーログ確認）。

## [0.1.0-rc1] - 2026-10-24

### Added
- QGIS プラグイン `qgis_dev_probe`（localhost ソケットサーバー、メインスレッド実行キュー、ポリシー、トークン認証）。
- GUI 操作ツール: `list_windows` / `dump_widgets` / `set_widget` / `click_widget` / `close_window` / `screenshot`。
- QGIS 操作ツール: レイヤ、Processing、プラグイン再読込、ログ取得、検証レシピ（`run_recipe`）。
- stdio MCP サーバー `qgis-dev-probe-mcp`（MCP Python SDK 2.x の `MCPServer`）。
- `execute_code`（任意コード実行）。既定は無効で、セッション限りの明示的な有効化が必要。

### Fixed
- サーバーを Stop → Start するとメインスレッド系ツールがすべてタイムアウトする不具合（ポンプの `timeout` シグナルを切断していた）。QGIS 3.44.13 実機で発見・修正確認。
- 接続スレッドの `makefile()` を閉じ忘れ、QGIS ログに `ResourceWarning` が出る問題。

### Changed
- `dump_widgets` は既定で非表示ウィジェットを除く（`visible_only=true`）。QGIS 本体のように非表示が大量にあるウィンドウで上限が埋まるため。
- `click_widget` の説明から「action」を削除（QAction・メニュー項目は未対応）。

### Known limitations
- 検証済みは Windows 11 / QGIS 3.44.13 / Claude Desktop のみ。結果は `docs/VERIFY.md`。
