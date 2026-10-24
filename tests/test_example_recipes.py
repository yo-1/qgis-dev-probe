"""同梱 recipe が読み込め、偽の ctx で期待どおりに動くこと（QGIS 不要）。"""

import unittest
from pathlib import Path

from qgis_dev_probe.core import recipes

EXAMPLES = Path(__file__).resolve().parent.parent / "recipes_example"


class ExampleRecipeTests(unittest.TestCase):
    def test_all_examples_listed_with_docstring(self):
        listed = {r["name"]: r for r in recipes.list_recipes(str(EXAMPLES))}
        for name in ("smoke_test", "reload_and_check", "check_plugin_entrypoints", "check_dialog_widgets", "check_plugin_metadata", "example_open_layer_and_buffer"):
            self.assertIn(name, listed)
            self.assertTrue(listed[name]["summary"], name)

    def _ctx(self, responses):
        calls = []

        def call(tool, **kwargs):
            calls.append((tool, kwargs))
            value = responses[tool]
            return value(kwargs) if callable(value) else value

        return recipes.RecipeContext(iface=None, project=None, call=call, log=lambda m: None), calls

    def test_smoke_test(self):
        ctx, calls = self._ctx(
            {
                "get_info": {"qgis_version": "3.44.13"},
                "list_layers": {"count": 0, "layers": []},
                "run_algorithm": {"results": {"OUTPUT": {"layer_name": "grid"}}, "elapsed_s": 0.1},
            }
        )
        result = recipes.run_recipe(str(EXAMPLES), "smoke_test", {}, ctx)
        self.assertTrue(result["ok"])
        self.assertEqual([c[0] for c in calls], ["get_info", "list_layers", "run_algorithm"])

    def test_reload_and_check_reports_new_problems_only(self):
        def read_log(kwargs):
            if kwargs.get("limit") == 1:
                return {"last_id": 40, "entries": []}
            self.assertEqual(kwargs["since_id"], 40)  # 再読込前の最終 ID 以降だけを見る
            if kwargs["level"] == "warning":
                return {"entries": [{"id": 42, "message": "w"}]}
            return {"entries": [{"id": 41, "message": "c"}]}

        ctx, _ = self._ctx({"read_log": read_log, "reload_plugin": {"active": True}})
        result = recipes.run_recipe(str(EXAMPLES), "reload_and_check", {"plugin": "p"}, ctx)
        self.assertFalse(result["ok"])
        self.assertEqual([e["id"] for e in result["new_problems"]], [41, 42])

    def _entry_ctx(self, plugins, actions):
        def list_actions(kwargs):
            needle = kwargs["text"].lower()
            return {"actions": [a for a in actions if needle in a["text"].lower()]}

        return self._ctx({"list_plugins": {"plugins": plugins}, "list_actions": list_actions})[0]

    @staticmethod
    def _action(text, **kw):
        return {"text": text, "enabled": True, "visible": True, "submenu": False, **kw}

    def test_check_plugin_entrypoints_ok(self):
        ctx = self._entry_ctx(
            [{"name": "P", "version": "1.0", "active": True}],
            [self._action("P を起動"), self._action("P を起動 設定"), self._action("無関係")],
        )
        result = recipes.run_recipe(str(EXAMPLES), "check_plugin_entrypoints", {"plugin": "P", "actions": ["P を起動"]}, ctx)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"][0]["count"], 1)  # 部分一致（「P を起動 設定」）は数えない

    def test_check_plugin_entrypoints_reports_each_problem(self):
        actions = [self._action("A"), self._action("A"), self._action("B", enabled=False)]
        cases = [
            ([{"name": "P", "active": False}], ["A"], "not active"),
            ([], ["A"], "not installed"),
            ([{"name": "P", "active": True}], ["C"], "not found"),
            ([{"name": "P", "active": True}], ["B"], "disabled"),
            ([{"name": "P", "active": True}], ["A"], "duplicate"),
        ]
        for plugins, wanted, expect in cases:
            with self.subTest(expect=expect):
                result = recipes.run_recipe(
                    str(EXAMPLES), "check_plugin_entrypoints", {"plugin": "P", "actions": wanted},
                    self._entry_ctx(plugins, actions),
                )
                self.assertFalse(result["ok"])
                self.assertTrue(any(expect in p for p in result["problems"]), result["problems"])

    def test_check_plugin_entrypoints_validates_args(self):
        for bad in ({}, {"plugin": "P"}, {"plugin": "P", "actions": []}, {"plugin": "P", "actions": [1]}):
            with self.subTest(args=bad), self.assertRaises(ValueError):
                recipes.run_recipe(str(EXAMPLES), "check_plugin_entrypoints", bad, self._ctx({})[0])

    def test_reload_and_check_requires_plugin_arg(self):
        ctx, _ = self._ctx({})
        with self.assertRaises(ValueError):
            recipes.run_recipe(str(EXAMPLES), "reload_and_check", {}, ctx)

    def test_reload_and_check_ok_when_clean(self):
        ctx, _ = self._ctx(
            {"read_log": lambda k: {"last_id": 1, "entries": []}, "reload_plugin": {"active": True}}
        )
        self.assertTrue(recipes.run_recipe(str(EXAMPLES), "reload_and_check", {"plugin": "p"}, ctx)["ok"])


    def test_check_dialog_widgets(self):
        dumped = {
            "window": {"object_name": "dlg"},
            "widgets": [
                {"class": "QLineEdit", "object_name": "codeEdit", "visible": True, "enabled": True},
                {"class": "QComboBox", "object_name": "gridCombo", "visible": True, "enabled": False},
                {"class": "QLabel", "object_name": "", "visible": True, "enabled": True},
            ],
            "truncated": False,
        }
        ctx, calls = self._ctx({"dump_widgets": dumped})
        ok = recipes.run_recipe(str(EXAMPLES), "check_dialog_widgets", {"window": "dlg", "widgets": ["codeEdit"]}, ctx)
        self.assertTrue(ok["ok"])
        bad = recipes.run_recipe(
            str(EXAMPLES), "check_dialog_widgets", {"window": "dlg", "widgets": ["codeEdit", "gridCombo", "nope"]}, ctx
        )
        self.assertEqual(bad["problems"], ["disabled: gridCombo", "missing: nope"])
        self.assertFalse(bad["ok"])
        with self.assertRaises(ValueError):
            recipes.run_recipe(str(EXAMPLES), "check_dialog_widgets", {"window": "dlg", "widgets": []}, ctx)

    def _run_metadata(self, metadata):
        import sys
        import types

        fake_utils = types.ModuleType("qgis.utils")
        fake_utils.pluginMetadata = lambda pkg, key: metadata.get(key, "__error__")
        fake_qgis = types.ModuleType("qgis")
        fake_qgis.utils = fake_utils
        saved = {name: sys.modules.get(name) for name in ("qgis", "qgis.utils")}
        sys.modules["qgis"], sys.modules["qgis.utils"] = fake_qgis, fake_utils
        try:
            ctx, _ = self._ctx({})
            return recipes.run_recipe(str(EXAMPLES), "check_plugin_metadata", {"plugin": "p"}, ctx)
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_check_plugin_metadata(self):
        full = {k: "x" for k in ("name", "qgisMinimumVersion", "description", "about", "author", "repository")}
        full.update({"version": "0.1.0-rc4", "email": ""})
        ok = self._run_metadata(full)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["version"], "0.1.0-rc4")
        without_description = {k: v for k, v in full.items() if k != "description"}
        bad = self._run_metadata(without_description)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["problems"], ["missing: description"])
        blank = dict(full, about="  ")
        self.assertEqual(self._run_metadata(blank)["problems"], ["empty: about"])
        unreadable = self._run_metadata({})
        self.assertEqual(len(unreadable["problems"]), 1)
        self.assertIn("not readable", unreadable["problems"][0])


if __name__ == "__main__":
    unittest.main()
