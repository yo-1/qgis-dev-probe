"""run_recipe / execute_code 実行時の環境情報ログ行の整形（qgis に依存しない純粋関数）。

記録するのは「Desktop / QGIS 版 / Python 版 / 対象レシピ名」だけ。コード本文や引数は記録しない。
レシピ名は呼び出し側（MCP クライアント）由来の入力なので、制御文字を除去し長さを制限する。
"""

from __future__ import annotations

MAX_TARGET_CHARS = 80


def _sanitize_target(target: str) -> str:
    # 改行・制御文字を含むとログ行の偽装（log injection）に使えるため空白へ置換する
    cleaned = "".join(ch if ch.isprintable() else " " for ch in str(target)).strip()
    if len(cleaned) > MAX_TARGET_CHARS:
        cleaned = cleaned[:MAX_TARGET_CHARS] + "...[truncated]"
    return cleaned


def format_environment_line(tool: str, qgis_version: str, python_version: str, target: str | None = None) -> str:
    """例: ``run_recipe environment: QGIS Desktop QGIS=3.44.15 Python=3.12.15 target=my_recipe``"""
    line = f"{tool} environment: QGIS Desktop QGIS={qgis_version} Python={python_version}"
    if target is not None:
        line += f" target={_sanitize_target(target)}"
    return line
