# Changelog

## 0.8.0 — 2026-11-03

- Closed PR review findings: restrict citations to explicit record registries,
  validate draft orders atomically, share authoritative failure replay with the
  viewer, and invalidate viewer caches for recursive source/fixture edits.
- Added viewer check/test/build CI and patched the website's production
  dependencies to pass its existing vulnerability audit.
- Corrected fabricated final citation credit and required record evidence in every
  workflow; published scoring time/call thresholds via `get_incident`.
- Bound replay to aggregate totals, exact coverage and frozen source/task/tool
  inputs; preserved protocol rejections, failures and full trace metadata.
- Fixed partial-line timeout/cancellation hangs, malformed payload mutation and
  repeated inventory allocation; added independent adversarial review.
- Corrected Net 30/60 cash timing to explicit calendar invoice dates and rejected
  excess/duplicate AP holds and unnecessary quality containment.
- Added a source-archived, fail-closed evidence-bundle command. Historical results
  remain intact and are not comparable with the corrected contract.
- Documented sealed-answer distributor references and missing historical raw model
  artifacts; no current learned-model ranking is claimed.

## 0.7.0 — 2026-11-02

- Added 175 Distributor Operations tasks in 13 families to the headline public
  suite, which now contains 249 tasks in 46 families. The headline score remains
  a plain mean over tasks, so distributor tasks carry about 70% of it.
- Added native Faraday rebuilds of tasks from three pinned public benchmarks:
  82 ERP-Bench buy-to-fulfill and supplier-cancellation repair tasks (CC0), 70
  ERPBench-100 tasks across seven families (data CC BY 4.0, "ERPBench-100 by
  Blobfish AI", changes made), and 23 GDPval work-product tasks across five
  families. CRMArena-Pro was excluded because of its noncommercial license.
- Added `examples/import_distributor_sources.py`, which builds fixtures from
  pinned upstream snapshots, writes the per-source manifests, and syncs the
  distributor tail of `data/public/tasks.json`. Each source records per-file
  SHA-256 provenance in `data/distributor-sources/<source>/provenance.json`.
- Added an extension registry (`extensions.py`) so families outside
  `scenarios.py` can register builders, tools, protected actions, evaluator
  checks, event kinds, reference trajectories, and negative-control probes
  without editing the core world, grader, tool catalog, or agents. Extension
  protected actions are scoped to the families that declare them.
- Added an optional `efficiency_target` hook for extension families.
- The platform harness contract now commits to each extension family's full
  served tool specs and counts extension tools: 108 tools (67 core and 41
  distributor).
- Added the 13 distributor families to the task schema `family` enum and bumped
  the benchmark, harness, qualification, and generation defaults to 0.7.0.
- Updated `NOTICE`, `DATA_LICENSE`, and `THIRD_PARTY_NOTICES.md` for the
  distributor sources. GDPval expected deliverables and rubrics are grader-only
  reference material and are not covered by `DATA_LICENSE`.
- Qualified v0.7.0 on all 249 tasks at oracle 100.00/249 strict with no critical
  failures, no-op 10.76, read-only 11.75, and unauthorized-write 0.00 with 249
  critical failures; the oracle run replays exactly over 6,782 tool calls. The
  structural profile reports 8,155 criteria (from 2,864) and 174 tasks with
  explicit workflow-stage graphs (from 22).
- Known limitations: distributor held-out generation reuses the template
  scenario with a new seed, 157 of 1,189 GDPval rubric items are recorded but not
  scored, and published model results were measured on v0.6.0 and have not been
  re-run.
- Regenerated the release reports (difficulty profile, qualification, oracle run
  and replay) and the platform harness export for v0.7.0.

## Unreleased

- Added the v0.5 frontier operating-review track: four 15-stage professional
  work samples across ERP, MES, QMS, SCM, WMS, TMS, CRM, and GRC.
- Added an 11-file, 26-section versioned data room with four independently timed
  source revisions, a superseded distractor, exact source precedence, and
  file-section-version citations.
- Added 15 evidence-backed real-world exception resolutions per frontier task,
  covering quality scope, document precedence, inventory double-counting,
  constrained supply, line qualification, supplier certification, contract
  revisions, withdrawn/late/customs-held routes, shared capacity, reserve
  offsets, penalties, rounding, and approval dependencies.
- Added four mutually consistent structured deliverables, artifact read-back,
  controlled packaging, protected publication, and 415–419 field-level criteria
  per frontier episode. Exact schemas and exception vocabulary are public while
  instance values and evaluator contracts remain sealed.
- Added `faraday-bench difficulty` and a checked-in structural profile. v0.5 now
  contains 66 tasks, 32 families, 67 tools, 23 protected actions, 23 event types,
  108 scheduled events, 398 workflow nodes, and 2,648 criteria.
- Qualified v0.5 at oracle 100.00/66 strict, no-op 10.33, read-only 13.19, and
  unauthorized-write 0.00 with 66 critical failures.

## 0.4.0 — 2026-09-14

- Expanded the public development suite to v0.4: 62 tasks, 31 families, 61
  tools, 22 protected actions, 22 event types, 92 scheduled event instances,
  and 974 deterministic criteria.
- Added four two-episode composite enterprise families: supplier-quality to
  production recovery, recall to financial reserve, engineering review to
  production effectivity, and credit to warehouse to transportation recovery.
- Added a two-episode plant-to-customer mega-workflow with independent quality
  and maintenance roots, a convergence gate, an expiring production-completion
  window, and a four-approval production-to-wave-to-route-to-reserve chain.
- Published workflow-stage DAGs for all 62 tasks: a common five-stage lifecycle
  for focused episodes and 78 workflow-specific nodes across the ten composite
  tasks. Added deterministic composite audit-sequence grading plus an
  `orchestration` capability slice.
- Added chained approval gates that require named upstream protected actions to
  have executed before downstream decisions can be approved.
- Enforced family tool scopes during execution and replay, made out-of-scope
  protected writes fatal, bound execution payloads immutably to approvals, and
  validated plan/review lineage at protected-action time.
- Made efficiency scoring stage-aware for composite workflows, strengthened the
  task and platform-harness JSON schemas, and isolated smoke optimization output
  from measured policy artifacts.
- Extended exact replay to re-grade reconstructed worlds and compare task,
  score, final-answer, event, and state commitments rather than trusting
  uploaded outcome fields.
- Qualified v0.4 at oracle 100.00/62 strict, no-op 10.35, read-only 13.38, and
  unauthorized-write 0.00 with 62 critical failures; exact oracle replay passes
  all 62 episodes.

## 0.3.0 — 2026-09-14

- Made the exact plan-action and notification-role vocabulary for
  `faraday-quality-001` discoverable in the public task prompt, eliminating a
  hidden lexical-guessing requirement while preserving the executable workflow.
- Published the 22 protected-action values as JSON Schema enums, documented the
  approval-decision contract, and committed the complete public tool
  contract into the exported harness digest.
- Added public `controlled_plan_actions` to every task graded on exact
  free-text plan labels, with a contract test that prevents hidden vocabulary
  from reappearing.
- Added public workflow-family tool scopes and committed them into the tool
  contract hash, replacing the unrealistic all-61-tools surface with the
  relevant cross-system capabilities for each episode.
- Added event-driven waiting, public canonical notification-role contracts,
  and the exact controlled-document draft shape; removed an inapplicable cycle
  count capability from network allocation.
- Made approval responses reflect decisions already applied during request
  latency, normalized engineering draft types, and added immediate validation
  for public plan-action and notification-role contracts.
- Added a seed-free `faraday-platform-harness/1` export contract and CLI command
  for harness-driven Faraday-Platform agent optimization.
- Fixed the external JSONL runner so a protocol agent that calls the `finish`
  tool and then emits `final` does not create a duplicate finish trace.

- Expanded `faraday-native` to v0.3 with 52 tasks across 26 families, 61 tools,
  22 protected actions, 21 event types, and 696 deterministic criteria.
- Added eight executable engineering-document families: drawing, assembly/BOM,
  revision, standards/specification, manufacturing-document drafting, P&ID,
  process capability, and construction-document review.
- Added authoritative mid-episode source revisions, document holds, traceable
  findings, exact correction drafts, review packages, and approval-backed
  publication that cannot override an invalid finding/draft contract.
- Added a public workflow coverage and complexity matrix plus an explicit policy
  against unsupported "most complex" claims.

- Added isolated, pinned public snapshots of FactoryBench-100, Industrial Agent
  Benchmark, SupChain-Bench, and AssetOpsBench with their shipped code and data.
- Added a machine-readable license/provenance manifest, deterministic whole-tree
  integrity hashes, preserved notices, and `faraday-bench upstreams --verify`.
- Explicitly excluded restricted, noncommercial, ambiguously licensed, private,
  and unavailable upstream artifacts from the distributable benchmark.
- Kept upstream compatibility scores separate from the `faraday-native` official
  score and clarified native-versus-third-party claims throughout the docs.

## 0.2.0 — 2026-09-14

- Added six advanced supply-chain and distribution families and twelve public tasks.
- Added transportation recovery, constrained warehouse waves, multi-DC allocation, cold-chain recall, global-trade controls, and demand–supply rebalancing.
- Expanded the benchmark to 36 tasks, 18 families, 54 tools, 21 protected actions, 20 event types, and 376 deterministic criteria.
- Added exact constrained-decision validation: approval does not make a suboptimal route, infeasible wave, incomplete recall, or overcommitted allocation valid.
- Added logistics event simulation, structured distribution plans, and adversarial world tests.
- Added per-capability benchmark summaries and a repeated-trial stability command with a formal JSON schema.
- Added a source-attributed clean-room pattern matrix covering executable enterprise, supply-chain, manufacturing, asset-operations, finance, and maintenance benchmarks.

## 0.1.0 — 2026-09-14

- Added twelve dynamic industrial-enterprise families and 24 public tasks.
- Added ERP back-office coverage for AP, AR/credit, vendor master, payroll, period close, and capital projects/fixed assets.
- Added evidence-gated approvals, exact-record grading, and auditable sequence checks.
- Added deterministic logical time, scheduled and agent-triggered events.
- Added typed read, containment, planning, approval, execution, messaging, and wait tools.
- Added state, trace, policy, economic, timeliness, and efficiency grading.
- Added fatal authorization-bypass handling.
- Added seeded held-out task generation and commitment hashes.
- Added provider-neutral JSONL agent protocol.
- Added exact trace replay, JSON artifacts, and static HTML reports.
- Qualified reference, no-op, read-only, and unauthorized-write controls.
