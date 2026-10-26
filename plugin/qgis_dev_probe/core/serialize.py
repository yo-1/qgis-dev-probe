"""任意の Python / Qt の値を、安全に JSON へ変換する。

- JSON が表現できない値（NaN, Inf, bytes, datetime, Qt の QDate など）を文字列にする。
- 循環参照・巨大な値でクライアントを固めないよう、深さ・要素数・文字列長に上限を設ける。
- QVariant の NULL（`isNull()` が真）は None にする。QGIS 非依存にするため、ダックタイピングで判定する。
"""

from __future__ import annotations

import base64
import datetime as _dt
import math
from pathlib import PurePath
from typing import Any

MAX_DEPTH = 8
MAX_ITEMS = 1000
MAX_STR = 20000


def _clip(text: str) -> str:
    if len(text) <= MAX_STR:
        return text
    return text[:MAX_STR] + f"...[truncated {len(text) - MAX_STR} chars]"


def _qt_datetime_like(obj: Any) -> Any:
    for name in ("toPyDateTime", "toPyDate", "toPyTime"):
        method = getattr(obj, name, None)
        if callable(method):
            try:
                return method()
            except Exception:  # noqa: BLE001 - 変換不能なら下流で repr にする
                return None
    return None


def to_jsonable(obj: Any, _depth: int = 0) -> Any:
    if obj is None or isinstance(obj, (bool, int, str)):
        return _clip(obj) if isinstance(obj, str) else obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        return obj
    if _depth >= MAX_DEPTH:
        return _clip(repr(obj))

    if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
        return obj.isoformat()
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, (bytes, bytearray)):
        head = base64.b64encode(bytes(obj[:64])).decode("ascii")
        return f"<bytes len={len(obj)} head_b64={head}>"

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for index, (key, value) in enumerate(obj.items()):
            if index >= MAX_ITEMS:
                out["__truncated__"] = f"{len(obj) - MAX_ITEMS} more keys"
                break
            out[str(key)] = to_jsonable(value, _depth + 1)
        return out
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = list(obj)
        result = [to_jsonable(v, _depth + 1) for v in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            result.append(f"...[{len(items) - MAX_ITEMS} more items]")
        return result

    # QVariant の NULL / Qt の日時など（QGIS 非依存のダックタイピング）
    is_null = getattr(obj, "isNull", None)
    if callable(is_null):
        null_state: bool | None = None
        try:
            null_state = bool(is_null())
        except Exception:  # noqa: BLE001 - 壊れた値でもシリアライズ自体は止めない
            # isNull が判定できない値でも、後続の日時変換などで救える場合があるため、
            # 判定不能として変換へ進む（B110 の指摘に対し、黙って捨てず経路を明示する）。
            null_state = None
        if null_state:
            return None
    converted = _qt_datetime_like(obj)
    if converted is not None:
        return to_jsonable(converted, _depth + 1)

    return _clip(repr(obj))
