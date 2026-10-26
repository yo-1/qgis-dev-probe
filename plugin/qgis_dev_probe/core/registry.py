"""ツール一覧の唯一の定義元（名前・カテゴリ・既定タイムアウト・スレッド要件）。

MCP サーバー側（src/qgis_dev_probe_mcp/server.py）は配布物が別なのでこのモジュールを import しない。
代わりに tests/test_registry_sync.py が、両者のツール名が一致していることを検査する。

カテゴリの意味:
  observe : 状態を読むだけ（既定の readonly モードで許可）。スクリーンショットは専用の出力フォルダへ
            自動生成した名前でだけ書く。
  act     : GUI 操作・Processing 実行・レイヤ追加削除・プラグイン再読込・レシピ実行。interactive が必要。
  exec    : 任意コード実行。interactive かつ「任意コード実行を許可」のセッション限りの設定が必要。
"""

from __future__ import annotations

from dataclasses import dataclass

OBSERVE = "observe"
ACT = "act"
EXEC = "exec"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    category: str
    main_thread: bool = True  # Qt / QGIS API に触る処理は必ずメインスレッド
    timeout_s: float = 15.0


_SPECS = [
    # --- observe ---
    ToolSpec("ping", OBSERVE, timeout_s=5.0),
    ToolSpec("get_info", OBSERVE),
    ToolSpec("list_windows", OBSERVE),
    ToolSpec("dump_widgets", OBSERVE),
    ToolSpec("list_actions", OBSERVE),
    ToolSpec("screenshot", OBSERVE, timeout_s=30.0),
    ToolSpec("list_layers", OBSERVE),
    ToolSpec("inspect_layer", OBSERVE, timeout_s=60.0),
    ToolSpec("list_algorithms", OBSERVE),
    ToolSpec("get_algorithm_params", OBSERVE),
    ToolSpec("list_plugins", OBSERVE),
    ToolSpec("read_log", OBSERVE, main_thread=False),
    ToolSpec("list_recipes", OBSERVE, main_thread=False),
    # --- act ---
    ToolSpec("set_widget", ACT),
    ToolSpec("click_widget", ACT),
    ToolSpec("trigger_action", ACT),
    ToolSpec("close_window", ACT),
    ToolSpec("add_layer", ACT, timeout_s=60.0),
    ToolSpec("remove_layer", ACT),
    ToolSpec("run_algorithm", ACT, timeout_s=600.0),
    ToolSpec("reload_plugin", ACT, timeout_s=60.0),
    ToolSpec("run_recipe", EXEC, timeout_s=600.0),
    # --- exec ---
    ToolSpec("execute_code", EXEC, timeout_s=60.0),
]

TOOL_SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in _SPECS}
