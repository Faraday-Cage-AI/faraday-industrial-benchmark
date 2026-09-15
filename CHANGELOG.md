# Changelog

## Unreleased

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
