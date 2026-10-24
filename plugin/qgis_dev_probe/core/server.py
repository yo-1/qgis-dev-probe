"""localhost 限定のソケットサーバー（スレッド）。QGIS / Qt には依存しない。

* 1 行 1 メッセージの JSON（core/protocol.py）。1 接続で複数リクエストを順に処理する。
* 認証はリクエストごとにトークンを検査する（hmac.compare_digest）。不一致なら接続を閉じる。
* 要求サイズ・同時接続数・アイドル時間に上限を設ける。
* 実処理は Dispatcher に委譲する。Dispatcher が必要に応じてメインスレッドへ処理を渡す。
"""

from __future__ import annotations

import hmac
import logging
import os
import socket
import threading

from .dispatcher import Dispatcher
from .errors import AuthFailed, BadRequest, Busy, ProbeError
from .protocol import (
    MAX_LINE_BYTES,
    MAX_RESPONSE_BYTES,
    error_response,
    ok_response,
    parse_request,
)

logger = logging.getLogger("qgis_dev_probe")


class ProbeServer:
    def __init__(
        self,
        dispatcher: Dispatcher,
        token: str,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        max_connections: int = 8,
        idle_timeout_s: float = 120.0,
    ) -> None:
        if host not in ("127.0.0.1", "::1"):
            raise ValueError(f"refusing to bind non-loopback host {host!r}")
        if not token:
            raise ValueError("token must not be empty")
        self._dispatcher = dispatcher
        self._token = token
        self._host = host
        self._requested_port = port
        self._idle_timeout_s = idle_timeout_s
        self._slots = threading.BoundedSemaphore(max_connections)
        self._stop = threading.Event()
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._connections: set[socket.socket] = set()
        self._connections_lock = threading.Lock()
        self.port = 0

    @property
    def running(self) -> bool:
        return self._accept_thread is not None and self._accept_thread.is_alive()

    def start(self) -> int:
        family = socket.AF_INET6 if ":" in self._host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        if os.name != "nt":
            # Windows の SO_REUSEADDR は「他プロセスが同じポートを奪える」意味になるため設定しない
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self._host, self._requested_port))
        listener.listen(8)
        listener.settimeout(0.5)  # 停止フラグを定期的に確認するため
        self._listener = listener
        self.port = listener.getsockname()[1]
        self._stop.clear()
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="qgis-dev-probe-accept", daemon=True
        )
        self._accept_thread.start()
        logger.info("server listening on %s:%d", self._host, self.port)
        return self.port

    def stop(self) -> None:
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        with self._connections_lock:
            connections = list(self._connections)
        for conn in connections:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass
        thread = self._accept_thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._accept_thread = None
        logger.info("server stopped")

    # ---- internals ----
    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            listener = self._listener
            if listener is None:
                break
            try:
                conn, _addr = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # listener が閉じられた
            if not self._slots.acquire(blocking=False):
                self._reject_busy(conn)
                continue
            with self._connections_lock:
                self._connections.add(conn)
            threading.Thread(
                target=self._serve_connection, args=(conn,), name="qgis-dev-probe-conn", daemon=True
            ).start()

    @staticmethod
    def _reject_busy(conn: socket.socket) -> None:
        try:
            conn.sendall(error_response(None, Busy("too many connections")))
        except OSError:
            pass
        finally:
            conn.close()

    def _serve_connection(self, conn: socket.socket) -> None:
        reader = None
        try:
            conn.settimeout(self._idle_timeout_s)
            reader = conn.makefile("rb")
            while not self._stop.is_set():
                line = reader.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break  # EOF
                if len(line) > MAX_LINE_BYTES and not line.endswith(b"\n"):
                    conn.sendall(error_response(None, BadRequest("request line too large")))
                    break
                if not self._handle_line(conn, line):
                    break
        except (socket.timeout, ConnectionError, OSError):
            pass
        except Exception:  # noqa: BLE001 - 接続スレッドの想定外例外はログに残して接続を閉じる
            logger.exception("unexpected error in connection thread")
        finally:
            with self._connections_lock:
                self._connections.discard(conn)
            # makefile() のラッパを閉じ忘れると、GC 時に ResourceWarning が QGIS のログに出る（実機で確認）
            if reader is not None:
                try:
                    reader.close()
                except OSError:
                    pass
            try:
                conn.close()
            except OSError:
                pass
            self._slots.release()

    def _handle_line(self, conn: socket.socket, line: bytes) -> bool:
        """1 リクエストを処理して応答を送る。接続を継続するなら True。"""
        request_id = None
        try:
            request = parse_request(line)
            request_id = request.id
            if not hmac.compare_digest(request.token.encode("utf-8"), self._token.encode("utf-8")):
                logger.warning("rejected request with invalid token")
                conn.sendall(error_response(request_id, AuthFailed("invalid token")))
                return False
            result = self._dispatcher.handle(request)
            payload = ok_response(request_id, result)
            if len(payload) > MAX_RESPONSE_BYTES:
                payload = error_response(
                    request_id,
                    ProbeError(
                        f"response too large ({len(payload)} bytes > {MAX_RESPONSE_BYTES}); "
                        "narrow the query (limit/filters)",
                        code="response_too_large",
                    ),
                )
        except ProbeError as exc:
            payload = error_response(request_id, exc)
        except ValueError as exc:  # encode() の NaN など。通常は serialize で除去済み
            payload = error_response(request_id, ProbeError(f"cannot encode response: {exc}"))
        conn.sendall(payload)
        return True
