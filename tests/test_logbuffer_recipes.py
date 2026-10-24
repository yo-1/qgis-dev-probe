import os
import sys
import tempfile
import unittest
from pathlib import Path

from qgis_dev_probe.core.errors import BadRequest
from qgis_dev_probe.core.logbuffer import LogBuffer
from qgis_dev_probe.core.recipes import RecipeContext, list_recipes, load_recipe, run_recipe


class LogBufferTests(unittest.TestCase):
    def _filled(self):
        buf = LogBuffer(maxlen=5)
        for i in range(8):
            buf.add(f"msg {i}", "Tag" if i % 2 else "Other", "INFO" if i < 6 else "WARNING")
        return buf

    def test_ring_buffer_drops_oldest(self):
        out = self._filled().read(limit=100)
        self.assertEqual([e["id"] for e in out["entries"]], [4, 5, 6, 7, 8])
        self.assertEqual(out["last_id"], 8)
        self.assertEqual(out["buffered"], 5)

    def test_filters_and_limit(self):
        buf = self._filled()
        self.assertEqual([e["id"] for e in buf.read(tag="Tag")["entries"]], [4, 6, 8])
        self.assertEqual([e["id"] for e in buf.read(level="warning")["entries"]], [7, 8])
        self.assertEqual([e["id"] for e in buf.read(contains="MSG 5")["entries"]], [6])
        self.assertEqual([e["id"] for e in buf.read(limit=2)["entries"]], [7, 8])

    def test_since_id_gives_incremental_reads(self):
        buf = self._filled()
        first = buf.read(limit=100)
        buf.add("new", "Tag", "INFO")
        second = buf.read(since_id=first["last_id"])
        self.assertEqual([e["message"] for e in second["entries"]], ["new"])

    def test_long_message_is_truncated(self):
        buf = LogBuffer()
        buf.add("x" * 10000, "t", "INFO")
        self.assertTrue(buf.read()["entries"][0]["message"].endswith("[truncated]"))


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.ctx = RecipeContext(iface=None, project=None, call=lambda tool, **kw: (tool, kw), log=lambda m: None)

    def _write(self, name, body):
        (self.dir / name).write_text(body, encoding="utf-8")

    def test_run_recipe_passes_context_and_args(self):
        self._write("check.py", 'def run(ctx, args):\n    return {"tool": ctx.call("ping", x=args["x"]), "ok": True}\n')
        result = run_recipe(str(self.dir), "check", {"x": 3}, self.ctx)
        self.assertEqual(result, {"tool": ("ping", {"x": 3}), "ok": True})

    def test_recipe_source_is_reloaded_each_call(self):
        self._write("r.py", "def run(ctx, args):\n    return 1\n")
        self.assertEqual(run_recipe(str(self.dir), "r", {}, self.ctx), 1)
        self._write("r.py", "def run(ctx, args):\n    return 2\n")
        self.assertEqual(run_recipe(str(self.dir), "r", {}, self.ctx), 2)

    def test_no_pycache_is_created_in_recipe_dir(self):
        self._write("r.py", "def run(ctx, args):\n    return 1\n")
        run_recipe(str(self.dir), "r", {}, self.ctx)
        self.assertFalse((self.dir / "__pycache__").exists())

    def test_japanese_source_and_values(self):
        self._write("jp.py", '"""森林メッシュの検査"""\ndef run(ctx, args):\n    return {"結果": "合格"}\n')
        self.assertEqual(run_recipe(str(self.dir), "jp", {}, self.ctx), {"結果": "合格"})
        self.assertEqual(list_recipes(str(self.dir)), [{"name": "jp", "summary": "森林メッシュの検査"}])

    def test_list_does_not_execute_recipes(self):
        marker = self.dir / "executed.flag"
        self._write("danger.py", f'"""summary line\n\nmore"""\nopen({str(marker)!r}, "w").write("x")\n')
        self._write("bad-syntax.py", "def run(:\n")
        self._write("not valid name.py", "x = 1\n")
        listing = {r["name"]: r["summary"] for r in list_recipes(str(self.dir))}
        self.assertFalse(marker.exists())
        self.assertEqual(listing["danger"], "summary line")
        self.assertIn("unreadable", listing["bad-syntax"])
        self.assertNotIn("not valid name", listing)

    def test_invalid_names_are_rejected(self):
        for name in ("../evil", "a/b", "a\\b", "", ".hidden", "x" * 80, "a.py"):
            with self.subTest(name=name), self.assertRaises(BadRequest):
                load_recipe(str(self.dir), name)

    def test_missing_recipe_lists_available(self):
        self._write("one.py", "def run(ctx, args):\n    return 1\n")
        with self.assertRaises(BadRequest) as cm:
            load_recipe(str(self.dir), "two")
        self.assertEqual(cm.exception.details, {"available": ["one"]})

    def test_recipe_without_run_is_rejected(self):
        self._write("norun.py", "x = 1\n")
        with self.assertRaisesRegex(BadRequest, "must define run"):
            load_recipe(str(self.dir), "norun")

    def test_syntax_error_propagates_for_dispatcher_to_wrap(self):
        self._write("broken.py", "def run(:\n")
        with self.assertRaises(SyntaxError):
            load_recipe(str(self.dir), "broken")
        self.assertNotIn("qgis_dev_probe_recipe_broken", sys.modules)

    def test_unconfigured_or_missing_dir(self):
        with self.assertRaisesRegex(BadRequest, "not configured"):
            list_recipes("")
        with self.assertRaisesRegex(BadRequest, "does not exist"):
            list_recipes(str(self.dir / "nope"))

    @unittest.skipIf(os.name == "nt", "symlink requires privileges on Windows")
    def test_symlink_escaping_recipe_dir_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "evil.py").write_text("def run(ctx, args):\n    return 'pwned'\n")
            (self.dir / "evil.py").symlink_to(Path(outside) / "evil.py")
            with self.assertRaisesRegex(BadRequest, "escapes"):
                load_recipe(str(self.dir), "evil")


if __name__ == "__main__":
    unittest.main()
