---
pretty_name: Industrial Agent Benchmark
language:
  - ja
  - en
license: apache-2.0
task_categories:
  - question-answering
  - text-generation
tags:
  - manufacturing
  - industrial-ai
  - industrial-agent
  - agent-evaluation
  - llm-evaluation
  - benchmark
size_categories:
  - n<1K
---

# Industrial Agent Benchmark v2.2.0

## Overview

Industrial Agent Benchmark is a public benchmark dataset for evaluating Industrial AI systems, Manufacturing AI assistants, and Industrial Agents.

**v2.2.0 is the Japanese Canonical Normalization release.** Japanese is now the canonical language of the benchmark. English should be treated as a future translated or derivative distribution, not as the source of truth.

v2.2.0 preserves the 180-task dataset composition and validation/export pipeline while migrating previously English-only tasks to Japanese canonical form.

## v2.2.0 Release Note

- Japanese Canonical Normalization completed.
- Previously English-only tasks migrated to Japanese canonical form.
- English-only tasks: 45 -> 0.
- Total tasks retained: 180.
- Layer balance retained: Knowledge 60 / Reasoning 60 / Agent 60.
- HF-compatible JSONL workflow preserved.
- No generated answers, private results, or provider-specific evaluation outputs are included.

Note: some machine-readable schema keys, enum-like final states, numeric check names, JSON field names, and accepted technical abbreviations may remain in English for evaluation compatibility.

## Dataset Structure

Primary files:

```text
data/v2/test.jsonl
docs/dataset_schema_v2.md
docs/dataset_export_v2.md
```

Each record is a single benchmark task with public reference material and a public rubric. Records do not contain generated model answers or model-specific evaluation results.

## Dataset Summary

| Layer | Count | Focus |
|---|---:|---|
| Knowledge | 60 | Manufacturing facts, procedures, constraints, governance, and reference-answer correctness |
| Reasoning | 60 | Root-cause analysis, risk tradeoffs, data integrity, CAPA, FMEA, and numeric capacity planning |
| Agent | 60 | Workflow design, tool use, human approval boundaries, safety, structured decisions, and auditability |
| Total | 180 | Balanced public benchmark split |

Category distribution:

| Layer | Category | Count |
|---|---|---:|
| Knowledge | `change_control` | 10 |
| Knowledge | `maintenance_engineering` | 10 |
| Knowledge | `improvement`, `manufacturing_execution`, `manufacturing_preparation`, `order`, `procurement`, `production_planning`, `quality`, `shipping` | 5 each |
| Reasoning | `data_integrity`, `numeric_capacity_planning`, `risk_tradeoff` | 10 each |
| Reasoning | `5why`, `abnormality_analysis`, `capa`, `fmea`, `fta`, `quality_improvement` | 5 each |
| Agent | `human_in_the_loop` | 13 |
| Agent | `workflow_design` | 14 |
| Agent | `agent_safety`, `hil_boundary`, `structured_decision`, `tool_trajectory` | 5 each |
| Agent | `agent_design` | 4 |
| Agent | `mcp`, `multi_agent_coordination`, `tool_selection` | 3 each |

## Task Format

Items are prompt-style benchmark records. A model or agent receives `context` and `question`, then produces a text or structured answer. Public `answer` and `rubric` fields are included for evaluation development and reproducibility.

## Splits

| Split | Status | Description |
|---|---|---|
| `test` | Public | Public benchmark tasks |

The v2.2.0 release uses the public `test` split with 180 records.

## Schema

Every record uses stable keys:

```json
{
  "id": "IA-HILB-001",
  "version": "2.0.0",
  "domain": "manufacturing",
  "category": "agent",
  "sub_category": "hil_boundary",
  "task_type": "case_analysis",
  "question": "...",
  "context": "...",
  "choices": [],
  "answer": "...",
  "rubric": "...",
  "expected_capabilities": [],
  "difficulty": "hard",
  "tags": [],
  "source": "synthetic",
  "public": true,
  "requires_external_knowledge": false,
  "notes": ""
}
```

The record-level `version` field is the **JSONL schema version** (currently `2.0.0`), not the benchmark release version. The record schema has not changed since v2.0.0, so this value is unchanged. The current public release version is **v2.2.0**. See `docs/versioning_policy.md` for the version identifier taxonomy.

## Intended Use

- Evaluate industrial and manufacturing agent capabilities.
- Develop public evaluation harnesses and judge workflows.
- Test handling of manufacturing constraints, approval boundaries, evidence traceability, and structured reasoning.
- Support local, reproducible benchmark experimentation without committing generated answers or run artifacts.

## Limitations

- The dataset is synthetic and should not be treated as operational manufacturing advice.
- The benchmark is not a certification benchmark.
- It does not cover all manufacturing domains, sectors, product types, or factory systems.
- English translation pairs are not yet the source of truth; English is planned as a derivative distribution.
- Machine-readable schema and evaluation compatibility fields may remain in English.

## Evaluation

**Evaluation status: the scoring utilities in this repository are placeholder / experimental. No official judge is implemented yet.** The current scorer (`rule_based_token_overlap_v2`) exists to validate pipeline file formats; it tokenizes ASCII words plus Japanese character bigrams, so pipeline validation works on the Japanese-canonical data, but its scores measure surface token overlap only and are not benchmark results. The Deterministic / Rubric / Executable Judge architecture is planned; see `docs/evaluation_architecture_v2.md`.

### Baseline Evaluation Status

An initial public benchmark baseline (6 models, all 180 tasks) is planned under a frozen research protocol; see `docs/baseline_experiment_plan_v1.md`, `docs/contamination_policy_v1.md`, and `docs/judge_validation_plan_v1.md` in the GitHub repository. Initial public benchmark baseline results are research artifacts, not an official leaderboard. The baseline report will be published in two stages: an initial report before human validation of the LLM judge, and a revised report after judge validation.

For official baseline runs only, `docs/public_artifact_policy_v1.md` (Section 3) permits publishing reproducibility metadata — official model IDs, providers, execution dates, snapshots, dataset and configuration hashes, decoding profile settings, and aggregated scores — while raw answers, judge texts, credentials, and the anonymization mapping remain private. Provider terms of service and model licenses take precedence where they restrict publication.

Contamination status:

> Industrial Agent Benchmark v2.2.0 was publicly accessible but had not been formally announced or promoted when the initial baseline protocol was initiated. We therefore consider contamination risk to be low but not provably absent. Results on the public 180-task set are reported as a diagnostic baseline on publicly available tasks, not as evidence of contamination-free generalization.

(日本語) Industrial Agent Benchmark v2.2.0 は、初期ベースラインプロトコル開始時点で公開状態にあったが、正式な告知・広報は行われておらず、実際の利用を示す証拠も確認されていない。したがって汚染リスクは「低いが、皆無とは証明できない」と位置付ける。公開180問での結果は「公開済み問題集合における診断的ベースライン」として報告し、汚染のない汎化性能の証拠としては主張しない。

The GitHub repository provides validation and evaluation scripts:

- `scripts/validate_dataset.py` (stable, data validation)
- `scripts/export_hf_dataset_v2.py` (stable, JSONL export)
- `scripts/validate_hf_dataset_v2.py` (stable, JSONL validation)
- `eval/run_simple_eval.py` (placeholder scoring pipeline, all 180 tasks)
- `eval/run_judge_eval.py` (placeholder scoring pipeline, all 180 tasks)
- `scripts/eval_v2_*` (experimental LLM-judge pipeline for the 30-task `evaluation_set_v2.yaml` subset; external APIs opt-in)

Example validation:

```bash
python scripts/validate_dataset.py
python scripts/export_hf_dataset_v2.py
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl
```

## Citation

If you use this dataset, cite the repository and release version:

```bibtex
@misc{sakae2026industrialagentbenchmark,
  title = {Industrial Agent Benchmark},
  author = {Masahiro Sakae},
  year = {2026},
  version = {2.2.0},
  url = {https://github.com/masahirosakae/industrial-agent-benchmark}
}
```

## License

Apache License 2.0. See the GitHub repository for full license files and dataset release notes.
