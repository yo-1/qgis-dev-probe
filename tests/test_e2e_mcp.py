"""実際に MCP サーバーを stdio の子プロセスとして起動し、mcp.Client から偽プローブ経由で呼ぶ。"""

import asyncio
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from mcp import Client, StdioServerParameters

from qgis_dev_probe.core.endpoint import EndpointInfo, write_endpoint
from tests.helpers import TOKEN, ProbeFixture

ROOT = Path(__file__).resolve().parent.parent


def _tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = zlib.compress(b"\x00\xff\x00\x00")
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


class E2ETests(unittest.TestCase):
    def test_tools_over_stdio(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "shot.png"
            png.write_bytes(_tiny_png())
            handlers = {
                "ping": lambda a: {"pong": True},
                "screenshot": lambda a: {"path": str(png), "width": 1, "height": 1},
                "execute_code": lambda a: {"result": 1},
            }
            with ProbeFixture(handlers) as fx:  # allow_exec=False
                write_endpoint(Path(tmp) / "endpoint.json", EndpointInfo("127.0.0.1", fx.port, TOKEN, 1, "t", 0.0))
                env = {**os.environ, "QGIS_DEV_PROBE_HOME": tmp, "PYTHONPATH": str(ROOT / "src")}
                params = StdioServerParameters(
                    command=sys.executable, args=["-m", "qgis_dev_probe_mcp.server"], env=env
                )
                asyncio.run(self._scenario(params))

    async def _scenario(self, params):
        async with Client(params) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            self.assertIn("screenshot", tools)
            self.assertIn("wait", tools)

            res = await client.call_tool("ping", {})
            self.assertFalse(res.is_error)

            shot = await client.call_tool("screenshot", {})
            self.assertFalse(shot.is_error)
            kinds = [c.type for c in shot.content]
            self.assertIn("image", kinds)

            denied = await client.call_tool("execute_code", {"code": "1"})
            self.assertTrue(denied.is_error)
            text = "".join(getattr(c, "text", "") for c in denied.content)
            self.assertIn("policy_denied", text)

            missing = await client.call_tool("list_layers", {})  # 偽ハンドラ未実装
            self.assertTrue(missing.is_error)

            waited = await client.call_tool("wait", {"seconds": 0.05})
            self.assertFalse(waited.is_error)


if __name__ == "__main__":
    unittest.main()
