# Benchmark tracks

Faraday v0.5 defines one official full-suite score and five diagnostic tracks.
Track scores are useful for analysis, but only the 66-task full-suite result is
eligible to be described as a complete Faraday v0.5 result.

| Track | Families | Public tasks | Focus |
|---|---:|---:|---|
| Full Industrial Enterprise | 32 | 66 | Official aggregate across all domains |
| Core Operations and ERP | 12 | 24 | Manufacturing, maintenance, engineering, finance, HCM, and asset accounting |
| Advanced Supply and Distribution | 6 | 12 | Transportation, warehousing, allocation, recall, trade, and integrated planning |
| Engineering Document Workflows | 8 | 16 | Drawing, BOM, revision, specification, drafting, P&ID, capability, and construction review |
| Composite Enterprise Orchestration | 6 | 14 | Supplier-quality, recall-to-finance, engineering-to-production, credit-to-fulfillment, plant-to-customer-to-finance, and integrated operating-review chains |
| Frontier Professional Work Sample | 1 | 4 | Changing 11-file data room, 15 exception resolutions, portfolio optimization, four reconciled artifacts, and controlled publication |

## Complexity dimensions

The advanced track is designed around interacting constraints rather than longer
prompts. Episodes combine several of the following:

- evidence that changes after the episode starts;
- source records distributed across three or more simulated systems;
- stale or incomplete data that must not be treated as authoritative;
- scarce inventory, capacity, labor, time, or service-level constraints;
- exact calculations and structured plans;
- reversible containment before irreversible action;
- approvals that are evidence-gated but do not legitimize an incorrect payload;
- downstream notifications and tamper-evident state replay.
- public workflow-stage DAGs with enforced predecessor execution;
- up to four independently approved writes in one episode, including parallel
  roots, convergence gates, and expiring predecessor windows;
- cross-document fact reconciliation with requirement-to-source traceability;
- exact finding-set and correction-draft contracts that remain binding even
  after a human approval is granted.
- plausible superseded, late, withdrawn, unqualified, provisional, and
  compliance-held records that must be dispositioned explicitly;
- field-level grading over four mutually consistent deliverables, with exact
  file-section-version citations and read-back before packaging;
- 15 separately persisted real-world exception resolutions spanning quality,
  inventory, production, supplier, customer, transport, finance, and governance.

## Reporting rules

Publish the benchmark version, task coverage, agent and model versions, attempt
policy, tool schema, aggregate score, per-family summaries, strict-success rate,
critical failures, tool calls, cost, latency, and exceptions. Never compare a
track score with a full-suite score without labeling the coverage difference.

Held-out rounds should generate multiple seeds per family, publish the seed
commitment before execution, and report uncertainty across those seeds.

## Upstream compatibility tracks

The repository also vendors pinned copies of FactoryBench-100, Industrial Agent
Benchmark, SupChain-Bench, and AssetOpsBench. These are independent benchmarks,
not additional Faraday task families. Run each with its original harness and
scorer, report its upstream version and commit, and publish its result in a
separate table. A pooled score would mix incompatible units, policies, task
distributions, and grading contracts and is therefore prohibited.

Use `faraday-bench upstreams --verify` before evaluation. The authoritative list,
license scope, exclusions, and content hashes are in
[`../third_party/manifest.json`](../third_party/manifest.json).
