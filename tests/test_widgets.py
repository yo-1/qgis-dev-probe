import unittest

from qgis_dev_probe.core.errors import BadRequest
from qgis_dev_probe.qgis_side import widgets as W

from .fakes import (
    FakeAction,
    FakeButton,
    FakeCheckBox,
    FakeComboBox,
    FakeDialog,
    FakeDoubleSpinBox,
    FakeFileWidget,
    FakeGrabbable,
    FakeGroupBox,
    FakeLabel,
    FakeLineEdit,
    FakePixmap,
    FakePlainTextEdit,
    FakeQObjectNonWidget,
    FakeSpinBox,
    FakeTabWidget,
    FakeWidget,
)


def _immediate(fn):
    fn()


def _make_dialog():
    ok = FakeButton("okButton", "&OK")
    cancel = FakeButton("", "キャンセル")
    inner = FakeWidget("frame", children=[FakeLineEdit("nameEdit", "山梨県", placeholder="name")])
    internal = FakeWidget("qt_scrollarea_vcontainer", children=[FakeButton("hiddenBtn", "x")])
    dialog = FakeDialog(
        "meshDialog",
        "森林資源量メッシュ生成",
        children=[
            FakeLabel("title", "メッシュ設定"),
            FakeComboBox("systemCombo", ["I", "VIII", "IX"], data=["sys1", "sys8", "sys9"]),
            FakeSpinBox("sizeSpin", 20, 1, 1000),
            FakeDoubleSpinBox("ratioSpin", 0.5, 0.0, 1.0),
            FakeCheckBox("overwriteCheck", "上書き"),
            FakeFileWidget("outputFile", "/tmp/a.gpkg"),
            FakePlainTextEdit("logView", "line1\nline2", read_only=True),
            FakeTabWidget("tabs", ["&General", "Advanced"]),
            FakeGroupBox("optsGroup", "Options"),
            inner,
            internal,
            FakeQObjectNonWidget(),
            FakeLineEdit("disabledEdit", "x", enabled=False),
            FakeButton("hiddenButton", "hidden", visible=False),
            ok,
            cancel,
        ],
    )
    return dialog, ok, cancel


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.main = FakeDialog("QgisApp", "QGIS 3.44")
        self.dialog = FakeDialog("meshDialog", "森林資源量メッシュ生成", modal=True)
        self.hidden = FakeDialog("hiddenWin", "Hidden", visible=False)
        self.top = [self.main, self.dialog, self.hidden]

    def test_list_windows_hides_invisible_by_default(self):
        names = [w["object_name"] for w in W.list_windows(self.top)]
        self.assertEqual(names, ["QgisApp", "meshDialog"])
        self.assertEqual(len(W.list_windows(self.top, include_hidden=True)), 3)
        self.assertTrue(W.list_windows(self.top)[1]["modal"])

    def test_select_by_object_name_title_and_substring(self):
        self.assertIs(W.select_window(self.top, "meshDialog"), self.dialog)
        self.assertIs(W.select_window(self.top, "森林資源量メッシュ生成"), self.dialog)
        self.assertIs(W.select_window(self.top, "メッシュ"), self.dialog)
        self.assertIs(W.select_window(self.top, "qgis 3.44"), self.main)  # 大文字小文字無視の部分一致

    def test_object_name_wins_over_title(self):
        other = FakeDialog("x", "meshDialog")
        self.assertIs(W.select_window([other, self.dialog], "meshDialog"), self.dialog)

    def test_hidden_windows_are_not_selectable(self):
        with self.assertRaises(BadRequest) as cm:
            W.select_window(self.top, "hiddenWin")
        self.assertIn("visible_windows", cm.exception.details)

    def test_ambiguous_selector_lists_candidates(self):
        a, b = FakeDialog("a", "Mesh A"), FakeDialog("b", "Mesh B")
        with self.assertRaises(BadRequest) as cm:
            W.select_window([a, b], "Mesh")
        self.assertEqual(len(cm.exception.details["candidates"]), 2)


class DescribeTests(unittest.TestCase):
    def test_each_widget_kind_is_described(self):
        d = {w["object_name"]: w for w in W.dump_widgets(_make_dialog()[0])["widgets"]}
        self.assertEqual(d["title"]["text"], "メッシュ設定")
        self.assertEqual(d["systemCombo"]["items"], ["I", "VIII", "IX"])
        self.assertEqual(d["systemCombo"]["current_text"], "I")
        self.assertEqual(d["sizeSpin"]["value"], 20)
        self.assertEqual((d["sizeSpin"]["minimum"], d["sizeSpin"]["maximum"]), (1, 1000))
        self.assertIs(d["overwriteCheck"]["checked"], False)
        self.assertEqual(d["outputFile"]["file_path"], "/tmp/a.gpkg")
        self.assertEqual(d["logView"]["text"], "line1\nline2")
        self.assertIs(d["logView"]["read_only"], True)
        self.assertEqual(d["tabs"]["tabs"], ["General", "Advanced"])
        self.assertEqual(d["optsGroup"]["title"], "Options")
        self.assertEqual(d["nameEdit"]["placeholder"], "name")
        self.assertIs(d["disabledEdit"]["enabled"], False)
        self.assertIs(d["hiddenButton"]["visible"], False)

    def test_non_checkable_button_has_no_checked_key(self):
        d = {w["object_name"]: w for w in W.dump_widgets(_make_dialog()[0])["widgets"]}
        self.assertNotIn("checked", d["okButton"])
        self.assertEqual(d["okButton"]["text"], "&OK")

    def test_scroll_area_contents_are_visible_but_viewport_is_not_listed(self):
        # オプション画面のように QScrollArea の中に部品がある場合（viewport 経由）。実機で見えなかった不具合の回帰
        combo = FakeComboBox("styleCombo", ["Fusion", "Windows"])
        viewport = FakeWidget("qt_scrollarea_viewport", children=[FakeWidget("pageContent", children=[combo])])
        area = FakeWidget("scrollArea", children=[viewport])
        dialog = FakeDialog("optsDialog", "Options", children=[area])
        names = [w["object_name"] for w in W.dump_widgets(dialog)["widgets"]]
        self.assertIn("styleCombo", names)
        self.assertNotIn("qt_scrollarea_viewport", names)
        self.assertIs(W.find_widget(dialog, object_name="styleCombo"), combo)

    def test_traversal_skips_qt_internal_and_non_widgets(self):
        result = W.dump_widgets(_make_dialog()[0])
        names = [w["object_name"] for w in result["widgets"]]
        self.assertNotIn("hiddenBtn", names)
        self.assertNotIn("timer", names)
        with_internal = W.dump_widgets(_make_dialog()[0], include_internal=True)
        self.assertIn("hiddenBtn", [w["object_name"] for w in with_internal["widgets"]])

    def test_depth_and_unnamed_reporting(self):
        result = W.dump_widgets(_make_dialog()[0])
        depths = {w["object_name"]: w["depth"] for w in result["widgets"] if w["object_name"]}
        self.assertEqual(depths["meshDialog"], 0)
        self.assertEqual(depths["nameEdit"], 2)
        self.assertGreaterEqual(result["unnamed_in_result"], 1)  # キャンセルボタンは名前なし

    def test_only_named_and_truncation(self):
        result = W.dump_widgets(_make_dialog()[0], only_named=True)
        self.assertTrue(all(w["object_name"] for w in result["widgets"]))
        limited = W.dump_widgets(_make_dialog()[0], max_items=3)
        self.assertEqual((limited["returned"], limited["truncated"]), (3, True))

    def test_visible_only_skips_hidden_but_keeps_root(self):
        everything = W.dump_widgets(_make_dialog()[0], include_internal=True)
        visible = W.dump_widgets(_make_dialog()[0], include_internal=True, visible_only=True)
        self.assertLess(visible["returned"], everything["returned"])
        self.assertIn("hiddenButton", [w["object_name"] for w in everything["widgets"]])
        self.assertNotIn("hiddenButton", [w["object_name"] for w in visible["widgets"]])
        self.assertEqual(visible["widgets"][0]["object_name"], "meshDialog")
        self.assertTrue(all(w["visible"] for w in visible["widgets"][1:]))

    def test_order_is_document_order(self):
        names = [w["object_name"] for w in W.dump_widgets(_make_dialog()[0])["widgets"][:4]]
        self.assertEqual(names, ["meshDialog", "title", "systemCombo", "sizeSpin"])


class FindTests(unittest.TestCase):
    def setUp(self):
        self.dialog, self.ok, self.cancel = _make_dialog()

    def test_find_by_object_name_and_by_button_text(self):
        self.assertIs(W.find_widget(self.dialog, object_name="okButton"), self.ok)
        self.assertIs(W.find_widget(self.dialog, text="OK"), self.ok)  # & を無視
        self.assertIs(W.find_widget(self.dialog, text="キャンセル"), self.cancel)
        self.assertIs(W.find_widget(self.dialog, text="ok"), self.ok)

    def test_text_search_ignores_non_buttons(self):
        with self.assertRaises(BadRequest):
            W.find_widget(self.dialog, text="メッシュ設定")  # ラベルはボタンではない

    def test_requires_a_selector_and_reports_missing(self):
        with self.assertRaises(BadRequest):
            W.find_widget(self.dialog)
        with self.assertRaisesRegex(BadRequest, "no widget matches"):
            W.find_widget(self.dialog, object_name="nope")

    def test_duplicates_require_index(self):
        a, b = FakeButton("dup", "A"), FakeButton("dup", "B")
        root = FakeDialog("root", children=[a, b])
        with self.assertRaises(BadRequest) as cm:
            W.find_widget(root, object_name="dup")
        self.assertEqual(len(cm.exception.details["candidates"]), 2)
        self.assertIs(W.find_widget(root, object_name="dup", index=1), b)
        with self.assertRaises(BadRequest):
            W.find_widget(root, object_name="dup", index=2)


class SetValueTests(unittest.TestCase):
    def setUp(self):
        self.dialog, _, _ = _make_dialog()
        self.find = lambda name: W.find_widget(self.dialog, object_name=name)

    def test_line_edit(self):
        result = W.set_value(self.find("nameEdit"), "長野県")
        self.assertEqual((result["before"], result["after"]), ("山梨県", "長野県"))

    def test_line_edit_with_set_value_is_not_treated_as_spinbox(self):
        from tests.fakes import FakeFilterLineEdit

        edit = FakeFilterLineEdit("searchEdit", "")
        result = W.set_value(edit, "ネットワーク")
        self.assertEqual(result["after"], "ネットワーク")
        # MCP クライアントが "4" を数値 4 に変換して送る場合があるため、数値は文字列化して受け付ける
        self.assertEqual(W.set_value(edit, 5)["after"], "5")
        for bad in (True, ["4"], None):
            with self.assertRaises(BadRequest):
                W.set_value(edit, bad)

    def test_combo_by_text_case_insensitive_index_and_data(self):
        combo = self.find("systemCombo")
        W.set_value(combo, "VIII")
        self.assertEqual(combo.currentText(), "VIII")
        W.set_value(combo, "ix")
        self.assertEqual(combo.currentText(), "IX")
        W.set_value(combo, 0)
        self.assertEqual(combo.currentText(), "I")
        W.set_value(combo, "sys8")  # itemText に無い文字列 → userData の位置
        self.assertEqual(combo.currentText(), "VIII")
        # 整数は常にインデックス（userData の整数値とは解釈しない。曖昧さを避ける設計）
        with self.assertRaisesRegex(BadRequest, "out of range"):
            W.set_value(combo, 8)

    def test_combo_errors_list_items(self):
        combo = self.find("systemCombo")
        for bad in ("XX", 9, -1, True, 1.5, None):
            with self.subTest(bad=bad), self.assertRaises(BadRequest):
                W.set_value(combo, bad)
        with self.assertRaises(BadRequest) as cm:
            W.set_value(combo, "XX")
        self.assertEqual(cm.exception.details["items"], ["I", "VIII", "IX"])

    def test_spin_box_int_and_double(self):
        W.set_value(self.find("sizeSpin"), 40)
        self.assertEqual(self.find("sizeSpin").value(), 40)
        W.set_value(self.find("sizeSpin"), 40.0)  # 整数値の float は許可
        with self.assertRaisesRegex(BadRequest, "integers only"):
            W.set_value(self.find("sizeSpin"), 4.5)
        W.set_value(self.find("ratioSpin"), 1)  # int でも float に変換して渡す
        self.assertEqual(self.find("ratioSpin").value(), 1.0)
        for bad in ("5", True, None):
            with self.subTest(bad=bad), self.assertRaises(BadRequest):
                W.set_value(self.find("sizeSpin"), bad)

    def test_out_of_range_value_is_reported_via_after(self):
        result = W.set_value(self.find("sizeSpin"), 99999)
        self.assertEqual(result["after"], 1000)  # Qt がクランプした結果が見える

    def test_checkbox_requires_bool(self):
        W.set_value(self.find("overwriteCheck"), True)
        self.assertTrue(self.find("overwriteCheck").isChecked())
        with self.assertRaises(BadRequest):
            W.set_value(self.find("overwriteCheck"), "true")

    def test_file_widget_plaintext_and_tabs(self):
        W.set_value(self.find("outputFile"), "/tmp/b.gpkg")
        self.assertEqual(self.find("outputFile").filePath(), "/tmp/b.gpkg")
        W.set_value(self.find("tabs"), "Advanced")
        self.assertEqual(self.find("tabs").currentIndex(), 1)

    def test_refuses_disabled_hidden_and_readonly(self):
        with self.assertRaisesRegex(BadRequest, "disabled"):
            W.set_value(self.find("disabledEdit"), "y")
        with self.assertRaisesRegex(BadRequest, "read-only"):
            W.set_value(self.find("logView"), "y")
        hidden = FakeLineEdit("h", "x", visible=False)
        with self.assertRaisesRegex(BadRequest, "not visible"):
            W.set_value(hidden, "y")

    def test_unsupported_widgets(self):
        for name in ("title", "okButton", "optsGroup"):
            with self.subTest(name=name), self.assertRaisesRegex(BadRequest, "not supported"):
                W.set_value(self.find(name), "x")


class ClickAndCloseTests(unittest.TestCase):
    def test_click_is_deferred_through_scheduler(self):
        dialog, ok, _ = _make_dialog()
        scheduled = []
        result = W.click(ok, scheduled.append)
        self.assertEqual(ok.clicks, 0)  # まだ実行されない（モーダルを開くボタンでもブロックしない）
        self.assertTrue(result["deferred"])
        scheduled[0]()
        self.assertEqual(ok.clicks, 1)

    def test_click_checkable_toggles(self):
        box = FakeCheckBox("c", "c")
        W.click(box, _immediate)
        self.assertTrue(box.isChecked())

    def test_click_refuses_disabled_hidden_and_non_buttons(self):
        dialog, _, _ = _make_dialog()
        for name, message in (("hiddenButton", "not visible"), ("title", "cannot be clicked")):
            with self.subTest(name=name), self.assertRaisesRegex(BadRequest, message):
                W.click(W.find_widget(dialog, object_name=name), _immediate)
        with self.assertRaisesRegex(BadRequest, "disabled"):
            W.click(FakeButton("d", "d", enabled=False), _immediate)

    def test_close_window_is_deferred(self):
        class Closable(FakeDialog):
            closed = 0

            def close(self):
                self.closed += 1

        win = Closable("w", "t")
        scheduled = []
        W.close_window(win, scheduled.append)
        self.assertEqual(win.closed, 0)
        scheduled[0]()
        self.assertEqual(win.closed, 1)
        with self.assertRaises(BadRequest):
            W.close_window(FakeWidget("x"), _immediate)


class GrabTests(unittest.TestCase):
    def test_grab_saves_png(self):
        widget = FakeGrabbable("w")
        info = W.grab_to_file(widget, "/tmp/x.png")
        self.assertEqual(info, {"width": 640, "height": 480})
        self.assertEqual(widget.pixmap.saved, [("/tmp/x.png", "PNG")])

    def test_grab_failure_is_reported(self):
        with self.assertRaisesRegex(BadRequest, "failed to write"):
            W.grab_to_file(FakeGrabbable("w", pixmap=FakePixmap(ok=False)), "/tmp/x.png")


if __name__ == "__main__":
    unittest.main()


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.launch = FakeAction("", "&MORIZON を開く")
        self.disabled = FakeAction("actOff", "無効な項目", enabled=False)
        self.submenu = FakeAction("actSub", "サブメニュー", menu=object())
        self.dup1 = FakeAction("", "重複")
        self.dup2 = FakeAction("", "重複")
        self.hidden = FakeAction("actHidden", "非表示", visible=False)
        self.separator = FakeAction("", "", separator=True)
        self.toolbar = FakeWidget("pluginToolBar", actions=[self.launch, self.dup1, self.separator])
        # 同じ QAction がメニューとツールバーの両方にあっても 1 件として数える
        self.menu = FakeWidget("pluginMenu", actions=[self.launch, self.disabled, self.submenu, self.dup2, self.hidden])
        self.window = FakeDialog("QgisApp", "QGIS", children=[self.toolbar, self.menu])

    def test_list_actions_dedupes_and_hides_separator_and_hidden(self):
        texts = [a["text"] for a in W.list_actions(self.window)["actions"]]
        self.assertEqual(texts.count("MORIZON を開く"), 1)  # & は除去、重複は 1 件
        self.assertNotIn("非表示", texts)
        self.assertNotIn("", texts)
        self.assertIn("非表示", [a["text"] for a in W.list_actions(self.window, include_hidden=True)["actions"]])

    def test_list_actions_text_filter(self):
        result = W.list_actions(self.window, text="morizon")
        self.assertEqual([a["text"] for a in result["actions"]], ["MORIZON を開く"])

    def test_trigger_by_text_is_deferred_and_ignores_mnemonic(self):
        scheduled = []
        action = W.find_action(self.window, text="MORIZON を開く")
        result = W.trigger_action(action, scheduled.append)
        self.assertEqual(self.launch.triggered, 0)  # まだ実行されない（遅延）
        scheduled[0]()
        self.assertEqual(self.launch.triggered, 1)
        self.assertTrue(result["deferred"])

    def test_find_by_object_name_and_errors(self):
        self.assertIs(W.find_action(self.window, object_name="actOff"), self.disabled)
        with self.assertRaises(BadRequest):
            W.find_action(self.window, text="存在しない")
        with self.assertRaises(BadRequest):
            W.find_action(self.window)  # 指定なし

    def test_ambiguous_text_needs_index(self):
        with self.assertRaises(BadRequest) as ctx:
            W.find_action(self.window, text="重複")
        self.assertIn("candidates", ctx.exception.details)
        self.assertIs(W.find_action(self.window, text="重複", index=1), self.dup2)

    def test_disabled_and_submenu_are_refused(self):
        for name in ("actOff", "actSub"):
            with self.subTest(name=name), self.assertRaises(BadRequest):
                W.trigger_action(W.find_action(self.window, object_name=name), lambda fn: None)
