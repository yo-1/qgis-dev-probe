"""ツール実装（QGIS / Qt に依存）。すべてメインスレッドで実行される（read_log / list_recipes を除く）。

使用している QGIS API は docs/VERIFY.md の「API 確認表」に列挙している。QGIS 3.44 での動作は
実機で確認するまで未確認として扱うこと。
"""

from __future__ import annotations

import contextlib
import functools
import io
import logging
import os
import platform
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from qgis import utils as qgis_utils
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeatureRequest,
    QgsMapLayer,
    QgsProcessingFeedback,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QTimer
from qgis.PyQt.QtWidgets import QApplication

from .. import __version__
from ..core import args as A
from ..core import recipes
from ..core.config import ProbeConfig
from ..core.errors import BadRequest, PolicyDenied, ProbeError
from ..core.logbuffer import LogBuffer
from ..core.paths import unique_path
from ..core.policy import Policy
from . import widgets as W

logger = logging.getLogger("qgis_dev_probe")

SELF_PLUGIN = __name__.split(".")[0]  # "qgis_dev_probe"。自分自身は再読込しない
MAX_ROWS = 500


@dataclass
class HandlerContext:
    iface: Any
    config: ProbeConfig
    policy: Policy
    logbuffer: LogBuffer
    handlers: dict[str, Callable[[dict], Any]] = field(default_factory=dict)


# ------------------------------------------------------------------ 共通ヘルパ
def enum_name(value: Any) -> str:
    """QGIS 3.3x 以降の Python enum と、従来の整数型 enum の両方を文字列にする。"""
    return str(getattr(value, "name", None) or value)


def _schedule(fn: Callable[[], Any]) -> None:
    QTimer.singleShot(0, fn)


def _top_levels() -> list:
    return list(QApplication.topLevelWidgets())


def _check_window_allowed(ctx: HandlerContext, window: Any) -> None:
    info = W.describe_window(window)
    if not ctx.policy.window_allowed(info["object_name"], info["title"]):
        raise PolicyDenied(
            f"window {info['object_name'] or info['title']!r} is not in the window allowlist",
            details={"allowlist": list(ctx.config.window_allowlist)},
        )


def _action_window(ctx: HandlerContext, args: dict) -> Any:
    window = W.select_window(_top_levels(), A.get_str(args, "window"))
    _check_window_allowed(ctx, window)
    return window


def _find_layer(selector: str) -> Any:
    project = QgsProject.instance()
    layer = project.mapLayer(selector)
    if layer is not None:
        return layer
    matches = project.mapLayersByName(selector)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise BadRequest(
            f"no layer with id or name {selector!r}",
            details={"layers": [{"id": lyr.id(), "name": lyr.name()} for lyr in project.mapLayers().values()][:50]},
        )
    raise BadRequest(
        f"layer name {selector!r} is ambiguous ({len(matches)} layers); use the layer id",
        details={"candidates": [{"id": lyr.id(), "name": lyr.name()} for lyr in matches]},
    )


def _layer_brief(layer: Any) -> dict[str, Any]:
    return {
        "id": layer.id(),
        "name": layer.name(),
        "type": enum_name(layer.type()),
        "valid": layer.isValid(),
        "crs": layer.crs().authid(),
        "source": layer.publicSource(),  # パスワード等の機微情報を除いた表現
    }


# ------------------------------------------------------------------ observe
def h_ping(ctx: HandlerContext, args: dict) -> dict:
    return {
        "pong": True,
        "plugin_version": __version__,
        "mode": ctx.config.mode,
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "time": time.time(),
    }


def h_get_info(ctx: HandlerContext, args: dict) -> dict:
    project = QgsProject.instance()
    return {
        "qgis_version": Qgis.version(),
        "qgis_version_int": Qgis.versionInt(),
        "python": sys.version.split()[0],
        "qt": QT_VERSION_STR,
        "pyqt": PYQT_VERSION_STR,
        "platform": platform.platform(),
        "profile_dir": QgsApplication.qgisSettingsDirPath(),
        "project_file": project.fileName(),
        "project_title": project.title(),
        "project_crs": project.crs().authid(),
        "layer_count": len(project.mapLayers()),
        "plugin_version": __version__,
        "home": str(ctx.config.home_path),
        "out_dir": str(ctx.config.out_path),
        "recipe_dir": ctx.config.recipe_dir,
        "mode": ctx.config.mode,
    }


def h_list_windows(ctx: HandlerContext, args: dict) -> dict:
    modal = QApplication.activeModalWidget()
    return {
        "windows": W.list_windows(_top_levels(), include_hidden=A.get_bool(args, "include_hidden")),
        "active_modal": W.describe_window(modal) if modal is not None else None,
    }


def h_dump_widgets(ctx: HandlerContext, args: dict) -> dict:
    window = W.select_window(_top_levels(), A.get_str(args, "window"))
    return W.dump_widgets(
        window,
        max_items=A.get_int(args, "max_items", default=400, minimum=1, maximum=2000),
        only_named=A.get_bool(args, "only_named"),
        include_internal=A.get_bool(args, "include_internal"),
        visible_only=A.get_bool(args, "visible_only", default=True),
    )


def h_screenshot(ctx: HandlerContext, args: dict) -> dict:
    window_selector = A.get_str(args, "window", required=False)
    object_name = A.get_str(args, "object_name", required=False)
    window = W.select_window(_top_levels(), window_selector) if window_selector else ctx.iface.mainWindow()
    target = W.find_widget(window, object_name=object_name) if object_name else window
    label = A.get_str(args, "name", required=False) or object_name or window_selector or "mainwindow"
    path = unique_path(ctx.config.out_path, label, ".png")  # 出力先は固定。呼び出し側はパスを指定できない
    size = W.grab_to_file(target, path)
    return {"path": str(path), **size, "window": W.describe_window(window)}


def h_list_layers(ctx: HandlerContext, args: dict) -> dict:
    layers = [_layer_brief(layer) for layer in QgsProject.instance().mapLayers().values()]
    return {"layers": layers[:MAX_ROWS], "count": len(layers)}


def h_inspect_layer(ctx: HandlerContext, args: dict) -> dict:
    layer = _find_layer(A.get_str(args, "layer"))
    sample = A.get_int(args, "sample", default=3, minimum=0, maximum=20)
    info = _layer_brief(layer)
    extent = layer.extent()
    info["extent"] = [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()]

    if isinstance(layer, QgsVectorLayer):
        names = [field_.name() for field_ in layer.fields()]
        info.update(
            kind="vector",
            provider=layer.providerType(),
            feature_count=layer.featureCount(),
            geometry_type=QgsWkbTypes.geometryDisplayString(layer.geometryType()),
            wkb_type=QgsWkbTypes.displayString(layer.wkbType()),
            subset_filter=layer.subsetString(),
            fields=[{"name": f.name(), "type": f.typeName()} for f in layer.fields()],
        )
        if sample:
            request = QgsFeatureRequest()
            request.setLimit(sample)
            info["samples"] = [
                {"fid": feature.id(), "attributes": dict(zip(names, feature.attributes()))}
                for feature in layer.getFeatures(request)
            ]
    elif isinstance(layer, QgsRasterLayer):
        provider = layer.dataProvider()
        bands = []
        for band in range(1, layer.bandCount() + 1):
            has_nodata = provider.sourceHasNoDataValue(band)
            bands.append(
                {
                    "band": band,
                    "data_type": enum_name(provider.dataType(band)),
                    "nodata": provider.sourceNoDataValue(band) if has_nodata else None,
                }
            )
        info.update(
            kind="raster",
            width=layer.width(),
            height=layer.height(),
            band_count=layer.bandCount(),
            pixel_size=[layer.rasterUnitsPerPixelX(), layer.rasterUnitsPerPixelY()],
            bands=bands,
        )
    else:
        info["kind"] = "other"
    return info


def _is_optional(parameter: Any) -> bool:
    try:  # 3.36+ の名前空間付き enum
        return bool(parameter.flags() & Qgis.ProcessingParameterFlag.Optional)
    except Exception:  # noqa: BLE001 - 旧 API へフォールバック
        from qgis.core import QgsProcessingParameterDefinition

        return bool(parameter.flags() & QgsProcessingParameterDefinition.Flag.FlagOptional)


def h_list_algorithms(ctx: HandlerContext, args: dict) -> dict:
    registry = QgsApplication.processingRegistry()
    needle = (A.get_str(args, "search", required=False) or "").lower()
    provider = A.get_str(args, "provider", required=False)
    limit = A.get_int(args, "limit", default=50, minimum=1, maximum=MAX_ROWS)
    rows = []
    for algorithm in registry.algorithms():
        if provider and algorithm.provider().id() != provider:
            continue
        if needle and needle not in algorithm.id().lower() and needle not in algorithm.displayName().lower():
            continue
        rows.append({"id": algorithm.id(), "name": algorithm.displayName(), "provider": algorithm.provider().id()})
    return {
        "algorithms": rows[:limit],
        "total_matching": len(rows),
        "providers": sorted(p.id() for p in registry.providers()),
    }


def h_get_algorithm_params(ctx: HandlerContext, args: dict) -> dict:
    algorithm_id = A.get_str(args, "algorithm_id")
    algorithm = QgsApplication.processingRegistry().algorithmById(algorithm_id)
    if algorithm is None:
        raise BadRequest(
            f"unknown algorithm id {algorithm_id!r}; use list_algorithms(search=...) to find it"
        )
    parameters = []
    for parameter in algorithm.parameterDefinitions():
        entry: dict[str, Any] = {
            "name": parameter.name(),
            "description": parameter.description(),
            "type": parameter.type(),
            "optional": _is_optional(parameter),
            "default": parameter.defaultValue(),
        }
        options = getattr(parameter, "options", None)  # QgsProcessingParameterEnum
        if callable(options):
            entry["options"] = list(options())
        for key in ("minimum", "maximum"):  # QgsProcessingParameterNumber 系
            getter = getattr(parameter, key, None)
            if callable(getter):
                entry[key] = getter()
        parameters.append(entry)
    return {
        "id": algorithm.id(),
        "name": algorithm.displayName(),
        "provider": algorithm.provider().id(),
        "group": algorithm.group(),
        "summary": algorithm.shortDescription(),
        "parameters": parameters,
        "outputs": [
            {"name": o.name(), "description": o.description(), "type": o.type()}
            for o in algorithm.outputDefinitions()
        ],
    }


def h_list_plugins(ctx: HandlerContext, args: dict) -> dict:
    active = set(qgis_utils.active_plugins)
    rows = [
        {
            "name": name,
            "version": qgis_utils.pluginMetadata(name, "version"),
            "active": name in active,
        }
        for name in sorted(qgis_utils.available_plugins)
    ]
    return {"plugins": rows[:MAX_ROWS], "count": len(rows)}


def h_read_log(ctx: HandlerContext, args: dict) -> dict:
    return ctx.logbuffer.read(
        limit=A.get_int(args, "limit", default=50, minimum=1, maximum=MAX_ROWS),
        tag=A.get_str(args, "tag", required=False),
        level=A.get_str(args, "level", required=False),
        contains=A.get_str(args, "contains", required=False),
        since_id=A.get_int(args, "since_id", minimum=0),
    )


def h_list_recipes(ctx: HandlerContext, args: dict) -> dict:
    return {"recipe_dir": ctx.config.recipe_dir, "recipes": recipes.list_recipes(ctx.config.recipe_dir)}


# ------------------------------------------------------------------ act
def h_set_widget(ctx: HandlerContext, args: dict) -> dict:
    window = _action_window(ctx, args)
    if "value" not in args:
        raise BadRequest("'value' is required")
    widget = W.find_widget(
        window,
        object_name=A.get_str(args, "object_name"),
        index=A.get_int(args, "index", minimum=0),
    )
    return W.set_value(widget, args["value"])


def h_list_actions(ctx: HandlerContext, args: dict) -> dict:
    window = W.select_window(_top_levels(), A.get_str(args, "window", required=False, default="QgisApp"))
    return W.list_actions(
        window,
        text=A.get_str(args, "text", required=False),
        include_hidden=A.get_bool(args, "include_hidden"),
    )


def h_trigger_action(ctx: HandlerContext, args: dict) -> dict:
    window = W.select_window(_top_levels(), A.get_str(args, "window", required=False, default="QgisApp"))
    _check_window_allowed(ctx, window)
    action = W.find_action(
        window,
        object_name=A.get_str(args, "object_name", required=False),
        text=A.get_str(args, "text", required=False),
        index=A.get_int(args, "index", minimum=0),
    )
    return W.trigger_action(action, _schedule)


def h_click_widget(ctx: HandlerContext, args: dict) -> dict:
    window = _action_window(ctx, args)
    widget = W.find_widget(
        window,
        object_name=A.get_str(args, "object_name", required=False),
        text=A.get_str(args, "text", required=False),
        index=A.get_int(args, "index", minimum=0),
    )
    return W.click(widget, _schedule)


def h_close_window(ctx: HandlerContext, args: dict) -> dict:
    return W.close_window(_action_window(ctx, args), _schedule)


def h_add_layer(ctx: HandlerContext, args: dict) -> dict:
    path = A.get_str(args, "path")
    kind = A.get_str(args, "kind", required=False, default="auto")
    if kind not in ("auto", "vector", "raster"):
        raise BadRequest("'kind' must be 'auto', 'vector' or 'raster'")
    file_part = path.split("|", 1)[0]  # GeoPackage のサブレイヤ指定 (path|layername=x) に対応
    if "://" not in file_part and not os.path.exists(file_part):
        raise BadRequest(f"file does not exist: {file_part}")
    name = A.get_str(args, "name", required=False) or os.path.basename(file_part)

    candidates: list[Any] = []
    if kind in ("auto", "vector"):
        candidates.append(QgsVectorLayer(path, name, "ogr"))
    if kind in ("auto", "raster"):
        candidates.append(QgsRasterLayer(path, name))
    layer = next((c for c in candidates if c.isValid()), None)
    if layer is None:
        errors = [c.error().summary() for c in candidates if hasattr(c, "error")]
        raise BadRequest(f"could not open as a valid layer: {path}", details={"errors": errors})
    QgsProject.instance().addMapLayer(layer)
    return _layer_brief(layer)


def h_remove_layer(ctx: HandlerContext, args: dict) -> dict:
    layer = _find_layer(A.get_str(args, "layer"))
    brief = _layer_brief(layer)
    QgsProject.instance().removeMapLayer(layer.id())
    return {"removed": brief}


class _CollectingFeedback(QgsProcessingFeedback):
    """Processing のログを集めて、結果と一緒に返す（QGIS ログを見に行かずに原因が分かるように）。"""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def _add(self, kind: str, text: str) -> None:
        if len(self.lines) < MAX_ROWS:
            self.lines.append(f"[{kind}] {text}")

    def pushInfo(self, info):  # noqa: N802
        self._add("info", info)
        super().pushInfo(info)

    def pushWarning(self, warning):  # noqa: N802
        self._add("warning", warning)
        super().pushWarning(warning)

    def reportError(self, error, fatalError=False):  # noqa: N802, N803
        self._add("error", error)
        super().reportError(error, fatalError)

    def pushCommandInfo(self, info):  # noqa: N802
        self._add("command", info)
        super().pushCommandInfo(info)

    def pushDebugInfo(self, info):  # noqa: N802
        self._add("debug", info)
        super().pushDebugInfo(info)

    def pushConsoleInfo(self, info):  # noqa: N802
        self._add("console", info)
        super().pushConsoleInfo(info)


def _result_value(value: Any) -> Any:
    if isinstance(value, QgsMapLayer):
        return {"layer_id": value.id(), "layer_name": value.name(), "source": value.publicSource()}
    if isinstance(value, (list, tuple)):
        return [_result_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _result_value(v) for k, v in value.items()}
    return value


def h_run_algorithm(ctx: HandlerContext, args: dict) -> dict:
    import processing  # QGIS 同梱の processing プラグイン。起動直後は未読込のことがあるため遅延 import

    algorithm_id = A.get_str(args, "algorithm_id")
    parameters = A.get_dict(args, "parameters", required=True)
    feedback = _CollectingFeedback()
    started = time.monotonic()
    try:
        # 同期実行のため、完了まで QGIS の UI は応答しない。長い処理は MCP 側の timeout_s を延ばすこと
        results = processing.run(algorithm_id, parameters, feedback=feedback)
    except Exception as exc:  # noqa: BLE001 - アルゴリズムの失敗はログ付きで返す
        raise ProbeError(
            f"{type(exc).__name__}: {exc}",
            code="algorithm_failed",
            details={"algorithm_id": algorithm_id, "log": feedback.lines},
        ) from exc
    return {
        "algorithm_id": algorithm_id,
        "results": _result_value(results),
        "log": feedback.lines,
        "elapsed_s": round(time.monotonic() - started, 3),
    }


def _purge_modules(package: str) -> int:
    doomed = [name for name in sys.modules if name == package or name.startswith(package + ".")]
    for name in doomed:
        del sys.modules[name]
    return len(doomed)


def h_reload_plugin(ctx: HandlerContext, args: dict) -> dict:
    name = A.get_str(args, "name")
    if name == SELF_PLUGIN:
        raise BadRequest("cannot reload qgis_dev_probe itself (it would stop the server mid-request)")
    if name not in qgis_utils.available_plugins:
        raise BadRequest(f"unknown plugin {name!r}", details={"hint": "use list_plugins"})
    was_active = name in qgis_utils.active_plugins
    unloaded = qgis_utils.unloadPlugin(name) if was_active else None
    # unload 後にモジュールを破棄しないと、loadPlugin が古いコードを再利用して反映されない
    purged = _purge_modules(name)
    loaded = qgis_utils.loadPlugin(name)
    started = qgis_utils.startPlugin(name) if loaded else False
    return {
        "name": name,
        "was_active": was_active,
        "unloaded": unloaded,
        "modules_purged": purged,
        "loaded": loaded,
        "started": started,
        "active": name in qgis_utils.active_plugins,
    }


def h_run_recipe(ctx: HandlerContext, args: dict) -> Any:
    name = A.get_str(args, "name")
    recipe_args = A.get_dict(args, "args")
    recipe_context = recipes.RecipeContext(
        iface=ctx.iface,
        project=QgsProject.instance(),
        call=lambda tool, **kwargs: _call_tool(ctx, tool, kwargs),
        log=lambda message: logger.info("recipe %s: %s", name, message),
    )
    return recipes.run_recipe(ctx.config.recipe_dir, name, recipe_args, recipe_context)


def _call_tool(ctx: HandlerContext, tool: str, kwargs: dict) -> Any:
    handler = ctx.handlers.get(tool)
    if handler is None or tool in ("run_recipe", "execute_code"):
        raise BadRequest(f"recipes cannot call tool {tool!r}")
    return handler(kwargs)


# ------------------------------------------------------------------ exec
def h_execute_code(ctx: HandlerContext, args: dict) -> dict:
    if not ctx.config.allow_exec:  # ポリシーでも検査済み。ハンドラ側でも多重に確認する
        raise PolicyDenied("arbitrary code execution is disabled")
    code = A.get_str(args, "code")
    scope: dict[str, Any] = {
        "__name__": "__qgis_dev_probe_exec__",
        "iface": ctx.iface,
        "project": QgsProject.instance(),
        "result": None,
    }
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(code, "<qgis_dev_probe.execute_code>", "exec"), scope)  # noqa: S102 - 設計上の機能
    return {"result": scope.get("result"), "stdout": stdout.getvalue()[-20000:]}


_HANDLERS: dict[str, Callable[[HandlerContext, dict], Any]] = {
    "ping": h_ping,
    "get_info": h_get_info,
    "list_windows": h_list_windows,
    "dump_widgets": h_dump_widgets,
    "list_actions": h_list_actions,
    "screenshot": h_screenshot,
    "list_layers": h_list_layers,
    "inspect_layer": h_inspect_layer,
    "list_algorithms": h_list_algorithms,
    "get_algorithm_params": h_get_algorithm_params,
    "list_plugins": h_list_plugins,
    "read_log": h_read_log,
    "list_recipes": h_list_recipes,
    "set_widget": h_set_widget,
    "click_widget": h_click_widget,
    "trigger_action": h_trigger_action,
    "close_window": h_close_window,
    "add_layer": h_add_layer,
    "remove_layer": h_remove_layer,
    "run_algorithm": h_run_algorithm,
    "reload_plugin": h_reload_plugin,
    "run_recipe": h_run_recipe,
    "execute_code": h_execute_code,
}


def build_handlers(ctx: HandlerContext) -> dict[str, Callable[[dict], Any]]:
    """ツール名 → 引数 dict だけを受け取るハンドラ、の辞書を作る。"""
    ctx.handlers = {name: functools.partial(func, ctx) for name, func in _HANDLERS.items()}
    return ctx.handlers
