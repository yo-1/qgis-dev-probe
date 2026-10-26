# セットアップマニュアル

初めて導入する人が、**導入 → 起動 → 疎通確認**まで進むための手順です。ツールの使い方は [USAGE.md](USAGE.md)。

> 開発専用です。共有・本番の QGIS には入れないでください（[SECURITY.md](../SECURITY.md)）。
> 実機確認済みの環境: Windows 11 / QGIS 3.44.13 / Claude Desktop・Claude Code（Windows の手順 2 は Python 3.10.2、Linux の手順 2 は Python 3.12.3 で確認）。Codex・他の QGIS バージョン・macOS は**未確認**です（[VERIFY.md](VERIFY.md)）。

## 0. この文書の約束事（先に読んでください）

### 0-1. どのフォルダで実行するか

コマンドは、**実行したフォルダ（今いる場所）**で動きます。場所を間違えると、`.\.venv\Scripts\python.exe` のような相対パスが見つからず、「用語 '...' は、コマンドレット、関数、スクリプト ファイル、または実行可能プログラムの名前として認識されません」と出ます。

- この文書のコマンドは、**原則として最初の行で `Set-Location`（Bash は `cd`）して、場所を決めます。** ブロックを上から、そのままコピーして実行してください。
- 今いる場所は、`Get-Location`（Bash は `pwd`）で確認できます。PowerShell のプロンプト `PS C:\Users\...>` の `...` も、今いる場所です。
- `.\` は「今いるフォルダ」、`$HOME` は「あなたのホームフォルダ（`C:\Users\<ユーザー名>`）」です。
- 新しい PowerShell を開くと、場所はホームに戻ります。別のウィンドウでは、必ず `Set-Location` からやり直してください。

### 0-2. 2 種類のフォルダ

| 何のフォルダか | この文書での場所 | 決まり方 |
|---|---|---|
| リポジトリの clone（ソース、`.venv`、`dist` など） | Windows: `C:\Users\<ユーザー名>\Documents\qgis-dev-probe`（= `$HOME\Documents\qgis-dev-probe`）<br>Linux / macOS: `$HOME/qgis-dev-probe` | **あなたが決める。** この文書では、上の場所に置く前提で書きます。別の場所にする場合は、文書中の `$HOME\Documents\qgis-dev-probe` を読み替えてください |
| 接続情報（`endpoint.json`） | `C:\Users\<ユーザー名>\.qgis_dev_probe` | **固定。** ユーザーのホーム直下に、プラグインが自動で作る。clone 先とは別の場所です |

`git clone` は、実行したフォルダの下に `qgis-dev-probe` フォルダを作ります。すでに同名のフォルダがあると、失敗します。

### 0-3. 用意するもの

| 部品 | 入れる場所 | 入手方法 |
|---|---|---|
| QGIS プラグイン `qgis_dev_probe` | QGIS | Release の `qgis_dev_probe-<version>.zip` |
| MCP サーバー `qgis-dev-probe-mcp` | AI クライアントを動かす PC | このリポジトリを clone して `pip install -e .` |

```
AI クライアント ─stdio→ qgis-dev-probe-mcp（Python） ─localhost→ QGIS 内の qgis_dev_probe プラグイン
```

QGIS と AI クライアントは**同じ PC・同じ OS ユーザー**で動かします（接続情報のファイルを共有するため）。

## 1. 事前確認

次を、PowerShell 7 で実行します（場所は問いません）。

```powershell
git --version
gh --version
py -3 --version        # Python 3.10 以上と表示されること
python --version       # 版が出ること。「Python」とだけ出るなら、Microsoft Store のエイリアス（下の注意）
```

- QGIS 3.44（Qt5）。`metadata.txt` の qgisMinimumVersion も 3.44 としています。他バージョンは未検証です。
- Python 3.10 以上（MCP サーバー用。QGIS 内蔵の Python とは別です）。
- **Windows の注意:** `python` が `...\WindowsApps\python.exe` を指している場合は、Microsoft Store の案内（アプリ実行エイリアス）で、実体ではありません。この文書では、`py -3` を使います。`py -3 --version` も通らない場合は、python.org から Python を入れてください。
- `mcp>=2.3,<3`（`pip install -e .` で入ります。v1 系の `FastMCP` とは非互換）。
- 対応クライアント: stdio で MCP サーバーを起動できるもの。**ChatGPT の Web/アプリは対象外**です。
- **リポジトリが private の間は、GitHub の認証が必要です。** 認証なしの `git clone` は `could not read Username for 'https://github.com'` で失敗し、Releases の ZIP もログインなしではダウンロードできません。事前に GitHub CLI で認証します（`gh auth login` → `gh auth setup-git`）。認証できない環境には、ソースの zip を別途渡して展開してください（git は不要です）。

## 2. 手順 1: QGIS プラグインを入れる

1. [Releases](https://github.com/yo-1/qgis-dev-probe/releases) から `qgis_dev_probe-<version>.zip` をダウンロードします。ブラウザで入れない場合は、コマンドでも取得できます（`Downloads` の下に `release-check` フォルダを作って保存します）。

```powershell
# PowerShell 7 / 場所は問わない（保存先を絶対パスで指定している）
New-Item -ItemType Directory -Force "$HOME\Downloads\release-check" | Out-Null
gh release download v0.1.0 --repo yo-1/qgis-dev-probe --pattern "*.zip" --dir "$HOME\Downloads\release-check" --clobber
Get-ChildItem "$HOME\Downloads\release-check" | Select-Object Name, Length
```

2. QGIS: プラグイン → プラグインの管理とインストール → ZIP からインストール → 上の ZIP を指定 → プラグインをインストール。
3. 「インストール済み」で `QGIS Dev Probe（開発用・AI実機検証ブリッジ）` にチェックが入っていることを確認します（プラグイン管理の一覧の名前は「ブリッジ」付き、手順 3 のメニュー名は「ブリッジ」なしで、どちらも正しい表記です）。
   - 実験的プラグイン（`experimental=True`）なので、一覧に出ない場合は「設定」で「実験的プラグインも表示する」を有効にします。

ソースから ZIP を作る場合（開発者向け。手順 2 でリポジトリを clone した後に実行します）:

```powershell
# PowerShell 7
Set-Location $HOME\Documents\qgis-dev-probe
Get-Location                                              # ...\Documents\qgis-dev-probe であること
.\.venv\Scripts\python.exe scripts/package_plugin.py      # dist\qgis_dev_probe-<version>.zip ができる
```

```bash
# Bash（Linux / macOS）
cd "$HOME/qgis-dev-probe"
pwd                                                       # .../qgis-dev-probe であること
./.venv/bin/python scripts/package_plugin.py              # dist/qgis_dev_probe-<version>.zip ができる
```

## 3. 手順 2: MCP サーバーを入れる

Windows（PowerShell 7）。**上から順に、そのまま実行します。**

```powershell
# PowerShell 7
Set-Location $HOME\Documents                 # clone 先の親フォルダ。この下に qgis-dev-probe フォルダができる
git clone https://github.com/yo-1/qgis-dev-probe.git
Set-Location $HOME\Documents\qgis-dev-probe
Get-Location                                 # C:\Users\<ユーザー名>\Documents\qgis-dev-probe であること

py -3 -m venv .venv                          # python が Store のエイリアスなので py -3 を使う
Test-Path .\.venv\Scripts\python.exe         # True であること。False なら、ここで止めてトラブルシューティングを見る
.\.venv\Scripts\python.exe -m pip install --upgrade pip   # 仮想環境の中の pip だけを更新する（古い pip では、次の行が失敗する）
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -c "import qgis_dev_probe_mcp as m; print(m.__version__)"   # 0.1.0 と表示される
```

Linux / macOS（Bash）。Linux（Ubuntu 24.04 / Python 3.12.3）で実機確認済みです。

```bash
# Bash
cd "$HOME"                                   # clone 先の親フォルダ。この下に qgis-dev-probe フォルダができる
git clone https://github.com/yo-1/qgis-dev-probe.git
cd "$HOME/qgis-dev-probe"
pwd                                          # .../qgis-dev-probe であること

python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
./.venv/bin/python -c "import qgis_dev_probe_mcp as m; print(m.__version__)"   # 0.1.0 と表示される
```

- 成功の目印: `Successfully installed ... qgis-dev-probe-0.1.0` と、最後の `0.1.0`。**`Defaulting to user installation` が出たら、仮想環境の外に入っています**（`.venv` ができていない）。トラブルシューティングを見てください。
- `git clone` が `could not read Username` で失敗したら、事前確認の GitHub 認証を済ませてから再実行します。`destination path ... already exists` と出たら、すでに同名のフォルダがあります。
- 仮想環境は有効化せず、`.venv` の `python.exe` を直接呼びます。`Activate.ps1` を使わないので、PowerShell の実行ポリシーの影響を受けません。
- 仮想環境の Python のパスは、クライアントへの登録（手順 4）で使います。次のコマンドで、絶対パスを表示できます。

```powershell
# PowerShell 7
(Resolve-Path "$HOME\Documents\qgis-dev-probe\.venv\Scripts\python.exe").Path
```

## 4. 手順 3: サーバーを起動する（QGIS 側）

1. QGIS のメニュー: プラグイン → `QGIS Dev Probe（開発用・AI実機検証）` → `QGIS Dev Probe 設定...`
2. ダイアログの「サーバー起動 / Start server」を押します。
3. 状態が `実行中 / RUNNING  127.0.0.1:<ポート>` になれば成功です。
4. 操作系のツール（入力・クリック・Processing 実行など）を使うときだけ、モードを `interactive` にします。通常は `readonly` のままにしてください。

- 既定は**停止**です。QGIS を再起動すると、サーバーは自動では起動しません。
- 起動のたびに手動で押したくない場合は、QGIS を起動する前に環境変数 `QGIS_DEV_PROBE_AUTOSTART=1` を設定します。
- 接続情報（ポートとトークン）は `C:\Users\<ユーザー名>\.qgis_dev_probe\endpoint.json`（Linux / macOS は `~/.qgis_dev_probe/endpoint.json`）に書かれます。clone 先のフォルダとは別の場所です。**トークンは他人に見せないでください。**

## 5. 手順 4: クライアントに MCP サーバーを登録する

設定の詳細と例は [CLIENTS.md](CLIENTS.md)。要点だけ示します。登録には、手順 2 で表示した**絶対パス**を使います。

**Claude Desktop** — `claude_desktop_config.json` の `mcpServers` に追加し、Claude Desktop を**完全に終了して**起動し直します。JSON の中では、`\` を `\\` と 2 つ重ねます。

```json
{
  "mcpServers": {
    "qgis-dev-probe": {
      "command": "C:\\Users\\<ユーザー名>\\Documents\\qgis-dev-probe\\.venv\\Scripts\\python.exe",
      "args": ["-m", "qgis_dev_probe_mcp.server"]
    }
  }
}
```

**Claude Code**

```powershell
# PowerShell 7
Set-Location $HOME\Documents\qgis-dev-probe      # claude mcp add は、実行したフォルダ限定で登録される（CLIENTS.md 参照）
claude mcp add qgis-dev-probe -- "$HOME\Documents\qgis-dev-probe\.venv\Scripts\python.exe" -m qgis_dev_probe_mcp.server
claude mcp list     # qgis-dev-probe が Connected になれば登録成功
```

**Codex（ChatGPT デスクトップアプリ）** — 画面の操作手順を、スクリーンショット付きで [CLIENTS.md](CLIENTS.md) に書いています（`ping` / `get_info` まで実機で確認済み。CLI と IDE 拡張は未確認）。

## 6. 手順 5: 疎通を確認する

クライアントで次のように依頼します。

1. 「qgis-dev-probe の `ping` を実行して」（QGIS 側でサーバーを起動した後でないと、`[not_running]` になります）→ プラグインのバージョン・モード・QGIS の PID が返れば、接続は成功です。
2. 「`run_recipe` で `smoke_test` を実行して」→ 下の「レシピのフォルダ」を設定していれば、QGIS のバージョン取得と Processing 実行（一時レイヤのグリッド作成）までの一通りを確認できます。プロジェクトは変更しません。

### レシピのフォルダ（任意）

`run_recipe` を使うには、QGIS Dev Probe のダイアログの「レシピ フォルダ / Recipe dir」に、レシピ（`.py`）を置いたフォルダを指定します。同梱例は、リポジトリの `recipes_example` です（`C:\Users\<ユーザー名>\Documents\qgis-dev-probe\recipes_example`）。レシピは任意コードの実行と同等のため exec 区分で、`execute_code` と同じくダイアログの「コード実行を許可」を有効にする必要があります（再起動で無効に戻ります）。

- 設定できるのは**サーバー停止中のみ**です。いったん「サーバー停止」を押し、フォルダを入れて、再度「サーバー起動」を押します。
- **信頼できるフォルダだけ**を指定してください。レシピは Python をそのまま実行します。

## 7. トラブルシューティング

| 症状 | 原因の見立て | 対処 |
|---|---|---|
| `用語 '.\.venv\Scripts\python.exe' は、コマンドレット、関数、スクリプト ファイル、または実行可能プログラムの名前として認識されません` | **今いるフォルダが違う**（`.\` は今いるフォルダ。`.venv` がない場所で実行している）。または、`.venv` が作られていない | `Get-Location` で場所を確認し、`Set-Location $HOME\Documents\qgis-dev-probe` で移動する。`Test-Path .\.venv\Scripts\python.exe` が `False` なら、下の「`python -m venv` が `Python` とだけ表示する」を見る |
| `[not_running]` と返る | サーバーが起動していない、または `endpoint.json` がない | 手順 3 を実施。QGIS を再起動した後は、毎回起動し直す |
| `[auth_failed]` | 古いトークン。QGIS を再起動した、または別のユーザー・別のホームで動いている | クライアントを経由せず、もう一度呼び直す（毎回 `endpoint.json` を読み直します）。解決しなければ、QGIS とクライアントが同じ OS ユーザーか確認する。別ホームの場合は両方に `QGIS_DEV_PROBE_HOME` を設定する |
| `[policy_denied]` | モードが `readonly`、または `execute_code` が未許可 | ダイアログでモードを `interactive` にする。`execute_code` は [USAGE.md](USAGE.md) の手順で許可する |
| ツールが増えない・古いまま | MCP サーバーのプロセスが古いコードのまま動いている | クライアントを完全に終了して再起動する |
| `claude mcp list` が Connected にならない | Python のパスが違う、`pip install -e .` を実行した環境が違う | 手順 2 で表示した絶対パスを使っているか確認する。登録した Python で `-c "import qgis_dev_probe_mcp"` が通るか確認する |
| Claude Code の呼び出しが `Login expired` | Claude Code 側のログイン切れ（このツールとは無関係） | Claude Code で `/login` |
| `pip install -e .` が `File "setup.py" or "setup.cfg" not found ... editable mode currently requires a setuptools-based build` で失敗する | 仮想環境の `pip` が古い（21.3 未満）。Python 3.10.2 の `venv` が同梱する pip は 21.2.4 で、`pyproject.toml` だけのプロジェクトを editable で入れられない（Windows の実機で確認） | `.\.venv\Scripts\python.exe -m pip install --upgrade pip` を実行してから、再度 `pip install -e .` |
| `python -m venv .venv` が `Python` とだけ表示する。`.venv` ができない | `python` が Microsoft Store のエイリアスで、実体の Python ではない | `Get-Command python` が `WindowsApps` 配下なら該当。`py -3 --version` が通るなら `py -3 -m venv .venv` を使う。通らなければ、python.org などで Python 3.10 以上を入れる。`pip install -e .` は、`.venv` ができるまで実行しない（`pip` が `Defaulting to user installation` と表示したら、仮想環境の外に入っている） |
| `git clone` が `destination path ... already exists and is not an empty directory` | その場所に同名のフォルダがある | 別の名前で clone する（`git clone <URL> <フォルダ名>`）か、既存のフォルダを使う（中身を確認してから） |
| プラグインが一覧に出ない | 実験的プラグインが非表示 | 「設定」で実験的プラグインを表示する |
| 再起動後にプラグインが無効になる | `metadata.txt` の必須項目の欠落など（このツールの検証対象プラグインで実際に起きた事例） | QGIS の起動時のログ（ログメッセージ → プラグイン）でエラーを確認する |
| タイムアウトする | メインスレッドが塞がっている（長い処理、モーダルの待機など） | 長い処理は `timeout_s` を指定する。`details.started` が false なら、処理が始まる前のタイムアウト |

エラーコードの一覧は [PROTOCOL.md](PROTOCOL.md)。

## 8. 更新・削除

更新は、次の順で行います。

```powershell
# PowerShell 7 / MCP サーバーの更新
Set-Location $HOME\Documents\qgis-dev-probe
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
```

- **プラグインの更新:** 新しい ZIP を手順 1 と同じ方法で入れ直します（上書き）。その後、QGIS を再起動します。
- **MCP サーバーの更新:** 上のコマンドを実行し、**クライアントを完全に再起動**します。
- **削除:** QGIS のプラグイン管理でアンインストールし、`claude mcp remove qgis-dev-probe`（Claude Code の場合）や設定ファイルの該当項目の削除で、登録を外します。`.qgis_dev_probe` フォルダと clone 先のフォルダは、不要なら手動で削除します（削除前に、中身を確認してください）。
