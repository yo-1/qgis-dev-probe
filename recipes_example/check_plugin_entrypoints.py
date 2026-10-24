"""プラグインの起動口チェック: プラグインが有効で、メニュー/ツールバーの項目が揃っていて押せる状態か。

使い方:
  run_recipe(name="check_plugin_entrypoints", args={
      "plugin": "MORIZON",                                  # list_plugins の name（パッケージ名）
      "actions": ["MORIZON Reloaded を起動", "MORIZON Reloaded 設定"],   # 項目の表示テキスト（& は無視）
  })

再読込の直後は QAction の数が落ち着いていない（Qt の遅延削除・遅延生成）ため、この recipe は
reload しない。reload_plugin → 2 秒ほど待つ → この recipe、の順で呼ぶこと。
画面を開く確認は同期で待てないので recipe にできない。docs/SCENARIOS.md の手順をクライアントが 1 手ずつ進める。
"""


def run(ctx, args):
    plugin = args.get("plugin")
    actions = args.get("actions")
    if not isinstance(plugin, str) or not plugin:
        raise ValueError("args.plugin（list_plugins の name）が必要です")
    if not isinstance(actions, list) or not actions or not all(isinstance(a, str) and a for a in actions):
        raise ValueError("args.actions（項目の表示テキストの配列。1 件以上）が必要です")

    plugins = {p["name"]: p for p in ctx.call("list_plugins")["plugins"]}
    entry = plugins.get(plugin)
    plugin_status = {
        "installed": entry is not None,
        "active": bool(entry and entry.get("active")),
        "version": entry.get("version") if entry else None,
    }

    results = []
    for text in actions:
        found = ctx.call("list_actions", text=text, include_hidden=True)["actions"]
        exact = [a for a in found if a["text"].lower() == text.replace("&", "").lower()]
        results.append(
            {
                "text": text,
                "count": len(exact),
                "found": bool(exact),
                "enabled": any(a["enabled"] for a in exact),
                "visible": any(a["visible"] for a in exact),
                "submenu": any(a["submenu"] for a in exact),
            }
        )
    problems = []
    if not plugin_status["active"]:
        problems.append("plugin is not installed" if not plugin_status["installed"] else "plugin is not active")
    for r in results:
        if not r["found"]:
            problems.append(f"action not found: {r['text']}")
        elif not r["enabled"]:
            problems.append(f"action disabled: {r['text']}")
        elif r["count"] > 1:
            problems.append(f"action appears {r['count']} times (duplicate registration?): {r['text']}")
    return {"plugin": plugin_status, "actions": results, "problems": problems, "ok": not problems}
