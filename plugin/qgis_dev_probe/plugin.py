"""プラグイン本体: メニュー登録、サーバーの起動/停止、ログ収集、unload 時の後始末。

サーバーは既定で停止状態。起動は (1) メニューのダイアログ、または (2) 環境変数
QGIS_DEV_PROBE_AUTOSTART=1 のときだけ。allow_exec は設定に保存せず、環境変数
QGIS_DEV_PROBE_ALLOW_EXEC=1 かダイアログのチェックでセッション中だけ有効にする。
"""

from __future__ import annotations

import json
import logging
import os
import time

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtWidgets import QAction

from . import __version__
from .core.config import ProbeConfig
from .core.dispatcher import Dispatcher
from .core.endpoint import EndpointInfo, new_token, remove_endpoint_if_token, write_endpoint
from .core.jobqueue import JobQueue
from .core.logbuffer import LogBuffer
from .core.policy import Policy
from .core.server import ProbeServer
from .qgis_side.handlers import HandlerContext, build_handlers
from .qgis_side.mainthread import MainThreadPump

SETTINGS_KEY = "qgis_dev_probe/config"
MENU = "&QGIS Dev Probe（開発用・AI実機検証）"
logger = logging.getLogger("qgis_dev_probe")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class QgisDevProbePlugin:
    def __init__(self, iface) -> None:
        self.iface = iface
        self.config = self._load_config()
        self.logbuffer = LogBuffer()
        self.queue = JobQueue()
        self.pump = MainThreadPump(self.queue)
        self.server: ProbeServer | None = None
        self.dispatcher: Dispatcher | None = None
        self.token: str | None = None
        self._action: QAction | None = None
        self._dialog = None
        self._log_connected = False

    # ---------------------------------------------------------- QGIS ライフサイクル
    def initGui(self) -> None:  # noqa: N802 - QGIS が呼ぶ名前
        self._action = QAction("QGIS Dev Probe 設定...", self.iface.mainWindow())
        self._action.setObjectName("qgisDevProbeAction")
        self._action.triggered.connect(self.show_dialog)
        self.iface.addPluginToMenu(MENU, self._action)  # 再ロード時の二重登録を unload で防ぐ
        self._connect_log()
        if _env_flag("QGIS_DEV_PROBE_AUTOSTART"):
            try:
                self.start_server()
            except Exception:  # noqa: BLE001
                logger.exception("autostart failed")

    def unload(self) -> None:
        self.stop_server()
        self.pump.shutdown()
        self._disconnect_log()
        if self._dialog is not None:
            self._dialog.close()
            self._dialog.deleteLater()
            self._dialog = None
        if self._action is not None:
            self.iface.removePluginMenu(MENU, self._action)
            self._action.triggered.disconnect(self.show_dialog)
            self._action.deleteLater()
            self._action = None

    # ---------------------------------------------------------- サーバー操作
    @property
    def running(self) -> bool:
        return self.server is not None and self.server.running

    def start_server(self) -> int:
        if self.running:
            return self.server.port
        if _env_flag("QGIS_DEV_PROBE_ALLOW_EXEC"):
            self.config.allow_exec = True
        self.config.validate()
        ctx = HandlerContext(
            iface=self.iface, config=self.config, policy=Policy(self.config), logbuffer=self.logbuffer
        )
        handlers = build_handlers(ctx)
        self.dispatcher = Dispatcher(handlers, self.config, self.queue)
        self.token = new_token()
        server = ProbeServer(self.dispatcher, self.token, host=self.config.bind_host, port=self.config.port)
        port = server.start()
        self.server = server
        self.pump.start()
        write_endpoint(
            self.config.endpoint_file,
            EndpointInfo(self.config.bind_host, port, self.token, os.getpid(), __version__, time.time()),
        )
        self._log(f"server started on {self.config.bind_host}:{port} mode={self.config.mode}")
        return port

    def stop_server(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None
            if self.token is not None:
                remove_endpoint_if_token(self.config.endpoint_file, self.token)
                self.token = None
            self._log("server stopped")
        self.pump.stop()

    # ---------------------------------------------------------- 設定
    def _load_config(self) -> ProbeConfig:
        raw = QgsSettings().value(SETTINGS_KEY, "")
        try:
            data = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            data = {}
        return ProbeConfig.from_mapping(data if isinstance(data, dict) else {})

    def save_config(self) -> None:
        QgsSettings().setValue(SETTINGS_KEY, json.dumps(self.config.to_persistable()))

    # ---------------------------------------------------------- ログ収集（QGIS メッセージログ → LogBuffer）
    def _connect_log(self) -> None:
        if not self._log_connected:
            QgsApplication.messageLog().messageReceived.connect(self._on_message)
            self._log_connected = True

    def _disconnect_log(self) -> None:
        if self._log_connected:
            QgsApplication.messageLog().messageReceived.disconnect(self._on_message)
            self._log_connected = False

    def _on_message(self, message, tag, level) -> None:
        names = {Qgis.MessageLevel.Info: "info", Qgis.MessageLevel.Warning: "warning", Qgis.MessageLevel.Critical: "critical", Qgis.MessageLevel.Success: "success"}
        self.logbuffer.add(message, tag, names.get(level, str(level)))

    def _log(self, message: str) -> None:
        self.logbuffer.add(message, "QgisDevProbe", "info")
        logger.info(message)

    # ---------------------------------------------------------- UI
    def show_dialog(self) -> None:
        from .dialog import ProbeDialog

        if self._dialog is None:
            self._dialog = ProbeDialog(self, self.iface.mainWindow())
        self._dialog.refresh()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

