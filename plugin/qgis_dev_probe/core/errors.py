"""プロトコル全体で使う例外。

`code` はワイヤ上（JSON）のエラーコードになる。MCP 側はこのコードを見て
利用者向けのメッセージを組み立てるため、文字列を変更するときは docs/PROTOCOL.md も更新すること。
"""

from __future__ import annotations

from typing import Any


class ProbeError(Exception):
    code = "error"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details


class BadRequest(ProbeError):
    code = "bad_request"


class AuthFailed(ProbeError):
    code = "auth_failed"


class PolicyDenied(ProbeError):
    code = "policy_denied"


class UnknownTool(ProbeError):
    code = "unknown_tool"


class Busy(ProbeError):
    code = "busy"


class JobTimeout(ProbeError):
    code = "timeout"


class HandlerError(ProbeError):
    """ハンドラ内で想定外の例外が起きたとき（元の例外は details に要約する）。"""

    code = "handler_error"
