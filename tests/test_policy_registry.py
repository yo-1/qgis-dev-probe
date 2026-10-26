import unittest

from qgis_dev_probe.core.config import MODE_INTERACTIVE, MODE_READONLY, ProbeConfig
from qgis_dev_probe.core.errors import PolicyDenied
from qgis_dev_probe.core.policy import Policy
from qgis_dev_probe.core.registry import ACT, EXEC, OBSERVE, TOOL_SPECS


def _policy(**kwargs):
    return Policy(ProbeConfig(**kwargs).validate())


class PolicyTests(unittest.TestCase):
    def test_readonly_allows_only_observe(self):
        policy = _policy(mode=MODE_READONLY)
        for spec in TOOL_SPECS.values():
            with self.subTest(tool=spec.name):
                if spec.category == OBSERVE:
                    policy.check(spec)
                else:
                    with self.assertRaises(PolicyDenied):
                        policy.check(spec)

    def test_interactive_allows_act_but_not_exec_by_default(self):
        policy = _policy(mode=MODE_INTERACTIVE)
        for spec in TOOL_SPECS.values():
            with self.subTest(tool=spec.name):
                if spec.category in (OBSERVE, ACT):
                    policy.check(spec)
                else:
                    with self.assertRaises(PolicyDenied):
                        policy.check(spec)

    def test_exec_needs_both_interactive_and_allow_exec(self):
        spec = TOOL_SPECS["execute_code"]
        _policy(mode=MODE_INTERACTIVE, allow_exec=True).check(spec)
        with self.assertRaises(PolicyDenied):
            _policy(mode=MODE_READONLY, allow_exec=True).check(spec)

    def test_run_recipe_is_exec_gated(self):
        # レシピは任意コードの実行なので、execute_code と同じ EXEC 区分にする
        spec = TOOL_SPECS["run_recipe"]
        self.assertEqual(spec.category, EXEC)
        with self.assertRaises(PolicyDenied):
            _policy(mode=MODE_INTERACTIVE).check(spec)
        _policy(mode=MODE_INTERACTIVE, allow_exec=True).check(spec)

    def test_policy_follows_live_config_changes(self):
        cfg = ProbeConfig().validate()
        policy = Policy(cfg)
        with self.assertRaises(PolicyDenied):
            policy.check(TOOL_SPECS["click_widget"])
        cfg.mode = MODE_INTERACTIVE
        policy.check(TOOL_SPECS["click_widget"])

    def test_window_allowlist(self):
        open_policy = _policy()
        self.assertTrue(open_policy.window_allowed("anything", "Any Title"))
        policy = _policy(window_allowlist="ForestMeshDialog, Mesh 20m")
        self.assertTrue(policy.window_allowed("ForestMeshDialog", ""))
        self.assertTrue(policy.window_allowed("", "森林 mesh 20M generator"))
        self.assertFalse(policy.window_allowed("QgisApp", "QGIS"))
        self.assertFalse(policy.window_allowed("ForestMeshDialogX", "other"))


class RegistryTests(unittest.TestCase):
    def test_specs_are_consistent(self):
        for name, spec in TOOL_SPECS.items():
            self.assertEqual(name, spec.name)
            self.assertIn(spec.category, (OBSERVE, ACT, EXEC))
            self.assertGreater(spec.timeout_s, 0)

    def test_state_changing_tools_are_not_observe(self):
        for name in ("set_widget", "click_widget", "trigger_action", "close_window", "add_layer", "remove_layer",
                     "run_algorithm", "reload_plugin"):
            self.assertEqual(TOOL_SPECS[name].category, ACT, name)
        # 任意コードの実行に当たる2つは EXEC（許可経路監査に基づく）
        self.assertEqual(TOOL_SPECS["execute_code"].category, EXEC)
        self.assertEqual(TOOL_SPECS["run_recipe"].category, EXEC)

    def test_only_thread_safe_tools_skip_main_thread(self):
        off_main = {n for n, s in TOOL_SPECS.items() if not s.main_thread}
        self.assertEqual(off_main, {"read_log", "list_recipes"})


if __name__ == "__main__":
    unittest.main()
