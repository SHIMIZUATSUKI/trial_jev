# jevの能力を測定 — メール緊急度分類ベンチマーク

日本語ビジネスメールの **緊急度（high / medium / low）分類** で、TypeSafe **Jev** の精度と応答速度を測るベンチマークです。同じ条件で、次の3つと比較しています。

- OpenAI **Decisions API**（分類専用 API）
- OpenAI **Chat Completions**（汎用 LLM）
- **TF-IDF + ロジスティック回帰**（古典的なベースライン）

📄 **レポート**: [`report/report.html`](report/report.html)（グラフ付き。「データ」タブで例文100件と各モデルの予測を確認できます）／ [`report/report.md`](report/report.md)

## 結果サマリー

メール100件、各メール1回ずつ測定した結果です（2026-10-14 実施）。

| モデル | 正解率 | 難易度high の正解率 (20件) | 処理時間の中央値 | 処理時間の最大 | 標準偏差 |
|---|---|---|---|---|---|
| **Jev** (`jev-latest`) | **1.00** | **1.00** | **180 ms** | **251 ms** | **20 ms** |
| Decisions API (`gpt-6-luna`) | 0.99 | 1.00 | 237 ms | 668 ms | 67 ms |
| Chat Completions (`gpt-4.1-mini`) | 0.95 | 0.95 | 686 ms | 1628 ms | 180 ms |
| TF-IDF + LogReg | 0.86 | 0.85 | 2 ms | 4 ms | 1 ms |

- **精度**: Jev は100件すべてに正解しました。GPT の誤分類5件のうち4件は、「今週金曜まで」のように期限が書いてあるだけの medium のメールを high と判定したものでした。ただし API の3モデルの差は数件分で、統計的に有意とは言えません（McNemar 検定で、Jev と GPT は p=0.062）。
- **速度**: Jev は100件中94件で Decisions API より速く、ばらつきも最も小さい結果でした。GPT より約3.8倍速い計算です（中央値で比較）。

詳しい考察と限界は [レポート](report/report.md) を参照してください。

## データセット

[`data/emails.csv`](data/emails.csv) — 日本語のビジネスメール100件（件名と本文、95〜220字）

| 列 | 内容 |
|---|---|
| `label` | 正解の緊急度。`high`（今日〜数時間以内に対応が必要）／`medium`（数日以内）／`low`（期限なし・情報共有）。high 33 / medium 34 / low 33 |
| `difficulty` | 判断の難しさ（緊急度とは別の軸）。`high` 20 / `medium` 33 / `low` 47 |
| `subject`, `body` | 件名と本文 |

難易度の基準:
- **high**: 件名や言葉が正解と逆を指す（例:「【緊急】件名のメール訓練について」→ 緊急度low）、重要な情報が末尾に埋もれている、控えめな書き方から状況を推し量る必要がある（例:「ちょっと気になったこと」でガスの臭いを報告 → 緊急度high）
- **medium**: 緊急ワードはないが、期限や影響を読めば判断できる
- **low**: 「至急」「本日17時」などの手がかりが、正解とそのまま一致する

> [!NOTE]
> 100件のうち80件は生成 AI（Claude）で作成した架空のメールです。登場する人名・社名はすべて架空です。正解ラベルと難易度は作成者の判断で付けました。旧版の20件は [`data/emails_20.csv`](data/emails_20.csv) にあります。

## 実行方法

### 必要なもの
- Python 3.10 以上（3.13.7 で動作確認）
- OpenAI API キー（GPT と Decisions API 用）
- TypeSafe API キー（Jev 用）

API キーがなくても、TF-IDF だけなら無料で実行できます。

### セットアップ
```bash
git clone <このリポジトリ>
cd trial_jev
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 作成した .env を開き、行頭の「# 」を消してキーを書き込む
```

`.env` に書く変数:

| 変数 | 用途 | 既定値 |
|---|---|---|
| `OPENAI_API_KEY` | GPT・Decisions API | （必須） |
| `OPENAI_MODEL` | GPT のモデル | `gpt-4.1-mini` |
| `OPENAI_DECISIONS_MODEL` | Decisions API のモデル | `gpt-6-luna` |
| `TYPESAFE_API_KEY` または `JEV_API_KEY` | Jev | （必須） |
| `JEV_MODEL` | Jev のモデル | `jev-latest` |

`.env` は `.gitignore` に含まれているので、コミットされません。

### ベンチマークの実行
```bash
# TF-IDF のみ（API を使わない・無料）
python scripts/verify_urgency.py --models tfidf

# 4モデルすべて（API を合計303回呼び出す）
python scripts/verify_urgency.py --out result_run1.json
```

| オプション | 説明 | 既定値 |
|---|---|---|
| `--models` | `tfidf` `gpt` `decisions` `jev` から選ぶ（複数指定可） | 4つすべて |
| `--repeat` | 何周するか（処理時間を安定させる用） | `1` |
| `--out` | 結果 JSON の保存先 | `urgency_results.json` |
| `--data` | 入力 CSV | `data/emails.csv` |

キーが設定されていないモデルは `[skip]`、エラーが出たモデルは `[error]` と表示され、残りのモデルの計測は続きます。

### レポートの作り直し
```bash
python scripts/build_report.py   # report.md + result_run1.json + emails.csv → report/report.html
```

### テスト
```bash
python -m unittest discover -s tests -t .
```
テストは API をモックに置き換えて動くので、キーは不要です。

## 測定方法

- **共通の条件**: 全モデルが同じ100件を1件ずつ分類します。プロンプトの定義文と選択肢の説明は、API の3モデルで共通です。
- **公平な時間計測**: API を使う3モデルは、クライアントを1つ作って使い回し、計測しない空打ちを1回してから計測します。これで接続準備の時間を計測から除いています。時間は `time.perf_counter()` で、リクエストを送ってから答えが返るまでを測ります。
- **各モデルの呼び出し方**
  - **Jev**: `TypeSafeClient.system_one` に `Choice` 質問（high / medium / low と各選択肢の説明）を送ります。
  - **Decisions API**: `client.decisions.create` に `choice` 質問を送ります。
  - **GPT**: Chat Completions（temperature=0、JSON モード）で `{"urgency": "..."}` を返させます。
  - **TF-IDF**: 文字の1〜3文字の並び（`char_wb`）を TF-IDF で数値化し、ロジスティック回帰で分類します。Leave-one-out で評価し、学習時間は推論時間に含めません。
- **評価指標**: 正解率、Macro-F1、難易度別の正解率、混同行列、処理時間（平均・中央値・p95・最大）

## ディレクトリ構成

```
trial_jev/
├── data/
│   ├── emails.csv            # 100件（現行）
│   └── emails_20.csv         # 20件（旧版）
├── src/
│   ├── urgency_data.py       # CSV の読み込み
│   └── urgency_benchmark.py  # 各モデルの分類・計測・評価
├── scripts/
│   ├── verify_urgency.py     # ベンチマークの実行入口
│   └── build_report.py       # レポート HTML の生成
├── tests/                    # 単体テスト（API はモック）
├── report/
│   ├── report.md
│   └── report.html
├── result_run1.json          # レポートに使った測定結果
├── design.md                 # 検証の設計書
├── requirements.txt
└── .env.example
```

## 限界

- データは100件と少なく、大半は生成した例文です。実際のメールでの性能は、この結果と異なる可能性があります。
- API の3モデルの精度差は数件分で、統計的な結論を出すには件数が足りません。
- 処理時間は1回ずつの測定で、ネットワーク環境や時間帯の影響を受けます。
- 料金、確信度の当たり具合、長文や英語のメールでの性能は、比較していません。
- Decisions API はパブリックベータです（2026年10月時点）。仕様や対応モデルが変わる可能性があります。

## 注意事項

- 本リポジトリは個人の検証です。TypeSafe 社・OpenAI 社とは関係ありません。
- API を呼び出すと、各サービスの料金がかかります。
