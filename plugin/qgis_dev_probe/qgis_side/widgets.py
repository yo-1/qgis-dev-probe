"""Qt ウィジェットの観察と操作。

重要: このモジュールは `qgis` / `PyQt` を import しない（ダックタイピングだけで書く）。
  * 実 Qt が無い環境（CI・このリポジトリの単体テスト）でも、偽ウィジェットで論理を検証できる。
  * 本物のウィジェット（QPushButton, QLineEdit, QComboBox, QgsFileWidget など）は、
    `text()` / `isChecked()` / `itemText()` / `setValue()` 等のメソッドの有無で種類を判定する。
  * Qt 本体を呼ぶ部分（トップレベル列挙、QTimer.singleShot）は handlers.py が注入する。

ウィンドウは `window` セレクタ（objectName の完全一致 → windowTitle の完全一致 → 部分一致）、
ウィジェットは objectName（または、ボタンのみ表示テキスト）で指定する。曖昧なら候補を返して失敗する。
objectName の無いウィジェットは dump_widgets で確認できるので、検証対象のプラグイン側で
setObjectName を付けるのが最も安定する（docs/DESIGN.md 参照）。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Callable

from ..core.errors import BadRequest

MAX_CANDIDATES_IN_ERROR = 10
MAX_COMBO_ITEMS = 50
MAX_TEXT_CHARS = 2000


# ---------------------------------------------------------------- 基本情報
def class_name(widget: Any) -> str:
    try:
        return str(widget.metaObject().className())
    except Exception:  # noqa: BLE001
        return type(widget).__name__


def _safe(call: Callable[[], Any], default: Any = None) -> Any:
    try:
        return call()
    except Exception:  # noqa: BLE001 - 一部のウィジェットは削除済み C++ オブジェクトで例外になる
        return default


def _geometry(widget: Any) -> list[int] | None:
    rect = _safe(widget.geometry)
    if rect is None:
        return None
    return [int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())]


def _strip_mnemonic(text: str) -> str:
    return text.replace("&", "").strip()


def describe_window(widget: Any) -> dict[str, Any]:
    return {
        "class": class_name(widget),
        "object_name": _safe(widget.objectName, ""),
        "title": _safe(widget.windowTitle, ""),
        "visible": bool(_safe(widget.isVisible, False)),
        "modal": bool(_safe(widget.isModal, False)),
        "geometry": _geometry(widget),
    }


def list_windows(top_levels: Iterable[Any], *, include_hidden: bool = False) -> list[dict[str, Any]]:
    windows = []
    for widget in top_levels:
        info = describe_window(widget)
        if not include_hidden and not info["visible"]:
            continue
        windows.append(info)
    return windows


# ---------------------------------------------------------------- ウィンドウ選択
def select_window(top_levels: Iterable[Any], selector: str) -> Any:
    """表示中のウィンドウから 1 つ選ぶ。0 件・複数件は候補付きの BadRequest。"""
    visible = [w for w in top_levels if _safe(w.isVisible, False)]
    needle = selector.strip()
    lowered = needle.lower()
    tiers: list[Callable[[Any], bool]] = [
        lambda w: _safe(w.objectName, "") == needle,
        lambda w: _safe(w.windowTitle, "") == needle,
        lambda w: lowered in str(_safe(w.windowTitle, "")).lower(),
    ]
    for matcher in tiers:
        matches = [w for w in visible if matcher(w)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise BadRequest(
                f"window selector {selector!r} is ambiguous ({len(matches)} matches); "
                "use the exact objectName or a longer title",
                details={"candidates": [describe_window(w) for w in matches[:MAX_CANDIDATES_IN_ERROR]]},
            )
    raise BadRequest(
        f"no visible window matches {selector!r}",
        details={"visible_windows": [describe_window(w) for w in visible[:MAX_CANDIDATES_IN_ERROR]]},
    )


# ---------------------------------------------------------------- 走査と記述
_SCROLL_VIEWPORT_NAME = "qt_scrollarea_viewport"


def iter_widgets(
    root: Any, *, include_internal: bool = False, max_depth: int = 20
) -> Iterator[tuple[Any, int]]:
    """root 自身を含め、子ウィジェットを深さ優先で列挙する（(widget, depth)）。"""
    stack = [(root, 0)]
    while stack:
        widget, depth = stack.pop()
        yield widget, depth
        if depth >= max_depth:
            continue
        children = [c for c in _safe(widget.children, []) if _safe(c.isWidgetType, False)]
        if not include_internal:
            # qt_ で始まる名前は Qt 内部（scrollbar container など）なので除く。ただし QScrollArea の
            # 中身は viewport の子なので、viewport 自体は出さずに子だけを繋ぎ替える（除外すると
            # スクロール領域内の部品が全部見えなくなる。実機のオプション画面で確認）。
            visible_children = []
            for child in children:
                child_name = str(_safe(child.objectName, ""))
                if child_name == _SCROLL_VIEWPORT_NAME:
                    visible_children.extend(
                        g for g in _safe(child.children, []) if _safe(g.isWidgetType, False)
                    )
                elif not child_name.startswith("qt_"):
                    visible_children.append(child)
            children = visible_children
        for child in reversed(children):  # 元の順序で訪問するため逆順に積む
            stack.append((child, depth + 1))


def describe_widget(widget: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "class": class_name(widget),
        "object_name": _safe(widget.objectName, ""),
        "visible": bool(_safe(widget.isVisible, False)),
        "enabled": bool(_safe(widget.isEnabled, True)),
        "geometry": _geometry(widget),
    }
    tooltip = _safe(widget.toolTip, "") if hasattr(widget, "toolTip") else ""
    if tooltip:
        info["tooltip"] = str(tooltip)[:200]

    if hasattr(widget, "itemText") and hasattr(widget, "count"):  # QComboBox 系
        count = int(_safe(widget.count, 0))
        info["current_text"] = _safe(widget.currentText, "")
        info["current_index"] = _safe(widget.currentIndex, -1)
        info["count"] = count
        info["items"] = [_safe(lambda i=i: widget.itemText(i), "") for i in range(min(count, MAX_COMBO_ITEMS))]
    elif hasattr(widget, "tabText") and hasattr(widget, "count"):  # QTabWidget / QTabBar
        count = int(_safe(widget.count, 0))
        info["current_index"] = _safe(widget.currentIndex, -1)
        info["tabs"] = [_strip_mnemonic(str(_safe(lambda i=i: widget.tabText(i), ""))) for i in range(count)]
    elif hasattr(widget, "toPlainText"):  # QTextEdit / QPlainTextEdit
        info["text"] = str(_safe(widget.toPlainText, ""))[:MAX_TEXT_CHARS]
    elif callable(getattr(widget, "text", None)):  # QLabel / QPushButton / QLineEdit / QMessageBox ...
        info["text"] = str(_safe(widget.text, ""))[:MAX_TEXT_CHARS]
    elif callable(getattr(widget, "title", None)):  # QGroupBox（QgsCollapsibleGroupBox を含む）
        info["title"] = str(_safe(widget.title, ""))[:MAX_TEXT_CHARS]

    if hasattr(widget, "filePath") and callable(widget.filePath):  # QgsFileWidget
        info["file_path"] = _safe(widget.filePath, "")
    if hasattr(widget, "isChecked") and (not hasattr(widget, "isCheckable") or _safe(widget.isCheckable, False)):
        info["checked"] = bool(_safe(widget.isChecked, False))
    if (
        callable(getattr(widget, "value", None))
        and not hasattr(widget, "itemText")
        and not hasattr(widget, "tabText")
    ):  # QSpinBox / QSlider / QProgressBar ...
        info["value"] = _safe(widget.value)
        for key in ("minimum", "maximum"):
            if callable(getattr(widget, key, None)):
                info[key] = _safe(getattr(widget, key))
    if callable(getattr(widget, "placeholderText", None)):
        placeholder = _safe(widget.placeholderText, "")
        if placeholder:
            info["placeholder"] = str(placeholder)
    if callable(getattr(widget, "isReadOnly", None)):
        info["read_only"] = bool(_safe(widget.isReadOnly, False))
    return info


def dump_widgets(
    root: Any,
    *,
    max_items: int = 400,
    only_named: bool = False,
    include_internal: bool = False,
    visible_only: bool = False,
) -> dict[str, Any]:
    items = []
    total = 0
    for widget, depth in iter_widgets(root, include_internal=include_internal):
        name = _safe(widget.objectName, "")
        if only_named and not name and depth > 0:
            continue
        # QGIS 本体のように非表示ページ・メニュー・ツールバーが大量にあるウィンドウでは、
        # 非表示を除かないと上限が非表示ウィジェットで埋まる（実機 3.44 で確認）
        if visible_only and depth > 0 and not _safe(widget.isVisible, False):
            continue
        total += 1
        if len(items) < max_items:
            entry = describe_widget(widget)
            entry["depth"] = depth
            items.append(entry)
    unnamed = sum(1 for e in items if not e["object_name"])
    return {
        "window": describe_window(root),
        "widgets": items,
        "returned": len(items),
        "total_matching": total,
        "truncated": total > len(items),
        "unnamed_in_result": unnamed,
    }


# ---------------------------------------------------------------- QAction
# メニュー項目・ツールバーのボタンは QWidget ではなく QAction。プラグインの起動口は多くがこれ。
MAX_ACTIONS = 500


def iter_actions(root: Any) -> Iterator[Any]:
    """root 配下のウィジェット（メニュー・ツールバー含む）に属する QAction を重複なく列挙する。"""
    seen: set[int] = set()
    for widget, _depth in iter_widgets(root, include_internal=True):
        actions = _safe(widget.actions, []) if callable(getattr(widget, "actions", None)) else []
        for action in actions:
            if id(action) in seen:
                continue
            seen.add(id(action))
            yield action


def _action_menu(action: Any) -> Any:
    return _safe(action.menu, None) if callable(getattr(action, "menu", None)) else None


def describe_action(action: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "object_name": _safe(action.objectName, ""),
        "text": _strip_mnemonic(str(_safe(action.text, ""))),
        "enabled": bool(_safe(action.isEnabled, True)),
        "visible": bool(_safe(action.isVisible, True)),
        "checkable": bool(_safe(action.isCheckable, False)),
        "submenu": _action_menu(action) is not None,
    }
    if info["checkable"]:
        info["checked"] = bool(_safe(action.isChecked, False))
    tooltip = str(_safe(action.toolTip, "") or "")
    if tooltip and tooltip != info["text"]:
        info["tooltip"] = tooltip[:200]
    return info


def list_actions(root: Any, *, text: str | None = None, include_hidden: bool = False) -> dict[str, Any]:
    needle = text.lower() if text else None
    items = []
    total = 0
    for action in iter_actions(root):
        if _safe(action.isSeparator, False):
            continue
        entry = describe_action(action)
        if not entry["object_name"] and not entry["text"]:
            continue
        if not include_hidden and not entry["visible"]:
            continue
        if needle and needle not in entry["text"].lower() and needle not in entry["object_name"].lower():
            continue
        total += 1
        if len(items) < MAX_ACTIONS:
            items.append(entry)
    return {"window": describe_window(root), "actions": items, "returned": len(items), "total_matching": total,
            "truncated": total > len(items)}


def find_action(root: Any, *, object_name: str | None = None, text: str | None = None, index: int | None = None) -> Any:
    if not object_name and not text:
        raise BadRequest("specify 'object_name' (preferred) or 'text'")
    matches = []
    for action in iter_actions(root):
        if _safe(action.isSeparator, False):
            continue
        if object_name and _safe(action.objectName, "") != object_name:
            continue
        if text and _strip_mnemonic(str(_safe(action.text, ""))).lower() != _strip_mnemonic(text).lower():
            continue
        matches.append(action)
    selector_text = f"object_name={object_name!r}" if object_name else f"text={text!r}"
    if not matches:
        raise BadRequest(f"no action matches {selector_text}; run list_actions to list available actions")
    if index is not None:
        if not 0 <= index < len(matches):
            raise BadRequest(f"index {index} out of range (0..{len(matches) - 1})")
        return matches[index]
    if len(matches) > 1:
        raise BadRequest(
            f"{len(matches)} actions match {selector_text}; pass 'index' or use object_name",
            details={"candidates": [describe_action(a) for a in matches[:MAX_CANDIDATES_IN_ERROR]]},
        )
    return matches[0]


def trigger_action(action: Any, schedule: Callable[[Callable[[], Any]], None]) -> dict[str, Any]:
    """QAction を実行する。モーダルを開く項目でも応答が止まらないよう、click と同様に遅延実行する。"""
    info = describe_action(action)
    if not info["enabled"]:
        raise BadRequest("action is disabled", details=info)
    if info["submenu"]:
        raise BadRequest("action opens a submenu; trigger one of its items instead", details=info)
    if not callable(getattr(action, "trigger", None)):
        raise BadRequest("not a triggerable action", details=info)
    schedule(action.trigger)
    return {"action": info, "triggered": True, "deferred": True}


# ---------------------------------------------------------------- 検索
def find_widget(
    root: Any, *, object_name: str | None = None, text: str | None = None, index: int | None = None
) -> Any:
    if not object_name and not text:
        raise BadRequest("specify 'object_name' (preferred) or 'text' (buttons only)")
    matches = []
    for widget, _depth in iter_widgets(root, include_internal=True):
        if object_name and _safe(widget.objectName, "") != object_name:
            continue
        if text:
            if not callable(getattr(widget, "click", None)) or not callable(getattr(widget, "text", None)):
                continue  # text 指定はボタン類のみ
            if _strip_mnemonic(str(_safe(widget.text, ""))).lower() != _strip_mnemonic(text).lower():
                continue
        matches.append(widget)

    selector_text = f"object_name={object_name!r}" if object_name else f"text={text!r}"
    if not matches:
        raise BadRequest(
            f"no widget matches {selector_text}; run dump_widgets to list available widgets",
        )
    if index is not None:
        if not 0 <= index < len(matches):
            raise BadRequest(f"index {index} out of range (0..{len(matches) - 1})")
        return matches[index]
    if len(matches) > 1:
        raise BadRequest(
            f"{len(matches)} widgets match {selector_text}; pass 'index' (0-based) to choose",
            details={"candidates": [describe_widget(w) for w in matches[:MAX_CANDIDATES_IN_ERROR]]},
        )
    return matches[0]


# ---------------------------------------------------------------- 操作
def _require_interactable(widget: Any) -> None:
    """人間が操作できない状態（非表示・無効）のウィジェットは、GUI テストとして失敗させる。"""
    if not _safe(widget.isVisible, False):
        raise BadRequest("widget is not visible", details=describe_widget(widget))
    if not _safe(widget.isEnabled, True):
        raise BadRequest("widget is disabled", details=describe_widget(widget))


def current_value(widget: Any) -> Any:
    info = describe_widget(widget)
    for key in ("checked", "current_text", "file_path", "value", "text"):
        if key in info:
            if key == "current_text":
                return {"text": info["current_text"], "index": info.get("current_index")}
            return info[key]
    if "current_index" in info:
        return info["current_index"]
    return None


def _match_item(widget: Any, value: Any, getter: str, setter_name: str) -> int:
    count = int(widget.count())
    texts = [_strip_mnemonic(str(getattr(widget, getter)(i))) for i in range(count)]
    if isinstance(value, bool):
        raise BadRequest("value must be an item text (string) or a 0-based index (integer)")
    if isinstance(value, int):
        if not 0 <= value < count:
            raise BadRequest(f"index {value} out of range (0..{count - 1})", details={"items": texts[:50]})
        return value
    if isinstance(value, str):
        wanted = _strip_mnemonic(value)
        for i, item in enumerate(texts):
            if item == wanted:
                return i
        for i, item in enumerate(texts):
            if item.lower() == wanted.lower():
                return i
        if setter_name == "combo" and callable(getattr(widget, "findData", None)):
            found = widget.findData(value)
            if isinstance(found, int) and found >= 0:
                return found
        raise BadRequest(f"no item {value!r}", details={"items": texts[:MAX_COMBO_ITEMS]})
    raise BadRequest("value must be an item text (string) or a 0-based index (integer)")


def _as_text(value: Any) -> str:
    """テキスト入力へ渡す値。MCP クライアントが "4" を数値 4 へ変換して送ることがある（実機で確認）ため、
    bool 以外の数値は文字列化して受け付ける。"""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BadRequest("value must be a string")
    return value if isinstance(value, str) else str(value)


def set_value(widget: Any, value: Any) -> dict[str, Any]:
    """入力系ウィジェットへ値を設定する。変更前後の値を返す（呼び出し側が反映を確認できる）。"""
    _require_interactable(widget)
    if callable(getattr(widget, "isReadOnly", None)) and _safe(widget.isReadOnly, False):
        raise BadRequest("widget is read-only", details=describe_widget(widget))
    before = current_value(widget)

    if hasattr(widget, "itemText") and hasattr(widget, "setCurrentIndex"):
        widget.setCurrentIndex(_match_item(widget, value, "itemText", "combo"))
    elif hasattr(widget, "tabText") and hasattr(widget, "setCurrentIndex"):
        widget.setCurrentIndex(_match_item(widget, value, "tabText", "tabs"))
    elif hasattr(widget, "setFilePath"):
        if not isinstance(value, str):
            raise BadRequest("value must be a string path")
        widget.setFilePath(value)
    elif hasattr(widget, "setPlainText"):
        widget.setPlainText(_as_text(value))
    elif hasattr(widget, "setChecked") and (not hasattr(widget, "isCheckable") or _safe(widget.isCheckable, False)):
        if not isinstance(value, bool):
            raise BadRequest("value must be true or false")
        widget.setChecked(value)
    # QLineEdit 系は setValue より先に判定する。QgsFilterLineEdit は setValue を持つため、
    # 後ろに置くとスピンボックス扱いされて文字列が拒否される（実機で確認）。QLabel は対象外。
    elif hasattr(widget, "setText") and hasattr(widget, "setReadOnly"):  # QLineEdit 系（QLabel は対象外）
        widget.setText(_as_text(value))
    elif hasattr(widget, "setValue"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BadRequest("value must be a number")
        # QSpinBox は int、QDoubleSpinBox は float（decimals の有無で判別）を要求する
        if hasattr(widget, "decimals"):
            widget.setValue(float(value))
        elif isinstance(value, float) and not value.is_integer():
            raise BadRequest("this widget accepts integers only")
        else:
            widget.setValue(int(value))
    else:
        raise BadRequest(
            f"setting a value is not supported for {class_name(widget)}",
            details=describe_widget(widget),
        )
    return {
        "widget": _brief(widget),
        "before": before,
        "after": current_value(widget),
    }


def click(widget: Any, schedule: Callable[[Callable[[], Any]], None]) -> dict[str, Any]:
    """ボタン類をクリックする。

    クリックは `schedule` 経由で「次のイベントループ」に回し、すぐ戻る。
    ボタンがモーダルダイアログを開く場合、`widget.click()` を直接呼ぶと、そのダイアログが閉じるまで
    戻らず、ツール呼び出し全体がタイムアウトするため。結果は、呼び出し後に list_windows /
    dump_widgets / read_log で確認する。
    """
    _require_interactable(widget)
    if not callable(getattr(widget, "click", None)):
        raise BadRequest(
            f"{class_name(widget)} cannot be clicked (not a button); use set_widget for inputs",
            details=describe_widget(widget),
        )
    schedule(widget.click)
    return {"widget": _brief(widget), "clicked": True, "deferred": True}


def close_window(window: Any, schedule: Callable[[Callable[[], Any]], None]) -> dict[str, Any]:
    if not callable(getattr(window, "close", None)):
        raise BadRequest("window cannot be closed")
    schedule(window.close)
    return {"window": describe_window(window), "close_requested": True, "deferred": True}


def _brief(widget: Any) -> dict[str, Any]:
    return {"class": class_name(widget), "object_name": _safe(widget.objectName, "")}


# ---------------------------------------------------------------- スクリーンショット
def grab_to_file(widget: Any, path: Any) -> dict[str, Any]:
    pixmap = widget.grab()
    if not pixmap.save(str(path), "PNG"):
        raise BadRequest(f"failed to write screenshot to {path}")
    return {"width": int(pixmap.width()), "height": int(pixmap.height())}
