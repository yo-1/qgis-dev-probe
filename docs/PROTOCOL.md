# プロトコル v1

TCP（127.0.0.1 / ::1）。1 接続 1 リクエスト想定、UTF-8 JSON を**改行区切り**で 1 行。

要求: `{"id": 1, "tool": "ping", "token": "<endpoint.json の token>", "args": {}, "timeout_s": 30}`
成功: `{"id": 1, "ok": true, "result": ...}`
失敗: `{"id": 1, "ok": false, "error": {"code": "...", "message": "...", "details": ...}}`

| code | 意味 |
|---|---|
| bad_request | JSON/引数の不正、対象が見つからない等 |
| auth_failed | トークン不一致 |
| policy_denied | モード/許可/ウィンドウ許可リストにより拒否 |
| unknown_tool | 未知または未実装のツール |
| busy | 接続数/キュー上限 |
| timeout | メインスレッドが時間内にジョブを開始/完了しなかった（メインスレッドが塞がっている、またはポンプ停止。`details.started` で開始前か判別） |
| handler_error | ハンドラ内の想定外例外（traceback が details に入る） |
| algorithm_failed | Processing の失敗（details.log に feedback ログ） |
| response_too_large | 応答が 8 MiB 超 |

上限: 要求 1 MiB / 応答 8 MiB / timeout_s は (0, 3600]。`endpoint.json`: `~/.qgis_dev_probe/endpoint.json`（`QGIS_DEV_PROBE_HOME` で変更）。
