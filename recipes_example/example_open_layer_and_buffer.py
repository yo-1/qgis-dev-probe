"""サンプル: ベクターレイヤを追加して native:buffer を実行し、結果レイヤ数を返す。

使い方: このファイルを設定した recipe_dir にコピーし、
  run_recipe(name="example_open_layer_and_buffer", args={"path": "/path/to/data.gpkg", "distance": 10})
"""


def run(ctx, args):
    path = args["path"]
    distance = float(args.get("distance", 10))
    layer = ctx.call("add_layer", path=path)
    ctx.log(f"added {layer['name']}")
    result = ctx.call(
        "run_algorithm",
        algorithm_id="native:buffer",
        parameters={"INPUT": layer["id"], "DISTANCE": distance, "OUTPUT": "memory:"},
    )
    return {"input": layer["id"], "outputs": result["results"], "log_lines": len(result["log"])}
