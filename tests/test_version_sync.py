"""版の表記が 4 か所で揃っていること（プラグイン側 0.1.0-rc1 / PEP 440 側 0.1.0rc1）。"""

import re
import unittest
from pathlib import Path

import qgis_dev_probe
import qgis_dev_probe_mcp

ROOT = Path(__file__).resolve().parent.parent


class VersionSyncTests(unittest.TestCase):
    def test_versions_match(self):
        metadata = re.search(
            r"^version=(\S+)$", (ROOT / "plugin/qgis_dev_probe/metadata.txt").read_text(encoding="utf-8"), re.M
        ).group(1)
        pyproject = re.search(
            r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
        ).group(1)
        self.assertEqual(metadata, qgis_dev_probe.__version__)
        self.assertEqual(pyproject, qgis_dev_probe_mcp.__version__)
        self.assertEqual(metadata.replace("-rc", "rc"), pyproject)


if __name__ == "__main__":
    unittest.main()
