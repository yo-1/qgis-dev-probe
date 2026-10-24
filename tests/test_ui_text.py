import unittest

from qgis_dev_probe.core import ui_text as T
from qgis_dev_probe.core.config import MODES


class UiTextTests(unittest.TestCase):
    def test_every_mode_has_a_japanese_label_containing_its_internal_value(self):
        self.assertEqual(set(T.MODE_LABELS), set(MODES))
        for mode, label in T.MODE_LABELS.items():
            self.assertIn(mode, label)  # 内部値で選べなくならないよう、表示にも内部値を残す

    def test_status_text(self):
        self.assertIn("RUNNING", T.status_text(True, "127.0.0.1", 5555))
        self.assertIn("127.0.0.1:5555", T.status_text(True, "127.0.0.1", 5555))
        self.assertIn("STOPPED", T.status_text(False))

    def test_info_html_shows_version_and_escapes_path(self):
        html = T.build_info_html("0.1.0-rc4", "C:\\Users\\<x>&y\\endpoint.json")
        self.assertIn("0.1.0-rc4", html)
        self.assertIn("&lt;x&gt;&amp;y", html)
        self.assertNotIn("<x>", html)
        for mode in MODES:
            self.assertIn(mode, html)  # 全モードの説明がある


if __name__ == "__main__":
    unittest.main()
