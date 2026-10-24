"""endpoint.json（接続先とトークン）の読み書き。

MCP サーバーはこのファイルを読んで接続する。クライアント設定にトークンを書かずに済み、
QGIS を再起動してポートが変わっても設定変更が不要になる。

POSIX ではファイル 0600・ディレクトリ 0700 にする。Windows では chmod が実質無効なので、
ユーザープロファイル配下（既定で当該ユーザーのみ読める）に置くことに依存する。
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EndpointInfo:
    host: str
    port: int
    token: str
    pid: int
    version: str
    started_at: float


def new_token() -> str:
    return secrets.token_urlsafe(32)


def write_endpoint(path: Path, info: EndpointInfo) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass  # Windows など。失敗しても動作は継続する
    payload = json.dumps(
        {
            "host": info.host,
            "port": info.port,
            "token": info.token,
            "pid": info.pid,
            "version": info.version,
            "started_at": info.started_at,
        },
        indent=2,
    )
    # 一時ファイルに 0600 で書いてから置換する（部分書き込みや緩い権限の瞬間を作らない）
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    os.replace(tmp, path)


def read_endpoint(path: Path) -> EndpointInfo:
    data = json.loads(path.read_text(encoding="utf-8"))
    return EndpointInfo(
        host=str(data["host"]),
        port=int(data["port"]),
        token=str(data["token"]),
        pid=int(data.get("pid", 0)),
        version=str(data.get("version", "")),
        started_at=float(data.get("started_at", time.time())),
    )


def remove_endpoint(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def remove_endpoint_if_token(path: Path, token: str) -> bool:
    """自分が書いたファイル（トークン一致）の場合だけ削除する。

    QGIS を複数起動して同じホームを共有すると、後から起動した側が endpoint.json を上書きする。
    先に停止した側が、相手の接続情報まで消してしまわないための保護。
    """
    try:
        current = read_endpoint(path)
    except (FileNotFoundError, ValueError, KeyError, OSError):
        return False
    if current.token != token:
        return False
    remove_endpoint(path)
    return True
