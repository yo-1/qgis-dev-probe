"""検証レシピ: 各プラグインのリポジトリに置いた Python ファイルを、名前で呼び出す仕組み。

レシピの規約:
    ファイル  : <recipe_dir>/<name>.py   （name は英数字・_・- のみ）
    関数      : def run(ctx, args: dict) -> JSON 化できる値
    ctx       : RecipeContext（iface / project / call(tool, **kwargs) / log(msg)）

呼び出しごとにソースを読み直して実行する（編集がすぐ反映される。__pycache__ も作らない）。
一覧取得（list_recipes）は ast で docstring を読むだけで、コードは実行しない。

セキュリティ: レシピは任意の Python を実行できる。recipe_dir は利用者が明示的に設定した、
信頼できるフォルダだけにすること（docs/DESIGN.md 参照）。名前にパス区切りや .. は許さない。
"""

from __future__ import annotations

import ast
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import BadRequest

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,63}$")


@dataclass
class RecipeContext:
    iface: Any
    project: Any
    call: Callable[..., Any]  # 他のツール（ハンドラ）を直接呼ぶ。例: ctx.call("inspect_layer", layer="x")
    log: Callable[[str], None]


def _recipe_dir(recipe_dir: str) -> Path:
    if not recipe_dir:
        raise BadRequest(
            "recipe_dir is not configured; set it in the QGIS Dev Probe dialog "
            "(folder that contains <name>.py recipes)"
        )
    path = Path(recipe_dir).expanduser()
    if not path.is_dir():
        raise BadRequest(f"recipe_dir does not exist or is not a directory: {recipe_dir}")
    return path.resolve()


def list_recipes(recipe_dir: str) -> list[dict[str, str]]:
    base = _recipe_dir(recipe_dir)
    result = []
    for path in sorted(base.glob("*.py")):
        if not NAME_RE.match(path.stem):
            continue
        summary = ""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            doc = ast.get_docstring(tree)
            if doc:
                summary = doc.strip().splitlines()[0]
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            summary = f"(unreadable: {type(exc).__name__})"
        result.append({"name": path.stem, "summary": summary})
    return result


def load_recipe(recipe_dir: str, name: str) -> Callable[[RecipeContext, dict], Any]:
    base = _recipe_dir(recipe_dir)
    if not NAME_RE.match(name):
        raise BadRequest("recipe name may contain only letters, digits, '_' and '-'")
    path = (base / f"{name}.py").resolve()
    if path.parent != base:  # シンボリックリンクで外へ出るケースも拒否
        raise BadRequest("recipe path escapes recipe_dir")
    if not path.is_file():
        raise BadRequest(f"recipe not found: {name}", details={"available": [r["name"] for r in list_recipes(recipe_dir)]})

    module_name = f"qgis_dev_probe_recipe_{name.replace('-', '_')}"
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    sys.modules[module_name] = module  # dataclass 等が sys.modules を参照するため登録する
    try:
        source = path.read_text(encoding="utf-8")
        exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - 設計上の機能
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    run = getattr(module, "run", None)
    if not callable(run):
        raise BadRequest(f"recipe '{name}' must define run(ctx, args)")
    return run


def run_recipe(recipe_dir: str, name: str, args: dict[str, Any], context: RecipeContext) -> Any:
    return load_recipe(recipe_dir, name)(context, args)
