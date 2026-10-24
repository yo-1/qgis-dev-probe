"""メインスレッドで JobQueue を処理するポンプ。

ソケットスレッドから渡された処理は、Qt のオブジェクトを触るため必ずメインスレッドで実行する。
QTimer はメインスレッドのイベントループで発火する。モーダルダイアログ表示中（ネストしたイベントループ）でも
発火するかは Qt の仕様上は期待できるが、QGIS 3.44 実機では未確認（docs/VERIFY.md 参照）。
"""

from __future__ import annotations

from qgis.PyQt.QtCore import QObject, QTimer

from ..core.jobqueue import JobQueue


class MainThreadPump(QObject):
    def __init__(self, queue: JobQueue, interval_ms: int = 25, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue = queue
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_timeout)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        # シグナルは切断しない。切断すると再 start() してもジョブが処理されなくなる（Stop→Start で発生した不具合）。
        # 接続は __init__ で 1 回だけ行い、解放は QObject の破棄に任せる。
        self._timer.stop()

    def shutdown(self) -> None:
        """プラグイン unload 時に呼ぶ。以後は再利用しない。"""
        self._timer.stop()
        self._timer.deleteLater()

    def _on_timeout(self) -> None:
        self._queue.pump()
