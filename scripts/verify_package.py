"""提出用 ZIP の構造・metadata・個人情報ゲートを検査する。

scripts/package_plugin.py が作った ZIP を対象に、plugins.qgis.org への提出前に
最低限そろっていなければならないものを機械的に確認する。

使い方: python scripts/verify_package.py <zip-path>
終了コード: 不備があれば 1、なければ 0。
"""

from __future__ import annotations

import configparser
import io
import sys
import zipfile
from pathlib import Path

TOP = "qgis_dev_probe"
REQUIRED_FIXED = [f"{TOP}/metadata.txt", f"{TOP}/__init__.py", f"{TOP}/LICENSE"]
REQUIRED_METADATA = ["name", "version", "description", "author", "email", "qgisMinimumVersion"]
# 公開物に混入してはならない文字列（小文字で比較）。
# 保守者の氏名そのものは、ゲートのパターンとして書くこと自体が公開になるため
# ここには含めない。氏名の混入は提出前の目視確認で担保する。
FORBIDDEN = [
    "gmail.com",
    "so-net.ne.jp",
    "yoichi_wada@",
    "users.noreply.github.com",
    "akasabi",
]


def main() -> int:
    zip_path = Path(sys.argv[1])
    problems: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        tops = {name.split("/")[0] for name in names if name}
        if tops != {TOP}:
            problems.append(f"トップレベルフォルダが {TOP} のみでない: {sorted(tops)}")
        for required in REQUIRED_FIXED:
            if required not in names:
                problems.append(f"必須ファイル不足: {required}")
        if any("__pycache__" in name or name.endswith(".pyc") for name in names):
            problems.append("__pycache__ / .pyc が混入している")
        metadata_text = ""
        if f"{TOP}/metadata.txt" in names:
            metadata_text = archive.read(f"{TOP}/metadata.txt").decode("utf-8")
            parser = configparser.ConfigParser()
            parser.read_file(io.StringIO(metadata_text))
            general = parser["general"] if parser.has_section("general") else {}
            for key in REQUIRED_METADATA:
                if key not in general or not general[key].strip():
                    problems.append(f"metadata.txt に {key} がない")
            icon = general.get("icon", "").strip()
            if icon and f"{TOP}/{icon}" not in names:
                problems.append(f"metadata の icon={icon} が ZIP にない")
        if f"{TOP}/__init__.py" in names:
            init_text = archive.read(f"{TOP}/__init__.py").decode("utf-8")
            if "def classFactory" not in init_text:
                problems.append("__init__.py に classFactory がない")
        for name in names:
            if name.endswith((".py", ".txt", ".md", ".json", ".cfg")):
                text = archive.read(name).decode("utf-8", errors="ignore").lower()
                for needle in FORBIDDEN:
                    if needle.lower() in text:
                        problems.append(f"個人情報ゲート: {name} に {needle!r} が含まれる")
    if problems:
        for problem in problems:
            print(f"NG: {problem}")
        print(f"Package verify: {len(problems)} 件の不備")
        return 1
    print(f"Package verify: 問題なし（{zip_path.name}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
