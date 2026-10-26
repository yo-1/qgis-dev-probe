# 取扱説明書

導入済み（[SETUP.md](SETUP.md)）の環境で、日常の使い方をまとめます。ツールの引数は MCP サーバーの定義（`src/qgis_dev_probe_mcp/server.py`）が正です。

> 開発専用です。実機確認済みの範囲は [VERIFY.md](VERIFY.md)。

## 1. 基本の流れ

1. QGIS で「サーバー起動 / Start server」を押す（状態が `実行中 / RUNNING`）。
2. クライアントで `ping` を実行し、つながっていることを確認する。
3. 観察する（`list_windows` → `dump_widgets` → `screenshot` → `read_log`）。
4. 操作が必要なときだけ、QGIS 側でモードを `interactive` にする。
5. 終わったらモードを `readonly` に戻し、「サーバー停止」を押す。

## 2. モードと権限

| 区分 | できること | 条件 |
|---|---|---|
| observe | 参照のみ（ウィンドウ・部品・レイヤ・ログ・プラグイン一覧など） | 常時（`readonly`） |
| act | 入力・クリック・メニュー項目の実行・レイヤ追加と削除・Processing 実行・プラグイン再読込・レシピ実行 | モード `interactive` |
| exec | `execute_code`（任意の Python の実行） | `interactive` + このセッションの許可チェック |

条件を満たさない呼び出しは `policy_denied` で拒否されます。

### `execute_code` を許可する手順

1. モードを `interactive` にする。
2. ダイアログの「execute_code を許可 / Allow execute_code」にチェックを入れる。
3. 使い終わったらチェックを外す。

- この許可は**保存されません**。QGIS を再起動すると無効に戻ります。
- 任意の Python をそのまま実行します。読み取りだけで済む確認でも、まずは observe 系のツールで足りないか検討してください。

### 操作対象の制限(Window allowlist)

ダイアログの「対象ウィンドウの制限 / Window allowlist」に、objectName またはタイトルをカンマ区切りで入れると、操作系のツールの対象をそのウィンドウに限れます。空欄は制限なしです。サーバー停止中のみ編集できます。

## 3. ツール一覧

| ツール | 区分 | 用途 |
|---|---|---|
| `ping` | observe | 接続確認（プラグインのバージョン、モード、QGIS の PID） |
| `get_info` | observe | QGIS / Python / Qt のバージョン、プロファイル、プロジェクト、出力先 |
| `list_windows` | observe | トップレベルのウィンドウ一覧（objectName、タイトル、クラス、モーダルか） |
| `dump_widgets` | observe | ウィンドウ内の部品の一覧 |
| `list_actions` | observe | メニュー項目・ツールバーの QAction の一覧 |
| `screenshot` | observe | QGIS 本体・ウィンドウ・部品の画像 |
| `list_layers` / `inspect_layer` | observe | レイヤ一覧 / フィールド、ジオメトリ、サンプル地物など |
| `list_algorithms` / `get_algorithm_params` | observe | Processing アルゴリズムの検索 / パラメータ定義 |
| `list_plugins` | observe | インストール済みプラグインとバージョン、有効かどうか |
| `read_log` | observe | QGIS のメッセージログ（プローブ起動後の分） |
| `list_recipes` | observe | レシピの一覧 |
| `set_widget` | act | 部品に値を入れる |
| `click_widget` | act | ボタン・チェックボックスなどを押す |
| `trigger_action` | act | メニュー項目などの QAction を実行する |
| `close_window` | act | ウィンドウを閉じる |
| `add_layer` / `remove_layer` | act | ローカルのレイヤの追加 / プロジェクトからの削除 |
| `run_algorithm` | act | Processing の同期実行（実行中は QGIS の画面が止まる） |
| `reload_plugin` | act | 別のプラグインの再読込（`qgis_dev_probe` 自身は不可） |
| `run_recipe` | exec | レシピの実行（任意コードの実行と同等のため exec 区分） |
| `execute_code` | exec | 任意の Python の実行 |
| `wait` | (MCP 側のみ) | 指定秒数の待機（最大 60 秒） |

## 4. 使い方のコツ

### 画面を開いて確認する

`click_widget` と `trigger_action` は**遅延実行**で、結果が出る前に応答が返ります。モーダルダイアログを開いても応答が止まりません。次の順で、1 手ずつ確認します。

`trigger_action` → `wait`(1〜2 秒) → `list_windows` → `dump_widgets` → `screenshot` → `close_window`

具体例は [SCENARIOS.md](SCENARIOS.md)。

### 部品の指定は objectName を優先する

`set_widget` と `click_widget` は、objectName での指定を優先します。表示テキストは代替です。名前のない部品は狙って操作できません。検証対象のプラグインの UI には、`objectName` を付けてください（[DESIGN.md](DESIGN.md)）。

### `set_widget` の注意点

- 無効・非表示・読み取り専用の部品は、操作を拒否されます。
- コンボボックスは、表示名でも内部値でも選べます。存在しない項目は、候補つきのエラーになります。
- 数字だけの値（`4` など）も、テキスト入力に入ります。
- 設定ダイアログの値を変えて確認した場合は、最後に必ず「キャンセル」で閉じてください（保存しない）。

### 変更を保存しない・書き出さない

OK ボタンの押下は、保存や書き込みを伴うことがあります。検証対象が GeoPackage などへ書き出す場合は、事前に出力先を使い捨てのファイルにし、利用者の許可を得てから押してください。

### 長い処理

`run_algorithm` と `run_recipe` は、`timeout_s`（既定 600 秒）を指定できます。実行中は QGIS の画面が止まります。

## 5. レシピ（検証手順を再利用する）

レシピは、`def run(ctx, args)` を持つ Python ファイルです。検証対象のプラグイン固有の手順は、そのリポジトリに置きます。

```python
"""一行目が list_recipes に表示される説明。"""


def run(ctx, args):
    info = ctx.call("get_info")          # 他のツールを呼ぶ
    ctx.log(f"QGIS {info['qgis_version']}")
    return {"ok": True}                    # JSON にできる値を返す
```

- `ctx` は `iface`、`project`、`call(tool, **kwargs)`、`log(msg)` を持ちます。
- 実行は**同期**です。画面を開いて結果を待つ手順（遅延実行）は、レシピに入れず、クライアントが 1 手ずつ進めます。
- 実行のたびにソースを読み直すので、編集がすぐ反映されます。
- ファイル名は英数字・`_`・`-` のみです。フォルダはダイアログの「レシピ フォルダ」で指定します（停止中のみ）。
- **信頼できるフォルダだけ**を指定してください。

同梱例（`recipes_example`）:

| レシピ | 用途 |
|---|---|
| `smoke_test` | 疎通確認（バージョン取得、グリッド作成） |
| `check_plugin_entrypoints` | プラグインが有効で、起動口（メニュー項目）があるか |
| `check_plugin_metadata` | プラグインの `metadata.txt` の必須項目の確認。ZIP を入れ替えたら、再起動前に実行 |
| `check_dialog_widgets` | 開いているダイアログに必要な objectName が揃い、有効か |
| `reload_and_check` | プラグインを再読込し、その間に QGIS ログへ出た warning 以上を返す |
| `example_open_layer_and_buffer` | ベクターレイヤを追加して `native:buffer` を実行する例 |

## 6. 検証対象のプラグインを更新したとき

1. ZIP を入れ替えた場合は、再起動前に `check_plugin_metadata` を実行します。
2. コードだけを変えた場合は、`reload_plugin` で再読込します（QGIS の再起動は不要です）。
3. 再読込の直後は、QAction の数が落ち着きません。2 秒待ってから `list_actions` で確認します。

## 7. 使い終わったら

- モードを `readonly` に戻し、`execute_code` のチェックを外します。
- 「サーバー停止」を押します。
- 開いたままのダイアログがないか、`list_windows` で確認します。

## 8. 既知の制約

- 未確認: Codex、他の QGIS バージョン、他の OS、HiDPI の別環境（[VERIFY.md](VERIFY.md)）。
- `screenshot` の画像表示は、クライアントによって差がある可能性があります。ファイルのパスもテキストで返ります。
- `run_algorithm` は同期実行で、実行中は QGIS の画面が止まります。非同期の Processing は対象外です。
- 複数の QGIS の同時制御、リモート接続は対象外です。
