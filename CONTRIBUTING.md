# Contributing

## 開発環境

- Python 3.10 以上（MCP サーバー側）。プラグイン側は QGIS 同梱の Python（3.9 互換で書く）。
- 依存: `mcp>=2.3,<3`、開発用に `ruff`。

```bash
# Bash（リポジトリ直下）
uv sync --extra dev          # もしくは python -m venv .venv && pip install -e ".[dev]"
python -m unittest discover -s tests -t . -v
ruff check .
```

```powershell
# PowerShell 7（リポジトリ直下）
uv sync --extra dev
python -m unittest discover -s tests -t . -v
ruff check .
```

テストは標準 `unittest` で書かれており、`pytest` からも実行できます。
QGIS / Qt が無い環境でも動くよう、QGIS 依存コードは `plugin/qgis_dev_probe/qgis_side/` に隔離しています。

## 方針

- 純 Python のロジック（`core/`）には必ず単体テストを付ける。
- QGIS API を新しく使う場合は `docs/VERIFY.md` の確認表に 1 行追加する（実機で確認するまで「未確認」と書く）。
- ツールを追加するときは `core/registry.py`（カテゴリ・タイムアウト）、`qgis_side/handlers.py`、`src/qgis_dev_probe_mcp/server.py` の 3 か所と、`tests/test_registry_sync.py` を更新する。
- `execute_code` を除き、任意コード実行や任意パス書き込みを増やさない。

## ブランチとコミット

- `main` は常に `python -m unittest` と `ruff check .` が通る状態にする。
- 作業は `feature/<要約>` ブランチ、PR で `main` へ。小さく意味のある単位でコミットする。
- コミットメッセージ: `feat:` / `fix:` / `docs:` / `test:` / `chore:` の接頭辞 + 日本語または英語の要約。
- 秘密情報（トークン、`endpoint.json`）をコミットしない。`.gitignore` を確認すること。

## リリース

1. `CHANGELOG.md` を更新、`plugin/qgis_dev_probe/metadata.txt` と `pyproject.toml` のバージョンを揃える。
2. 実機検証（`docs/VERIFY.md`）の結果を PR に記載。
3. `python scripts/package_plugin.py` でプラグイン zip を作成。
4. タグ `vX.Y.Z` を打つ。

## バージョンの付け方（実機検証ビルドの識別）

検証用にビルドを QGIS へ入れ直すたびに版を上げ、どのコードが動いているか `ping` の `plugin_version` で分かるようにします。

- 実機検証用: `0.1.0-rc1`, `0.1.0-rc2` ...（変更を入れ直す都度 rc を +1）
- 検証が一通り済んだら `0.1.0` とし、タグ `v0.1.0` を打つ（タグは手動）
- 更新箇所は 3 つ: `plugin/qgis_dev_probe/metadata.txt`, `plugin/qgis_dev_probe/__init__.py`（`0.1.0-rc1` 表記）と、`pyproject.toml`, `src/qgis_dev_probe_mcp/__init__.py`（PEP 440 の `0.1.0rc1` 表記）。`tests/test_version_sync.py` が不一致を検出します。
- 未確認: QGIS のプラグイン管理が `-rc1` 付きの版比較を想定どおり扱うか（実機で確認すること）。
