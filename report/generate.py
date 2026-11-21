"""Static HTML Report Generator for PaySift.

Generates self-contained static HTML pages (inline CSS & JS, no external CDN/assets)
under report/out/:
- index.html: Dashboard linking all runs, kill-matrix, and scenarios
- <run_id>.html: Detailed run inspection with badge, shrink history, and rule texts
- kill_matrix.html: Complete mutant kill matrix table
- scenarios.html: Static scenario replay and break-it demonstration
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from pilot.packets import RULE_TEXTS

DARK_THEME_CSS = """
:root {
  --bg-main: #0b0f19;
  --bg-card: #131b2e;
  --bg-subtle: #1e293b;
  --border: #334155;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --color-pass: #22c55e;
  --color-fail: #ef4444;
  --color-warn: #f59e0b;
  --color-blue: #3b82f6;
  --color-purple: #8b5cf6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-main);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.5;
  padding: 2rem;
}
.container { max-width: 1200px; margin: 0 auto; }
h1, h2, h3, h4 { color: var(--text-main); font-weight: 700; margin-bottom: 1rem; }
h1 { font-size: 2.25rem; display: flex; align-items: center; gap: 1rem; }
a { color: var(--color-blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.nav { display: flex; gap: 1.5rem; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.nav a { font-weight: 600; font-size: 1.1rem; }
.card {
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.stat-box {
  background-color: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  text-align: center;
}
.stat-num {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 2.25rem;
  font-weight: 700;
  line-height: 1.1;
  margin-top: 0.5rem;
}
.stat-pass { color: var(--color-pass); }
.stat-fail { color: var(--color-fail); }
.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.badge-live { background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }
.badge-pre-run { background-color: rgba(139, 92, 246, 0.2); color: #c084fc; border: 1px solid #8b5cf6; }
.badge-stub { background-color: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
.badge-mutant { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
.badge-reference { background-color: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
th { background-color: var(--bg-subtle); font-weight: 600; color: var(--text-muted); }
tr:hover { background-color: rgba(255, 255, 255, 0.02); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
pre {
  background-color: #030712;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}
.timeline-step {
  border-left: 2px solid var(--color-blue);
  padding-left: 1.25rem;
  margin-left: 0.5rem;
  margin-bottom: 1rem;
  position: relative;
}
.timeline-step::before {
  content: '';
  position: absolute;
  left: -7px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: var(--color-blue);
}
.callout-fail {
  border-left: 4px solid var(--color-fail);
  background-color: rgba(239, 68, 68, 0.1);
  padding: 1rem;
  border-radius: 0 6px 6px 0;
  margin: 1rem 0;
}
"""


def _get_badge_html(source: str) -> str:
    """Format source label and badge."""
    src = str(source).lower()
    if src == "mutant":
        return '<span class="badge badge-mutant">HAND-WRITTEN MUTANT</span>'
    elif src == "reference":
        return '<span class="badge badge-reference">REFERENCE HANDLER</span>'
    elif src == "pre-run":
        return '<span class="badge badge-pre-run">PRE-RUN CACHED</span>'
    elif src == "stub":
        return '<span class="badge badge-stub">STUB (TEST STAND-IN)</span>'
    elif src == "live":
        return '<span class="badge badge-live">LIVE GENERATION</span>'
    return f'<span class="badge badge-pre-run">{html.escape(source.upper())}</span>'


def generate_index_html(runs: List[Dict[str, Any]], out_dir: Path) -> str:
    """Generate index.html dashboard."""
    rows = []
    for r in runs:
        rid = r.get("run_id", "unknown")
        cand = r.get("candidate", {})
        cid = cand.get("id", "unknown")
        model = cand.get("model", "-")
        cond = cand.get("condition", "-")
        src = cand.get("source", "unknown")
        badge = _get_badge_html(src)
        fail_count = len(r.get("failures", []))
        fail_badge = f'<span style="color:var(--color-fail); font-weight:700;">{fail_count} failures</span>' if fail_count > 0 else '<span style="color:var(--color-pass); font-weight:700;">CLEAN (0)</span>'
        repaired = f'<span style="color:var(--color-pass);">Repairs {r.get("repair_of")}</span>' if r.get("repair_of") else '-'

        rows.append(f"""
        <tr>
          <td><a href="{rid}.html" class="mono"><strong>{html.escape(rid)}</strong></a></td>
          <td>{badge}</td>
          <td><code>{html.escape(str(cid))}</code></td>
          <td><code>{html.escape(str(model))}</code></td>
          <td>{html.escape(str(cond))}</td>
          <td>{fail_badge}</td>
          <td>{repaired}</td>
        </tr>
        """)

    table_body = "\n".join(rows) if rows else "<tr><td colspan='7'>No runs recorded.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PaySift - Verification Dashboard</title>
  <style>{DARK_THEME_CSS}</style>
</head>
<body>
  <div class="container">
    <h1>PaySift Verification Dashboard</h1>
    <p style="color:var(--text-muted); margin-bottom: 1.5rem;">Stress-test AI-written payment webhook code against financial integrity invariants.</p>
    
    <div class="nav">
      <a href="index.html">Runs Dashboard</a>
      <a href="kill_matrix.html">Kill Matrix</a>
      <a href="scenarios.html">Break-it Scenarios Replay</a>
    </div>

    <div class="card">
      <h2>Completed Runs ({len(runs)})</h2>
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Type</th>
            <th>Candidate</th>
            <th>Model</th>
            <th>Condition</th>
            <th>Status</th>
            <th>Repair Of</th>
          </tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def generate_run_html(run_dict: Dict[str, Any]) -> str:
    """Generate individual run report page with shrink history and rule citations."""
    rid = run_dict.get("run_id", "unknown")
    cand = run_dict.get("candidate", {})
    cid = cand.get("id", "unknown")
    label = cand.get("label", cid)
    src = cand.get("source", "unknown")
    badge = _get_badge_html(src)
    spec_sha = run_dict.get("spec_sha", "unknown")
    oracle_sha = run_dict.get("oracle_sha", "unknown")
    seeds = run_dict.get("seeds", [0, 99])

    results = run_dict.get("results", {})
    stat_boxes = []
    for inv in ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]:
        data = results.get(inv, {})
        norm = data.get("normal") or {"passed": 0, "failed": 0}
        pass_count = norm.get("passed", 0)
        fail_count = norm.get("failed", 0)
        num_class = "stat-fail" if fail_count > 0 else "stat-pass"
        stat_boxes.append(f"""
        <div class="stat-box">
          <div style="font-size:0.85rem; color:var(--text-muted);">{inv}</div>
          <div class="stat-num {num_class}">{pass_count}/{pass_count + fail_count}</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">{fail_count} failed</div>
        </div>
        """)

    failures = run_dict.get("failures", [])
    failure_cards = []
    for idx, f in enumerate(failures):
        rule_id = f.get("rule", "Unknown")
        rule_desc = RULE_TEXTS.get(rule_id, "Rule description not available.")
        expl = f.get("explanation", "")
        repro = f.get("repro", {})
        repro_text = f"{repro.get('reproduced', 0)} of {repro.get('runs', 0)} runs" if repro else "Not tested"
        one_min = f.get("one_minimal", False)

        # Shrink history steps
        shrink_history = f.get("shrink_history", [])
        history_steps = []
        if shrink_history:
            for s_idx, stream_snap in enumerate(shrink_history):
                step_title = "Initial Stream" if s_idx == 0 else (f"Reduction Step {s_idx}" if s_idx < len(shrink_history) - 1 else "Minimal Counterexample (1-minimal)")
                events_list = "".join(f"<li><code>{html.escape(str(ev.get('summary', ev)))}</code></li>" for ev in stream_snap)
                history_steps.append(f"""
                <div class="timeline-step">
                  <strong>{step_title}</strong> ({len(stream_snap)} events)
                  <ul style="margin-left:1.5rem; margin-top:0.25rem;">{events_list}</ul>
                </div>
                """)
        else:
            # Minimal stream fallback
            min_stream = f.get("minimal_stream") or f.get("stream") or []
            events_list = "".join(f"<li><code>{html.escape(str(ev.get('summary', ev)))}</code></li>" for ev in min_stream)
            history_steps.append(f"<div class='timeline-step'><strong>Counterexample Trace</strong> ({len(min_stream)} events)<ul>{events_list}</ul></div>")

        history_html = "\n".join(history_steps)

        failure_cards.append(f"""
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>Failure #{idx + 1}: {f.get('invariant')} (Rule {rule_id})</h3>
            <span style="font-size:0.9rem; color:var(--color-fail); font-weight:700;">10x Repro: {repro_text}</span>
          </div>
          
          <div class="callout-fail">
            <strong>Rule {rule_id}:</strong> {html.escape(rule_desc)}
          </div>

          <p style="margin-bottom:1rem;"><strong>Explanation:</strong> {html.escape(expl)}</p>

          <h4>Shrinker History & Counterexample Timeline</h4>
          <div style="margin-top:1rem;">
            {history_html}
          </div>

          <h4 style="margin-top:1.5rem;">State Comparison</h4>
          <div class="grid">
            <div class="stat-box" style="text-align:left;">
              <strong>Expected State (Oracle)</strong>
              <pre>{html.escape(json.dumps(f.get('expected', {}), indent=2))}</pre>
            </div>
            <div class="stat-box" style="text-align:left;">
              <strong>Observed State (Candidate DB)</strong>
              <pre>{html.escape(json.dumps(f.get('observed', {}), indent=2))}</pre>
            </div>
          </div>
        </div>
        """)

    failures_html = "\n".join(failure_cards) if failure_cards else "<div class='card'><p style='color:var(--color-pass); font-weight:700;'>No failures recorded. Candidate passed all evaluated invariants.</p></div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PaySift - Run {html.escape(rid)}</title>
  <style>{DARK_THEME_CSS}</style>
</head>
<body>
  <div class="container">
    <div class="nav">
      <a href="index.html">&larr; Back to Dashboard</a>
      <a href="kill_matrix.html">Kill Matrix</a>
      <a href="scenarios.html">Scenarios Replay</a>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
      <h1>Run: <span class="mono">{html.escape(rid)}</span></h1>
      {badge}
    </div>
    <p style="color:var(--text-muted); margin-bottom:1.5rem;"><strong>Target:</strong> {html.escape(label)} | Seeds: {seeds[0]}..{seeds[1]}</p>

    <div class="card" style="font-size:0.9rem; display:flex; gap:2rem; flex-wrap:wrap;">
      <div><strong>Spec SHA:</strong> <code class="mono">{html.escape(spec_sha[:16])}...</code></div>
      <div><strong>Oracle SHA:</strong> <code class="mono">{html.escape(oracle_sha[:16])}...</code></div>
      <div><strong>Created:</strong> {html.escape(run_dict.get('created_at', '-'))}</div>
    </div>

    <h2>Invariant Scorecard</h2>
    <div class="grid">
      {"".join(stat_boxes)}
    </div>

    <h2>Failure Diagnostics ({len(failures)})</h2>
    {failures_html}
  </div>
</body>
</html>
"""


def generate_kill_matrix_html(km_dict: Dict[str, Any]) -> str:
    """Generate kill_matrix.html page."""
    rows = km_dict.get("rows", [])
    invariants = ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]

    table_rows = []
    for r in rows:
        cid = r.get("id")
        lbl = r.get("label")
        src = r.get("source", "mutant")
        expected_rule = r.get("expected_rule", "-")
        badge = _get_badge_html(src)

        inv_cells = []
        for inv in invariants:
            cell_data = r.get(inv, {})
            status = cell_data.get("status", "pass")
            if status == "pass":
                inv_cells.append('<td style="color:var(--color-pass); font-weight:700; text-align:center;">PASS</td>')
            else:
                rule_cited = cell_data.get("rule", expected_rule)
                inv_cells.append(f'<td style="color:var(--color-fail); font-weight:700; text-align:center;">KILLED ({rule_cited})</td>')

        table_rows.append(f"""
        <tr>
          <td><code class="mono"><strong>{html.escape(str(cid))}</strong></code></td>
          <td>{badge}</td>
          <td>{html.escape(str(lbl))}</td>
          <td><code>{html.escape(str(expected_rule))}</code></td>
          {"".join(inv_cells)}
        </tr>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PaySift - Mutant Kill Matrix</title>
  <style>{DARK_THEME_CSS}</style>
</head>
<body>
  <div class="container">
    <div class="nav">
      <a href="index.html">&larr; Back to Dashboard</a>
      <a href="scenarios.html">Scenarios Replay</a>
    </div>

    <h1>Mutant Kill Matrix</h1>
    <p style="color:var(--text-muted); margin-bottom:1.5rem;">Proof of test suite sensitivity: reference passes all invariants, while every intentional mutant is killed by its intended rule.</p>

    <div class="card">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Description</th>
            <th>Target Rule</th>
            <th>I1 Signature</th>
            <th>I2 Idempotency</th>
            <th>I3 Conservation</th>
            <th>I4 Bounds</th>
            <th>I5 Interface</th>
          </tr>
        </thead>
        <tbody>
          {"".join(table_rows)}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def generate_scenarios_html(scenarios_data: Dict[str, Any]) -> str:
    """Generate static interactive scenario replay page (no API required)."""
    data_json = json.dumps(scenarios_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PaySift - Break-it Scenarios Replay</title>
  <style>
    {DARK_THEME_CSS}
    .scenario-btn {{
      background-color: var(--bg-subtle);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 0.6rem 1.2rem;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
    }}
    .scenario-btn.active {{
      background-color: var(--color-blue);
      border-color: var(--color-blue);
      color: white;
    }}
    .counter-box {{
      background: #000;
      border: 2px solid var(--color-fail);
      border-radius: 8px;
      padding: 1.5rem;
      text-align: center;
      margin-top: 1rem;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="nav">
      <a href="index.html">&larr; Back to Dashboard</a>
      <a href="kill_matrix.html">Kill Matrix</a>
    </div>

    <h1>Break-it Scenarios (Static Replay)</h1>
    <p style="color:var(--text-muted); margin-bottom:1.5rem;">Interactive scenario replay built offline from pre-computed verdicts. Test how different handlers react to malicious or ill-formed webhook streams.</p>

    <div class="card">
      <div style="display:flex; gap:1rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem;">
        <label><strong>Select Candidate:</strong></label>
        <select id="cand-select" style="background:var(--bg-subtle); color:var(--text-main); border:1px solid var(--border); padding:0.5rem; border-radius:4px;">
        </select>

        <label style="margin-left:1.5rem;"><strong>Select Scenario:</strong></label>
        <div id="scenario-buttons" style="display:flex; gap:0.5rem; flex-wrap:wrap;"></div>
      </div>
    </div>

    <div class="card" id="details-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2 id="sc-title">Scenario Title</h2>
        <span id="sc-verdict" class="badge">VERDICT</span>
      </div>
      <p id="sc-expl" style="color:var(--text-muted); margin:0.5rem 0 1rem 0;"></p>

      <div class="grid">
        <div class="stat-box">
          <div style="font-size:0.85rem; color:var(--text-muted);">Expected Balance</div>
          <div class="stat-num stat-pass" id="sc-exp-bal">Rs 0.00</div>
        </div>
        <div class="stat-box">
          <div style="font-size:0.85rem; color:var(--text-muted);">Observed Balance</div>
          <div class="stat-num" id="sc-obs-bal">Rs 0.00</div>
        </div>
        <div class="stat-box">
          <div style="font-size:0.85rem; color:var(--text-muted);">Money Created From Nothing</div>
          <div class="stat-num stat-fail" id="sc-diff-bal">Rs 0.00</div>
        </div>
      </div>

      <div id="money-counter-banner" class="counter-box" style="display:none;">
        <div style="color:var(--color-fail); font-weight:700; font-size:1.1rem; text-transform:uppercase;">Financial Breach Detected</div>
        <div id="money-counter-text" style="font-family:ui-monospace, monospace; font-size:2.5rem; font-weight:800; color:var(--color-fail); margin-top:0.5rem;">+Rs 500.00</div>
        <div id="money-counter-rule" style="color:var(--text-muted); font-size:0.9rem; margin-top:0.25rem;">Violates Rule R3: Event Idempotency</div>
      </div>

      <h3 style="margin-top:1.5rem;">Stream Steps</h3>
      <div id="sc-steps"></div>
    </div>
  </div>

  <script>
    const data = {data_json};
    let currentCandidate = "reference";
    let currentScenario = "duplicate_capture";

    const candSelect = document.getElementById("cand-select");
    const buttonsDiv = document.getElementById("scenario-buttons");

    // Populate candidate dropdown
    data.candidates.forEach(c => {{
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      candSelect.appendChild(opt);
    }});

    candSelect.addEventListener("change", (e) => {{
      currentCandidate = e.target.value;
      render();
    }});

    // Populate scenario buttons
    Object.keys(data.scenarios).forEach((sKey, idx) => {{
      const btn = document.createElement("button");
      btn.className = "scenario-btn" + (idx === 0 ? " active" : "");
      btn.textContent = data.scenarios[sKey].title;
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".scenario-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentScenario = sKey;
        render();
      }});
      buttonsDiv.appendChild(btn);
    }});

    function render() {{
      const scInfo = data.scenarios[currentScenario];
      const candData = (data.by_candidate[currentCandidate] || {{}})[currentScenario];

      document.getElementById("sc-title").textContent = scInfo.title + " (Target: Rule " + scInfo.rule + ")";
      document.getElementById("sc-expl").textContent = scInfo.explanation;

      if (!candData) {{
        document.getElementById("sc-verdict").textContent = "NO DATA";
        return;
      }}

      const verdictSpan = document.getElementById("sc-verdict");
      if (candData.verdict === "pass") {{
        verdictSpan.className = "badge badge-reference";
        verdictSpan.textContent = "PASS";
      }} else {{
        verdictSpan.className = "badge badge-mutant";
        verdictSpan.textContent = "FAIL";
      }}

      const diff = candData.ledger_diff || {{}};
      const expBal = (diff.expected_balance_paise || 0) / 100;
      const obsBal = (diff.observed_balance_paise || 0) / 100;
      const diffBal = (diff.balance_diff_paise || 0) / 100;

      document.getElementById("sc-exp-bal").textContent = "Rs " + expBal.toFixed(2);
      document.getElementById("sc-obs-bal").textContent = "Rs " + obsBal.toFixed(2);
      document.getElementById("sc-diff-bal").textContent = (diffBal > 0 ? "+" : "") + "Rs " + diffBal.toFixed(2);

      const counterBanner = document.getElementById("money-counter-banner");
      if (diffBal > 0) {{
        counterBanner.style.display = "block";
        document.getElementById("money-counter-text").textContent = "+Rs " + diffBal.toFixed(2);
        document.getElementById("money-counter-rule").textContent = diff.diff_summary;
      }} else {{
        counterBanner.style.display = "none";
      }}

      const stepsDiv = document.getElementById("sc-steps");
      stepsDiv.innerHTML = "";
      (candData.steps || []).forEach(st => {{
        const el = document.createElement("div");
        el.className = "timeline-step";
        el.innerHTML = "<strong>Step " + (st.step_index + 1) + "</strong> [" + st.tag + "] &rarr; Status: <code>" + st.observed_status + "</code> (Expected: <code>" + st.expected_status + "</code>)";
        if (st.has_violation) {{
          el.innerHTML += "<div style='color:var(--color-fail); margin-top:0.25rem;'>" + st.explanation + "</div>";
        }}
        stepsDiv.appendChild(el);
      }});
    }}

    render();
  </script>
</body>
</html>
"""


def build_reports(
    runs_dir: Path = Path("runs"),
    out_dir: Path = Path("report/out"),
) -> List[Path]:
    """Generate all static HTML reports into report/out/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_files: List[Path] = []

    # 1. Load runs
    run_files = sorted(runs_dir.glob("*.json"))
    runs: List[Dict[str, Any]] = []
    for rf in run_files:
        if rf.name in ("scenario_verdicts.json", "kill_matrix.json", "kill_matrix.sample.json"):
            continue
        try:
            r = json.loads(rf.read_text(encoding="utf-8"))
            if isinstance(r, dict) and "run_id" in r:
                runs.append(r)
                # Generate individual run page
                run_html = generate_run_html(r)
                out_path = out_dir / f"{r['run_id']}.html"
                out_path.write_text(run_html, encoding="utf-8")
                generated_files.append(out_path)
        except Exception:
            continue

    # 2. Generate index.html
    index_html = generate_index_html(runs, out_dir)
    index_file = out_dir / "index.html"
    index_file.write_text(index_html, encoding="utf-8")
    generated_files.append(index_file)

    # 3. Generate kill_matrix.html
    km_file = runs_dir / "kill_matrix.json"
    if not km_file.exists():
        km_file = runs_dir / "kill_matrix.sample.json"
    if km_file.exists():
        km_dict = json.loads(km_file.read_text(encoding="utf-8"))
        km_html = generate_kill_matrix_html(km_dict)
        km_out = out_dir / "kill_matrix.html"
        km_out.write_text(km_html, encoding="utf-8")
        generated_files.append(km_out)

    # 4. Generate scenarios.html
    sc_file = runs_dir / "scenario_verdicts.json"
    if sc_file.exists():
        sc_data = json.loads(sc_file.read_text(encoding="utf-8"))
        sc_html = generate_scenarios_html(sc_data)
        sc_out = out_dir / "scenarios.html"
        sc_out.write_text(sc_html, encoding="utf-8")
        generated_files.append(sc_out)

    return generated_files
