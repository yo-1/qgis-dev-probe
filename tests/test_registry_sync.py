"""プラグイン側 registry と MCP 側ツール定義の名前が一致していること。

MCP 側 `wait` はローカル専用ヘルパなので除外する。handlers.py は qgis に依存して import できないため、
ソースを ast で読んで _HANDLERS のキーを取り出す。
"""

import ast
import asyncio
import unittest
from pathlib import Path

from qgis_dev_probe.core.registry import TOOL_SPECS
from qgis_dev_probe_mcp.server import server

LOCAL_ONLY = {"wait"}
HANDLERS_SRC = Path(__file__).resolve().parent.parent / "plugin/qgis_dev_probe/qgis_side/handlers.py"


def _handler_keys() -> set[str]:
    tree = ast.parse(HANDLERS_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "_HANDLERS":
            return {k.value for k in node.value.keys}
    raise AssertionError("_HANDLERS not found")


class RegistrySyncTests(unittest.TestCase):
    def test_mcp_tools_match_registry(self):
        mcp_names = {t.name for t in asyncio.run(server.list_tools())} - LOCAL_ONLY
        self.assertEqual(mcp_names, set(TOOL_SPECS))

    def test_handlers_match_registry(self):
        self.assertEqual(_handler_keys(), set(TOOL_SPECS))


if __name__ == "__main__":
    unittest.main()
