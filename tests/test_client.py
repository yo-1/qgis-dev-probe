import json
import tempfile
import unittest
from pathlib import Path

from qgis_dev_probe.core.endpoint import EndpointInfo, write_endpoint
from qgis_dev_probe.core.errors import BadRequest
from qgis_dev_probe_mcp import client
from tests.helpers import TOKEN, ProbeFixture


def _fixture():
    def echo(args):
        return {"echo": args}

    def boom(args):
        raise BadRequest("nope", details={"hint": "x"})

    return ProbeFixture({"ping": echo, "get_info": boom})


class ClientTests(unittest.TestCase):
    def _home(self, tmp, port, token=TOKEN):
        home = Path(tmp)
        write_endpoint(home / "endpoint.json", EndpointInfo("127.0.0.1", port, token, 1, "t", 0.0))
        return home

    def test_call_roundtrip_and_error_mapping(self):
        with _fixture() as fx, tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp, fx.port)
            self.assertEqual(client.call("ping", {"a": "日本語"}, home=home), {"echo": {"a": "日本語"}})
            with self.assertRaises(client.ProbeClientError) as ctx:
                client.call("get_info", home=home)
            self.assertEqual(ctx.exception.code, "bad_request")
            self.assertIn("hint", str(ctx.exception))

    def test_wrong_token_is_auth_failed(self):
        with _fixture() as fx, tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp, fx.port, token="wrong")
            with self.assertRaises(client.ProbeClientError) as ctx:
                client.call("ping", home=home)
            self.assertEqual(ctx.exception.code, "auth_failed")

    def test_missing_and_stale_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(client.ProbeClientError) as ctx:
                client.call("ping", home=Path(tmp))
            self.assertEqual(ctx.exception.code, "not_running")
            (Path(tmp) / "endpoint.json").write_text("{bad", encoding="utf-8")
            with self.assertRaises(client.ProbeClientError) as ctx:
                client.call("ping", home=Path(tmp))
            self.assertEqual(ctx.exception.code, "bad_endpoint")
            # 閉じたポート（QGIS が落ちた後の古い endpoint.json）
            (Path(tmp) / "endpoint.json").write_text(
                json.dumps({"host": "127.0.0.1", "port": 1, "token": "t"}), encoding="utf-8"
            )
            with self.assertRaises(client.ProbeClientError) as ctx:
                client.call("ping", home=Path(tmp))
            self.assertEqual(ctx.exception.code, "unreachable")


if __name__ == "__main__":
    unittest.main()
