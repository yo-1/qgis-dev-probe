"""ワイヤプロトコル（改行区切り JSON, UTF-8）。

リクエスト : {"id": 1, "token": "...", "tool": "ping", "args": {...}, "timeout_s": 15}
レスポンス : {"id": 1, "ok": true, "result": ...}
             {"id": 1, "ok": false, "error": {"code": "...", "message": "...", "details": ...}}

1 行 = 1 メッセージ。JSON は ensure_ascii=False なので日本語はそのまま流れる。
MCP 側 (src/qgis_dev_probe_mcp/client.py) は意図的にこのモジュールを import せず、同じ仕様を
再実装している（配布物を分けるため）。互換性は tests/test_e2e_mcp.py で担保する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .errors import BadRequest, ProbeError

PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 1_048_576  # 1 MiB。これを超える要求は拒否する
MAX_RESPONSE_BYTES = 8_388_608  # 8 MiB。巨大な結果を返してクライアントを固めないための上限
MAX_TIMEOUT_S = 3600.0


@dataclass
class Request:
    id: Any
    tool: str
    token: str
    args: dict[str, Any] = field(default_factory=dict)
    timeout_s: float | None = None


def encode(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode(
        "utf-8"
    )


def parse_request(line: bytes) -> Request:
    """1 行のバイト列を検証して Request にする。不正なら BadRequest。"""
    try:
        data = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadRequest(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BadRequest("request must be a JSON object")

    tool = data.get("tool")
    if not isinstance(tool, str) or not tool:
        raise BadRequest("'tool' must be a non-empty string")
    token = data.get("token", "")
    if not isinstance(token, str):
        raise BadRequest("'token' must be a string")
    args = data.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise BadRequest("'args' must be an object")

    timeout_s = data.get("timeout_s")
    if timeout_s is not None:
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
            raise BadRequest("'timeout_s' must be a number")
        if not 0 < timeout_s <= MAX_TIMEOUT_S:
            raise BadRequest(f"'timeout_s' must be in (0, {MAX_TIMEOUT_S}]")
        timeout_s = float(timeout_s)

    return Request(id=data.get("id"), tool=tool, token=token, args=args, timeout_s=timeout_s)


def ok_response(request_id: Any, result: Any) -> bytes:
    return encode({"id": request_id, "ok": True, "result": result})


def error_response(request_id: Any, error: ProbeError) -> bytes:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.details is not None:
        payload["details"] = error.details
    return encode({"id": request_id, "ok": False, "error": payload})
