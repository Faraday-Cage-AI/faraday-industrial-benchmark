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

A replay-verified `gpt-4o` Faraday-Platform **v0.3** public-development run is
stored at `runs/faraday-platform-gpt4o-optimized-full.json`: 90.78 mean, 29/52
strict, zero critical failures, and 52/52 exact replay. It is a historical
optimization baseline, not a held-out result and not a v0.5 score. The expanded
v0.5 contract must be run separately.

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
