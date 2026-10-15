# メール緊急度分類の検証設計

## 1. 目的

本プロジェクトは、メールの緊急度を `high` / `medium` / `low` に分類するための比較実験を行う。比較対象は、TF-IDF + ロジスティック回帰、OpenAI API（GPT・Chat Completions）、OpenAI Decisions API（gpt-6-luna）、TypeSafe Jev を想定しており、同じ100件のメールを使って精度と応答時間を比較する。

## 2. 設計思想

### 2.1 データの分離

- メール本文の正解ラベルと文面は CSV として切り出す。
- 分析コードは CSV を読むだけで動くようにし、本文テキストをコード中に埋め込まない。
- 実験コードとデータの責務を分離することで、再利用性と再検証性を確保する。

### 2.2 実験条件の整合

- 全モデルで同じ 100 件のメール（high 33 / medium 34 / low 33）を使用する。
- 各メールに判断の難しさ `difficulty`（high / medium / low）を付与し、難易度別の正解率も出力する（緊急度ラベルとは別の軸）。
  - low（47件）: 「至急」「本日17時」など表層の手がかりが正解ラベルと一致する。
  - medium（33件）: 明示的な緊急語はないが期限や影響を読めば判断できる、または紛らわしい語が本文ですぐ打ち消される。
  - high（20件）: 件名や語が正解と逆を指す、重要情報が末尾に埋もれている、控えめな書き方から状況を推論する必要がある。
- 旧20件版は `data/emails_20.csv` に残しており、`--data data/emails_20.csv` で再現できる。
- 1件ずつ分類し、`time.perf_counter()` で推論時間を計測する。
- API モデル（GPT / Decisions / Jev）はクライアントを1つ作って使い回し、各周の最初に計測外のウォームアップを1回行う（接続確立時間を除外し条件を揃える）。
- GPT・Decisions・Jev には同じ緊急度の定義（high/medium/low）を与える。
- `--repeat` をかけて複数周実行し、レイテンシのばらつきを安定させる。
- そのため、比較の基準は「単発の速度」ではなく「集計した平均・p95・最大値」で見る。

### 2.3 評価指標

- Accuracy: すべてのサンプルに対する正解率。
- Macro-F1: 3クラスの平均F1を計算し、クラス間の偏りに強い。
- Confusion matrix: `高/中/低` ごとの誤分類の傾向を可視化しやすくする。
- Latency: 平均、p95、最大時間を記録し、APIの応答性を定量化する。

### 2.4 実験の注意点

- いくつかのメールには「緊急」などの単語が含まれるが、実際の緊急度が低い例がある。
- 逆に「至急」などの表現がなくても、事業影響が大きいケースがある。
- そのため、単語の表層一致だけではなく、文脈と事業インパクトを読み取る必要がある。

## 3. 実装方針

- CSV を `data/emails.csv` に保存する。
- 読み込みロジックを `src/urgency_data.py` に切り出す。
- 実験処理と評価指標を `src/urgency_benchmark.py` にまとめる。
- 実行入口を `scripts/verify_urgency.py` に置く。
- `.env.example` に APIキーの変数名を明示し、実運用時は `.env` に保存する（`trial_jev/.env` → 親ディレクトリの `.env` の順に python-dotenv で自動読み込み）。

## 4. 期待する結果

- TF-IDF は比較的安定した高速なベースラインになる。
- GPT は文脈理解の面で強く、外部APIのレイテンシが大きくなる。
- Decisions API と Jev はどちらも分類専用 API（choice 質問＋確率を返す）で、汎用 Chat の GPT より高速になることが期待される。直接の競合同士の比較になる。
- Jev は API 仕様に応じた実装が必要であり、`classify_jev` の実装依存度が高い。
- 重要なのは「精度を落とさずに、どこまで速く分類できるか」を同じ条件下で比較することだ。

## 5. 実行イメージ

```bash
cd /Users/shimizuatsuki/Desktop/松尾研/第1回/宿題/trial_jev
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/verify_urgency.py --models tfidf --repeat 1
```

GPT や Jev を使う場合は `.env` にキーを置けば自動で読み込まれる。

```bash
python3 scripts/verify_urgency.py --models tfidf gpt decisions jev --repeat 1
```
