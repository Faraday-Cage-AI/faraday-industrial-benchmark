const metrics = [
  ["249", "public episodes"],
  ["46", "workflow families"],
  ["108", "typed tools"],
  ["8,259", "deterministic criteria"],
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
          <p className="eyebrow"><span className="status-dot" /> Public development suite · v0.8.0</p>
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
            <span>PLANT RECOVERY / ILLUSTRATION</span>
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
        <div className="metric metric-wide"><strong>175</strong><span>fixed distributor episodes · about 70% of the mean</span></div>
      </section>

      <section className="section verdict-section" id="benchmark">
        <div className="section-kicker">01 / EVALUATION SCOPE</div>
        <div className="section-heading">
          <h2>Industrial workflows with observable outcomes.</h2>
          <p>Faraday checks what an agent reads, changes, and verifies in a synthetic enterprise.</p>
        </div>
        <div className="verdict-layout">
          <div className="verdict-statement">
            <span className="verdict-label">What the evidence supports</span>
            <h3>A broad executable development suite. Current full-suite model results remain unmeasured.</h3>
            <p>
              Agents investigate records, follow modeled approval policies, and execute changes across connected systems. Distributor reference trajectories use sealed fixture plans or answers; their success establishes execution consistency, not independent derivation from public evidence. No learned agent has a validated full-suite result on v0.8.0. Historical model measurements use earlier versions and cannot be presented as current scores.
            </p>
          </div>
          <div className="difficulty-stack" aria-label="Current benchmark composition">
            {[
              ["Workflow coverage", "46 families"],
              ["Tool contract", "108 typed tools"],
              ["Core episodes", "74 public tasks"],
              ["Distributor episodes", "175 fixed tasks"],
            ].map(([label, value]) => (
              <div className="difficulty-row" key={label}>
                <div><span>{label}</span><strong>{value}</strong></div>
              </div>
            ))}
            <p className="chart-note">Counts describe suite composition. They are not measured difficulty scores or a cross-benchmark ranking.</p>
          </div>
        </div>
      </section>

      <section className="section comparison-section" id="compare">
        <div className="section-kicker">02 / HISTORICAL LANDSCAPE</div>
        <div className="section-heading comparison-heading">
          <h2>A dated view of the field.</h2>
          <p>Historical September 14, 2026 snapshot · Faraday v0.5 · not a present-day ranking</p>
        </div>
        <div className="comparison-table" role="table" aria-label="Historical September 14, 2026 benchmark comparison">
          <div className="comparison-row comparison-header" role="row">
            <span role="columnheader">Benchmark</span><span role="columnheader">Public scale</span><span role="columnheader">Executable state</span><span role="columnheader">Governed writes</span><span role="columnheader">Distinctive strength</span>
          </div>
          <div className="comparison-row faraday-row" role="row">
            <span role="cell"><b>Faraday v0.5</b><em>historical version</em></span><span role="cell">66 episodes<br/>32 families · 67 tools</span><span role="cell"><i className="yes">YES</i> dynamic events + time</span><span role="cell"><i className="yes">YES</i> approval + payload gates</span><span role="cell">Plant-to-ledger recovery plus a 15-exception, four-artifact frontier operating review</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://arxiv.org/abs/2604.11304" target="_blank" rel="noreferrer"><b>BankerToolBench ↗</b></a><em>2026</em></span><span role="cell">100 work samples<br/>~150 rubric criteria / task</span><span role="cell"><i className="partial">FILES</i> office-document workspace</span><span role="cell"><i className="partial">RUBRIC</i> expert client-readiness</span><span role="cell">Long-form banking deliverables across spreadsheets, slides, documents, and PDFs</span>
          </div>
          <div className="comparison-row" role="row">
            <span role="cell"><a href="https://github.com/blobfishai/factory-agent-simulation" target="_blank" rel="noreferrer"><b>FactoryBench-100 ↗</b></a><em>v3.3.5</em></span><span role="cell">100 workflows<br/>20 families · 94 tools</span><span role="cell"><i className="yes">YES</i> isolated SQLite worlds</span><span role="cell"><i className="yes">YES</i> mutation + readback</span><span role="cell">Artifact-grounded ERP workflows: 2,800 files and 100 unique graphs in the audited release</span>
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
        <p className="audit-note">This archived comparison reflects the cited releases as reviewed on September 14, 2026. Faraday v0.5 counts are preserved for that snapshot; current v0.8.0 has 249 episodes, 46 families, and 108 tools. Other projects may have changed. These structural descriptions do not establish comparative model performance.</p>
      </section>

      <section className="section systems-section">
        <div className="section-kicker">03 / COVERAGE</div>
        <div className="section-heading">
          <h2>Connected systems and selected industrial workflows.</h2>
          <p>The suite models handoffs across operational systems. Its 46 families do not establish exhaustive industrial coverage.</p>
        </div>
        <div className="systems-grid">
          {[
            ["ERP · FINANCE", "AP, AR, GL, close, vendor master, payroll, project and asset accounting"],
            ["MES · APS", "Production work, constrained rescheduling, effectivity, capacity and promises"],
            ["QMS · PLM", "Genealogy, containment, CAPA-shaped evidence, drawings, BOMs and revisions"],
            ["SCM · PROCUREMENT", "Supplier delays, supply buckets, expedites, allocations and trade controls"],
            ["WMS · DISTRIBUTION", "Verified stock, wave feasibility, cold chain, recall scope and network allocation"],
            ["TMS · CRM", "Carrier capacity, route economics, customer commitments and controlled notifications"],
            ["CMMS · HISTORIAN", "Equipment evidence, failure isolation, maintenance orders and recovery gates"],
            ["ENGINEERING DOCS", "Structured drawing, P&ID, construction, requirements and controlled review"],
          ].map(([name, desc], index) => (
            <article className="system-card" key={name}>
              <span className="system-index">0{index + 1}</span><h3>{name}</h3><p>{desc}</p>
            </article>
          ))}
        </div>
        <p className="coverage-note">Coverage labels overlap. Engineering tasks use structured synthetic facts; native PDF perception, CAD geometry, and BIM coordination are outside the measured scope.</p>
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
          <article><span>GOVERNANCE</span><h3>Approval is necessary, not sufficient.</h3><p>Protected writes require matching approval. Scenario-specific checks evaluate evidence, payloads, and prerequisites. An authorization bypass zeros the episode.</p></article>
          <article><span>REPLAY</span><h3>The trace has to survive reconstruction.</h3><p>Every result commits a state hash. Replay rebuilds the world and compares tasks, events, answers, scores, and final state.</p></article>
          <article><span>TIME</span><h3>Every investigation has a cost.</h3><p>Calls advance logical time. Supplier replies arrive, trucks close, routes fail, and production windows expire while the agent works.</p></article>
          <article><span>OUTCOMES</span><h3>Business feasibility is executable.</h3><p>Scenario checks evaluate stock allocation, recall scope, wave feasibility, financial records, and route choices against explicit modeled constraints.</p></article>
          <article><span>VARIATION</span><h3>Variation depends on the family.</h3><p>Core families support procedural variants. The 175 distributor episodes reuse fixed fixtures under new seeds; those seeds do not create independent business instances. Distributor tasks contribute about 70% of the plain task mean.</p></article>
        </div>
      </section>

      <section className="section controls-section">
        <div className="section-kicker">06 / QUALIFICATION</div>
        <div className="section-heading">
          <h2>The grader separates safe completion from shortcuts.</h2>
          <p>Reference and negative controls test fixture execution, authorization boundaries, and grader behavior. Their results do not establish model difficulty, generalization, or real-world safety.</p>
        </div>
        <div className="control-layout">
          <div className="control-chart">
            <p className="chart-note">Historical v0.5 controls · 66 episodes. These scores are not current v0.8.0 results.</p>
            {[["Reference oracle","100.00","100%","66 / 66 strict"],["Read-only shortcut","13.19","13.19%","0 / 66 strict"],["No-op","10.33","10.33%","0 / 66 strict"],["Unauthorized write","0.00","0%","66 critical failures"]].map(([label,score,width,note]) => (
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
          <pre><code><span className="code-dim"># install the public benchmark</span>{`\n`}python3 -m venv .venv{`\n`}source .venv/bin/activate{`\n`}pip install -e <b>&apos;.[dev]&apos;</b>{`\n\n`}<span className="code-dim"># validate, qualify, and run</span>{`\n`}faraday-bench validate{`\n`}faraday-bench qualify{`\n`}faraday-bench run --agent <b>oracle</b> --output runs/oracle.json{`\n\n`}<span className="code-dim"># reconstruct and verify the trace</span>{`\n`}faraday-bench replay runs/oracle.json</code></pre>
        </div>
      </section>

      <section className="section lineage-section">
        <div className="section-kicker">08 / OPEN BY CONSTRUCTION</div>
        <div className="lineage-layout">
          <h2>Study the field.<br/>Preserve the lineage.<br/>Document the sources.</h2>
          <div className="lineage-copy">
            <p>The suite combines independently authored synthetic workflows with 175 distributor rebuilds derived from pinned ERP-Bench, ERPBench-100, and GDPval sources. GDPval has no declared license and is included under a documented owner-approved exception; source terms remain in force. Four other upstream snapshots ship as separate compatibility tracks whose scores are excluded from the headline result.</p>
            <div className="license-row"><span>CODE</span><b>Apache-2.0</b><span>NATIVE DATA</span><b>CC BY 4.0</b><span>UPSTREAMS</span><b>Original terms retained</b></div>
            <p className="source-note">The engineering-document taxonomy is informed by the public workflow categories published by <a href="https://www.manufacturingintelligence.org/use-cases/" target="_blank" rel="noreferrer">Manufacturing Intelligence ↗</a>. It is not a copied dataset.</p>
          </div>
        </div>
      </section>

      <section className="final-cta">
        <p>THE FACTORY FLOOR IS ONLY HALF THE TEST.</p>
        <h2>Evaluate agents across industrial workflows.</h2>
        <a className="button button-large" href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark">Run Faraday <span>↗</span></a>
      </section>

      <footer>
        <a className="wordmark footer-wordmark" href="#top"><span className="mark">F</span><span>FARADAY</span></a>
        <p>Industrial Benchmark · v0.8.0 public development suite</p>
        <div><a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark">GitHub ↗</a><a href="https://github.com/Faraday-Cage-AI/faraday-industrial-benchmark/blob/main/BENCHMARK_CARD.md">Benchmark card ↗</a></div>
      </footer>
    </main>
  );
}
