import json
import unittest

from qgis_dev_probe.core import protocol
from qgis_dev_probe.core.errors import BadRequest, PolicyDenied


class ParseRequestTests(unittest.TestCase):
    def test_minimal_valid_request(self):
        req = protocol.parse_request(b'{"tool":"ping","token":"t"}')
        self.assertEqual(req.tool, "ping")
        self.assertEqual(req.token, "t")
        self.assertEqual(req.args, {})
        self.assertIsNone(req.timeout_s)
        self.assertIsNone(req.id)

    def test_full_request(self):
        line = json.dumps(
            {"id": 7, "tool": "run_algorithm", "token": "t", "args": {"a": 1}, "timeout_s": 12}
        ).encode()
        req = protocol.parse_request(line)
        self.assertEqual((req.id, req.args, req.timeout_s), (7, {"a": 1}, 12.0))

    def test_null_args_becomes_empty_dict(self):
        req = protocol.parse_request(b'{"tool":"ping","args":null}')
        self.assertEqual(req.args, {})

    def test_invalid_inputs_raise_bad_request(self):
        bad_lines = [
            b"not json",
            b"\xff\xfe",
            b"[1,2,3]",
            b'{"token":"t"}',
            b'{"tool":""}',
            b'{"tool":5}',
            b'{"tool":"x","token":5}',
            b'{"tool":"x","args":[1]}',
            b'{"tool":"x","timeout_s":"10"}',
            b'{"tool":"x","timeout_s":true}',
            b'{"tool":"x","timeout_s":0}',
            b'{"tool":"x","timeout_s":-1}',
            b'{"tool":"x","timeout_s":99999}',
        ]
        for line in bad_lines:
            with self.subTest(line=line), self.assertRaises(BadRequest):
                protocol.parse_request(line)


class EncodeTests(unittest.TestCase):
    def test_japanese_is_not_escaped_and_ends_with_newline(self):
        data = protocol.encode({"msg": "森林資源量メッシュ"})
        self.assertTrue(data.endswith(b"\n"))
        self.assertIn("森林資源量メッシュ".encode(), data)
        self.assertEqual(json.loads(data)["msg"], "森林資源量メッシュ")

    def test_nan_is_rejected(self):
        with self.assertRaises(ValueError):
            protocol.encode({"v": float("nan")})

    def test_error_response_shape(self):
        err = PolicyDenied("nope", details={"mode": "readonly"})
        data = json.loads(protocol.error_response(3, err))
        self.assertEqual(data["id"], 3)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "policy_denied")
        self.assertEqual(data["error"]["details"], {"mode": "readonly"})

    def test_ok_response_shape(self):
        data = json.loads(protocol.ok_response("a", {"x": 1}))
        self.assertEqual(data, {"id": "a", "ok": True, "result": {"x": 1}})


if __name__ == "__main__":
    unittest.main()
