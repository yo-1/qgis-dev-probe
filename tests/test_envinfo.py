"""core.envinfo（run_recipe / execute_code の環境ログ行整形）のテスト。qgis 不要。"""

from __future__ import annotations

import unittest

from qgis_dev_probe.core.envinfo import MAX_TARGET_CHARS, format_environment_line


class FormatEnvironmentLineTest(unittest.TestCase):
    def test_execute_code_has_no_target(self):
        line = format_environment_line("execute_code", "3.44.15-Solothurn", "3.12.15")
        self.assertEqual(line, "execute_code environment: QGIS Desktop QGIS=3.44.15-Solothurn Python=3.12.15")
        self.assertNotIn("target=", line)

    def test_run_recipe_includes_target(self):
        line = format_environment_line("run_recipe", "3.44.15", "3.12.15", "my_recipe")
        self.assertIn("QGIS Desktop", line)
        self.assertIn("QGIS=3.44.15", line)
        self.assertIn("Python=3.12.15", line)
        self.assertTrue(line.endswith("target=my_recipe"))

    def test_target_control_characters_are_neutralized(self):
        line = format_environment_line("run_recipe", "3", "3", "evil\nexecute_code environment: forged\r\x00x")
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        self.assertNotIn("\x00", line)

    def test_target_length_is_capped(self):
        line = format_environment_line("run_recipe", "3", "3", "a" * 1000)
        self.assertIn("...[truncated]", line)
        self.assertLess(len(line), 200 + MAX_TARGET_CHARS)

    def test_empty_target_and_japanese_target(self):
        self.assertTrue(format_environment_line("run_recipe", "3", "3", "").endswith("target="))
        self.assertIn("target=標高レシピ", format_environment_line("run_recipe", "3", "3", "標高レシピ"))


if __name__ == "__main__":
    unittest.main()
