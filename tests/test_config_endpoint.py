import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qgis_dev_probe.core import config as C
from qgis_dev_probe.core import endpoint as E


class ConfigTests(unittest.TestCase):
    def test_defaults_are_safe(self):
        cfg = C.ProbeConfig().validate()
        self.assertEqual(cfg.mode, C.MODE_READONLY)
        self.assertFalse(cfg.allow_exec)
        self.assertEqual(cfg.host, "127.0.0.1")

    def test_non_loopback_host_is_rejected(self):
        for host in ("0.0.0.0", "192.168.1.10", "example.com", ""):
            with self.subTest(host=host), self.assertRaises(ValueError):
                C.ProbeConfig(host=host).validate()

    def test_loopback_hosts_are_accepted(self):
        for host in ("127.0.0.1", "localhost", "::1"):
            C.ProbeConfig(host=host).validate()
        self.assertEqual(C.ProbeConfig(host="localhost").bind_host, "127.0.0.1")

    def test_invalid_port_and_mode(self):
        for kwargs in ({"port": -1}, {"port": 65536}, {"port": True}, {"mode": "root"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                C.ProbeConfig(**kwargs).validate()

    def test_allowlist_parsing(self):
        cfg = C.ProbeConfig(window_allowlist="a, b\n c ,,").validate()
        self.assertEqual(cfg.window_allowlist, ("a", "b", "c"))

    def test_allow_exec_is_never_persisted(self):
        cfg = C.ProbeConfig(allow_exec=True, mode=C.MODE_INTERACTIVE).validate()
        self.assertNotIn("allow_exec", cfg.to_persistable())
        restored = C.ProbeConfig.from_mapping({**cfg.to_persistable(), "allow_exec": True})
        self.assertFalse(restored.allow_exec)

    def test_roundtrip_and_garbage_fallback(self):
        cfg = C.ProbeConfig(
            port=9000, mode=C.MODE_INTERACTIVE, recipe_dir="/r", out_dir="/o", window_allowlist=("x", "y")
        ).validate()
        restored = C.ProbeConfig.from_mapping(cfg.to_persistable())
        self.assertEqual(restored.port, 9000)
        self.assertEqual(restored.mode, C.MODE_INTERACTIVE)
        self.assertEqual(restored.window_allowlist, ("x", "y"))
        garbage = C.ProbeConfig.from_mapping({"port": "abc", "mode": "root", "window_allowlist": 5})
        self.assertEqual((garbage.port, garbage.mode), (0, C.MODE_READONLY))
        self.assertEqual(C.ProbeConfig.from_mapping({"port": 99999}).port, 0)

    def test_paths_follow_home_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = C.ProbeConfig(home=tmp).validate()
            self.assertEqual(cfg.endpoint_file, Path(tmp) / "endpoint.json")
            self.assertEqual(cfg.out_path, Path(tmp) / "out")
            self.assertEqual(C.ProbeConfig(home=tmp, out_dir="/x").out_path, Path("/x"))

    def test_default_home_env_override(self):
        with mock.patch.dict(os.environ, {C.HOME_ENV: "/custom/home"}):
            self.assertEqual(C.default_home(), Path("/custom/home"))


class EndpointTests(unittest.TestCase):
    def _info(self):
        return E.EndpointInfo("127.0.0.1", 5555, E.new_token(), 123, "0.1.0", 1.5)

    def test_tokens_are_unique_and_long(self):
        a, b = E.new_token(), E.new_token()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 32)

    def test_write_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "endpoint.json"
            info = self._info()
            E.write_endpoint(path, info)
            self.assertEqual(E.read_endpoint(path), info)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_file_is_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d" / "endpoint.json"
            E.write_endpoint(path, self._info())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_remove_only_when_token_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "endpoint.json"
            mine, theirs = self._info(), self._info()
            E.write_endpoint(path, theirs)  # 別の QGIS が後から上書きした状態
            self.assertFalse(E.remove_endpoint_if_token(path, mine.token))
            self.assertTrue(path.exists())
            self.assertTrue(E.remove_endpoint_if_token(path, theirs.token))
            self.assertFalse(path.exists())
            self.assertFalse(E.remove_endpoint_if_token(path, mine.token))  # 無くても例外にしない
            path.write_text("{broken", encoding="utf-8")
            self.assertFalse(E.remove_endpoint_if_token(path, mine.token))  # 壊れていても例外にしない

    def test_rewrite_replaces_and_remove_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "endpoint.json"
            E.write_endpoint(path, self._info())
            second = self._info()
            E.write_endpoint(path, second)
            self.assertEqual(E.read_endpoint(path).token, second.token)
            E.remove_endpoint(path)
            E.remove_endpoint(path)  # 2 回目も例外にならない
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
