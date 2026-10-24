"""開発ループ: プラグインを再読込し、その間に QGIS ログへ出た warning 以上を返す。

使い方: run_recipe(name="reload_and_check", args={"plugin": "your_plugin_package"})
コードを編集 → この recipe → 返ってきた new_problems を確認、を繰り返す。
再読込後の画面確認は、続けて list_windows / click_widget / screenshot を呼ぶ。
"""


def run(ctx, args):
    plugin = args.get("plugin")
    if not isinstance(plugin, str) or not plugin:
        raise ValueError("args.plugin（プラグインのパッケージ名。list_plugins の name）が必要です")
    before = ctx.call("read_log", limit=1)
    since_id = before.get("last_id", 0)
    reload_result = ctx.call("reload_plugin", name=plugin)
    problems = []
    for level in ("warning", "critical"):
        entries = ctx.call("read_log", level=level, since_id=since_id, limit=100)["entries"]
        problems.extend(entries)
    problems.sort(key=lambda e: e["id"])
    return {
        "reload": reload_result,
        "ok": bool(reload_result.get("active")) and not problems,
        "new_problems": problems,
    }
