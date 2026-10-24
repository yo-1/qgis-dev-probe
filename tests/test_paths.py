import tempfile
import unittest
from pathlib import Path

from qgis_dev_probe.core.paths import safe_stem, unique_path


class SafeStemTests(unittest.TestCase):
    def test_path_traversal_and_separators_are_neutralised(self):
        for text in ("../../etc/passwd", "..\\..\\Windows\\system32", "a/b/c", "/abs/path"):
            with self.subTest(text=text):
                stem = safe_stem(text)
                self.assertNotIn("/", stem)
                self.assertNotIn("\\", stem)
                self.assertFalse(stem.startswith("."))

    def test_japanese_is_kept(self):
        self.assertEqual(safe_stem("メッシュ生成ダイアログ"), "メッシュ生成ダイアログ")

    def test_empty_and_reserved_names(self):
        self.assertEqual(safe_stem(None), "capture")
        self.assertEqual(safe_stem("../.."), "capture")
        self.assertEqual(safe_stem("   "), "capture")
        self.assertEqual(safe_stem("CON"), "_CON")
        self.assertEqual(safe_stem("com1"), "_com1")

    def test_length_is_limited(self):
        self.assertLessEqual(len(safe_stem("a" * 500)), 60)


class UniquePathTests(unittest.TestCase):
    def test_creates_directory_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "out"
            first = unique_path(out, "shot")
            first.write_bytes(b"1")
            second = unique_path(out, "shot")
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, out)
            self.assertTrue(second.name.endswith(".png"))

    def test_hostile_name_stays_inside_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = unique_path(Path(tmp), "../../evil")
            self.assertEqual(path.resolve().parent, Path(tmp).resolve())


if __name__ == "__main__":
    unittest.main()
