import datetime
import unittest
from pathlib import Path

from qgis_dev_probe.core import args as A
from qgis_dev_probe.core import serialize as S
from qgis_dev_probe.core.errors import BadRequest


class ArgsTests(unittest.TestCase):
    def test_get_str(self):
        self.assertEqual(A.get_str({"a": "x"}, "a"), "x")
        self.assertIsNone(A.get_str({}, "a", required=False))
        self.assertEqual(A.get_str({}, "a", required=False, default="d"), "d")
        for bad in ({}, {"a": None}, {"a": ""}, {"a": 1}):
            with self.subTest(bad=bad), self.assertRaises(BadRequest):
                A.get_str(bad, "a")

    def test_get_str_optional_empty_string_is_allowed(self):
        self.assertEqual(A.get_str({"a": ""}, "a", required=False), "")

    def test_get_int_rejects_bool_and_float(self):
        self.assertEqual(A.get_int({"n": 3}, "n"), 3)
        self.assertEqual(A.get_int({}, "n", default=9), 9)
        for bad in (True, 1.5, "3"):
            with self.subTest(bad=bad), self.assertRaises(BadRequest):
                A.get_int({"n": bad}, "n")

    def test_get_int_bounds(self):
        self.assertEqual(A.get_int({"n": 5}, "n", minimum=5, maximum=5), 5)
        with self.assertRaises(BadRequest):
            A.get_int({"n": 4}, "n", minimum=5)
        with self.assertRaises(BadRequest):
            A.get_int({"n": 6}, "n", maximum=5)

    def test_get_bool_and_dict(self):
        self.assertTrue(A.get_bool({"b": True}, "b"))
        self.assertFalse(A.get_bool({}, "b"))
        with self.assertRaises(BadRequest):
            A.get_bool({"b": "true"}, "b")
        self.assertEqual(A.get_dict({}, "d"), {})
        self.assertEqual(A.get_dict({"d": {"k": 1}}, "d"), {"k": 1})
        with self.assertRaises(BadRequest):
            A.get_dict({"d": []}, "d")
        with self.assertRaises(BadRequest):
            A.get_dict({}, "d", required=True)


class _FakeNull:
    def isNull(self):  # noqa: N802 - Qt 命名に合わせる
        return True


class _FakeQDate:
    def isNull(self):  # noqa: N802
        return False

    def toPyDate(self):  # noqa: N802
        return datetime.date(2026, 10, 24)


class SerializeTests(unittest.TestCase):
    def test_special_floats(self):
        self.assertEqual(S.to_jsonable(float("nan")), "NaN")
        self.assertEqual(S.to_jsonable(float("inf")), "Infinity")
        self.assertEqual(S.to_jsonable(float("-inf")), "-Infinity")
        self.assertEqual(S.to_jsonable(-9999.0), -9999.0)

    def test_scalars_and_containers(self):
        data = {"a": (1, 2), "b": {3}, "c": None, "d": True, 5: "x"}
        out = S.to_jsonable(data)
        self.assertEqual(out["a"], [1, 2])
        self.assertEqual(out["b"], [3])
        self.assertIs(out["d"], True)
        self.assertEqual(out["5"], "x")

    def test_datetime_path_bytes(self):
        self.assertEqual(S.to_jsonable(datetime.date(2026, 1, 2)), "2026-01-02")
        self.assertEqual(S.to_jsonable(datetime.datetime(2026, 1, 2, 3, 4, 5)), "2026-01-02T03:04:05")
        self.assertEqual(S.to_jsonable(Path("a") / "b"), str(Path("a") / "b"))
        self.assertTrue(S.to_jsonable(b"abc").startswith("<bytes len=3"))

    def test_qt_like_objects(self):
        self.assertIsNone(S.to_jsonable(_FakeNull()))
        self.assertEqual(S.to_jsonable(_FakeQDate()), "2026-10-24")

    def test_limits(self):
        self.assertTrue(S.to_jsonable("x" * (S.MAX_STR + 5)).endswith("chars]"))
        long_list = S.to_jsonable(list(range(S.MAX_ITEMS + 10)))
        self.assertEqual(len(long_list), S.MAX_ITEMS + 1)
        self.assertIn("more items", long_list[-1])
        nested: list = []
        cursor = nested
        for _ in range(S.MAX_DEPTH + 3):
            nxt: list = []
            cursor.append(nxt)
            cursor = nxt
        S.to_jsonable(nested)  # 深い入れ子でも例外にならない

    def test_circular_reference_does_not_hang(self):
        loop: list = []
        loop.append(loop)
        S.to_jsonable(loop)

    def test_unknown_object_uses_repr(self):
        class Odd:
            def __repr__(self):
                return "<Odd>"

        self.assertEqual(S.to_jsonable(Odd()), "<Odd>")

    def test_japanese_roundtrip(self):
        self.assertEqual(S.to_jsonable({"名前": "山梨県甲府市"}), {"名前": "山梨県甲府市"})


if __name__ == "__main__":
    unittest.main()
