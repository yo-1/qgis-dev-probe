"""開いているダイアログに、操作したい入力部品（objectName）が揃っているかを確認する。

使い方（ダイアログを開いた後に呼ぶ。開く操作は同期で待てないので recipe に含められない）:
  run_recipe(name="check_dialog_widgets", args={
      "window": "forestMapSheetGeneratorDialog",              # list_windows の object_name かタイトル
      "widgets": ["mapCodeEdit", "gridTypeCombo", "buttonBox"],   # 必須の objectName
  })

返り値の problems が空なら ok。objectName が無い（名前未付与）部品は missing として報告する。
読み取りだけを行い、値の変更・クリックはしない。
"""


def run(ctx, args):
    window = args.get("window")
    names = args.get("widgets")
    if not isinstance(window, str) or not window:
        raise ValueError("args.window（list_windows の object_name かタイトル）が必要です")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) and n for n in names):
        raise ValueError("args.widgets（必須の objectName の配列。1 件以上）が必要です")

    dumped = ctx.call("dump_widgets", window=window, only_named=True, visible_only=False)
    by_name = {w["object_name"]: w for w in dumped["widgets"] if w.get("object_name")}

    results = []
    problems = []
    for name in names:
        widget = by_name.get(name)
        results.append(
            {
                "object_name": name,
                "found": widget is not None,
                "class": widget["class"] if widget else None,
                "visible": bool(widget and widget.get("visible")),
                "enabled": bool(widget and widget.get("enabled")),
            }
        )
        if widget is None:
            problems.append(f"missing: {name}")
        elif not widget.get("enabled"):
            problems.append(f"disabled: {name}")
    if dumped.get("truncated"):
        problems.append("dump_widgets was truncated; some widgets may not have been checked")
    return {"window": dumped["window"].get("object_name") or window, "widgets": results, "problems": problems, "ok": not problems}
