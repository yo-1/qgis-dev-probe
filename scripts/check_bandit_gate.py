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


def main() -> int:
    report_path = Path(sys.argv[1])
    plugin_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("plugin/qgis_dev_probe")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    skips = read_skips(plugin_dir)
    blocking = 0
    for issue in data.get("results", []):
        severity = site_severity(issue)
        location = f"{issue.get('filename')}:{issue.get('line_number')}"
        label = f"{issue.get('test_id')} {issue.get('test_name')}: {issue.get('issue_text')}"
        if severity == "critical":
            blocking += 1
            note = "（critical はスキップ不可）" if issue.get("test_id") in skips else ""
            print(f"[critical] {location} {label}{note}")
        elif issue.get("test_id") in skips:
            allowed = SKIP_LOCATION_ALLOWLIST.get(issue.get("test_id"))
            if allowed is not None and not any(issue.get("filename", "").endswith(p) for p in allowed):
                blocking += 1
                print(f"[unapproved] {location} {label} （スキップ対象として承認された箇所ではないため失敗）")
            else:
                print(f"[skipped ] {location} {label} （プロジェクト .bandit の skips による）")
        else:
            print(f"[{severity:8}] {location} {label}")
    if blocking:
        print(f"Bandit gate: critical {blocking} 件のため失敗")
        return 1
    print("Bandit gate: critical なし。通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
