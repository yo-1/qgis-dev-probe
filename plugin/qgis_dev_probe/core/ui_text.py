"""ダイアログに表示する文言（日本語＋英語併記）。

Qt に依存しない純 Python にしてあるのは、全モードに説明があるか等を QGIS なしでテストするため。
objectName や内部値（readonly / interactive）は変えない。表示だけを変える。
"""

from __future__ import annotations

from html import escape

from .config import MODE_INTERACTIVE, MODE_READONLY

# 内部値 -> コンボボックスの表示。set_widget は表示文字列でも内部値（アイテムデータ）でも選べる
MODE_LABELS = {
    MODE_READONLY: "readonly（読み取り専用）",
    MODE_INTERACTIVE: "interactive（操作を許可）",
}

LABELS = {
    "status": "状態 / Status",
    "mode": "モード / Mode",
    "allow_exec": "execute_code を許可 / Allow execute_code（このセッションのみ・保存されません）",
    "recipe_dir": "レシピ フォルダ / Recipe dir",
    "allowlist": "対象ウィンドウの制限 / Window allowlist",
    "allowlist_placeholder": "objectName またはタイトルをカンマ区切り。空 = すべてのウィンドウ",
    "activity": "直近の呼び出し / Recent calls（引数は記録しません）",
    "start": "サーバー起動 / Start server",
    "stop": "サーバー停止 / Stop server",
    "close": "閉じる / Close",
    "running": "実行中 / RUNNING",
    "stopped": "停止中 / STOPPED",
}


def status_text(running: bool, host: str = "", port: int = 0) -> str:
    if running:
        return f"{LABELS['running']}  {host}:{port}"
    return LABELS["stopped"]


def build_info_html(version: str, endpoint_file: str) -> str:
    """右側の説明パネル（リッチテキスト）。外部入力（パス）は必ずエスケープする。"""
    return f"""
<h3>QGIS Dev Probe</h3>
<p><b>バージョン / Version:</b> {escape(version)}</p>
<p><b>開発専用</b>です。AI クライアント（MCP）が QGIS の画面や処理を操作して実機検証するための
ツールで、<b>本番機では使わないでください</b>。<br>
<small>Development-only. Do not use on production machines.</small></p>
<p>接続は <b>localhost のみ</b>、サーバーは手動で起動したときだけ動きます。</p>
<h4>モード / Mode</h4>
<ul>
<li><b>readonly</b>: 画面・レイヤ・ログの参照のみ。値の入力、クリック、処理の実行はできません。</li>
<li><b>interactive</b>: 入力・クリック、Processing 実行、プラグイン再読込も許可します。</li>
</ul>
<h4>execute_code</h4>
<p>任意の Python を実行できる危険な機能です。チェックしたセッションだけ有効で、
QGIS を再起動すると無効に戻ります（保存されません）。</p>
<h4>設定欄</h4>
<ul>
<li><b>Recipe dir</b>: 検証レシピ（.py）のフォルダ。</li>
<li><b>Window allowlist</b>: 操作対象を制限します。</li>
<li>どちらもサーバー<b>停止中のみ</b>編集できます。</li>
</ul>
<h4>接続情報 / Endpoint</h4>
<p><small>{escape(endpoint_file)}</small></p>
"""
