"""QGIS メッセージログのリングバッファ。

QgsApplication.messageLog().messageReceived に接続して add() を呼ぶのは plugin.py（メインスレッド）。
read() はソケットスレッドから呼ばれるため、ロックで保護する。
プラグイン起動前に出たログは取得できない（QGIS 側に読み出し API がないため）。
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

MAX_MESSAGE_CHARS = 4000


class LogBuffer:
    def __init__(self, maxlen: int = 1000) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, message: str, tag: str, level: str) -> None:
        text = str(message)
        if len(text) > MAX_MESSAGE_CHARS:
            text = text[:MAX_MESSAGE_CHARS] + "...[truncated]"
        with self._lock:
            self._entries.append(
                {
                    "id": self._next_id,
                    "ts": time.time(),
                    "level": str(level),
                    "tag": str(tag),
                    "message": text,
                }
            )
            self._next_id += 1

    def read(
        self,
        *,
        limit: int = 50,
        tag: str | None = None,
        level: str | None = None,
        contains: str | None = None,
        since_id: int | None = None,
    ) -> dict[str, Any]:
        """新しい順ではなく古い→新しい順で、条件に合う末尾 limit 件を返す。

        since_id を渡すと、それより新しいものだけを返す（前回の last_id を渡して差分取得できる）。
        """
        with self._lock:
            snapshot = list(self._entries)
            last_id = self._next_id - 1
        needle = contains.lower() if contains else None
        selected = []
        for entry in snapshot:
            if since_id is not None and entry["id"] <= since_id:
                continue
            if tag is not None and entry["tag"] != tag:
                continue
            if level is not None and entry["level"].upper() != level.upper():
                continue
            if needle is not None and needle not in entry["message"].lower():
                continue
            selected.append(entry)
        return {"entries": selected[-limit:], "last_id": last_id, "buffered": len(snapshot)}
