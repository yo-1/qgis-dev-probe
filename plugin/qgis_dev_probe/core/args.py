"""ハンドラ引数の検証ヘルパ。

型が合わないときは BadRequest にして、どの引数が悪いかを呼び出し側（AI クライアント）へ返す。
"""

from __future__ import annotations

from typing import Any

from .errors import BadRequest

_MISSING = object()


def get_str(
    args: dict[str, Any], key: str, *, required: bool = True, default: str | None = None
) -> str | None:
    value = args.get(key, _MISSING)
    if value is _MISSING or value is None:
        if required:
            raise BadRequest(f"'{key}' is required")
        return default
    if not isinstance(value, str):
        raise BadRequest(f"'{key}' must be a string")
    if required and value == "":
        raise BadRequest(f"'{key}' must not be empty")
    return value


def get_int(
    args: dict[str, Any],
    key: str,
    *,
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    value = args.get(key, _MISSING)
    if value is _MISSING or value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadRequest(f"'{key}' must be an integer")
    if minimum is not None and value < minimum:
        raise BadRequest(f"'{key}' must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise BadRequest(f"'{key}' must be <= {maximum}")
    return value


def get_bool(args: dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = args.get(key, _MISSING)
    if value is _MISSING or value is None:
        return default
    if not isinstance(value, bool):
        raise BadRequest(f"'{key}' must be a boolean")
    return value


def get_dict(args: dict[str, Any], key: str, *, required: bool = False) -> dict[str, Any]:
    value = args.get(key, _MISSING)
    if value is _MISSING or value is None:
        if required:
            raise BadRequest(f"'{key}' is required")
        return {}
    if not isinstance(value, dict):
        raise BadRequest(f"'{key}' must be an object")
    return value
