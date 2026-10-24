"""インストール済みプラグインの metadata.txt に必須項目が揃っているかを確認する（再起動不要）。

使い方:
  run_recipe(name="check_plugin_metadata", args={"plugin": "forest_map_sheet_generator"})   # パッケージ名

背景: description が欠けたプラグインは、手動の読み込み（ZIP インストール直後・reload_plugin）では動くのに、
QGIS 再起動後の自動読み込みで「メタデータを読み込み中にエラー」となり外れる。実機で確認した（2026-10-24）。
ZIP を入れ替えたら、再起動する前にこの recipe を実行する。

QGIS が保持するメタデータ（qgis.utils.pluginMetadata）を読むだけで、ファイルや設定は変更しない。
キーが無いと pluginMetadata は "__error__" を返す。空値は警告（email は空でも可）。
"""

REQUIRED_KEYS = ("name", "qgisMinimumVersion", "description", "about", "version", "author", "email", "repository")
EMPTY_OK = ("email",)
MISSING = "__error__"


def run(ctx, args):
    plugin = args.get("plugin")
    if not isinstance(plugin, str) or not plugin:
        raise ValueError("args.plugin（パッケージ名）が必要です")

    import qgis.utils  # QGIS 内でのみ import できるため関数内で読み込む（単体テストでは差し替える）

    values = {key: qgis.utils.pluginMetadata(plugin, key) for key in REQUIRED_KEYS}
    missing = [key for key, value in values.items() if value == MISSING]
    empty = [key for key, value in values.items() if value != MISSING and not str(value).strip() and key not in EMPTY_OK]
    problems = [f"missing: {key}" for key in missing] + [f"empty: {key}" for key in empty]
    # 全項目が __error__ なら、項目欠落ではなくメタデータ自体が読めていない（未インストール・パース不能）
    if len(missing) == len(REQUIRED_KEYS):
        problems = ["metadata not readable (plugin not installed or metadata.txt cannot be parsed)"]
    return {
        "plugin": plugin,
        "version": None if values["version"] == MISSING else values["version"],
        "missing": missing,
        "empty": empty,
        "problems": problems,
        "ok": not problems,
    }
