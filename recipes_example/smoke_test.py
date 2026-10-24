"""疎通確認: get_info / list_layers / list_algorithms / run_algorithm(グリッド作成) を一通り実行して結果を返す。

使い方: run_recipe(name="smoke_test")。データファイルは不要。プロジェクトは変更しない（結果は一時レイヤで、追加もしない）。
"""


def run(ctx, args):
    info = ctx.call("get_info")
    ctx.log(f"QGIS {info['qgis_version']}")
    layers = ctx.call("list_layers")
    grid = ctx.call(
        "run_algorithm",
        algorithm_id="native:creategrid",
        parameters={
            "TYPE": 2,
            "EXTENT": "139.0,139.5,35.0,35.5 [EPSG:4326]",
            "HSPACING": 0.1,
            "VSPACING": 0.1,
            "HOVERLAY": 0,
            "VOVERLAY": 0,
            "CRS": "EPSG:4326",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
        timeout_s=60,
    )
    return {
        "qgis_version": info["qgis_version"],
        "layer_count": layers["count"],
        "grid_layer": grid["results"]["OUTPUT"]["layer_name"],
        "algorithm_elapsed_s": grid["elapsed_s"],
        "ok": True,
    }
