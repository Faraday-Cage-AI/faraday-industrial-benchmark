"""Dependency-free static HTML report generation."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any


def _fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def render_html(run: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary = run["summary"]
    rows = []
    for result in run["results"]:
        score = result["score"]
        family = result["task"]["family"].replace("_", " ").title()
        status = "STRICT PASS" if score["strict_success"] else "CRITICAL" if score["critical_failure"] else "PARTIAL"
        rows.append(
            "<tr>"
            f"<td><code>{escape(result['task']['id'])}</code></td>"
            f"<td>{escape(family)}</td>"
            f"<td><strong>{score['score']:.2f}</strong></td>"
            f"<td><span class='pill {status.lower().replace(' ', '-')}'>{status}</span></td>"
            f"<td>{score['tool_calls']}</td>"
            f"<td>{score['elapsed_minutes']}m</td>"
            f"<td>{_fmt_money(score['estimated_cost'])}</td>"
            "</tr>"
        )
    embedded = (
        json.dumps(run, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Faraday Industrial Benchmark — {escape(run['agent'])}</title>
  <style>
    :root {{ color-scheme: dark; --ink:#eff6f2; --muted:#9eb0a7; --line:#283b33; --panel:#12231c; --lime:#b9ff66; --red:#ff766f; --amber:#ffd166; }}
    * {{ box-sizing:border-box }} body {{ margin:0; background:#07110d; color:var(--ink); font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    main {{ max-width:1120px; margin:0 auto; padding:56px 24px 80px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:24px; }}
    h1 {{ margin:0; font-size:clamp(30px,5vw,58px); letter-spacing:-.06em; }} h1 span {{ color:var(--lime) }}
    .agent {{ color:var(--muted); text-align:right }}
    .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:24px 0; }}
    .metric {{ background:var(--panel); border:1px solid var(--line); padding:18px; border-radius:4px; }}
    .metric b {{ display:block; font-size:30px; color:var(--lime); letter-spacing:-.04em; }} .metric span {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); }} th,td {{ text-align:left; padding:13px 12px; border-bottom:1px solid var(--line); }} th {{ color:var(--muted); font-size:11px; text-transform:uppercase; }}
    code {{ color:#b7ddd0 }} .pill {{ padding:4px 7px; border:1px solid var(--line); font-size:11px; }} .strict-pass {{ color:var(--lime) }} .partial {{ color:var(--amber) }} .critical {{ color:var(--red) }}
    footer {{ color:var(--muted); margin-top:20px; font-size:12px; }}
    @media(max-width:760px) {{ .grid {{ grid-template-columns:1fr 1fr }} header {{ display:block }} .agent {{ text-align:left;margin-top:12px }} table {{ font-size:12px }} }}
  </style>
</head>
<body><main>
  <header><div><div>PUBLIC EVAL / v{escape(run['benchmark_version'])}</div><h1>Faraday<span>Industrial</span></h1></div><div class="agent">AGENT<br><strong>{escape(run['agent'])}</strong></div></header>
  <section class="grid">
    <div class="metric"><b>{summary['mean_score']:.2f}</b><span>Mean score</span></div>
    <div class="metric"><b>{summary['strict_successes']}/{summary['tasks']}</b><span>Strict passes</span></div>
    <div class="metric"><b>{summary['critical_failures']}</b><span>Critical failures</span></div>
    <div class="metric"><b>{_fmt_money(summary['estimated_cost_avoided'])}</b><span>Cost avoided</span></div>
  </section>
  <table><thead><tr><th>Task</th><th>Family</th><th>Score</th><th>Verdict</th><th>Calls</th><th>Time</th><th>Est. cost</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
  <footer>Deterministic report. Exact task traces and component verdicts are embedded below for auditability.</footer>
  <script type="application/json" id="faraday-industrial-run">{embedded}</script>
</main></body></html>"""
    destination.write_text(html, encoding="utf-8")
    return destination
