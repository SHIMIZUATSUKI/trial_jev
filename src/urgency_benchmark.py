from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.urgency_data import DEFAULT_CSV, build_mail_text, load_emails_csv

LABELS = ["high", "medium", "low"]
JP = {"high": "高", "medium": "中", "low": "低"}


def pct(values: List[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def summarize(name: str, labels: List[str], preds: List[str], times: List[float]) -> Dict[str, Any]:
    acc = sum(p == y for p, y in zip(preds, labels)) / len(labels)
    f1s = []
    for c in LABELS:
        tp = sum(p == c and y == c for p, y in zip(preds, labels))
        fp = sum(p == c and y != c for p, y in zip(preds, labels))
        fn = sum(p != c and y == c for p, y in zip(preds, labels))
        f1s.append(0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))

    return {
        "model": name,
        "accuracy": round(acc, 3),
        "macro_f1": round(sum(f1s) / 3, 3),
        "mean_ms": round(statistics.mean(times) * 1000, 2),
        "p95_ms": round(pct(times, 0.95) * 1000, 2),
        "max_ms": round(max(times) * 1000, 2),
        "total_s": round(sum(times), 3),
    }


def confusion(labels: List[str], preds: List[str]) -> List[List[int]]:
    return [[sum(l == y and p == c for l, p in zip(labels, preds)) for c in LABELS] for y in LABELS]


def run_tfidf(texts: List[str], labels: List[str]) -> Tuple[List[str], List[float], Dict[str, Any]]:
    """leave-one-out。学習時間は fit_mean_ms として返す。"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    preds: List[str] = []
    times: List[float] = []
    fit_times: List[float] = []

    for i in range(len(texts)):
        tr_x = [t for j, t in enumerate(texts) if j != i]
        tr_y = [l for j, l in enumerate(labels) if j != i]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3))
        clf = LogisticRegression(max_iter=1000, C=10)
        t0 = time.perf_counter()
        clf.fit(vec.fit_transform(tr_x), tr_y)
        fit_times.append(time.perf_counter() - t0)

        t1 = time.perf_counter()
        p = clf.predict(vec.transform([texts[i]]))[0]
        times.append(time.perf_counter() - t1)
        preds.append(p)

    return preds, times, {"fit_mean_ms": round(statistics.mean(fit_times) * 1000, 2)}


_DEFINITIONS = (
    "high = 今日〜数時間以内の対応が必要。"
    "medium = 数日以内の対応が必要。"
    "low = 対応期限がなく情報共有中心。"
    "事業影響、期限、顧客/社内への影響度を総合的に見てください。"
)

_SYSTEM = (
    "あなたはメールの緊急度分類器です。" + _DEFINITIONS +
    "回答は high / medium / low のいずれかを JSON で返してください。"
    '例: {"urgency": "high"}'
)


def _classify_gpt(client: Any, model: str, text: str) -> str:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"メール本文:\n{text}\n\n"
                    "このメールの緊急度を high / medium / low のどれかで決めてください。"
                    "JSONだけを返してください。"
                ),
            },
        ],
    )

    content = response.choices[0].message.content or "{}"
    try:
        urgency = json.loads(content).get("urgency")
    except (json.JSONDecodeError, AttributeError):
        urgency = None

    if urgency not in LABELS:
        for label in LABELS:
            if label in content.lower():
                urgency = label
                break
    if urgency not in LABELS:
        raise ValueError(f"GPT の返答が不正です: {content!r}")
    return urgency


def run_gpt(texts: List[str], warmup: bool = True) -> Tuple[List[str], List[float], Dict[str, Any]]:
    """同じクライアントでウォームアップ1回（計測外）→ 各メールを計測。"""
    from openai import OpenAI

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    preds: List[str] = []
    times: List[float] = []

    if warmup and texts:
        _classify_gpt(client, model, texts[0])

    for t in texts:
        t0 = time.perf_counter()
        preds.append(_classify_gpt(client, model, t))
        times.append(time.perf_counter() - t0)
    return preds, times, {}


_URGENCY_CRITERIA = {
    "high": "重大な障害、法務・セキュリティ・契約解除などの緊急対応が必要。",
    "medium": "数日以内の対応が必要だが、今すぐではない。",
    "low": "情報共有、定例、事務連絡で対応期限が明確でない。",
}


def _classify_decisions(client: Any, model: str, text: str) -> str:
    """OpenAI Decisions API の choice 質問で緊急度を判定する。"""
    decision = client.decisions.create(
        model=model,
        input=text,
        questions=[
            {
                "type": "choice",
                "name": "urgency",
                "instructions": "メールの緊急度を high / medium / low の3択で判定してください。" + _DEFINITIONS,
                "choices": [{"value": k, "description": v} for k, v in _URGENCY_CRITERIA.items()],
            }
        ],
    )
    answer = decision.answers[0]
    if answer.type == "refusal":
        raise ValueError("Decisions API が回答を拒否しました")
    if getattr(answer, "choice", None) in LABELS:
        return answer.choice
    if getattr(answer, "probabilities", None):
        return max(answer.probabilities, key=lambda p: p.probability).value
    raise ValueError("Decisions API の応答から緊急度を抽出できませんでした")


def run_gpt_decisions(texts: List[str], warmup: bool = True) -> Tuple[List[str], List[float], Dict[str, Any]]:
    """GPT/Jev と同条件（クライアント使い回し・計測外ウォームアップ1回）で Decisions API を計測。"""
    from openai import OpenAI

    client = OpenAI()
    model = os.environ.get("OPENAI_DECISIONS_MODEL", "gpt-6-luna")
    preds: List[str] = []
    times: List[float] = []

    if warmup and texts:
        _classify_decisions(client, model, texts[0])

    for t in texts:
        t0 = time.perf_counter()
        preds.append(_classify_decisions(client, model, t))
        times.append(time.perf_counter() - t0)
    return preds, times, {}


def _jev_api_key() -> str:
    api_key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
    if not api_key:
        raise RuntimeError("Jev を使うには TYPESAFE_API_KEY または JEV_API_KEY を設定してください。")
    os.environ["TYPESAFE_API_KEY"] = api_key
    return api_key


def _import_typesafe() -> Any:
    try:
        import typesafe_sdk
    except ImportError as exc:  # pragma: no cover - 実行時に依存が不足している場合
        raise RuntimeError("typesafe-sdk が未インストールです。pip install -r requirements.txt を実行してください。") from exc
    return typesafe_sdk


def classify_jev(text: str, client: Any = None) -> str:
    """TypeSafe Jev を使い、メールの緊急度を高/中/低に分類する。client を渡すと使い回す。"""
    sdk = _import_typesafe()
    if client is None:
        _jev_api_key()
        with sdk.TypeSafeClient() as own_client:
            return classify_jev(text, own_client)

    question = sdk.Choice(
        instructions="メールの緊急度を high / medium / low の3択で判定してください。" + _DEFINITIONS,
        criteria=_URGENCY_CRITERIA,
    )
    response = client.system_one(
        model=os.environ.get("JEV_MODEL", "jev-latest"),
        state=text,
        questions={"urgency": question},
    )
    result = response.answers["urgency"]
    if getattr(result, "choice", None) in LABELS:
        return result.choice
    if getattr(result, "probabilities", None):
        return max(result.probabilities.items(), key=lambda kv: kv[1])[0]
    raise ValueError("Jev の応答から緊急度を抽出できませんでした")


def run_jev(texts: List[str], warmup: bool = True) -> Tuple[List[str], List[float], Dict[str, Any]]:
    """GPT と条件を揃え、同じクライアントでウォームアップ1回（計測外）→ 各メールを計測。"""
    sdk = _import_typesafe()
    _jev_api_key()
    preds: List[str] = []
    times: List[float] = []
    with sdk.TypeSafeClient() as client:
        if warmup and texts:
            classify_jev(texts[0], client)
        for t in texts:
            t0 = time.perf_counter()
            preds.append(classify_jev(t, client))
            times.append(time.perf_counter() - t0)
    return preds, times, {}


def load_env() -> None:
    """trial_jev/.env → その親の .env の順に読み込む（既存の環境変数は上書きしない）。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[1]
    for path in (root / ".env", root.parent / ".env"):
        if path.exists():
            load_dotenv(path, override=False)


def _ordered_difficulties(difficulties: List[str]) -> List[str]:
    """難易度を high → medium → low の順に並べる（未知の値は後ろ）。"""
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted({d for d in difficulties if d}, key=lambda d: (order.get(d, 9), d))


def main() -> None:
    ap = argparse.ArgumentParser(description="メール緊急度の精度・速度ベンチマーク")
    ap.add_argument(
        "--models",
        nargs="+",
        default=["tfidf", "gpt", "decisions", "jev"],
        choices=["tfidf", "gpt", "decisions", "jev"],
    )
    ap.add_argument("--repeat", type=int, default=1, help="何周するか（レイテンシ安定化用）")
    ap.add_argument("--out", default="urgency_results.json")
    ap.add_argument("--data", type=str, default=str(DEFAULT_CSV), help="CSV データファイルのパス")
    args = ap.parse_args()
    load_env()

    rows = load_emails_csv(args.data)
    labels = [row["label"] for row in rows]
    difficulties = [row.get("difficulty", "") for row in rows]
    texts = [build_mail_text(row["subject"], row["body"]) for row in rows]
    lens = [len(t) for t in texts]

    print(f"メール数={len(texts)}  文字数: 平均{statistics.mean(lens):.0f} / 最小{min(lens)} / 最大{max(lens)}")

    results: List[Dict[str, Any]] = []
    details: Dict[str, Dict[str, Any]] = {}
    per_mail: Dict[str, List[float]] = {}

    for m in args.models:
        if m in ("gpt", "decisions") and not os.environ.get("OPENAI_API_KEY"):
            print(f"[skip] {m}: OPENAI_API_KEY が未設定")
            continue
        if m == "jev" and not (os.environ.get("JEV_API_KEY") or os.environ.get("TYPESAFE_API_KEY")):
            print("[skip] jev: JEV_API_KEY / TYPESAFE_API_KEY が未設定")
            continue

        all_preds: List[str] = []
        all_times: List[float] = []
        extra: Dict[str, Any] = {}

        try:
            for r in range(args.repeat):
                if m == "tfidf":
                    p, t, extra = run_tfidf(texts, labels)
                elif m == "gpt":
                    p, t, extra = run_gpt(texts)
                elif m == "decisions":
                    p, t, extra = run_gpt_decisions(texts)
                else:
                    p, t, extra = run_jev(texts)
                all_preds += p
                all_times += t
        except NotImplementedError as e:
            print(f"[skip] {m}: {e}")
            continue
        except Exception as e:
            print(f"[error] {m}: {type(e).__name__}: {e}")
            continue

        res = summarize(m, labels * args.repeat, all_preds, all_times)
        res.update(extra)
        for diff in _ordered_difficulties(difficulties):
            idx = [i for i, d in enumerate(difficulties * args.repeat) if d == diff]
            res[f"acc_diff_{diff}"] = round(sum(all_preds[i] == (labels * args.repeat)[i] for i in idx) / len(idx), 3)
        results.append(res)
        per_mail[m] = [round(statistics.mean(all_times[i::len(texts)]) * 1000, 2) for i in range(len(texts))]
        details[m] = {
            "preds_last_round": all_preds[-len(texts):],
            "confusion(rows=true high/med/low, cols=pred)": confusion(labels * args.repeat, all_preds),
            "latency_ms_per_mail": per_mail[m],
        }

    print(f"\n{'model':9} {'acc':>6} {'macroF1':>8} {'mean(ms)':>9} {'p95(ms)':>9} {'max(ms)':>9} {'total(s)':>9}")
    for r in results:
        print(
            f"{r['model']:9} {r['accuracy']:>6} {r['macro_f1']:>8} {r['mean_ms']:>9} "
            f"{r['p95_ms']:>9} {r['max_ms']:>9} {r['total_s']:>9}"
        )
        if "fit_mean_ms" in r:
            print(f"         (参考) 学習1回の平均 {r['fit_mean_ms']} ms ← 推論時間には含めていない")

    diffs = _ordered_difficulties(difficulties)
    if diffs and results:
        counts = collections.Counter(difficulties)
        print("\n[難易度別の正解率]  " + "  ".join(f"難易度{d}({counts[d]}通)" for d in diffs))
        for r in results:
            print(f"  {r['model']:9} " + "  ".join(f"{r.get('acc_diff_' + d, '-'):>16}" for d in diffs))

    if per_mail:
        print("\n[メールごとの平均レイテンシ ms]  # 文字数 / " + " / ".join(per_mail))
        for i in range(len(texts)):
            cols = "  ".join(f"{per_mail[m][i]:>8}" for m in per_mail)
            print(f"  #{i+1:03d} 正解={JP[labels[i]]} {lens[i]:>4}字  {cols}  {rows[i]['subject'][:18]}")

    for m, d in details.items():
        print(f"\n[{m}] 混同行列 (行=正解 高/中/低, 列=予測 高/中/低)")
        for y, row in zip(LABELS, d["confusion(rows=true high/med/low, cols=pred)"]):
            print(f"  {JP[y]}: {row}")
        for i, p in enumerate(d["preds_last_round"]):
            if p != labels[i]:
                tag = f"[難易度{difficulties[i]}] " if difficulties[i] else ""
                print(f"  誤分類 #{i+1:03d} {tag}正解={JP[labels[i]]} 予測={JP.get(p, p)} : {rows[i]['subject']}")

    output_path = Path(args.out)
    output_path.write_text(
        json.dumps({"summary": results, "details": details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n結果を {args.out} に保存しました")


if __name__ == "__main__":
    main()
