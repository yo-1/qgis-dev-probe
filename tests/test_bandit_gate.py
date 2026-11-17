"""scripts/check_bandit_gate.py の回帰テスト（C-2）。

Windows / Linux のパス形式、接尾辞偽装、許可ファイル内の件数上限、
critical のスキップ不可を固定する。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_GATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_bandit_gate.py"
_spec = importlib.util.spec_from_file_location("check_bandit_gate", _GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

SKIPS = {"B102"}


def _issue(filename: str, test_id: str = "B102", severity: str = "MEDIUM", line: int = 84) -> dict:
    return {
        "filename": filename,
        "line_number": line,
        "test_id": test_id,
        "test_name": "exec_used",
        "issue_text": "Use of exec detected.",
        "issue_severity": severity,
        "issue_confidence": "HIGH",
    }


def _blocking(issues, skips=SKIPS) -> int:
    blocking, _lines = gate.evaluate({"results": issues}, skips)
    return blocking


class LocationAllowedTests(unittest.TestCase):
    def test_relative_and_package_prefixed_forms(self):
        for name in (
            "core/recipes.py",
            "./core/recipes.py",
            "qgis_dev_probe/core/recipes.py",
            "plugin/qgis_dev_probe/core/recipes.py",
        ):
            with self.subTest(name=name):
                self.assertTrue(gate.location_allowed(name, "core/recipes.py"))

    def test_windows_forms(self):
        for name in (
            ".\\core\\recipes.py",
            "qgis_dev_probe\\core\\recipes.py",
            "C:\\Users\\someone\\qgis_dev_probe\\core\\recipes.py",
            "C:\\repo\\plugin\\qgis_dev_probe\\qgis_side\\handlers.py",
        ):
            with self.subTest(name=name):
                rel = "qgis_side/handlers.py" if "handlers" in name else "core/recipes.py"
                self.assertTrue(gate.location_allowed(name, rel))

    def test_suffix_spoofing_is_rejected(self):
        for name in (
            "x/evilcore/recipes.py",
            "other/core/recipes.py",
            "core/recipes.py.bak",
            "qgis_dev_probe/evilcore/recipes.py",
        ):
            with self.subTest(name=name):
                self.assertFalse(gate.location_allowed(name, "core/recipes.py"))


class GateEvaluateTests(unittest.TestCase):
    def test_adopted_two_sites_pass_on_both_os_forms(self):
        posix = [_issue("qgis_dev_probe/core/recipes.py"), _issue("qgis_dev_probe/qgis_side/handlers.py", line=543)]
        windows = [_issue(".\\core\\recipes.py"), _issue(".\\qgis_side\\handlers.py", line=543)]
        self.assertEqual(_blocking(posix), 0)
        self.assertEqual(_blocking(windows), 0)  # Linux と Windows で同一結果

    def test_b102_in_unapproved_file_blocks(self):
        self.assertEqual(_blocking([_issue("qgis_dev_probe/core/other.py")]), 1)
        self.assertEqual(_blocking([_issue("x/evilcore/recipes.py")]), 1)

    def test_third_exec_in_allowed_files_blocks(self):
        issues = [
            _issue("qgis_dev_probe/core/recipes.py"),
            _issue("qgis_dev_probe/core/recipes.py", line=120),
        ]
        self.assertEqual(_blocking(issues), 1)  # ファイルごとの上限 1 件

    def test_critical_is_never_skippable(self):
        high = _issue("qgis_dev_probe/core/recipes.py", test_id="B301", severity="HIGH")
        self.assertEqual(_blocking([high], skips={"B301"}), 1)
        forced = _issue("qgis_dev_probe/core/recipes.py", test_id="B105", severity="MEDIUM")
        self.assertEqual(_blocking([forced], skips={"B105"}), 1)

    def test_no_findings_passes(self):
        self.assertEqual(_blocking([]), 0)


if __name__ == "__main__":
    unittest.main()
