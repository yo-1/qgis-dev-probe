"""MCP サーバー本体。ツール定義は plugin/.../core/registry.py と名前を一致させる（tests/test_registry_sync.py）。

プラグイン側は同期・ブロッキングなので、非同期ツールから asyncio.to_thread で呼ぶ
（長い run_algorithm 中に他のツール呼び出しやキャンセルを妨げないため）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__, client

INSTRUCTIONS = """\
Development-only probe for a QGIS instance running on this machine (plugin: qgis-dev-probe).
Typical flow: ping -> list_windows -> dump_widgets(window) -> set_widget / click_widget -> screenshot -> read_log.
- If a tool says 'not_running', ask the user to start the server from QGIS menu 'QGIS Dev Probe'.
- Acting tools need mode 'interactive' in the QGIS dialog; execute_code additionally needs the session-only exec checkbox.
- click_widget returns immediately; the click is deferred, so a modal dialog it opens does not block the reply.
  Use wait(seconds) then list_windows / screenshot to observe the result.
- Prefer widget objectName over visible text. Results of long operations (run_algorithm) can take minutes: pass timeout_s.
"""

server = MCPServer("qgis-dev-probe", instructions=INSTRUCTIONS, version=__version__)


async def _call(tool: str, args: dict[str, Any] | None = None, timeout_s: float | None = None) -> Any:
    clean = {k: v for k, v in (args or {}).items() if v is not None}
    try:
        return await asyncio.to_thread(client.call, tool, clean, timeout_s=timeout_s)
    except client.ProbeClientError as exc:
        # SDK は ToolError 以外の例外メッセージをモデルに見せない。code と details を読ませるため変換する
        raise ToolError(str(exc)) from exc


# ---------------------------------------------------------------- observe
@server.tool()
async def ping() -> Any:
    """Check connectivity; returns plugin version, mode and QGIS pid."""
    return await _call("ping")


@server.tool()
async def get_info() -> Any:
    """QGIS/Python/Qt versions, platform, profile dir, project, probe home and output dirs."""
    return await _call("get_info")


@server.tool()
async def list_windows(include_hidden: bool = False) -> Any:
    """List top-level windows (objectName, title, class, geometry, modal) and the active modal window."""
    return await _call("list_windows", {"include_hidden": include_hidden})


@server.tool()
async def dump_widgets(
    window: str,
    max_items: int = 400,
    only_named: bool = False,
    include_internal: bool = False,
    visible_only: bool = True,
) -> Any:
    """Dump the widget tree of a window (selector: objectName or title).

    Hidden widgets are skipped by default (visible_only); use only_named to cut noise further.
    Geometry of child widgets is relative to the parent; window geometry is in screen coordinates.
    """
    return await _call(
        "dump_widgets",
        {
            "window": window,
            "max_items": max_items,
            "only_named": only_named,
            "include_internal": include_internal,
            "visible_only": visible_only,
        },
    )


@server.tool()
async def screenshot(window: str | None = None, object_name: str | None = None, name: str | None = None) -> list:
    """Capture QGIS main window, a window, or one widget. Returns the PNG image plus its saved path."""
    info = await _call("screenshot", {"window": window, "object_name": object_name, "name": name})
    path = Path(str(info.get("path", "")))
    try:
        data = await asyncio.to_thread(path.read_bytes)
    except OSError as exc:
        # 別マシンの QGIS を指している等でファイルが読めない場合も、パスだけは返す
        return [f"screenshot saved at {path} but could not be read here: {exc}\n{info}"]
    return [Image(data=data, format="png"), f"saved: {path} ({info.get('width')}x{info.get('height')})"]


@server.tool()
async def list_layers() -> Any:
    """Layers in the current project (id, name, type, crs, public source)."""
    return await _call("list_layers")


@server.tool()
async def inspect_layer(layer: str, sample: int = 3) -> Any:
    """Details of a layer by id or unique name: fields/geometry (vector) or bands/nodata (raster), sample features."""
    return await _call("inspect_layer", {"layer": layer, "sample": sample})


@server.tool()
async def list_algorithms(search: str | None = None, provider: str | None = None, limit: int = 50) -> Any:
    """Search Processing algorithms by id/name substring."""
    return await _call("list_algorithms", {"search": search, "provider": provider, "limit": limit})


@server.tool()
async def get_algorithm_params(algorithm_id: str) -> Any:
    """Parameter and output definitions of a Processing algorithm (e.g. 'native:buffer')."""
    return await _call("get_algorithm_params", {"algorithm_id": algorithm_id})


@server.tool()
async def list_plugins() -> Any:
    """Installed plugins with version and active state."""
    return await _call("list_plugins")


@server.tool()
async def read_log(
    limit: int = 50,
    tag: str | None = None,
    level: str | None = None,
    contains: str | None = None,
    since_id: int | None = None,
) -> Any:
    """Read QGIS message-log entries captured since the probe was loaded. Use since_id to poll for new entries."""
    return await _call(
        "read_log", {"limit": limit, "tag": tag, "level": level, "contains": contains, "since_id": since_id}
    )


@server.tool()
async def list_recipes() -> Any:
    """List recipe files (name + docstring) in the configured recipe directory."""
    return await _call("list_recipes")


# ---------------------------------------------------------------- act
@server.tool()
async def set_widget(window: str, object_name: str, value: Any, index: int | None = None) -> Any:
    """Set a widget value (text, number, bool, combo index/text, ...). Refuses invisible/disabled/read-only widgets."""
    return await _call("set_widget", {"window": window, "object_name": object_name, "value": value, "index": index})


@server.tool()
async def click_widget(
    window: str, object_name: str | None = None, text: str | None = None, index: int | None = None
) -> Any:
    """Click a button/checkbox/tool button by objectName or visible text (for QActions / menu items use trigger_action).

    The click is deferred; the reply is immediate, so a modal dialog it opens does not block.
    """
    return await _call(
        "click_widget", {"window": window, "object_name": object_name, "text": text, "index": index}
    )


@server.tool()
async def list_actions(window: str = "QgisApp", text: str | None = None, include_hidden: bool = False) -> Any:
    """List QActions (menu items, toolbar buttons - where plugins usually put their entry) of a window.

    Use `text` to filter by substring. Pair with trigger_action to launch a plugin.
    """
    return await _call("list_actions", {"window": window, "text": text, "include_hidden": include_hidden})


@server.tool()
async def trigger_action(
    object_name: str | None = None, text: str | None = None, window: str = "QgisApp", index: int | None = None
) -> Any:
    """Trigger a QAction by objectName (preferred) or its visible text (mnemonic '&' ignored).

    The trigger is deferred; the reply is immediate, so a modal dialog it opens does not block.
    Submenus and disabled actions are refused. Check the result with list_windows / screenshot.
    """
    return await _call(
        "trigger_action", {"window": window, "object_name": object_name, "text": text, "index": index}
    )


@server.tool()
async def close_window(window: str) -> Any:
    """Close a window (deferred)."""
    return await _call("close_window", {"window": window})


@server.tool()
async def add_layer(path: str, name: str | None = None, kind: str = "auto") -> Any:
    """Add a vector/raster layer from a local path (GeoPackage sublayer syntax 'file.gpkg|layername=x' works)."""
    return await _call("add_layer", {"path": path, "name": name, "kind": kind})


@server.tool()
async def remove_layer(layer: str) -> Any:
    """Remove a layer from the project by id or unique name."""
    return await _call("remove_layer", {"layer": layer})


@server.tool()
async def run_algorithm(algorithm_id: str, parameters: dict, timeout_s: float = 600.0) -> Any:
    """Run a Processing algorithm synchronously. QGIS UI is blocked meanwhile. Returns results and the log."""
    return await _call(
        "run_algorithm", {"algorithm_id": algorithm_id, "parameters": parameters}, timeout_s=timeout_s
    )


@server.tool()
async def reload_plugin(name: str) -> Any:
    """Unload, purge modules and reload a plugin so code edits take effect (not for qgis_dev_probe itself)."""
    return await _call("reload_plugin", {"name": name}, timeout_s=60.0)


@server.tool()
async def run_recipe(name: str, args: dict | None = None, timeout_s: float = 600.0) -> Any:
    """Run a recipe (a Python file with `def run(ctx, args)`) from the configured recipe directory."""
    return await _call("run_recipe", {"name": name, "args": args or {}}, timeout_s=timeout_s)


# ---------------------------------------------------------------- exec
@server.tool()
async def execute_code(code: str) -> Any:
    """Execute arbitrary Python inside QGIS (iface, project in scope; set `result`). Requires the exec opt-in."""
    return await _call("execute_code", {"code": code})


# ---------------------------------------------------------------- local helper
@server.tool()
async def wait(seconds: float = 1.0) -> str:
    """Sleep (max 60 s) so deferred GUI actions can finish before the next observation."""
    seconds = max(0.0, min(float(seconds), 60.0))
    await asyncio.sleep(seconds)
    return f"waited {seconds:.1f}s"


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
