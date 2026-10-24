"""プローブプラグインへの同期 TCP クライアント（標準ライブラリのみ）。

1 呼び出し = 1 接続。QGIS 再起動でポートが変わっても、毎回 endpoint.json を読み直すので追従できる。
"""

from __future__ import annotations

import itertools
import json
import os
import socket
from pathlib import Path
from typing import Any

HOME_ENV = "QGIS_DEV_PROBE_HOME"
MAX_RESPONSE_BYTES = 8_388_608 + 65_536  # プラグイン側の上限 + 余裕
_ids = itertools.count(1)


class ProbeClientError(Exception):
    """接続不可、またはプラグインがエラーを返した。LLM がそのまま読めるメッセージにする。"""

    def __init__(self, message: str, *, code: str = "client_error", details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def __str__(self) -> str:
        text = f"[{self.code}] {super().__str__()}"
        if self.details:
            text += "\n" + json.dumps(self.details, ensure_ascii=False, indent=2, default=str)[:6000]
        return text


def default_home() -> Path:
    env = os.environ.get(HOME_ENV)
    return Path(env) if env else Path.home() / ".qgis_dev_probe"


def read_endpoint(home: Path | None = None) -> dict[str, Any]:
    path = (home or default_home()) / "endpoint.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"host": str(data["host"]), "port": int(data["port"]), "token": str(data["token"])}
    except FileNotFoundError:
        raise ProbeClientError(
            f"{path} not found. In QGIS: menu 'Plugins > QGIS Dev Probe' > Start server (サーバー起動) "
            "(or set QGIS_DEV_PROBE_AUTOSTART=1 before launching QGIS).",
            code="not_running",
        ) from None
    except (ValueError, KeyError, OSError) as exc:
        raise ProbeClientError(f"cannot read {path}: {exc}", code="bad_endpoint") from exc


def call(
    tool: str,
    args: dict[str, Any] | None = None,
    *,
    timeout_s: float | None = None,
    home: Path | None = None,
) -> Any:
    """ツールを 1 回呼び、result を返す。失敗時は ProbeClientError。"""
    endpoint = read_endpoint(home)
    request: dict[str, Any] = {
        "id": next(_ids),
        "tool": tool,
        "token": endpoint["token"],
        "args": args or {},
    }
    if timeout_s is not None:
        request["timeout_s"] = timeout_s
    # ソケット待ち時間はプラグイン側の処理上限より少し長くする（先にプラグイン側が job_timeout を返せるように）
    socket_timeout = (timeout_s if timeout_s is not None else 60.0) + 10.0
    payload = (json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        with socket.create_connection((endpoint["host"], endpoint["port"]), timeout=5.0) as sock:
            sock.settimeout(socket_timeout)
            sock.sendall(payload)
            line = _read_line(sock)
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        raise ProbeClientError(
            f"cannot talk to QGIS probe at {endpoint['host']}:{endpoint['port']}: {exc}. "
            "QGIS may have exited (stale endpoint.json) or the server was stopped.",
            code="unreachable",
        ) from exc
    try:
        response = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProbeClientError(f"invalid response from probe: {exc}", code="bad_response") from exc
    if response.get("ok"):
        return response.get("result")
    error = response.get("error") or {}
    raise ProbeClientError(
        str(error.get("message", "unknown error")),
        code=str(error.get("code", "error")),
        details=error.get("details"),
    )


def _read_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            raise ProbeClientError("connection closed before a full response arrived", code="unreachable")
        chunks.append(chunk)
        size += len(chunk)
        if b"\n" in chunk:
            return b"".join(chunks).split(b"\n", 1)[0]
        if size > MAX_RESPONSE_BYTES:
            raise ProbeClientError("response too large", code="response_too_large")
