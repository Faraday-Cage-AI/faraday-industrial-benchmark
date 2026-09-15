const metrics = [
  ["62", "executable episodes"],
  ["31", "workflow families"],
  ["61", "typed tools"],
  ["974", "deterministic criteria"],
];

export default function Home() {
  return (
    <main>
      <nav className="nav-shell" aria-label="Primary navigation">
        <a className="wordmark" href="#top" aria-label="Faraday home">
          <span className="mark" aria-hidden="true">F</span>
          <span>FARADAY</span>
          <span className="wordmark-tag">INDUSTRIAL BENCHMARK</span>
        </a>
        <div className="nav-links">
          <a href="#benchmark">Benchmark</a>
          <a href="#compare">Compare</a>
          <a href="#run">Run it</a>
        </div>
        <a className="button button-small" href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark">View on GitHub</a>
      </nav>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="status-dot" /> Public development suite · v0.4</p>
          <h1>Can your agent run the industrial enterprise?</h1>
          <p className="hero-lede">
            A dynamic, executable benchmark for the work between the factory floor and the back office—across ERP, MES, QMS, SCM, WMS, TMS, PLM, CMMS, and finance.
          </p>
          <div className="hero-actions">
            <a className="button" href="#run">Run the benchmark <span aria-hidden="true">→</span></a>
            <a className="text-link" href="#compare">See how it compares <span aria-hidden="true">↓</span></a>
          </div>
        </div>

        <div className="workflow-card" aria-label="Example benchmark workflow">
          <div className="terminal-bar">
            <span>PLANT RECOVERY / LIVE EPISODE</span>
            <span className="terminal-clock">T+46 MIN</span>
          </div>
          <div className="workflow-grid">
            <div className="rail rail-quality">
              <span className="rail-label">QUALITY</span>
              <div className="node complete"><b>01</b><span>Trace suspect lots</span><em>verified</em></div>
              <div className="node complete"><b>02</b><span>Contain production</span><em>2 holds</em></div>
            </div>
            <div className="rail rail-maintenance">
              <span className="rail-label">MAINTENANCE</span>
              <div className="node complete"><b>03</b><span>Diagnose line failure</span><em>bearing</em></div>
              <div className="node complete"><b>04</b><span>Qualify alternate line</span><em>ready</em></div>
            </div>
            <div className="convergence"><span>CONVERGENCE GATE</span><strong>Evidence aligned</strong></div>
            <div className="flow-line">
              <div className="flow-step active"><span>MES</span>Reschedule</div>
              <i aria-hidden="true">→</i>
              <div className="flow-step"><span>WMS</span>Release</div>
              <i aria-hidden="true">→</i>
              <div className="flow-step"><span>TMS</span>Reroute</div>
              <i aria-hidden="true">→</i>
              <div className="flow-step"><span>ERP</span>Post</div>
            </div>
          </div>
          <div className="card-footer"><span><i className="pulse" /> Dynamic event received</span><span>state hash 8821e4…d63</span></div>
        </div>
      </section>

      <section className="metric-strip" aria-label="Benchmark size">
        {metrics.map(([value, label]) => (
          <div className="metric" key={label}><strong>{value}</strong><span>{label}</span></div>
        ))}
        <div className="metric metric-wide"><strong>22</strong><span>protected actions where bypass = zero</span></div>
      </section>

      <section className="section verdict-section" id="benchmark">
        <div className="section-kicker">01 / DIFFICULTY</div>
        <div className="section-heading">
          <h2>A different kind of hard.</h2>
          <p>Faraday is built to punish plausible-looking answers that fail in the actual workflow.</p>
        </div>
        <div className="verdict-layout">
          <div className="verdict-statement">
            <span className="verdict-label">Our evidence-backed verdict</span>
            <h3>Frontier-tier for governed, cross-enterprise execution. Not yet the largest benchmark—and we do not claim “world’s hardest.”</h3>
            <p>
              Compared with static knowledge and reasoning sets, Faraday is materially more demanding at the interaction level: the agent must change a living enterprise state without crossing authorization boundaries. FactoryBench-100 is larger and more artifact-rich. AssetOpsBench is deeper in industrial time-series and multi-agent maintenance. Faraday’s distinctive challenge is the breadth and sequencing of governed workflows from plant incident to customer and ledger.
            </p>
          </div>
          <div className="difficulty-stack" aria-label="Faraday difficulty dimensions">
            {[
              ["Cross-system breadth", "31 families", "96%"],
              ["State + time pressure", "92 events", "91%"],
              ["Governance pressure", "22 protected actions", "94%"],
              ["Artifact perception", "structured facts today", "48%"],
            ].map(([label, value, width]) => (
              <div className="difficulty-row" key={label}>
                <div><span>{label}</span><strong>{value}</strong></div>
                <div className="difficulty-track"><i style={{ width }} /></div>
              </div>
            ))}
            <p className="chart-note">Visual profile, not a normalized cross-benchmark score.</p>
          </div>
        </div>
      </section>

      <section className="section comparison-section" id="compare">
        <div className="section-kicker">02 / LANDSCAPE AUDIT</div>
        <div className="section-heading comparison-heading">
          <h2>Complexity, without the chest-beating.</h2>
          <p>Published surface comparison · audited September 14, 2026</p>
        </div>
        <div className="comparison-table" role="table" aria-label="Industrial benchmark comparison">
          <div className="comparison-row comparison-header" role="row">
            <span role="columnheader">Benchmark</span><span role="columnheader">Public scale</span><span role="columnheader">Executable state</span><span role="columnheader">Governed writes</span><span role="columnheader">Distinctive strength</span>
          </div>
          <div className="comparison-row faraday-row" role="row">
            <span role="cell"><b>Faraday v0.4</b><em>this project</em></span><span role="cell">62 episodes<br/>31 families · 61 tools</span><span role="cell"><i className="yes">YES</i> dynamic events + time</span><span role="cell"><i className="yes">YES</i> approval + payload gates</span><span role="cell">Plant-to-ledger recovery with deterministic state, trace, and policy grading</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://github.com/blobfishai/factory-agent-simulation" target="_blank" rel="noreferrer"><b>FactoryBench-100 ↗</b></a><em>v3.3.5</em></span><span role="cell">100 workflows<br/>20 families · 94 tools</span><span role="cell"><i className="yes">YES</i> isolated SQLite worlds</span><span role="cell"><i className="yes">YES</i> mutation + readback</span><span role="cell">Largest artifact-grounded ERP surface here: 2,800 files and 100 unique graphs</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://github.com/masahirosakae/industrial-agent-benchmark" target="_blank" rel="noreferrer"><b>Industrial Agent ↗</b></a><em>v2.2.0</em></span><span role="cell">180 tasks<br/>3 evaluation layers</span><span role="cell"><i className="no">NO</i> response dataset</span><span role="cell"><i className="no">NO</i> planned judge</span><span role="cell">Broad Japanese manufacturing knowledge, reasoning, and agent-design coverage</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://aclanthology.org/2026.findings-acl.371/" target="_blank" rel="noreferrer"><b>SupChain-Bench ↗</b></a><em>ACL 2026</em></span><span role="cell">100 tool-use prompts<br/>8 tools</span><span role="cell"><i className="partial">READ</i> 3-tier order graph</span><span role="cell"><i className="no">NO</i> no enterprise writes</span><span role="cell">SOP-grounded and SOP-free long-horizon supply-chain orchestration</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://github.com/IBM/AssetOpsBench" target="_blank" rel="noreferrer"><b>AssetOpsBench ↗</b></a><em>KDD 2026</em></span><span role="cell">141+ scenarios<br/>5 domain agents</span><span role="cell"><i className="partial">MIXED</i> live industrial data</span><span role="cell"><i className="partial">MIXED</i> work-order writes</span><span role="cell">Time-series models, vibration, MCP specialists, and multi-agent orchestration</span>
          </div>
        </div>
        <p className="audit-note">Counts and capabilities come from each project’s public release documentation. This is a structural audit—not a claim that scores transfer across benchmarks.</p>
      </section>

      <section className="section systems-section">
        <div className="section-kicker">03 / COVERAGE</div>
        <div className="section-heading">
          <h2>One company. Every consequential handoff.</h2>
          <p>The benchmark connects the operational systems that industrial agents are usually tested on in isolation.</p>
        </div>
        <div className="systems-grid">
          {[
            ["ERP · FINANCE", "AP, AR, GL, close, vendor master, payroll, project and asset accounting", "7 families"],
            ["MES · APS", "Production work, constrained rescheduling, effectivity, capacity and promises", "5 families"],
            ["QMS · PLM", "Genealogy, containment, CAPA-shaped evidence, drawings, BOMs and revisions", "11 families"],
            ["SCM · PROCUREMENT", "Supplier delays, supply buckets, expedites, allocations and trade controls", "6 families"],
            ["WMS · DISTRIBUTION", "Verified stock, wave feasibility, cold chain, recall scope and network allocation", "6 families"],
            ["TMS · CRM", "Carrier capacity, route economics, customer commitments and controlled notifications", "5 families"],
            ["CMMS · HISTORIAN", "Equipment evidence, failure isolation, maintenance orders and recovery gates", "3 families"],
            ["ENGINEERING DOCS", "Structured drawing, P&ID, construction, requirements and controlled review", "8 families"],
          ].map(([name, desc, count], index) => (
            <article className="system-card" key={name}>
              <span className="system-index">0{index + 1}</span><h3>{name}</h3><p>{desc}</p><em>{count}</em>
            </article>
          ))}
        </div>
        <p className="coverage-note">Families overlap systems; counts are not additive.</p>
      </section>

      <section className="section workflow-section">
        <div className="section-kicker light">04 / LONG-HORIZON WORK</div>
        <div className="section-heading light-heading">
          <h2>Thirteen stages. Four approvals. One customer promise.</h2>
          <p>The flagship plant-to-customer recovery begins with two parallel investigations and ends only when physical recovery and financial truth agree.</p>
        </div>
        <div className="stage-map" aria-label="Plant fulfillment recovery stage map">
          <div className="stage-roots">
            <div className="stage-box"><span>01–02</span><b>Quality branch</b><em>Trace → contain</em></div>
            <div className="stage-box"><span>03–04</span><b>Maintenance branch</b><em>Diagnose → qualify</em></div>
          </div>
          <div className="stage-connector"><span>parallel evidence converges</span></div>
          <div className="stage-box stage-gate"><span>05</span><b>Convergence gate</b><em>Both branches must be complete</em></div>
          <div className="stage-chain">
            {[["06–07","MES / APS","Reschedule before deadline"],["08–09","WMS","Verify and release wave"],["10–11","TMS","Choose feasible route"],["12–13","ERP / GL","Reconcile and post reserve"]].map(([n,s,d]) => <div className="stage-box" key={n}><span>{n}</span><b>{s}</b><em>{d}</em></div>)}
          </div>
        </div>
        <div className="workflow-facts">
          <span><strong>2</strong> parallel roots</span><span><strong>4</strong> protected decisions</span><span><strong>8</strong> notified roles</span><span><strong>1</strong> tamper-evident final state</span>
        </div>
      </section>

      <section className="section constitution-section">
        <div className="section-kicker">05 / EVALUATION CONSTITUTION</div>
        <div className="section-heading">
          <h2>Correct means more than “sounds right.”</h2>
        </div>
        <div className="principle-grid">
          <article><span>STATE</span><h3>The world must actually change.</h3><p>Tools read and mutate a synthetic industrial company. The grader checks the resulting records, not just the final paragraph.</p></article>
          <article><span>GOVERNANCE</span><h3>Approval is necessary, not sufficient.</h3><p>Evidence must be fresh, the requested payload exact, and every upstream gate complete. A bypass zeros the episode.</p></article>
          <article><span>REPLAY</span><h3>The trace has to survive reconstruction.</h3><p>Every result commits a state hash. Replay rebuilds the world and compares tasks, events, answers, scores, and final state.</p></article>
          <article><span>TIME</span><h3>Every investigation has a cost.</h3><p>Calls advance logical time. Supplier replies arrive, trucks close, routes fail, and production windows expire while the agent works.</p></article>
          <article><span>OUTCOMES</span><h3>Business feasibility is executable.</h3><p>Overallocated stock, incomplete recalls, infeasible waves, wrong journals, and expensive-but-avoidable routes are rejected.</p></article>
          <article><span>VARIATION</span><h3>Public examples are not the test.</h3><p>Procedural seeds vary records and outcomes. Private manifests can be committed before a leaderboard round and revealed later.</p></article>
        </div>
      </section>

      <section className="section controls-section">
        <div className="section-kicker">06 / QUALIFICATION</div>
        <div className="section-heading">
          <h2>The grader separates safe completion from shortcuts.</h2>
          <p>Checked-in deterministic controls prove solvability and evaluator range across all 62 public episodes.</p>
        </div>
        <div className="control-layout">
          <div className="control-chart">
            {[["Reference oracle","100.00","100%","62 / 62 strict"],["Read-only shortcut","13.38","13.38%","0 / 62 strict"],["No-op","10.35","10.35%","0 / 62 strict"],["Unauthorized write","0.00","0%","62 critical failures"]].map(([label,score,width,note]) => (
              <div className="control-row" key={label}>
                <div><b>{label}</b><em>{note}</em></div><div className="control-bar"><i style={{ width }} /></div><strong>{score}</strong>
              </div>
            ))}
          </div>
          <aside className="score-card"><span>HEADLINE SCORE</span><strong>0–100</strong><p><b>80</b> deterministic state + trace criteria</p><p><b>10</b> economic mitigation + timeliness</p><p><b>10</b> tool-call efficiency</p><small>Any critical authorization violation forces the episode to zero.</small></aside>
        </div>
      </section>

      <section className="section run-section" id="run">
        <div className="run-copy">
          <div className="section-kicker light">07 / RUN IT</div>
          <h2>Provider-neutral by design.</h2>
          <p>Connect any agent that reads and writes newline-delimited JSON. No hosted eval product—and no model key for the qualification controls.</p>
          <div className="run-links">
            <a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark" className="button button-acid">Open the repository <span>↗</span></a>
            <a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark/blob/main/docs/jsonl-protocol.md" className="run-text-link">Read the JSONL protocol →</a>
          </div>
        </div>
        <div className="code-window" aria-label="Quickstart commands">
          <div className="code-title"><span>QUICKSTART.SH</span><span>PYTHON 3.11+</span></div>
          <pre><code><span className="code-dim"># install the public benchmark</span>{`\n`}python3 -m venv .venv{`\n`}source .venv/bin/activate{`\n`}pip install -e <b>&apos;.[dev]&apos;</b>{`\n\n`}<span className="code-dim"># validate, qualify, and run</span>{`\n`}faraday-bench validate{`\n`}faraday-bench qualify{`\n`}faraday-bench run --agent <b>oracle</b>{`\n\n`}<span className="code-dim"># reconstruct and verify the trace</span>{`\n`}faraday-bench replay runs/oracle.json</code></pre>
        </div>
      </section>

      <section className="section lineage-section">
        <div className="section-kicker">08 / OPEN BY CONSTRUCTION</div>
        <div className="lineage-layout">
          <h2>Study the field.<br/>Preserve the lineage.<br/>Build clean-room.</h2>
          <div className="lineage-copy">
            <p>Faraday-native tasks, systems, values, graders, and trajectories are independently authored and synthetic. License-compatible snapshots of four upstream projects ship as separate compatibility tracks; their scores never enter Faraday’s headline result.</p>
            <div className="license-row"><span>CODE</span><b>Apache-2.0</b><span>NATIVE DATA</span><b>CC BY 4.0</b><span>UPSTREAMS</span><b>Original terms retained</b></div>
            <p className="source-note">The engineering-document taxonomy is informed by the public workflow categories published by <a href="https://www.manufacturingintelligence.org/use-cases/" target="_blank" rel="noreferrer">Manufacturing Intelligence ↗</a>. It is not a copied dataset.</p>
          </div>
        </div>
      </section>

      <section className="final-cta">
        <p>THE FACTORY FLOOR IS ONLY HALF THE TEST.</p>
        <h2>Benchmark the whole industrial enterprise.</h2>
        <a className="button button-large" href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark">Run Faraday <span>↗</span></a>
      </section>

      <footer>
        <a className="wordmark footer-wordmark" href="#top"><span className="mark">F</span><span>FARADAY</span></a>
        <p>Industrial Benchmark · v0.4 public development suite</p>
        <div><a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark">GitHub ↗</a><a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark/blob/main/BENCHMARK_CARD.md">Benchmark card ↗</a></div>
      </footer>
    </main>
  );
}
