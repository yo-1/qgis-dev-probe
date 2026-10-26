"""Qt6 チェック（plugins.qgis.org）の静的近似。

公式の Qt6 バリデータが v0.1.0 で報告した「スコープなし列挙子」のパターンを
対象に、該当箇所を検出する。公式は実 Qt6 環境で検査するため、本スクリプトは
近似であり、検出ゼロが公式チェックの通過を保証するものではない。

使い方: python scripts/qt6_enum_check.py [対象ディレクトリ]
終了コード: 検出があれば 1、なければ 0。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# (正規表現, 問題の説明, 推奨表記)
RULES: list[tuple[str, str, str]] = [
    # Qt.TextFormat
    (r"\bQt\.(RichText|PlainText|AutoText)\b", "Qt の TextFormat 列挙子がスコープなし", r"Qt.TextFormat.\1"),
    # Qt.AlignmentFlag
    (
        r"\bQt\.(AlignLeft|AlignRight|AlignHCenter|AlignJustify|AlignTop|AlignBottom|AlignVCenter|AlignCenter|AlignBaseline)\b",
        "Qt の AlignmentFlag 列挙子がスコープなし",
        r"Qt.AlignmentFlag.\1",
    ),
    # Qt.TextInteractionFlag
    (
        r"\bQt\.(NoTextInteraction|TextSelectableByMouse|TextSelectableByKeyboard|TextEditable|LinksAccessibleByMouse|LinksAccessibleByKeyboard|TextBrowserInteraction)\b",
        "Qt の TextInteractionFlag 列挙子がスコープなし",
        r"Qt.TextInteractionFlag.\1",
    ),
    # QFrame.Shape
    (
        r"\bQFrame\.(NoFrame|Box|Panel|StyledPanel|HLine|VLine|WinPanel)\b",
        "QFrame の Shape 列挙子がスコープなし",
        r"QFrame.Shape.\1",
    ),
    # QFrame.Shadow
    (r"\bQFrame\.(Plain|Raised|Sunken)\b", "QFrame の Shadow 列挙子がスコープなし", r"QFrame.Shadow.\1"),
    # Qgis.MessageLevel
    (r"\bQgis\.(Info|Warning|Critical|Success)\b", "Qgis の MessageLevel 列挙子がスコープなし", r"Qgis.MessageLevel.\1"),
    # 旧 API フォールバック側の Flag* 表記（公式チェックが dialog/handlers で報告した型）
    (
        r"\bQgsProcessingParameterDefinition\.(Flag\w+)\b",
        "QgsProcessingParameterDefinition の旧 Flag 表記",
        "Qgis.ProcessingParameterFlag.* （3.36+ の名前空間付き enum）",
    ),
]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("plugin/qgis_dev_probe")
    findings = 0
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for pattern, label, suggestion in RULES:
                for match in re.finditer(pattern, line):
                    findings += 1
                    fixed = re.sub(pattern, suggestion, match.group(0)) if "\\" in suggestion else suggestion
                    print(f"{path}:{lineno}: {label}: {match.group(0)!r} -> {fixed}")
    if findings:
        print(f"Qt6 enum check: {findings} 件の検出")
        return 1
    print("Qt6 enum check: 検出なし")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
