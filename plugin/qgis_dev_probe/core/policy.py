"""どのツールを許可するか。設定（ProbeConfig）を毎回参照するので、ダイアログでの切り替えが即時に効く。"""

from __future__ import annotations

from .config import MODE_INTERACTIVE, ProbeConfig
from .errors import PolicyDenied
from .registry import ACT, EXEC, OBSERVE, ToolSpec


class Policy:
    def __init__(self, config: ProbeConfig) -> None:
        self._config = config

    def check(self, spec: ToolSpec) -> None:
        if spec.category == OBSERVE:
            return
        interactive = self._config.mode == MODE_INTERACTIVE
        if spec.category == ACT:
            if not interactive:
                raise PolicyDenied(
                    f"tool '{spec.name}' changes QGIS state and needs mode 'interactive' "
                    "(switch it in Plugins > QGIS Dev Probe)",
                    details={"mode": self._config.mode, "required": MODE_INTERACTIVE},
                )
            return
        if spec.category == EXEC:
            if not interactive:
                raise PolicyDenied(
                    f"tool '{spec.name}' needs mode 'interactive'",
                    details={"mode": self._config.mode},
                )
            if not self._config.allow_exec:
                raise PolicyDenied(
                    f"tool '{spec.name}' (arbitrary code execution) is disabled; "
                    "enable it explicitly in the QGIS Dev Probe dialog (not persisted across restarts)",
                )
            return
        raise PolicyDenied(f"tool '{spec.name}' has unknown category {spec.category!r}")

    def window_allowed(self, object_name: str, title: str) -> bool:
        """GUI 操作系ツールの対象ウィンドウ制限。許可リストが空なら制限なし。

        各項目は objectName との完全一致、または windowTitle への大文字小文字無視の部分一致。
        """
        allowlist = self._config.window_allowlist
        if not allowlist:
            return True
        title_lower = (title or "").lower()
        for pattern in allowlist:
            if pattern == (object_name or "") or pattern.lower() in title_lower:
                return True
        return False
