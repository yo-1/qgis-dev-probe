"""設定・状態ダイアログ（コードで構築。非モーダル）。

プローブ自身の UI は小さく固定なので .ui を使わずコードで組む。検証対象プラグイン側は
.ui + objectName を推奨（docs/DESIGN.md）。ここでも objectName は付けてあり、プローブ自身を
プローブで検証できる。
"""

from __future__ import annotations

import time

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from . import __version__
from .core import ui_text
from .core.config import MODES


class ProbeDialog(QDialog):
    def __init__(self, plugin, parent=None) -> None:
        super().__init__(parent)
        self._plugin = plugin
        self.setObjectName("qgisDevProbeDialog")
        self.setWindowTitle("QGIS Dev Probe")
        self.setModal(False)
        self.resize(900, 520)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("statusLabel")
        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("modeCombo")
        # 表示は日本語併記、内部値（readonly/interactive）はアイテムデータに持つ
        for mode in MODES:
            self.mode_combo.addItem(ui_text.MODE_LABELS[mode], mode)
        self.exec_check = QCheckBox(ui_text.LABELS["allow_exec"], self)
        self.exec_check.setObjectName("allowExecCheck")
        self.recipe_edit = QLineEdit(self)
        self.recipe_edit.setObjectName("recipeDirEdit")
        self.allowlist_edit = QLineEdit(self)
        self.allowlist_edit.setObjectName("allowlistEdit")
        self.allowlist_edit.setPlaceholderText(ui_text.LABELS["allowlist_placeholder"])
        self.activity_view = QPlainTextEdit(self)
        self.activity_view.setObjectName("activityView")
        self.activity_view.setReadOnly(True)
        self.toggle_button = QPushButton(self)
        self.toggle_button.setObjectName("toggleButton")
        self.close_button = QPushButton(ui_text.LABELS["close"], self)
        self.close_button.setObjectName("closeButton")

        form = QFormLayout()
        form.addRow(ui_text.LABELS["status"], self.status_label)
        form.addRow(ui_text.LABELS["mode"], self.mode_combo)
        form.addRow("", self.exec_check)
        form.addRow(ui_text.LABELS["recipe_dir"], self.recipe_edit)
        form.addRow(ui_text.LABELS["allowlist"], self.allowlist_edit)
        buttons = QHBoxLayout()
        buttons.addWidget(self.toggle_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(QLabel(ui_text.LABELS["activity"], self))
        left.addWidget(self.activity_view)
        left.addLayout(buttons)

        # 右側: バージョンと説明。リッチテキストなので外部入力（パス）は ui_text 側でエスケープ済み
        self.info_label = QLabel(self)
        self.info_label.setObjectName("infoLabel")
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info_panel = QFrame(self)
        self.info_panel.setObjectName("infoPanel")
        self.info_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.info_panel.setFixedWidth(340)
        QVBoxLayout(self.info_panel).addWidget(self.info_label)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addWidget(self.info_panel)

        self.toggle_button.clicked.connect(self._on_toggle)
        self.close_button.clicked.connect(self.close)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.exec_check.toggled.connect(self._on_exec_toggled)

    # ---------------------------------------------------------- 表示更新
    def refresh(self) -> None:
        config = self._plugin.config
        running = self._plugin.running
        self.status_label.setText(
            ui_text.status_text(running, config.bind_host, self._plugin.server.port if running else 0)
        )
        self.toggle_button.setText(ui_text.LABELS["stop"] if running else ui_text.LABELS["start"])
        self.info_label.setText(ui_text.build_info_html(__version__, str(config.endpoint_file)))
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(config.mode)))
        self.mode_combo.blockSignals(False)
        self.exec_check.blockSignals(True)
        self.exec_check.setChecked(config.allow_exec)
        self.exec_check.blockSignals(False)
        self.recipe_edit.setText(config.recipe_dir)
        self.allowlist_edit.setText(", ".join(config.window_allowlist))
        # 設定欄は停止中のみ編集可（起動中に変えて挙動が曖昧になるのを避ける）。mode と exec は即時反映
        self.recipe_edit.setEnabled(not running)
        self.allowlist_edit.setEnabled(not running)
        dispatcher = self._plugin.dispatcher
        lines = []
        if dispatcher is not None:
            for item in list(dispatcher.activity)[-30:]:
                lines.append(f"{time.strftime('%H:%M:%S', time.localtime(item.get('ts', 0)))} {item}")
        self.activity_view.setPlainText("\n".join(lines))

    # ---------------------------------------------------------- ハンドラ
    def _on_mode_changed(self, _index: int) -> None:
        mode = self.mode_combo.currentData()
        if mode in MODES:  # 想定外の値は設定へ入れない
            self._plugin.config.mode = mode
            self._plugin.save_config()

    def _on_exec_toggled(self, checked: bool) -> None:
        self._plugin.config.allow_exec = checked  # 保存しない

    def _on_toggle(self) -> None:
        try:
            if self._plugin.running:
                self._plugin.stop_server()
            else:
                config = self._plugin.config
                config.recipe_dir = self.recipe_edit.text().strip()
                config.window_allowlist = self.allowlist_edit.text()
                config.validate()
                self._plugin.save_config()
                self._plugin.start_server()
        except Exception as exc:  # noqa: BLE001 - ユーザーへ表示する
            self.status_label.setText(f"ERROR: {exc}")
            return
        self.refresh()
