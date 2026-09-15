---
pretty_name: Faraday Industrial Benchmark
license: cc-by-4.0
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

Faraday Industrial Benchmark v0.5 is a 66-episode public development suite across
32 plant-operations, ERP back-office, supply-chain, logistics, distribution, and
engineering-document families. The JSON task descriptors are only the
entry point: authoritative state, time-dependent events, typed tools, policy,
and grading execute in the open-source Python environment.

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
- `workflow_stages`: public dependency DAG; focused tasks use the shared lifecycle
  and composite tasks provide workflow-specific graphs

## Use

Install the repository package and use `faraday-bench run`. Static dataset loaders
cannot execute the benchmark or reproduce its scores because grading depends on
state transitions and the complete tool trace.

## Licensing and limitations

Faraday-native task content is CC BY 4.0 and native code is Apache-2.0. All
Faraday-native records are synthetic. Separately namespaced upstream snapshots
retain their own licenses and are not part of this dataset card or Faraday's
headline score. This is not a plant-safety certification and must not be
connected to physical equipment. See `BENCHMARK_CARD.md` for intended use,
exclusions, provenance, and reporting requirements.
