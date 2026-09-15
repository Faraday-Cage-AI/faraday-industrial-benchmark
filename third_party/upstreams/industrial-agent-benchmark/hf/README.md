---
language:
  - ja
  - en
license: apache-2.0
pretty_name: Industrial Agent Benchmark
task_categories:
  - question-answering
tags:
  - manufacturing
  - industrial-ai
  - industrial-agent
  - llm-evaluation
  - agent-evaluation
  - benchmark
size_categories:
  - n<1K
---

# Industrial Agent Benchmark

Industrial Agent Benchmark (IAB) is an open benchmark for evaluating Industrial AI systems, Manufacturing AI assistants, and Industrial Agents.

This Dataset Card describes the Hugging Face Dataset release for **Industrial Agent Benchmark v2.2.0 (Japanese Canonical Normalization)**.

Repository:

```text
https://github.com/masahirosakae/industrial-agent-benchmark
```

Hugging Face Dataset Repository:

```text
https://huggingface.co/datasets/MSakae/industrial-agent-benchmark
```

## Dataset Description

Industrial Agent Benchmark evaluates whether AI systems can handle manufacturing-domain tasks across three layers:

- **Knowledge**: factual and procedural manufacturing knowledge
- **Reasoning**: multi-step industrial reasoning, risk analysis, root-cause analysis, and numeric planning
- **Agent**: workflow design, tool-use boundaries, human approval requirements, safe escalation, and auditability

The current release is **v2.2.0**. Japanese is the canonical language of the benchmark: previously English-only tasks have been migrated to Japanese canonical form, and English is planned as a future translated or derivative distribution. Machine-readable schema keys, enum-like values, and accepted technical abbreviations may remain in English for evaluation compatibility.

Release history on this line: v2.0.0 (first stable release), v2.0.1 (metadata correction), v2.1.0 (multilingual architecture planning), v2.2.0 (Japanese canonical normalization, current).

## Dataset Statistics

| Split | Examples |
|---|---:|
| test | 180 |

| Layer | Examples |
|---|---:|
| Knowledge | 60 |
| Reasoning | 60 |
| Agent | 60 |
| Total | 180 |

Difficulty distribution in `data/v2/test.jsonl`:

| Difficulty | Examples |
|---|---:|
| easy | 4 |
| medium | 55 |
| hard | 91 |
| expert | 30 |

## Intended Use

This dataset is designed for:

- Manufacturing AI evaluation
- Industrial LLM evaluation
- Industrial Agent evaluation
- Research on domain-specific AI evaluation
- Comparing model behavior on industrial knowledge, reasoning, and agent-safety tasks

The benchmark is intended for research and evaluation. It is not a certification benchmark.

## Dataset Structure

v2.2.0 contains Japanese canonical benchmark tasks organized into three layers:

- `knowledge`
- `reasoning`
- `agent`

The dataset is distributed as JSONL and uses a single `test` split.

## Data Files

Primary data file:

```text
data/v2/test.jsonl
```

The JSONL file is generated from the public YAML benchmark items in the GitHub repository.

## Data Fields

The following fields are present in `data/v2/test.jsonl`:

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable benchmark item ID. |
| `version` | string | JSONL schema version, currently `2.0.0`. This is distinct from the benchmark release version (v2.2.0); it changes only when the record schema changes. |
| `domain` | string | High-level domain label. |
| `category` | string | Benchmark layer category: `knowledge`, `reasoning`, or `agent`. |
| `sub_category` | string | More specific task category within the layer. |
| `task_type` | string | Task format label, such as case-analysis style tasks. |
| `question` | string | Main prompt or question to answer. |
| `context` | string | Scenario or supporting context for the task. |
| `choices` | list | Multiple-choice options when present; empty for open tasks. |
| `answer` | string | Reference answer. |
| `rubric` | string | Evaluation rubric or grading guidance. |
| `expected_capabilities` | list | Capabilities expected for the task. |
| `difficulty` | string | Difficulty label: `easy`, `medium`, `hard`, or `expert`. |
| `tags` | list | Search and grouping tags. |
| `source` | string | Source type. All items are synthetic benchmark tasks. |
| `public` | boolean | Whether the item is public. |
| `requires_external_knowledge` | boolean | Whether external knowledge is required. |
| `notes` | string | Optional notes. |

## Loading Example

Standard loading after publication:

```python
from datasets import load_dataset

dataset = load_dataset("MSakae/industrial-agent-benchmark")
print(dataset)
```

If you need to specify the data file manually:

```python
from datasets import load_dataset

dataset = load_dataset(
    "json",
    data_files={"test": "data/v2/test.jsonl"},
)
print(dataset)
```

## Evaluation

**Evaluation status: the scoring utilities in the GitHub repository are placeholder / experimental. No official judge or leaderboard exists yet.** The current scorer (`rule_based_token_overlap_v2`) validates pipeline file formats only; it handles Japanese text via character-bigram tokenization, but its scores measure surface token overlap and must not be used as benchmark results. The Deterministic / Rubric / Executable Judge architecture is planned; see `docs/evaluation_architecture_v2.md` in the GitHub repository.

The GitHub repository provides validation and evaluation scripts:

- `scripts/validate_hf_dataset_v2.py` (stable, JSONL validation)
- `eval/run_simple_eval.py` (placeholder scoring pipeline)
- `eval/run_judge_eval.py` (placeholder scoring pipeline)

The dataset card describes the benchmark data. Evaluation outputs, generated answers, model-specific results, private reports, and leaderboard artifacts are intentionally not included in the dataset release.

### Baseline Evaluation Status

An initial public benchmark baseline (6 models, all 180 tasks) is planned under a frozen research protocol (`docs/baseline_experiment_plan_v1.md` in the GitHub repository). Initial public benchmark baseline results are research artifacts, not an official leaderboard. The baseline report will be published in two stages: an initial report before human validation of the LLM judge, and a revised report after judge validation (`docs/judge_validation_plan_v1.md`).

For official baseline runs only, `docs/public_artifact_policy_v1.md` (Section 3) permits publishing reproducibility metadata — official model IDs, providers, execution dates, snapshots, dataset and configuration hashes, decoding profile settings, and aggregated scores — while raw answers, judge texts, credentials, and the anonymization mapping remain private. Provider terms of service and model licenses take precedence where they restrict publication.

Contamination status (`docs/contamination_policy_v1.md`):

> Industrial Agent Benchmark v2.2.0 was publicly accessible but had not been formally announced or promoted when the initial baseline protocol was initiated. We therefore consider contamination risk to be low but not provably absent. Results on the public 180-task set are reported as a diagnostic baseline on publicly available tasks, not as evidence of contamination-free generalization.

(日本語) Industrial Agent Benchmark v2.2.0 は、初期ベースラインプロトコル開始時点で公開状態にあったが、正式な告知・広報は行われておらず、実際の利用を示す証拠も確認されていない。したがって汚染リスクは「低いが、皆無とは証明できない」と位置付ける。公開180問での結果は「公開済み問題集合における診断的ベースライン」として報告し、汚染のない汎化性能の証拠としては主張しない。

Example validation:

```bash
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl
```

Simple local evaluation utilities are available in the GitHub repository for users who generate their own answer files.

## Limitations

- v2.2.0 task content is Japanese canonical; an English translated distribution is planned but not yet released.
- The benchmark is not a certification benchmark and should not be used as proof of operational safety or regulatory compliance.
- It does not cover all manufacturing domains, sectors, product types, or factory systems.
- The dataset uses synthetic benchmark tasks and does not include private company data, customer data, or proprietary process data.

## License

Apache License 2.0.

See the GitHub repository for full license files and dataset release notes.

## Citation

```bibtex
@misc{sakae2026industrialagentbenchmark,
  title = {Industrial Agent Benchmark},
  author = {Masahiro Sakae},
  year = {2026},
  version = {2.2.0},
  url = {https://github.com/masahirosakae/industrial-agent-benchmark}
}
```
