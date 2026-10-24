"""スクリーンショット等の出力ファイル名を安全に作る。

呼び出し側（AI クライアント）が渡す `name` は、ファイル名の素材としてだけ使う。
パス区切り・相対パス・Windows の予約名などを無害化し、出力先フォルダの外へは書けないようにする。
"""

from __future__ import annotations

import re
import time
from pathlib import Path

_UNSAFE = re.compile(r"[^\w\-.]+", re.UNICODE)  # 日本語（\w は Unicode 文字を含む）は残す
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}  # fmt: skip


def safe_stem(text: str | None, *, fallback: str = "capture", max_len: int = 60) -> str:
    cleaned = _UNSAFE.sub("_", text or "").strip("._-")
    cleaned = cleaned[:max_len].strip("._-")
    if not cleaned:
        return fallback
    if cleaned.lower() in _WINDOWS_RESERVED:
        return f"_{cleaned}"
    return cleaned


def unique_path(directory: Path, stem: str, suffix: str = ".png") -> Path:
    """<directory>/<YYYYmmdd-HHMMSS>_<stem>[_n]<suffix>。既存ファイルは上書きしない。"""
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{time.strftime('%Y%m%d-%H%M%S')}_{safe_stem(stem)}"
    candidate = directory / f"{base}{suffix}"
    counter = 1
    while candidate.exists():
        counter += 1
        candidate = directory / f"{base}_{counter}{suffix}"
    resolved = candidate.resolve()
    if resolved.parent != directory.resolve():
        raise ValueError("output path escapes output directory")
    return candidate
