"""テスト共通: 実ソケットのプローブサーバーを、偽ハンドラで立ち上げる。"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any

from qgis_dev_probe.core.config import MODE_INTERACTIVE, ProbeConfig
from qgis_dev_probe.core.dispatcher import Dispatcher
from qgis_dev_probe.core.jobqueue import JobQueue
from qgis_dev_probe.core.server import ProbeServer

TOKEN = "test-token-0123456789"


class FakeMainThread:
    def __init__(self, queue: JobQueue):
        self.queue = queue
        self.thread_id: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.thread_id = threading.get_ident()
        while not self._stop.is_set():
            self.queue.pump()
            time.sleep(0.003)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)


class ProbeFixture:
    """handlers を渡すと、サーバーとメインスレッド模擬を起動する。"""

    def __init__(self, handlers: dict, *, mode: str = MODE_INTERACTIVE, allow_exec: bool = False):
        self.config = ProbeConfig(mode=mode, allow_exec=allow_exec).validate()
        self.queue = JobQueue()
        self.main = FakeMainThread(self.queue)
        self.dispatcher = Dispatcher(handlers, self.config, self.queue)
        self.server = ProbeServer(self.dispatcher, TOKEN, port=0, idle_timeout_s=5)

    def __enter__(self):
        self.main.start()
        self.port = self.server.start()
        return self

    def __exit__(self, *exc):
        self.server.stop()
        self.main.stop()

    def connect(self) -> socket.socket:
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        return sock


def send_line(sock: socket.socket, message: dict | bytes) -> dict[str, Any]:
    data = message if isinstance(message, bytes) else (json.dumps(message, ensure_ascii=False) + "\n").encode()
    sock.sendall(data)
    return read_response(sock)


def read_response(sock: socket.socket) -> dict[str, Any]:
    buffer = b""
    while not buffer.endswith(b"\n"):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buffer += chunk
    return json.loads(buffer.decode("utf-8")) if buffer else {}


def call(sock: socket.socket, tool: str, args: dict | None = None, *, token: str = TOKEN, **extra) -> dict:
    return send_line(sock, {"id": 1, "token": token, "tool": tool, "args": args or {}, **extra})
