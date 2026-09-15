# Benchmark card

## Intended use

Faraday Industrial Benchmark v0.6 evaluates tool-using AI systems on synthetic
industrial-enterprise workflows. It supports development comparisons, regression
testing, agent design, cost/quality experiments, and post-training reward signals.

## Unit of evaluation

An episode begins with an employee-style request and seeded enterprise state. The
agent receives only the request and typed tools. Tool calls advance logical time;
scheduled external events may change evidence or close decision windows. The
episode ends at `finish`, at the tool budget, or at the time horizon.

## Coverage

- Thirty-three scenario families and 74 public development episodes
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

All `faraday-native` data is generated from independently authored scenario
code. There are no customer records, copied ERP screens, vendor payloads,
proprietary manuals, or real people. Public task seeds are included for exact
reproduction. Hosted test operators should keep held-out seeds private and
publish a pre-run commitment.

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
- Sixty-six public episodes are a development suite, not statistically sufficient for
  a high-stakes model ranking.
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
