# Benchmark card

## Intended use

Faraday Industrial Benchmark v0.7 evaluates tool-using AI systems on synthetic
industrial-enterprise workflows. It supports development comparisons, regression
testing, agent design, cost/quality experiments, and post-training reward signals.

## Unit of evaluation

An episode begins with an employee-style request and seeded enterprise state. The
agent receives only the request and typed tools. Tool calls advance logical time;
scheduled external events may change evidence or close decision windows. The
episode ends at `finish`, at the tool budget, or at the time horizon.

## Coverage

- Forty-six scenario families and 249 public development episodes; the headline
  score is a plain mean over all 249, so the 175 Distributor Operations episodes
  carry about 70% of it
- 108 typed tools in the platform harness contract: 67 core and 41 distributor
- Transportation, carrier routing, warehouse waves, multi-DC allocation, cold-chain recall, global trade, and integrated demand–supply planning
- ERP AP, AR, GL, vendor master, payroll, project accounting, and fixed assets
- MES, QMS, WMS, APS, PLM, CMMS, historian, procurement, supplier, and customer-service concepts
- Read, reconciliation, containment, proposal, approval, protected write, notification, and wait operations
- Missing, stale, conflicting, pending, and newly arriving evidence
- Controlled drawing, assembly/BOM, revision, requirements, work-instruction,
  P&ID, process-capability, and construction-document review workflows
- Exact requirement-to-finding traceability, correction drafts, document holds,
  evidence-gated approval, and protected publication to human engineering review
- Six composite enterprise families with public dependency graphs, parallel
  diagnostic branches, convergence and deadline gates, up to four chained
  approvals, and cross-domain end-state checks
- Four frontier operating-review episodes with an 11-file versioned data room,
  four independently authored source revisions, 15 evidence-backed exception
  dispositions, four mutually consistent artifacts, exact version citations,
  artifact read-back, and controlled package publication
- Thirteen Distributor Operations families (175 episodes): buy-to-fulfill with
  supplier min/max, price tiers, lead times, invoicing policies, and
  supplier-cancellation repair; order import, shipment verification,
  receivables collection, price-list batches, inventory reorder, receiving/AP
  match, and channel order sync over versioned evidence case files with
  superseded and trap versions; and structured work products for sales
  analytics, pricing and quotation, inventory planning, warehouse shipping, and
  policy documents

### Optional development tracks

These manifests are separate contracts, not extra cases silently pooled into the
249-episode default score. Fixed-seed variants within a family are correlated.

| Manifest | Episodes | Added requirements |
|---|---:|---|
| `data/challenge/tasks.json` | 8 | Coupled recourse, customer floors, paired kits and nonlinear costs |
| `data/long-tail/tasks.json` | 24 | Qualification overrides, kit waivers, replacement credits and carrier constraints |
| `data/workforce/tasks.json` | 16 | Certified labor and protected treasury liquidity across eight outcomes |
| `data/professional/tasks.json` | 24 | Claims and AP reconciliation with mutually consistent operating-review artifacts |
| `data/researched-v3/tasks.json` | 8 | Receipt-cost propagation, ownership, mixed valuation and quarantine availability |
| `data/decision-challenge-v3/tasks.json` | 8 | Irrevocable early releases jointly optimized with supplier reservations and eight recourse branches; explicit scoring and artifact contracts |
| `data/subcontracting-v2/tasks.json` | 8 | Distributed event-sourced subcontracting corrections and four lifecycle variants feeding production, commitments and reserve; not model-measured |
| `data/close-chain-v2/tasks.json` | 8 | Subcontracting recost linked to partial intercompany receipts, entity journals, internal-profit elimination and reserve reclassification; public scoring contract; not model-measured |
| `data/close-execution/tasks.json` | 8 | Stateful sender/receiver/consolidation execution; historical interrupted attempts, no validated completed-model result |
| `data/close-execution-v2/tasks.json` | 8 | Corrected external-agent schema, order-independent exclusion reports and dimension-balanced diagnostics; no paid measurement yet |

The decision challenge is a separate 0.11.0-decision.3 development tier, currently
with completed matched measurement after [contract qualification](docs/decision-contract-audit.md)
and 302 passing regression tests. All 16 attempts replay exactly; strict successes
are 3/8 for GPT-5.4 and 6/8 for GPT-5.5. See [limitations and objective gaps](reports/decision-v3-results.md)
before interpreting these as capability differences. Its
constraints are disclosed, feasible policies may be executed even when suboptimal,
and all exact objective ties are accepted. A first pilot hit a response-token
limit; this is not evidence of an incorrect business decision. The completed
decision-v3 comparison above is separate from those earlier pilots. Do not pool
versions or inference budgets.
The v1 background pilot found optimal plans for both models; its lower GPT-5.5
score arose from report annotations, not incorrect planning. V2 addresses those
formatting deductions without changing the business constraints or objectives.
See [design, sources and measurement protocol](docs/decision-challenge.md).

The researched v3 comparison uses GPT-5.4 and GPT-5.5 with matched inference
settings, 300 tool calls, and a 600-minute simulated review horizon. It is a
tool-only structured-deliverable track, not an evaluation of native spreadsheet
authoring. Earlier manifests (`data/researched/tasks.json` and `data/researched-v2/tasks.json`)
are retained for provenance but excluded from capability claims after contract-clarity
and revision-lifecycle audits. V3 discloses complete nested schemas, accepts specified
audit annotations, and supersedes corrected exception resolutions without deleting history.
See [sources, qualification controls and protocol](docs/researched-workflows.md).

## Exclusions

The v0.6 contingent-recovery track adds eight episodes with common pre-revelation
capacity commitments, four constrained recourse branches, and exact minimax cost
grading within a 2% tolerance. See [the protocol](docs/contingent-recovery.md).
No GPT-5.4 or GPT-5.5 result is claimed for this version.

The benchmark does not claim exhaustive ERP coverage and does not test tax filing,
benefits administration, statutory consolidation, warehouse slotting, street-level
vehicle routing, PLC programming, direct machine control, robotics,
cybersecurity, worker surveillance, autonomous safety shutdowns, or compliance
certification. The v0.5 engineering-document and operating-review tracks operate on structured
synthetic document facts; it does not yet evaluate native CAD geometry, STEP,
BIM/IFC, scanned drawings, OCR, or pixel-level symbol detection. It is not
representative of every plant, geography, industry,
vendor implementation, labor practice, or regulatory regime.

## Data and provenance

All `faraday-native` data outside the Distributor Operations families is
generated from independently authored scenario code. There are no customer
records, copied ERP screens, vendor payloads, proprietary manuals, or real
people. Public task seeds are included for exact reproduction. Hosted test
operators should keep held-out seeds private and publish a pre-run commitment.

The Distributor Operations families are native Faraday rebuilds of tasks
selected from three public benchmarks, with Faraday world builders, tools,
sealed deterministic criteria, and reference oracles. Their fixtures are produced
by `examples/import_distributor_sources.py` from pinned upstream snapshots, and
each source records per-file SHA-256 provenance in
`data/distributor-sources/<source>/provenance.json`:

| Source | Pinned revision | License | Tasks |
|---|---|---|---:|
| ERP-Bench (agentic-labs/erp-bench) | `ceba3880af555129b5278e056a0c20f2fb5a0ba9` | CC0-1.0 | 82 |
| ERPBench-100 by Blobfish AI (blobfishai/erp-agent-simulation) | `5bdf458165fee71f6a7965ea30ca33dfbbce1332` | Code Apache-2.0, data CC BY 4.0; changes made | 70 |
| GDPval (openai/gdpval) | `11e7900cdcac61bc4daf59e65feb238acda98fbf` | None declared | 23 |

GDPval expected deliverables and rubrics are committed as grader-only reference
material. They are not covered by `DATA_LICENSE`; see `NOTICE` and
`THIRD_PARTY_NOTICES.md`. CRMArena-Pro was considered and excluded because of
its noncommercial license. The per-source manifests in
`data/distributor-erp-bench/`, `data/distributor-erpbench100/`, and
`data/distributor-gdpval/` are subsets of `data/public/tasks.json`, not
additional episodes.

The repository also contains separately namespaced upstream compatibility
snapshots. Those artifacts retain their original benchmark identity, license,
citation, task IDs, and scoring rules. They are excluded from the official
Faraday score. The commit and byte-level provenance is recorded in
`third_party/manifest.json`.

## Grading

Primary checks are deterministic and inspect state plus the full tool trace.
The evaluator does not grade hidden chain-of-thought. A task-specific weighted
contract contributes 80 points; economics and timeliness contribute 10; efficiency
contributes 10. Critical authorization bypass attempts force a zero.
Official run artifacts include family and capability slices. Optional stability
runs measure repeatability over multiple attempts per task rather than reporting
only the best attempt.

## Known limitations

- Economic amounts are synthetic and useful for relative scoring, not ROI claims.
- The reference agent uses a family-specific playbook and is not a learned baseline.
- 249 public episodes are a development suite, not statistically sufficient for
  a high-stakes model ranking. The 175 distributor episodes dominate the plain
  mean, and the 82 ERP-Bench episodes alone are a third of it.
- Distributor fixtures are fixed per task. Held-out generation for those
  families reuses the template scenario with a new seed; it does not create new
  distributor instances.
- Of 1,189 GDPval rubric items, 1,032 are scored mechanically. The other 157
  (presentation, file format, narrative quality, and similar) are recorded but
  not scored. Upstream prompt/reference inconsistencies in GDPval tasks 017,
  019, 022, and 023 were corrected and recorded in grader notes.
- ERP-Bench checks that apply only to manufacturing are not ported.
- Published model results were measured on v0.6.0 (74 tasks) and have not been
  re-run on v0.7.0.
- Procedural variants do not yet vary the dependency topology within a family.
- Deterministic checks can miss semantically poor explanations that achieve correct state.
- Simulation cannot establish safety in a real plant.
- No "most complex" or "best" claim is established without a dated comparative
  audit using the published dimensions in `docs/workflow-coverage.md`.
- Structural workload gates and oracle solvability do not establish that any
  named frontier model struggles; that requires a dated, reproducible model run.

## Recommended reporting

Report the exact benchmark version, agent/model version, prompt or policy hash,
tool schemas, inference settings, attempt policy, hardware/provider, per-task
score, strict-success rate, critical-failure rate, cost, latency, and exceptions.
Do not compare partial-suite runs with full-suite runs as if they were equivalent.
Do not report an upstream compatibility-track result as a Faraday-native result,
and do not pool scores across benchmark contracts.
