"""設定（純 Python）。QgsSettings への保存・読込は plugin.py 側が担当する。

安全上の不変条件をここで強制する:
  * host は loopback のみ（"127.0.0.1" / "localhost" / "::1"）。外部公開はできない。
  * allow_exec は永続化しない（`to_persistable()` に含めない）。QGIS 再起動で必ず無効に戻る。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODE_READONLY = "readonly"
MODE_INTERACTIVE = "interactive"
MODES = (MODE_READONLY, MODE_INTERACTIVE)

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
HOME_ENV = "QGIS_DEV_PROBE_HOME"


def default_home() -> Path:
    """トークン・スクリーンショット等の置き場。環境変数で上書きできる（テストと複数プロファイル用）。"""
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".qgis_dev_probe"


def _split_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("\n", ",").split(",")]
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = [str(p).strip() for p in value]
    else:
        return ()  # 想定外の型（壊れた保存値など）は空扱いにする
    return tuple(p for p in parts if p)


@dataclass
class ProbeConfig:
    host: str = "127.0.0.1"
    port: int = 0  # 0 = OS が空きポートを割り当てる。実際のポートは endpoint.json に書かれる
    mode: str = MODE_READONLY
    allow_exec: bool = False
    recipe_dir: str = ""
    out_dir: str = ""  # 空なら <home>/out
    window_allowlist: tuple[str, ...] = ()
    home: str = ""  # 空なら default_home()

    def validate(self) -> ProbeConfig:
        if self.host not in LOOPBACK_HOSTS:
            raise ValueError(f"host must be loopback ({', '.join(LOOPBACK_HOSTS)}), got {self.host!r}")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 0 <= self.port <= 65535:
            raise ValueError("port must be an integer in 0..65535")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        self.allow_exec = bool(self.allow_exec)
        self.window_allowlist = _split_list(self.window_allowlist)
        return self

    @property
    def home_path(self) -> Path:
        return Path(self.home).expanduser() if self.home else default_home()

    @property
    def out_path(self) -> Path:
        return Path(self.out_dir).expanduser() if self.out_dir else self.home_path / "out"

    @property
    def endpoint_file(self) -> Path:
        return self.home_path / "endpoint.json"

    @property
    def bind_host(self) -> str:
        # "localhost" は解決結果が ::1 になる環境があるため、IPv4 に固定する
        return "127.0.0.1" if self.host == "localhost" else self.host

    def to_persistable(self) -> dict[str, Any]:
        """QgsSettings に保存してよい項目だけ。allow_exec は意図的に含めない。"""
        return {
            "port": self.port,
            "mode": self.mode,
            "recipe_dir": self.recipe_dir,
            "out_dir": self.out_dir,
            "window_allowlist": ",".join(self.window_allowlist),
        }

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> ProbeConfig:
        """保存値から復元する。壊れた値は既定値にフォールバックし、例外にしない（起動不能を避ける）。"""
        config = cls()
        try:
            config.port = int(mapping.get("port", 0) or 0)
        except (TypeError, ValueError):
            config.port = 0
        mode = mapping.get("mode", MODE_READONLY)
        config.mode = mode if mode in MODES else MODE_READONLY
        config.recipe_dir = str(mapping.get("recipe_dir", "") or "")
        config.out_dir = str(mapping.get("out_dir", "") or "")
        config.window_allowlist = _split_list(mapping.get("window_allowlist"))
        try:
            return config.validate()
        except ValueError:
            return cls()
