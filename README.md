# Faraday Industrial Benchmark

**[Explore the public benchmark website](https://www.faradaycompute.com/faraday-industrial-benchmark)** · [Benchmark card](BENCHMARK_CARD.md) · [JSONL protocol](docs/jsonl-protocol.md)

Faraday Industrial Benchmark is an executable public benchmark for AI agents
operating across the industrial enterprise: ERP finance and back office, supply
chain, manufacturing operations, quality, maintenance, planning, and engineering.

It measures whether an agent can investigate changing evidence, contain risk,
form a feasible response, obtain human authorization, execute permitted changes,
and leave an auditable trail. It does **not** reward manufacturing trivia or prose
that merely sounds plausible.

## v0.6: decisions under uncertainty

**Corrected execution candidate:** `0.14.0-close-execution.2` at
`data/close-execution-v2/tasks.json` fixes external-agent tool-schema parity,
accepts unordered exclusion reports without accepting wrong records, and balances
diagnostic weights by dimension. Strict end-to-end success remains primary.
Previous interrupted execution runs are not validated model comparisons.
The [four-model sample plan](docs/four-model-sample-plan.md) has a $100 total
authorization; provider/budget integration is unfinished and no sample has launched.
The reservation ledger is tested infrastructure, not a standalone spending guard.

**Stateful execution extension (in development):** [0.14.0-close-execution.1](docs/close-execution-workflows.md)
adds approval-bound sender, receiver and consolidation postings, partial-receipt
holds, lost-acknowledgement recovery, idempotent retries and live-ledger reconciliation.
Eight cases: `--tasks data/close-execution/tasks.json`. Historical interrupted
attempts exist; no validated completed-model result is claimed for this tier.

**Linked close-chain extension (in development):** [0.13.0-close-chain.2](docs/close-chain-workflows.md)
connects subcontracting recost to intercompany margin, partial-receipt valuation,
multi-entity journals, consolidation eliminations and the recovery reserve.
Eight fixed cases use `--tasks data/close-chain-v2/tasks.json`. The scoring contract
is public without solved business values. Model difficulty has
not been measured; historical scores must not be attributed to this candidate.

**Subcontracting workflow extension (in development):** [0.12.0-subcontracting.2](docs/subcontracting-workflows.md)
adds event-sourced corrections, reversals, ownership and quality controls across
four source systems. Corrected supply and valuation affect customer allocations,
freight, production, penalties and all final deliverables. Eight fixed cases cover
four distinct lifecycle sequences. Combined V1/V2 qualification passes 94 tests;
frontier-model difficulty is not yet measured. Use
`--tasks data/subcontracting-v2/tasks.json`.

**Joint-decision challenge (in development):** [0.11.0-decision.3](docs/decision-challenge.md)
adds irrevocable early releases coupled across eight disruption outcomes, on top
of shared labor, liquidity, kit and customer constraints. All eight reference
workflows pass; a hindsight-policy ablation is rejected on 8/8 cases. These are
algorithmic checks, not model results. Use `--tasks data/decision-challenge-v3/tasks.json`.
V3 publishes scoring deadlines and artifact schemas, validates shapes with field-level
errors, and accepts documented ledger annotations without relaxing business values.
See the [contract audit](docs/decision-contract-audit.md) for the scoring-contract
and validation methodology.

**Research-backed extension (in development):** [0.10.0-researched.3](docs/researched-workflows.md)
adds eight operating-review cases with receipt-cost propagation, mixed valuation,
supplier ownership and quarantine-state exceptions. Use `--tasks data/researched-v3/tasks.json`.
All eight reference workflows pass; 32 deliberately corrupted submissions are rejected.
These are grader checks, not model results. Earlier model attempts were excluded
after contract and revision-lifecycle audits. V3 exposes complete field schemas,
allows specified audit metadata, and supports correcting exception resolutions.
No GPT-5.4/GPT-5.5 difficulty ranking is established yet.

**Professional work samples (in development):** [claims-aware operating reviews](docs/professional-workflows.md)
add 24 multi-artifact cases with raw-claims/AP reconciliation and cross-deliverable
financial consistency. Run with `--tasks data/professional/tasks.json`.

**Cross-functional extension:** [0.8.0-workforce.1](docs/workforce-suite.md) adds
16 cases with eight disruption outcomes, shared certified-worker capacity and
ring-fenced treasury liquidity. Use `--tasks data/workforce/tasks.json`.

**Long-tail extension:** [0.7.0-tail.1](docs/long-tail-suite.md) adds 24 synthetic
cases with scenario-specific qualification bans, kit-split waivers, replacement
credits, carrier minimum loads and emergency tariffs. Use
`--tasks data/long-tail/tasks.json`. Earlier stopped runs are not difficulty evidence.

**New harder challenge:** [0.7.0-hard.1](docs/coupled-hard-suite.md) adds compound
disruptions, customer service floors, paired installation kits, nonlinear credits,
shared activation fees, and exact two-objective optimization. Run it explicitly
with `--tasks data/challenge/tasks.json`. Model difficulty is not yet measured.

Eight new contingent network-recovery episodes require one common capacity
reservation before the disruption is known, four feasible recovery branches,
and execution of the realized branch with a reconciled ledger. Ten whole orders
share inventory, supplier capacity, emissions, delivery windows, and a cash budget.
Strict success requires worst-case cost within 2% of an exact optimum.
Raw evidence includes duplicates, reversals, consignment, holds, cancelled orders,
provisional offers, blocked lanes, and changing commercial terms.

A nominal-only optimizer misses the tolerance on 29/32 development seeds, even
with optimal recourse. This is **not an LLM result**. GPT-5.4/5.5 difficulty remains
unmeasured. See [design and evaluation protocol](docs/contingent-recovery.md)
and [reproducible ablation](reports/contingent-ablation.json).

## What makes it different

- **Dynamic time:** every tool call consumes simulated time, and external events
  arrive while the agent works.
- **Executable state:** tool calls read and mutate a synthetic industrial company
  rather than a static question-answer record.
- **Evidence-gated authorization:** protected actions require the scenario's
  prerequisite reads, events, containment records, and a matching approval.
  Bypass attempts are fatal failures even when the intended outcome is useful.
- **Outcome grading:** deterministic checks cover system state, trace evidence,
  policy, communication, estimated incident cost, and tool efficiency.
- **Procedural variants:** task seeds generate distinct records, quantities,
  equipment, lots, routes, distribution nodes, financial amounts, and event
  outcomes for held-out evaluation.
- **Constrained decisions:** approval is necessary but insufficient. Execution
  rejects suboptimal routes, infeasible waves, overallocated network stock,
  incomplete recalls, unsupported export releases, and incorrect demand plans.
- **Provider neutral:** agents connect through a tiny JSONL protocol; no model SDK
  or hosted eval product is required.
- **Workflow-scoped contracts:** the catalog contains 67 typed tools, while each
  episode exposes only its relevant cross-system surface plus its exact public
  controlled-action and notification-role vocabulary. Every task also publishes
  a topological lifecycle DAG; composite tasks replace the common five-stage
  lifecycle with a deeper workflow-specific graph.
- **Tamper-evident replay:** each tool result records a canonical post-call state
  hash. Replay reconstructs the world, re-grades the outcome, and compares the
  submitted task, score, final answer, event list, and state commitments.

The v0.6 public development suite contains 74 episodes across 33 families. It
exposes 67 typed tools, 25 protected actions, 23 event types, and 2,864 deterministic
task criteria:

| Area | Families | What the agent must prove |
|---|---|---|
| Manufacturing and quality | Quality drift, machine failure, engineering change | Genealogy containment, safe recovery, controlled revision effectivity |
| Engineering documents | Drawing, assembly/BOM, revision, standards/specification, work-instruction drafting, P&ID, process capability, construction | Cross-document reconciliation, revision history, exact traceable findings, correction drafts, held sources, approved review publication |
| Supply chain and planning | Supplier delay, rush order, inventory mismatch | Feasible commitments, exact stock reconciliation, approved commercial action |
| Transportation | Transportation disruption | Lowest-cost capacity-confirmed routing inside the service promise |
| Warehousing and distribution | Warehouse wave, network allocation | Priority-constrained wave release and multi-DC allocation without overcommitment |
| Distribution quality | Cold-chain recall | Telemetry investigation, full genealogy containment, exact customer recall scope |
| Global trade | Trade compliance | Screening, license, document, hold, and release controls |
| Integrated planning | Demand–supply rebalance | Confirmed signals, supply-bucket reconciliation, and exact residual expedite |
| Enterprise orchestration | Supplier-quality recovery, recall-to-finance, engineering-to-production, order-to-cash disruption, plant-to-customer recovery | Public workflow DAGs, parallel diagnostic roots, convergence gates, expiring windows, up to four dependent approvals, and cross-domain state consistency |
| Frontier operating review | Integrated operating review | 11-file changing data room, 15 real-world exception resolutions, constrained portfolio allocation, exact reserve math, four mutually consistent deliverables, version citations, read-back, package approval, and controlled publication |
| Procure-to-pay | Invoice exception, vendor-master change | Three-way match, payment holds, fraud-resistant master-data control |
| Order-to-cash | Customer credit | Cash application, exposure recalculation, controlled order release |
| HCM and payroll | Payroll anomaly | Least-privilege access, manager evidence, exact pay correction |
| Record-to-report | Period close | Source-to-journal reconciliation and balanced posting |
| Project and asset accounting | Capital project | Commissioning evidence and exact capitalization |

This is broad core coverage, not a claim to represent every ERP module or every
industry configuration. It is also not yet a verified claim that Faraday is the
world's most complex industrial benchmark; that claim requires a dated,
reproducible comparison against every relevant release. The implemented
complexity dimensions and claim policy are documented in
[the workflow coverage matrix](docs/workflow-coverage.md).

## Quick start

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'

faraday-bench validate
faraday-bench list
faraday-bench qualify
faraday-bench difficulty --output reports/difficulty-profile.json
faraday-bench run --agent oracle --output runs/oracle.json --html runs/oracle.html
faraday-bench replay runs/oracle.json
faraday-bench stability --agent oracle --attempts 5 --output runs/stability.json
```

No model key is needed for the reference and negative-control runs.

## Connect an agent

Any executable that reads and writes newline-delimited JSON can be evaluated:

```bash
faraday-bench run \
  --agent-command "python examples/jsonl_read_only_agent.py" \
  --agent-name my-agent \
  --output runs/my-agent.json \
  --html runs/my-agent.html
```

The runner sends one `start` message containing the work request and tool
schemas scoped to that workflow. Public task metadata also supplies any exact
controlled-plan labels and canonical notification roles used by the executable
contract. The agent emits `tool_call` messages, receives `tool_result` messages,
and ends with `final`. See [the protocol](docs/jsonl-protocol.md).

### Reproducible OpenAI model runs

Install the optional adapter and provide a newly issued key through the process
environment (never commit or paste it into a prompt):

```bash
python3 -m pip install -e '.[openai]'
export OPENAI_API_KEY='your-new-key'

faraday-bench run \
  --task faraday-operating-review-001 \
  --agent-command "python examples/openai_responses_agent.py --model gpt-5.5 --reasoning-effort xhigh" \
  --agent-name gpt-5.5-xhigh \
  --timeout 1800 \
  --output runs/gpt-5.5-frontier.json
```

Use the same task manifest, adapter commit, prompt, reasoning effort, attempt
policy, and output-token budget for comparisons. `gpt-5.4` can be substituted as
the model identifier. No GPT-5.4 or GPT-5.5 score is claimed in this repository
until the checked-in run passes exact replay.

## Use the Faraday-Platform optimization harness

Export a seed-free harness contract containing the public suite identity,
workflow cases, score dimensions, and promotion rules:

```bash
faraday-bench export-harness --output runs/faraday-platform-harness.json
```

The contract deliberately excludes procedural seeds, evaluator criteria, event
queues, economic truth, and oracle traces. Its suite commitment binds every
public prompt, workflow stage, budget, role, action label, and tool-contract
digest. Faraday-Platform imports it, runs its agent through the same JSONL protocol, converts benchmark evidence into
capability and safety loss buckets, proposes a policy mutation, and requires a
fresh exact replay before promotion.

## Score

The headline score is 0–100:

```text
80 × passed deterministic criterion weight / available criterion weight
+ 10 × economic mitigation and timeliness
+ 10 × tool-call efficiency
```

Any critical authorization violation sets the entire episode score to zero.
`strict_success` additionally requires every task criterion, full economic credit,
an explicit final answer, and no critical violation. See [scoring](docs/scoring.md).
Every run also emits standardized per-family slice summaries so a high aggregate
cannot conceal a weak finance, manufacturing, logistics, or distribution domain.
Capability summaries expose cross-suite investigation, accuracy, planning,
governance, containment, communication, economics, and efficiency attainment.

`faraday-bench stability` repeats every selected task and reports strict-run,
any-attempt, all-attempt, critical-failure, mean-score, and variance metrics. This
separates dependable agents from agents that succeed once and fail on repetition.

The checked-in qualification controls establish evaluator range:

| Control | Mean | Strict | Critical |
|---|---:|---:|---:|
| Reference oracle | 100.00 | 74/74 | 0 |
| No-op | 10.30 | 0/74 | 0 |
| Read-only shortcut | 12.85 | 0/74 | 0 |
| Unauthorized write | 0.00 | 0/74 | 74 |

The oracle proves solvability; it is not an eligible model submission.

## Native and upstream benchmark tracks

Faraday now ships two deliberately separate kinds of evaluation artifact:

- **`faraday-native`** is the official 74-episode executable suite described
  above. Its code, scenarios, data, graders, and oracle trajectories were
  independently authored for Faraday.
- **Upstream compatibility tracks** are exact public snapshots of
  FactoryBench-100, Industrial Agent Benchmark, SupChain-Bench, and
  AssetOpsBench. They keep the upstream names, task IDs, runners, licenses,
  citations, and scoring rules. Their results must be reported separately and
  must never be pooled into a Faraday headline score.

List the full license decision log or verify all copied files:

```bash
faraday-bench upstreams
faraday-bench upstreams --verify
```

The upstream manifest also records benchmarks that were intentionally not
copied because their complete datasets are restricted, their terms are
noncommercial, their licensing is inconsistent, or no authoritative public
repository was available. See [third-party tracks](third_party/README.md) and
[notices](THIRD_PARTY_NOTICES.md).

## Generate a held-out suite

The public tasks are development examples. A credible leaderboard should use a
private manifest generated before model execution:

```bash
faraday-bench generate \
  --root-seed 20261001 \
  --per-family 50 \
  --split leaderboard-2026q4 \
  --output private/leaderboard-2026q4.json
```

The CLI prints a SHA-256 seed commitment. Publish that commitment before accepting
submissions, keep the manifest private, and reveal or rotate seeds after the round.

## Repository map

```text
data/public/                 public task descriptors
docs/                        architecture, scoring, protocol, and threat model
examples/                    external-agent protocol example
reports/                     reproducible qualification and oracle evidence
schemas/                     JSON schemas for tasks and run artifacts
src/faraday_industrial_benchmark/  world, scenarios, tools, grader, runner, and CLI
tests/                       determinism, safety, controls, replay, and protocol tests
third_party/                 pinned upstream snapshots, licenses, and integrity manifest
```

## Scope and safety

All Faraday-native companies, people, records, systems, transactions, and
incidents are synthetic. The native tool surface models common business
capabilities; it is not copied from a vendor API. Third-party compatibility
tracks retain their upstream provenance and limitations. The benchmark is not a
safety certification and must never be connected directly to physical equipment.
It tests digital operational decision workflows in isolated simulations.

Read the [benchmark card](BENCHMARK_CARD.md), [threat model](docs/threat-model.md),
[benchmark tracks](docs/benchmark-tracks.md), and [design lineage](docs/design-lineage.md)
before publishing results.
The [workflow coverage and complexity matrix](docs/workflow-coverage.md) records
the new engineering-document track, its inspiration boundary, and the evidence
required before making comparative superlative claims.
The [public benchmark pattern matrix](docs/research-landscape.md) records which
ideas are adopted, which sources are mirrored as compatibility tracks, which
remain roadmap items, and the Faraday-native originality boundary.

Faraday-native code is Apache-2.0 and authored task content is CC BY 4.0. Copied
upstream tracks retain their original terms; see `DATA_LICENSE` and
`THIRD_PARTY_NOTICES.md`.
