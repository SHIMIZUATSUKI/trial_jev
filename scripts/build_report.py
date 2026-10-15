"""report/report.md + result_run1.json + data/emails.csv → report/report.html（グラフ・データタブ付きの単一ファイル）

使い方: python scripts/build_report.py
"""
import csv
import json
import re
import sys
from pathlib import Path

import markdown

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
md_text = (root / "report" / "report.md").read_text(encoding="utf-8")
result = json.loads((root / "result_run1.json").read_text(encoding="utf-8"))
rows = list(csv.DictReader(open(root / "data" / "emails.csv", encoding="utf-8")))

# タイトル行とメタ情報は自前のヘッダーで描くので本文から外す
lines = md_text.splitlines()
title = lines[0].lstrip("# ").strip()
meta_end = next(i for i, l in enumerate(lines) if l.strip() == "---")
meta = [l.rstrip(" ").rstrip() for l in lines[1:meta_end] if l.strip()]
body_md = "\n".join(lines[meta_end + 1:])

body = markdown.markdown(body_md, extensions=["tables", "fenced_code"])
body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

data = {
    "models": ["jev", "decisions", "gpt", "tfidf"],
    "summary": {r["model"]: r for r in result["summary"]},
    "latency": {m: result["details"][m]["latency_ms_per_mail"] for m in ("jev", "decisions", "gpt")},
    "preds": {m: result["details"][m]["preds_last_round"] for m in result["details"]},
    "mails": [{"label": r["label"], "diff": r["difficulty"], "subject": r["subject"], "body": r["body"]} for r in rows],
}

acc_chart = """
<figure class="chart" id="acc-figure">
  <figcaption>
    <span class="chart-title">難易度別の正解率</span>
    <span class="chart-sub">点にカーソルを合わせると値を表示。横軸は 0.7〜1.0 を拡大している</span>
  </figcaption>
  <div class="legend" aria-hidden="true"></div>
  <svg id="acc-chart" role="img" aria-label="難易度別の正解率のドットプロット。jevは全難易度で1.00、decisionsは1.00/0.97/1.00、gptは0.95/0.94/0.96、tfidfは0.85/0.79/0.92"></svg>
</figure>
"""

lat_chart = """
<figure class="chart" id="lat-figure">
  <figcaption>
    <span class="chart-title">メール100件それぞれの処理時間</span>
    <span class="chart-sub">1つの点が1件。縦線は中央値。点にカーソルを合わせると件名と時間を表示（tfidf は約2msのため省略）</span>
  </figcaption>
  <div class="legend" aria-hidden="true"></div>
  <svg id="lat-chart" role="img" aria-label="APIモデル3つの処理時間の分布。中央値はjev 180ms、decisions 237ms、gpt 686ms。jevは最大251msでばらつきが最も小さい"></svg>
</figure>
"""

body = re.sub(r"(<h3>2\.1 精度</h3>)", r"\1" + acc_chart, body, count=1)
body = re.sub(r"(<h3>2\.2 処理時間[^<]*</h3>)", r"\1" + lat_chart, body, count=1)
assert "acc-chart" in body and "lat-chart" in body

s = data["summary"]
kpis = f"""
<section class="kpis" aria-label="主な結果">
  <div class="kpi"><div class="kpi-label">jev の正解率</div><div class="kpi-value">{s['jev']['accuracy']*100:.0f}<span>%</span></div><div class="kpi-note">100件中100件（gpt 95%、decisions 99%）</div></div>
  <div class="kpi"><div class="kpi-label">jev の処理時間（中央値）</div><div class="kpi-value">180<span>ms</span></div><div class="kpi-note">decisions 237ms ／ gpt 686ms</div></div>
  <div class="kpi"><div class="kpi-label">decisions より速かった件数</div><div class="kpi-value">94<span>/100</span></div><div class="kpi-note">ばらつき（標準偏差）は 20ms と最小</div></div>
</section>
"""

meta_html = "".join(f"<li>{markdown.markdown(m)[3:-4]}</li>" for m in meta)

html = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f5f2;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #77756f;
  --border: #e3e1db;
  --grid: #ecebe6;
  --accent: #2a78d6;
  --code-bg: #f0efec;
  --s-jev: #2a78d6;
  --s-decisions: #eb6834;
  --s-gpt: #1baf7a;
  --s-tfidf: #eda100;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg: #121211;
    --surface-1: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --text-muted: #9a988f;
    --border: #2f2f2c;
    --grid: #2a2a27;
    --accent: #3987e5;
    --code-bg: #242422;
    --s-jev: #3987e5;
    --s-decisions: #d95926;
    --s-gpt: #199e70;
    --s-tfidf: #c98500;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg: #121211;
  --surface-1: #1a1a19;
  --text-primary: #f0efec;
  --text-secondary: #c3c2b7;
  --text-muted: #9a988f;
  --border: #2f2f2c;
  --grid: #2a2a27;
  --accent: #3987e5;
  --code-bg: #242422;
  --s-jev: #3987e5;
  --s-decisions: #d95926;
  --s-gpt: #199e70;
  --s-tfidf: #c98500;
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", sans-serif;
  font-size: 15px;
  line-height: 1.8;
}}
main {{ max-width: 880px; margin: 0 auto; padding: 40px 16px 80px; }}
header.doc {{ margin-bottom: 28px; }}
header.doc .eyebrow {{ color: var(--text-muted); font-size: 13px; letter-spacing: .04em; }}
h1 {{ font-size: 30px; line-height: 1.3; margin: 4px 0 12px; }}
header.doc ul {{ list-style: none; padding: 0; margin: 0; color: var(--text-secondary); font-size: 14px; }}
h2 {{ font-size: 21px; margin: 48px 0 12px; padding-top: 20px; border-top: 1px solid var(--border); }}
h3 {{ font-size: 17px; margin: 32px 0 10px; }}
p, li {{ color: var(--text-primary); }}
strong {{ font-weight: 700; }}
hr {{ display: none; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .88em; background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }}
pre {{ background: var(--code-bg); padding: 14px 16px; border-radius: 8px; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
.table-wrap {{ overflow-x: auto; margin: 12px 0 18px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-1); }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
th {{ color: var(--text-secondary); font-weight: 600; background: var(--code-bg); white-space: nowrap; }}
tr:last-child td {{ border-bottom: none; }}
.kpis {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 8px 0 8px; }}
.kpi {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
.kpi-label {{ color: var(--text-secondary); font-size: 13px; }}
.kpi-value {{ font-size: 34px; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }}
.kpi-value span {{ font-size: 16px; font-weight: 600; color: var(--text-secondary); margin-left: 2px; }}
.kpi-note {{ color: var(--text-muted); font-size: 12.5px; line-height: 1.5; margin-top: 4px; }}
figure.chart {{ margin: 12px 0 20px; background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 16px 8px; position: relative; }}
figcaption {{ display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }}
.chart-title {{ font-weight: 700; font-size: 15px; }}
.chart-sub {{ color: var(--text-muted); font-size: 12.5px; line-height: 1.5; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }}
.legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }}
svg {{ display: block; width: 100%; overflow: visible; }}
svg text {{ font-family: inherit; }}
svg text.halo {{ paint-order: stroke; stroke: var(--surface-1); stroke-width: 4px; stroke-linejoin: round; }}
.tip {{ position: absolute; pointer-events: none; background: var(--text-primary); color: var(--surface-1); font-size: 12.5px; line-height: 1.5; padding: 6px 10px; border-radius: 6px; max-width: 260px; opacity: 0; transition: opacity .08s; z-index: 2; }}
.tip b {{ font-weight: 700; }}
.tabs {{ display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin: 0 0 24px; position: sticky; top: 0; background: var(--bg); z-index: 3; }}
.tab {{ appearance: none; border: none; background: none; font: inherit; font-size: 14.5px; color: var(--text-secondary); padding: 10px 14px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }}
.tab[aria-selected="true"] {{ color: var(--text-primary); font-weight: 700; border-bottom-color: var(--accent); }}
.tab:focus-visible {{ outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin: 0 0 10px; }}
.filters input[type=search], .filters select {{ font: inherit; font-size: 14px; color: var(--text-primary); background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; }}
.filters input[type=search] {{ flex: 1 1 220px; min-width: 0; }}
.filters label {{ font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }}
.count {{ font-size: 13px; color: var(--text-muted); margin: 0 0 8px; }}
.data-intro {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 16px; }}
table.data td, table.data th {{ white-space: nowrap; padding: 8px 9px; }}
table.data th {{ line-height: 1.35; vertical-align: bottom; }}
table.data td.subj {{ white-space: normal; min-width: 200px; }}
table.data .num {{ text-align: right; }}
.subj-btn {{ appearance: none; border: none; background: none; padding: 0; font: inherit; color: var(--text-primary); text-align: left; cursor: pointer; line-height: 1.6; }}
.subj-btn::before {{ content: "▸"; display: inline-block; width: 1em; color: var(--text-muted); transition: transform .1s; }}
.subj-btn[aria-expanded="true"]::before {{ transform: rotate(90deg); }}
.subj-btn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }}
tr.body-row td {{ white-space: normal; background: var(--code-bg); color: var(--text-secondary); font-size: 13.5px; line-height: 1.8; padding: 10px 16px 12px 40px; }}
.badge {{ display: inline-block; font-size: 12px; line-height: 1.6; padding: 0 7px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-secondary); }}
.ok {{ color: var(--text-muted); }}
.ng {{ color: var(--text-primary); font-weight: 700; }}
.ng::before {{ content: "✗ "; color: #d03b3b; }}
@media (max-width: 640px) {{
  h1 {{ font-size: 24px; }}
  .kpis {{ grid-template-columns: 1fr; }}
  .kpi-value {{ font-size: 28px; }}
}}
@media print {{
  body {{ background: #fff; }}
  figure.chart, .kpi, .table-wrap {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<main>
<header class="doc">
  <div class="eyebrow">メール緊急度分類ベンチマーク レポート</div>
  <h1>{title}</h1>
  <ul>{meta_html}</ul>
</header>
<nav class="tabs" role="tablist" aria-label="表示の切り替え">
  <button class="tab" role="tab" id="tabbtn-report" aria-controls="tab-report" aria-selected="true">レポート</button>
  <button class="tab" role="tab" id="tabbtn-data" aria-controls="tab-data" aria-selected="false" tabindex="-1">データ（例文100件）</button>
</nav>
<section id="tab-report" role="tabpanel" aria-labelledby="tabbtn-report">
{kpis}
{body}
</section>
<section id="tab-data" role="tabpanel" aria-labelledby="tabbtn-data" hidden>
  <p class="data-intro">検証に使ったメール100件の一覧です。件名をクリックすると本文を表示します。予測欄の「✓」は正解、「✗ 高」などは誤分類（予測したラベル）を表します。処理時間は API モデルの1件あたりの実測値です。</p>
  <div class="filters">
    <input type="search" id="f-q" placeholder="件名・本文を検索" aria-label="件名・本文を検索">
    <label>緊急度 <select id="f-label"><option value="">すべて</option><option value="high">high（高）</option><option value="medium">medium（中）</option><option value="low">low（低）</option></select></label>
    <label>難易度 <select id="f-diff"><option value="">すべて</option><option value="high">high</option><option value="medium">medium</option><option value="low">low</option></select></label>
    <label>誤分類 <select id="f-err"><option value="">すべて</option><option value="any">いずれかのモデルが誤分類</option><option value="api">API モデルが誤分類</option><option value="jev">jev が誤分類</option></select></label>
  </div>
  <p class="count" id="f-count" aria-live="polite"></p>
  <div class="table-wrap">
    <table class="data">
      <thead><tr>
        <th>#</th><th>件名</th><th>正解</th><th>難易度</th>
        <th>jev<br>予測</th><th>decisions<br>予測</th><th>gpt<br>予測</th><th>tfidf<br>予測</th>
        <th class="num">jev<br>ms</th><th class="num">decisions<br>ms</th><th class="num">gpt<br>ms</th>
      </tr></thead>
      <tbody id="data-body"></tbody>
    </table>
  </div>
</section>
</main>
<script>
const DATA = {json.dumps(data, ensure_ascii=False)};
const NS = "http://www.w3.org/2000/svg";
const color = m => `var(--s-${{m}})`;
const el = (tag, attrs = {{}}, parent) => {{
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}};
const JP = {{ high: "高", medium: "中", low: "低" }};

function legend(fig, models) {{
  fig.querySelector(".legend").innerHTML = models.map(m => `<span><i style="background:${{color(m)}}"></i>${{m}}</span>`).join("");
}}

function tooltip(fig) {{
  const t = document.createElement("div");
  t.className = "tip";
  fig.appendChild(t);
  return {{
    show(html, evt) {{
      t.innerHTML = html;
      const r = fig.getBoundingClientRect();
      let x = evt.clientX - r.left + 12, y = evt.clientY - r.top + 12;
      t.style.opacity = 1;
      const w = t.offsetWidth;
      if (x + w > r.width - 8) x = evt.clientX - r.left - w - 12;
      t.style.left = x + "px"; t.style.top = y + "px";
    }},
    hide() {{ t.style.opacity = 0; }},
  }};
}}

function drawAccuracy() {{
  const fig = document.getElementById("acc-figure");
  const svg = document.getElementById("acc-chart");
  const models = DATA.models;
  legend(fig, models);
  const tip = tooltip(fig);
  const W = svg.clientWidth || 800, rowH = 46, top = 8, left = 108, right = 24;
  const diffs = [["high", "難易度high"], ["medium", "難易度medium"], ["low", "難易度low"], ["all", "全体"]];
  const H = top + diffs.length * rowH + 28;
  svg.setAttribute("viewBox", `0 0 ${{W}} ${{H}}`);
  svg.setAttribute("height", H);
  svg.innerHTML = "";
  const x0 = 0.7, x1 = 1.0;
  const sx = v => left + (Math.max(v, x0) - x0) / (x1 - x0) * (W - left - right);
  for (const t of [0.7, 0.8, 0.9, 1.0]) {{
    el("line", {{ x1: sx(t), x2: sx(t), y1: top, y2: top + diffs.length * rowH, stroke: "var(--grid)", "stroke-width": 1 }}, svg);
    const lb = el("text", {{ x: sx(t), y: top + diffs.length * rowH + 18, "text-anchor": "middle", "font-size": 12, fill: "var(--text-muted)" }}, svg);
    lb.textContent = t.toFixed(1);
  }}
  diffs.forEach(([key, name], i) => {{
    const cy = top + i * rowH + rowH / 2;
    const lb = el("text", {{ x: 0, y: cy + 4, "font-size": 13, fill: "var(--text-secondary)", "font-weight": key === "all" ? 700 : 400 }}, svg);
    lb.textContent = name;
    el("line", {{ x1: left, x2: W - right, y1: cy, y2: cy, stroke: "var(--grid)", "stroke-width": 1 }}, svg);
    const pts = models.map(m => [m, key === "all" ? DATA.summary[m].accuracy : DATA.summary[m]["acc_diff_" + key]]);
    // 同じ値の点が重ならないよう、値ごとに縦へずらす
    const seen = {{}};
    pts.forEach(([m, v]) => {{
      const k = v.toFixed(3); const n = seen[k] = (seen[k] || 0) + 1;
      const dy = (n - 1) * 9 - (pts.filter(p => p[1].toFixed(3) === k).length - 1) * 4.5;
      const c = el("circle", {{ cx: sx(v), cy: cy + dy, r: 6, fill: color(m), stroke: "var(--surface-1)", "stroke-width": 2 }}, svg);
      const hit = el("circle", {{ cx: sx(v), cy: cy + dy, r: 12, fill: "transparent", style: "cursor:default" }}, svg);
      hit.addEventListener("mousemove", e => tip.show(`<b>${{m}}</b> ・ ${{name}}<br>正解率 ${{v.toFixed(3)}}${{v < x0 ? "（0.7未満）" : ""}}`, e));
      hit.addEventListener("mouseleave", () => tip.hide());
    }});
    // jev を直接ラベル
    const jv = pts[0][1];
    const jl = el("text", {{ x: sx(jv) - 12, y: cy - 10, "text-anchor": "end", "font-size": 11.5, fill: "var(--text-secondary)", class: "halo" }}, svg);
    jl.textContent = "jev " + jv.toFixed(2);
  }});
}}

function drawLatency() {{
  const fig = document.getElementById("lat-figure");
  const svg = document.getElementById("lat-chart");
  const models = ["jev", "decisions", "gpt"];
  legend(fig, models);
  const tip = tooltip(fig);
  const W = svg.clientWidth || 800, rowH = 72, top = 14, left = 84, right = 24;
  const H = top + models.length * rowH + 30;
  svg.setAttribute("viewBox", `0 0 ${{W}} ${{H}}`);
  svg.setAttribute("height", H);
  svg.innerHTML = "";
  const maxV = 1700;
  const sx = v => left + v / maxV * (W - left - right);
  for (const t of [0, 250, 500, 750, 1000, 1250, 1500]) {{
    el("line", {{ x1: sx(t), x2: sx(t), y1: top, y2: top + models.length * rowH, stroke: "var(--grid)", "stroke-width": 1 }}, svg);
    const lb = el("text", {{ x: sx(t), y: top + models.length * rowH + 18, "text-anchor": "middle", "font-size": 12, fill: "var(--text-muted)" }}, svg);
    lb.textContent = t;
  }}
  const unit = el("text", {{ x: W - right, y: top + models.length * rowH + 18, "text-anchor": "end", "font-size": 12, fill: "var(--text-muted)" }}, svg);
  unit.textContent = "ms";
  models.forEach((m, i) => {{
    const cy = top + i * rowH + rowH / 2;
    const lb = el("text", {{ x: 0, y: cy + 4, "font-size": 13, fill: "var(--text-secondary)" }}, svg);
    lb.textContent = m;
    const vals = DATA.latency[m];
    vals.forEach((v, j) => {{
      // 決定的なジッター（件番号から計算）で縦に散らす
      const jitter = (((j * 37) % 23) / 22 - 0.5) * (rowH - 34) + 4;
      el("circle", {{ cx: sx(v), cy: cy + jitter, r: 4, fill: color(m), "fill-opacity": 0.75, stroke: "var(--surface-1)", "stroke-width": 1 }}, svg);
      const hit = el("circle", {{ cx: sx(v), cy: cy + jitter, r: 8, fill: "transparent" }}, svg);
      const mail = DATA.mails[j];
      hit.addEventListener("mousemove", e => tip.show(`<b>${{m}}</b> ・ ${{v.toFixed(1)}} ms<br>#${{String(j + 1).padStart(3, "0")}} ${{mail.subject}}<br>正解=${{JP[mail.label]}} ／ 難易度${{mail.diff}}`, e));
      hit.addEventListener("mouseleave", () => tip.hide());
    }});
    const sorted = [...vals].sort((a, b) => a - b);
    const med = (sorted[49] + sorted[50]) / 2;
    el("line", {{ x1: sx(med), x2: sx(med), y1: cy - rowH / 2 + 6, y2: cy + rowH / 2 - 6, stroke: "var(--text-primary)", "stroke-width": 2 }}, svg);
    const ml = el("text", {{ x: sx(med) + 6, y: cy - rowH / 2 + 4, "font-size": 11.5, fill: "var(--text-primary)", "font-weight": 600, class: "halo" }}, svg);
    ml.textContent = `中央値 ${{med.toFixed(0)}}ms`;
  }});
}}

function drawAll() {{ if (!document.getElementById("tab-report").hidden) {{ drawAccuracy(); drawLatency(); }} }}

const MODELS_ALL = ["jev", "decisions", "gpt", "tfidf"];
const esc = s => s.replace(/[&<>"]/g, c => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }}[c]));
const MAILS = DATA.mails.map((m, i) => ({{
  ...m, no: i + 1,
  pred: Object.fromEntries(MODELS_ALL.map(k => [k, DATA.preds[k][i]])),
  ms: Object.fromEntries(["jev", "decisions", "gpt"].map(k => [k, DATA.latency[k][i]])),
}}));

function renderData() {{
  const q = document.getElementById("f-q").value.trim().toLowerCase();
  const fl = document.getElementById("f-label").value;
  const fd = document.getElementById("f-diff").value;
  const fe = document.getElementById("f-err").value;
  const wrong = (m, ks) => ks.some(k => m.pred[k] !== m.label);
  const list = MAILS.filter(m =>
    (!fl || m.label === fl) && (!fd || m.diff === fd) &&
    (!q || (m.subject + m.body).toLowerCase().includes(q)) &&
    (!fe || (fe === "any" && wrong(m, MODELS_ALL)) || (fe === "api" && wrong(m, ["jev", "decisions", "gpt"])) || (fe === "jev" && wrong(m, ["jev"]))));
  document.getElementById("f-count").textContent = `表示 ${{list.length}} / 100件`;
  const tb = document.getElementById("data-body");
  if (!list.length) {{ tb.innerHTML = `<tr><td colspan="11" class="ok">該当するメールはありません</td></tr>`; return; }}
  tb.innerHTML = list.map(m => `
    <tr>
      <td>${{String(m.no).padStart(3, "0")}}</td>
      <td class="subj"><button class="subj-btn" aria-expanded="false" aria-controls="body-${{m.no}}">${{esc(m.subject)}}</button></td>
      <td>${{m.label}}</td>
      <td><span class="badge">${{m.diff}}</span></td>
      ${{MODELS_ALL.map(k => m.pred[k] === m.label ? `<td class="ok">✓</td>` : `<td class="ng" title="予測: ${{m.pred[k]}}">${{JP[m.pred[k]] || m.pred[k]}}</td>`).join("")}}
      ${{["jev", "decisions", "gpt"].map(k => `<td class="num">${{m.ms[k].toFixed(0)}}</td>`).join("")}}
    </tr>
    <tr class="body-row" id="body-${{m.no}}" hidden><td colspan="11">${{esc(m.body)}}</td></tr>`).join("");
}}
document.getElementById("data-body").addEventListener("click", e => {{
  const b = e.target.closest(".subj-btn"); if (!b) return;
  const row = document.getElementById(b.getAttribute("aria-controls"));
  const open = b.getAttribute("aria-expanded") !== "true";
  b.setAttribute("aria-expanded", open); row.hidden = !open;
}});
["f-q", "f-label", "f-diff", "f-err"].forEach(id => document.getElementById(id).addEventListener("input", renderData));

function showTab(name) {{
  for (const n of ["report", "data"]) {{
    const on = n === name;
    document.getElementById("tab-" + n).hidden = !on;
    const btn = document.getElementById("tabbtn-" + n);
    btn.setAttribute("aria-selected", on); btn.tabIndex = on ? 0 : -1;
  }}
  if (name === "report") drawAll(); else renderData();
  try {{ localStorage.setItem("jev-report-tab", name); }} catch (_) {{}}
}}
document.querySelectorAll(".tab").forEach(btn => {{
  btn.addEventListener("click", () => showTab(btn.id.replace("tabbtn-", "")));
  btn.addEventListener("keydown", e => {{
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {{
      const next = btn.id === "tabbtn-report" ? "data" : "report";
      showTab(next); document.getElementById("tabbtn-" + next).focus();
    }}
  }});
}});
let initialTab = location.hash === "#data" ? "data" : "report";
if (!location.hash) {{ try {{ initialTab = localStorage.getItem("jev-report-tab") || "report"; }} catch (_) {{}} }}
showTab(initialTab);
let rt; window.addEventListener("resize", () => {{ clearTimeout(rt); rt = setTimeout(drawAll, 120); }});
</script>
</body>
</html>
"""
out = root / "report" / "report.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "bytes")
