"""テスト共通設定: plugin/ と src/ を import パスに追加する。

実行: リポジトリ直下で `python -m unittest discover -s tests -t . -v`（pytest でも可）
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("plugin", "src"):
    _path = str(_ROOT / _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)
