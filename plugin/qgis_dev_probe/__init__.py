"""QGIS Dev Probe — 開発用プラグイン（配布しない）。

このファイルでは qgis を import しない。tests が QGIS なしで `core` を import できるようにするため、
QGIS 依存の読み込みは classFactory 内に遅延させている。
"""

__version__ = "0.1.2"


def classFactory(iface):  # noqa: N802 - QGIS が要求する名前
    from .plugin import QgisDevProbePlugin

    return QgisDevProbePlugin(iface)
