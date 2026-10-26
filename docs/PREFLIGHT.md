# 公式審査事前チェック（Plugin preflight）

plugins.qgis.org の公式審査で v0.1.0 が差し戻された（セキュリティスキャンの
Blocked と Qt6 チェック不合格）ことを受け、提出前に同じ観点を再現する
GitHub Actions ワークフロー `.github/workflows/plugin-preflight.yml` を用意した。
PR ごとに自動実行される。手動実行は workflow_dispatch からも可能。

## 運用ルール

- 提出に使う ZIP は、package ジョブを通過した artifact `submission-zip` のみとする。
- スキップ設定（`.bandit`）の採否は設計判断であり、理由とともに別途記録する。
  このチェックが緑であることは、コードの安全性の保証ではない。

## ジョブ構成

### Bandit（公式の重大度対応付けでゲート）

- 公式サイトと同じ Bandit（要件 bandit~=1.9）でプラグイン全体を走査する。
- 生のレポート（スキップなし）は artifact `bandit-raw-report` に必ず残す。
  抑制で検出自体が見えなくなることはない。
- ゲート判定は `scripts/check_bandit_gate.py` が公式の対応付けで行う:
  - Bandit LOW → info、MEDIUM → warning、HIGH → critical
  - 例外として B105〜B107 は MEDIUM でも critical に格上げ（公式の bandit_rules.json の注記による）
  - critical があれば失敗。critical はスキップ不可。
  - warning / info は、プラグインフォルダの `.bandit` に `skips:` で列挙された
    ルールだけゲート対象から外れる（公式の ZIP 同梱 `.bandit` と同じファイルを使う）。

### Qt6 enum チェック（静的近似）

- `scripts/qt6_enum_check.py` が、公式 Qt6 バリデータが v0.1.0 で報告した
  「スコープなし列挙子」のパターン（Qt.RichText、Qgis.Info、
  QgsProcessingParameterDefinition.Flag* など）を検出する。
- 公式は実 Qt6 環境で検査するため、これは近似であり、検出ゼロが公式チェックの
  通過を保証するものではない。

### Package（ZIP 構築と検証）

- `scripts/package_plugin.py` で提出用 ZIP を構築する（LICENSE はリポジトリ
  ルートのものを同梱、バージョン整合もこのスクリプトが確認する）。
- `scripts/verify_package.py` が ZIP の構造、metadata の必須項目、
  classFactory の有無、個人情報ゲート（公開すべきでないアドレス・氏名の混入）を
  検査する。

## v0.1.0 時点の既知の検出（このチェックが再現すべきもの）

- Bandit: B102（exec）2件、B110（try/except/pass）1件、B105 相当
  （`self.token = ""`）1件。公式表示は CRITICAL 1 件であり、B105 の格上げが
  その内訳と推定している。
- Qt6: 列挙子のスコープなし 10 件（dialog.py 5件、plugin.py 4件、handlers.py 1件）。

修正は GPT の事前検査とプロジェクト保守者の判断を経て、別の PR で行う。
