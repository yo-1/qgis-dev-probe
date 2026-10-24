"""リクエスト → ポリシー検査 → （必要ならメインスレッドで）ハンドラ実行 → JSON 化。"""

from __future__ import annotations

import collections
import logging
import time
import traceback
from collections.abc import Mapping
from typing import Any, Callable

from .config import ProbeConfig
from .errors import HandlerError, ProbeError, UnknownTool
from .jobqueue import JobQueue
from .policy import Policy
from .protocol import Request
from .registry import TOOL_SPECS, ToolSpec
from .serialize import to_jsonable

logger = logging.getLogger("qgis_dev_probe")

Handler = Callable[[dict], Any]


class Dispatcher:
    def __init__(
        self,
        handlers: Mapping[str, Handler],
        config: ProbeConfig,
        queue: JobQueue,
        *,
        specs: Mapping[str, ToolSpec] = TOOL_SPECS,
        activity_limit: int = 200,
    ) -> None:
        self._handlers = handlers
        self._specs = specs
        self._queue = queue
        self.policy = Policy(config)
        # ダイアログの「最近の呼び出し」表示用。引数は記録しない（パスや値に機微情報があり得るため）
        self.activity: collections.deque[dict[str, Any]] = collections.deque(maxlen=activity_limit)

    def handle(self, request: Request) -> Any:
        started = time.monotonic()
        spec = self._specs.get(request.tool)
        try:
            if spec is None:
                raise UnknownTool(
                    f"unknown tool {request.tool!r}", details={"available": sorted(self._specs)}
                )
            self.policy.check(spec)
            handler = self._handlers.get(request.tool)
            if handler is None:
                raise UnknownTool(f"tool {request.tool!r} is not implemented in this build")

            timeout_s = request.timeout_s or spec.timeout_s
            args = request.args
            if spec.main_thread:
                result = self._queue.submit(lambda: handler(args), timeout_s)
            else:
                result = handler(args)
            payload = to_jsonable(result)
        except ProbeError as exc:
            self._record(request.tool, spec, False, started, exc.code)
            raise
        except Exception as exc:  # noqa: BLE001 - ハンドラの想定外例外をプロトコルのエラーに変換する
            self._record(request.tool, spec, False, started, HandlerError.code)
            tail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            logger.error("tool=%s failed: %s: %s", request.tool, type(exc).__name__, exc)
            raise HandlerError(
                f"{type(exc).__name__}: {exc}",
                details={"type": type(exc).__name__, "traceback": tail[-3000:]},
            ) from exc

        self._record(request.tool, spec, True, started, None)
        return payload

    def _record(
        self, tool: str, spec: ToolSpec | None, ok: bool, started: float, code: str | None
    ) -> None:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        self.activity.append(
            {
                "ts": time.time(),
                "tool": tool,
                "category": spec.category if spec else "?",
                "ok": ok,
                "ms": elapsed_ms,
                "code": code,
            }
        )
        logger.info("tool=%s ok=%s ms=%d code=%s", tool, ok, elapsed_ms, code)
