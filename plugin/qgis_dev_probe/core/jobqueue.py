"""ソケットスレッド → メインスレッドへ処理を渡すキュー。

Qt のウィジェット操作と PyQGIS の大半はメインスレッドでしか安全に呼べない。
ソケットを受けるスレッドは `submit()` で仕事を積んで待ち、メインスレッドの QTimer が `pump()` を
定期的に呼んで実行する。

QTimer はモーダルダイアログ表示中（入れ子のイベントループ）でも発火するため、
ダイアログが開いたままでも観察・操作できる想定（実機での確認が必要: docs/VERIFY.md の項目 3）。

設計メモ:
  * このモジュールは Qt に依存しない。pump() を呼ぶ側（QTimer）は qgis_side/mainthread.py。
  * 実行前にタイムアウトしたジョブは CANCELLED にして実行しない（遅れて副作用が出るのを防ぐ）。
  * 実行中にタイムアウトしたジョブは止められない。呼び出し側へはタイムアウトを返し、ジョブは完走する。
  * pump() は再入しない（ハンドラ内で processEvents() が呼ばれても二重実行しない）。
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Any, Callable

from .errors import Busy, JobTimeout

_PENDING, _RUNNING, _DONE, _CANCELLED = "pending", "running", "done", "cancelled"


class _Job:
    __slots__ = ("fn", "event", "lock", "state", "result", "error")

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.fn = fn
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.state = _PENDING
        self.result: Any = None
        self.error: BaseException | None = None


class JobQueue:
    def __init__(self, max_pending: int = 16) -> None:
        self._max_pending = max_pending
        self._pending: collections.deque[_Job] = collections.deque()
        self._lock = threading.Lock()
        self._pumping = False

    def submit(self, fn: Callable[[], Any], timeout_s: float) -> Any:
        """ソケットスレッドから呼ぶ。メインスレッドで fn が終わるまで待ち、結果を返す。"""
        job = _Job(fn)
        with self._lock:
            if len(self._pending) >= self._max_pending:
                raise Busy(f"too many pending jobs (>{self._max_pending}); main thread is busy")
            self._pending.append(job)

        if not job.event.wait(timeout_s):
            with job.lock:
                if job.state == _PENDING:
                    job.state = _CANCELLED
                    raise JobTimeout(
                        f"main thread did not start the job within {timeout_s:g}s "
                        "(QGIS may be busy with a long operation)",
                        details={"started": False},
                    )
                still_running = job.state == _RUNNING
            if still_running:
                raise JobTimeout(
                    f"job is still running after {timeout_s:g}s; it was NOT cancelled "
                    "(subsequent calls will queue behind it)",
                    details={"started": True},
                )
            # タイムアウト判定の直後に完了していた場合は、そのまま結果を返す

        if job.error is not None:
            raise job.error
        return job.result

    def pump(self, budget_s: float = 0.05) -> int:
        """メインスレッドから定期的に呼ぶ。実行したジョブ数を返す。"""
        if self._pumping:
            return 0
        self._pumping = True
        executed = 0
        deadline = time.monotonic() + budget_s
        try:
            while True:
                with self._lock:
                    job = self._pending.popleft() if self._pending else None
                if job is None:
                    break
                with job.lock:
                    if job.state == _CANCELLED:
                        continue
                    job.state = _RUNNING
                try:
                    job.result = job.fn()
                except Exception as exc:  # noqa: BLE001 - 呼び出し元スレッドへ転送する
                    job.error = exc
                finally:
                    with job.lock:
                        job.state = _DONE
                    job.event.set()
                executed += 1
                if time.monotonic() >= deadline:
                    break
        finally:
            self._pumping = False
        return executed

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)
