---
pretty_name: Faraday Industrial Benchmark
license: other
license_name: mixed-per-source
license_link: DATA_LICENSE
language:
  - en
task_categories:
  - reinforcement-learning
  - question-answering
tags:
  - agents
  - manufacturing
  - supply-chain
  - distribution
  - logistics
  - erp
  - mes
  - deterministic-evaluation
  - tool-use
size_categories:
  - n<1K
---

# Faraday Industrial Benchmark

Faraday Industrial Benchmark v0.8.0 is a 249-episode public development suite
across 46 plant-operations, ERP back-office, supply-chain, logistics,
distribution, engineering-document, and distributor-operations families. The
JSON task descriptors are only the entry point: authoritative state,
time-dependent events, typed tools, policy, and grading execute in the
open-source Python environment.

## Composition

| Group | Families | Episodes |
|---|---:|---:|
| Core operations and ERP | 12 | 24 |
| Advanced supply and distribution | 6 | 12 |
| Engineering-document workflows | 8 | 16 |
| Composite enterprise orchestration, including the frontier operating review | 6 | 14 |
| Contingent network recovery | 1 | 8 |
| Distributor Operations | 13 | 175 |

The headline score is a plain mean over all 249 episodes, so Distributor
Operations carries about 70% of it. The `data/distributor-erp-bench/`,
`data/distributor-erpbench100/`, and `data/distributor-gdpval/` manifests are
per-source subsets of `data/public/tasks.json`, not additional episodes.

## Fields

- `id`: stable public task identifier
- `version`: benchmark task version
- `family`: procedural scenario builder
- `title`, `prompt`: agent-visible employee request
- `seed`: public development seed; hosted rounds should keep seeds private
- `difficulty`: qualitative development label
- `systems`: simulated source-system concepts
- `max_tool_calls`, `horizon_minutes`: episode budgets
- `tags`: retrieval and analysis metadata
- `controlled_plan_actions`: exact public vocabulary for graded free-text plans
- `workflow_stages`: evaluator-side dependency DAG, withheld from the agent;
  focused tasks use the shared lifecycle and composite tasks provide
  workflow-specific graphs

## Use

Install the repository package and use `faraday-bench run`. Static dataset loaders
cannot execute the benchmark or reproduce its scores because grading depends on
state transitions and the complete tool trace.

## Licensing and limitations

Faraday-authored task content is CC BY 4.0 and native code is Apache-2.0.
Faraday-authored records are synthetic. The Distributor Operations families are native Faraday
rebuilds of tasks selected from pinned public snapshots and keep their upstream
terms: ERP-Bench material (82 episodes) is CC0-1.0; ERPBench-100 material
(70 episodes, "ERPBench-100 by Blobfish AI", changes made) is CC BY 4.0; GDPval
material (23 episodes) has no declared license, and its expected deliverables
and rubrics are grader-only reference material not covered by `DATA_LICENSE`.
Per-file SHA-256 provenance is in
`data/distributor-sources/<source>/provenance.json`; see `NOTICE` and
`THIRD_PARTY_NOTICES.md`.

Distributor fixtures are fixed per task, so held-out generation for those
families reuses the template scenario with a new seed. Of 1,189 GDPval rubric
items, 157 subjective items are recorded but not scored. Separately namespaced
upstream snapshots under `third_party/` retain their own licenses and are not
part of this dataset card or Faraday's headline score. This is not a
plant-safety certification and must not be connected to physical equipment. See
`BENCHMARK_CARD.md` for intended use, exclusions, provenance, and reporting
requirements.
