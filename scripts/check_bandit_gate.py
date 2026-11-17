"""Bandit 結果を plugins.qgis.org 公式の重大度対応付けで判定するゲート。

公式対応付け（QGIS-Plugins-Website の bandit_rules.json による）:
  Bandit LOW    -> info     （公式では無効）
  Bandit MEDIUM -> warning  （有効・開発者がスキップ可能）
  Bandit HIGH   -> critical （有効・スキップ不可）
  例外: B105-B107（hardcoded credentials）は Bandit の MEDIUM でも critical に格上げ。

プロジェクトの .bandit（プラグインフォルダ内）に skips: があれば、そのルールの
warning / info はゲート対象から外す。ただし critical は公式どおりスキップ不可で、
設定に書かれていてもゲートは失敗する。生の Bandit レポートは別途 artifact に
残るため、スキップで検出自体が見えなくなることはない。

使い方: python scripts/check_bandit_gate.py <bandit-report.json> [plugin_dir]
終了コード: critical があれば 1、なければ 0。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FORCED_CRITICAL = {"B105", "B106", "B107"}

# スキップを認める箇所の限定管理。対象ルールが想定外のファイルで検出された
# 場合はスキップを適用せず、ゲートを失敗させる（将来の新規 exec を見逃さない）。
SKIP_LOCATION_ALLOWLIST = {
    "B102": ("core/recipes.py", "qgis_side/handlers.py"),
}

# 許可ファイル内でも、スキップを認めるのはファイルごとにこの件数まで。
# 許可済みファイルに新しい exec が増えた場合に見逃さないための上限。
SKIP_COUNT_LIMIT = {
    "B102": 1,
}

# パッケージのディレクトリ名。許可判定では、プラグインディレクトリからの
# 相対形（core/recipes.py）と、この名前を前置した形だけを認める。
PACKAGE_DIR_NAME = "qgis_dev_probe"


def path_parts(filename: str) -> tuple[str, ...]:
    """Bandit の filename を OS 非依存のパス要素に正規化する。

    Windows の区切り（\\）と POSIX の区切り（/）を統一し、先頭の ./ や
    空要素を取り除く。ドライブ文字（C:）や上位ディレクトリは要素として残る。
    """
    normalized = str(filename).replace("\\", "/")
    return tuple(part for part in normalized.split("/") if part not in ("", "."))


def location_allowed(filename: str, allowed_rel: str) -> bool:
    """filename が許可位置 allowed_rel（プラグイン内相対パス）に一致するか。

    文字列の接尾辞一致は使わない（evilcore/recipes.py のような接尾辞偽装を
    通さないため）。パス要素単位で、相対形そのものか、パッケージ名を前置
    した形の末尾と完全一致する場合だけ許可する。
    """
    parts = path_parts(filename)
    allowed = tuple(allowed_rel.split("/"))
    if parts == allowed:
        return True
    return len(parts) > len(allowed) and parts[-(len(allowed) + 1):] == (PACKAGE_DIR_NAME, *allowed)


def site_severity(issue: dict) -> str:
    if issue.get("issue_severity") == "HIGH" or issue.get("test_id") in FORCED_CRITICAL:
        return "critical"
    if issue.get("issue_severity") == "MEDIUM":
        return "warning"
    return "info"


def read_skips(plugin_dir: Path) -> set[str]:
    bandit_file = plugin_dir / ".bandit"
    if not bandit_file.exists():
        return set()
    match = re.search(r"^skips\s*:\s*(.+)$", bandit_file.read_text(encoding="utf-8"), re.M)
    if not match:
        return set()
    return {token.strip() for token in match.group(1).split(",") if token.strip()}


def evaluate(data: dict, skips: set[str]) -> tuple[int, list[str]]:
    """レポートを判定し、(失敗件数, 出力行) を返す。"""
    blocking = 0
    lines: list[str] = []
    skipped_counts: dict[tuple[str, str], int] = {}
    for issue in data.get("results", []):
        severity = site_severity(issue)
        location = f"{issue.get('filename')}:{issue.get('line_number')}"
        label = f"{issue.get('test_id')} {issue.get('test_name')}: {issue.get('issue_text')}"
        if severity == "critical":
            blocking += 1
            note = "（critical はスキップ不可）" if issue.get("test_id") in skips else ""
            lines.append(f"[critical] {location} {label}{note}")
        elif issue.get("test_id") in skips:
            test_id = issue.get("test_id")
            allowed = SKIP_LOCATION_ALLOWLIST.get(test_id)
            matched = None
            if allowed is not None:
                matched = next(
                    (rel for rel in allowed if location_allowed(issue.get("filename", ""), rel)),
                    None,
                )
                if matched is None:
                    blocking += 1
                    lines.append(
                        f"[unapproved] {location} {label} （スキップ対象として承認された箇所ではないため失敗）"
                    )
                    continue
                key = (test_id, matched)
                skipped_counts[key] = skipped_counts.get(key, 0) + 1
                limit = SKIP_COUNT_LIMIT.get(test_id)
                if limit is not None and skipped_counts[key] > limit:
                    blocking += 1
                    lines.append(
                        f"[unapproved] {location} {label} （許可ファイル内の上限 {limit} 件を超えたため失敗）"
                    )
                    continue
            lines.append(f"[skipped ] {location} {label} （プロジェクト .bandit の skips による）")
        else:
            lines.append(f"[{severity:8}] {location} {label}")
    return blocking, lines


def main() -> int:
    report_path = Path(sys.argv[1])
    plugin_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("plugin/qgis_dev_probe")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    skips = read_skips(plugin_dir)
    blocking, lines = evaluate(data, skips)
    for line in lines:
        print(line)
    if blocking:
        print(f"Bandit gate: critical {blocking} 件のため失敗")
        return 1
    print("Bandit gate: critical なし。通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
