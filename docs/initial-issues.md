# 初期 Issue 案（GitHub に登録する前の下書き）

1. **QGIS 3.44 実機検証（VERIFY.md の ⬜ を潰す）** — 受け入れ条件: 全項目に結果記入。特に #3 モーダル中の応答。
2. **モーダル中に QTimer ポンプが動かない場合の代替** — 別手段（`QgsApplication.processEvents` 経由、イベントフィルタ等）の調査。#1 の結果次第。
3. **非同期 Processing 実行**（`QgsProcessingAlgRunnerTask`）— UI を止めない実行と進捗取得。
4. **QGIS 4 / Qt6 対応の調査** — `qgis.PyQt` の差異、enum のスコープ変更。
5. **スクリーンショット比較（回帰検出）** — 基準画像との差分。
6. **QGIS 起動オプション付きのヘッドレス/CI 実行**（`xvfb` + 公式 Docker イメージ）で E2E。
7. **recipe の雛形ジェネレータ** と、forest_mesh20m 等での実運用フィードバック。
