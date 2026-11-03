# Benchmark tracks

Faraday v0.8 defines one official full-suite score and seven diagnostic tracks.
Track scores are useful for analysis, but only the 249-task full-suite result is
eligible to be described as a complete Faraday v0.8 result. The full-suite score
is a plain mean over tasks, so Distributor Operations (175 of 249 tasks)
carries about 70% of it.

| Track | Families | Public tasks | Focus |
|---|---:|---:|---|
| Full Industrial Enterprise | 46 | 249 | Official aggregate across all domains |
| Core Operations and ERP | 12 | 24 | Manufacturing, maintenance, engineering, finance, HCM, and asset accounting |
| Advanced Supply and Distribution | 6 | 12 | Transportation, warehousing, allocation, recall, trade, and integrated planning |
| Engineering Document Workflows | 8 | 16 | Drawing, BOM, revision, specification, drafting, P&ID, capability, and construction review |
| Composite Enterprise Orchestration | 6 | 14 | Supplier-quality, recall-to-finance, engineering-to-production, credit-to-fulfillment, plant-to-customer-to-finance, and integrated operating-review chains |
| Frontier Professional Work Sample | 1 | 4 | Changing 11-file data room, 15 exception resolutions, portfolio optimization, four reconciled artifacts, and controlled publication |
| Contingent Network Recovery | 1 | 8 | Common pre-revelation capacity commitments, four recourse branches, and minimax cost grading |
| Distributor Operations | 13 | 175 | Buy-to-fulfill, order intake, shipment, receivables, pricing, replenishment, receiving/AP, channel sync, and distributor work products |

The frontier track is a subset of the composite track.

## Distributor Operations

Distributor Operations is part of the headline `faraday-native` suite, not an
upstream compatibility track. Its 13 families are native Faraday rebuilds of
tasks selected from three public benchmarks. Each family is registered through
`src/faraday_industrial_benchmark/extensions.py`, implemented in
`src/faraday_industrial_benchmark/distributor/`, and has an IndustrialWorld
builder, typed tools, sealed deterministic criteria, and a reference oracle.
Fixtures are produced by `examples/import_distributor_sources.py` from pinned
upstream snapshots, with per-file SHA-256 provenance in
`data/distributor-sources/<source>/provenance.json`.

| Source | Families | Tasks | What the agent does |
|---|---|---:|---|
| ERP-Bench (`ceba3880`, CC0) | `distributor_buy_to_fulfill` | 82 (42 medium, 40 hard) | Screen customer requests, buy finished goods within supplier min/max, price tiers, and lead times, invoice per policy, and repair plans after supplier cancellations with minimal change |
| ERPBench-100 by Blobfish AI (`5bdf4581`, data CC BY 4.0) | `distributor_order_import`, `distributor_shipment_verification`, `distributor_receivables_collection`, `distributor_price_list_batch`, `distributor_inventory_reorder`, `distributor_receiving_ap_match`, `distributor_channel_order_sync` | 70 (10 each) | Work from versioned evidence case files, including superseded and trap versions, and commit ERP writes through protected actions with approval |
| GDPval (`11e7900c`, no license declared) | `distributor_sales_analytics`, `distributor_pricing_quotation`, `distributor_inventory_planning`, `distributor_warehouse_shipping`, `distributor_policy_documents` | 23 | Submit structured artifacts that cite case files |

Grading follows each source's intent:

- ERP-Bench: ports the upstream feasibility rules, scores optimality against the
  solver's optimal plan, and checks minimal change on repair tasks. Protected
  actions are `confirm_sales_order`, `confirm_purchase_order`,
  `cancel_purchase_order`, and `post_customer_invoice`. Upstream checks that
  apply only to manufacturing are not ported.
- ERPBench-100: maps the 100-point ERPScore rubric to criteria for discovery,
  calculation, decision, committed state, register and handoff, readback, and
  containment.
- GDPval: 1,032 of 1,189 rubric items are scored mechanically. The other 157
  (presentation, file format, narrative, and similar) are recorded but not
  scored. Web-research inputs are frozen into case files, and upstream
  prompt/reference inconsistencies in tasks 017, 019, 022, and 023 were
  corrected and recorded in grader notes.

Distributor fixtures are fixed per task. Held-out generation for these families
reuses the template scenario with a new seed rather than creating new
distributor instances. CRMArena-Pro was excluded because of its noncommercial
license.
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
not additional Faraday task families; the Distributor Operations families above
are native rebuilds and are not part of this list. Run each with its original harness and
scorer, report its upstream version and commit, and publish its result in a
separate table. A pooled score would mix incompatible units, policies, task
distributions, and grading contracts and is therefore prohibited.

Use `faraday-bench upstreams --verify` before evaluation. The authoritative list,
license scope, exclusions, and content hashes are in
[`../third_party/manifest.json`](../third_party/manifest.json).
