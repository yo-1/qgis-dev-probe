"""プラグインを QGIS の「ZIP からインストール」用に固める。

使い方:  python scripts/package_plugin.py   ->  dist/qgis_dev_probe-<version>.zip
metadata.txt と __init__.py の version 不一致、__pycache__ 混入を防ぐ。
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / "plugin" / "qgis_dev_probe"


def _metadata_version() -> str:
    match = re.search(r"^version=(\S+)\s*$", (PLUGIN_DIR / "metadata.txt").read_text(encoding="utf-8"), re.M)
    if not match:
        raise SystemExit("metadata.txt に version= がありません")
    return match.group(1)


def _init_version() -> str:
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"), re.M)
    if not match:
        raise SystemExit("__init__.py に __version__ がありません")
    return match.group(1)


def _pyproject_version() -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not match:
        raise SystemExit("pyproject.toml に version がありません")
    return match.group(1)


def main() -> int:
    version = _metadata_version()
    if version.replace("-rc", "rc") != _pyproject_version():
        print(f"version 不一致: metadata.txt={version} pyproject.toml={_pyproject_version()}", file=sys.stderr)
        return 1
    if version != _init_version():
        print(f"version 不一致: metadata.txt={version} __init__.py={_init_version()}", file=sys.stderr)
        return 1
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    target = dist / f"qgis_dev_probe-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            archive.write(path, Path("qgis_dev_probe") / path.relative_to(PLUGIN_DIR))
        archive.write(ROOT / "LICENSE", "qgis_dev_probe/LICENSE")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
