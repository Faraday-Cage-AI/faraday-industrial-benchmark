# Industrial Agent Benchmark

Industrial Agent Benchmark is a public benchmark for evaluating Industrial AI systems, Manufacturing AI assistants, and Industrial Agents.

The canonical language of Industrial Agent Benchmark is **Japanese**. English should be treated as a future translated or derivative distribution, not as the source of truth.

Japanese README: [README.md](README.md)

## Dataset Overview

**Current release: v2.2.0 Japanese Canonical Normalization**

v2.2.0 completed the migration of previously English-only benchmark tasks into Japanese canonical form while preserving the dataset size and validation pipeline.

- Total: 180 tasks
- Knowledge: 60
- Reasoning: 60
- Agent: 60
- English-only tasks: 45 -> 0
- HF-compatible JSONL: `data/v2/test.jsonl`
- Validation/export pipeline: preserved

Note: the release version (v2.2.0) and the record-level `version` field in `data/v2/test.jsonl` (the JSONL schema version, currently `2.0.0`) are separate identifiers. The record schema has not changed since v2.0.0, so `version` remains `"2.0.0"`. See [docs/versioning_policy.md](docs/versioning_policy.md).

| Layer | Count | Focus |
|---|---:|---|
| Industrial Knowledge | 60 | Manufacturing knowledge, procedures, quality, maintenance, and change control |
| Industrial Reasoning | 60 | Root-cause analysis, FMEA, CAPA, risk tradeoffs, data integrity, and numeric capacity planning |
| Industrial Agent | 60 | Workflow design, tool selection, human approval boundaries, safety, structured decisions, and auditability |
| Total | 180 |  |

## Language Policy

v2.2.0 establishes Japanese as the canonical language for benchmark tasks.

- Japanese records are the source of truth.
- English is planned as a translated or derivative distribution.
- English-only task records have been migrated to Japanese canonical form.
- Machine-readable schema keys, enum-like final states, JSON field names, and accepted technical abbreviations may remain in English where needed for evaluation compatibility.

## Quick Start

### Requirements

- Python 3.10+
- PyYAML

```bash
pip install pyyaml
```

### Validate the YAML benchmark files

```bash
python scripts/validate_dataset.py
```

Expected output:

```text
Checked: 180 problem files
Errors: 0
Warnings:0
```

### Export and validate the HF-compatible JSONL

```bash
python scripts/export_hf_dataset_v2.py
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl
```

### Load locally

```bash
python examples/load_dataset_v2.py
```

## Hugging Face Dataset

```text
https://huggingface.co/datasets/MSakae/industrial-agent-benchmark
```

Primary dataset file:

```text
data/v2/test.jsonl
```

## Evaluation Architecture

### Current implementation status

**The evaluation currently shipped in this repository is placeholder / experimental. No official judge is implemented yet.**

- The current scorer is `rule_based_token_overlap_v2`, a rule-based token-overlap placeholder used to validate the evaluation pipeline's file formats and plumbing. It tokenizes ASCII word tokens plus Japanese (hiragana / katakana / kanji) character bigrams, so pipeline validation works on the Japanese-canonical dataset.
- **Do not use its scores as benchmark results or for model comparison.** Scoring is surface token overlap only; it does not evaluate meaning, evidence, or rubric compliance.
- No official scores or leaderboard are provided.

### Which evaluation path to use

| Path | Scope | Status | Purpose |
|---|---|---|---|
| `scripts/validate_dataset.py` / `scripts/export_hf_dataset_v2.py` / `scripts/validate_hf_dataset_v2.py` | All 180 tasks | Stable | Data validation and JSONL export. Start here. |
| `eval/run_simple_eval.py` → `eval/run_judge_eval.py` → `eval/summarize_judge_eval.py` | All 180 tasks | Placeholder | Normalize your own pre-generated answers into the common schema and exercise the placeholder scorer. |
| `scripts/eval_v2_*` | 30-task subset in `evaluation_set_v2.yaml` | Experimental | LLM-judge evaluation experiments. External APIs are opt-in (dummy/dry-run by default). |

Recommendation for new users: validate and load the data first (`examples/load_dataset_v2.py`), and generate answers with your own harness. The scoring scripts in this repository are experimental at this time.

### Judge roadmap (planned)

The following judge architecture is designed but **not yet implemented**. See [docs/evaluation_architecture_v2.md](docs/evaluation_architecture_v2.md).

| Layer | Planned judge | Notes |
|---|---|---|
| Industrial Knowledge | Deterministic Judge | Expected points, keywords, and structured reference answers |
| Industrial Reasoning | Rubric Judge plus numeric checks | Evidence, constraints, feasibility, and calculation checks (with LLM-judge assistance) |
| Industrial Agent | Executable Judge | Safe workflow behavior, gate checks, action boundaries, escalation, and audit trails |

## Repository Layout

```text
industrial-agent-benchmark/
  README.md
  README_EN.md
  dataset_card.md
  data/
    v2/
      test.jsonl
  benchmark_data/
    knowledge/
    reasoning/
    agent/
  docs/
  examples/
  eval/
  scripts/
```

## Citation

If you use Industrial Agent Benchmark in research, evaluation, or public reporting, cite the repository and release version.

```text
Industrial Agent Benchmark v2.2.0.
https://github.com/masahirosakae/industrial-agent-benchmark
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the new-task procedure, validation flow, and PR checklist. CI runs dataset validation, a JSONL sync check, and tests on every pull request. Release history is tracked in [CHANGELOG.md](CHANGELOG.md), and citation metadata in [CITATION.cff](CITATION.cff).

Contributions should preserve the benchmark's public-release constraints:

- keep benchmark items manufacturing-domain relevant and public safe
- treat Japanese as the canonical language
- do not include private company data, customer data, proprietary process data, or provider-specific model results
- keep generated answers and evaluation outputs out of git
- update derived JSONL only through the documented export script

Before proposing dataset changes, run:

```bash
python scripts/validate_dataset.py
python scripts/export_hf_dataset_v2.py
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl
```

## License

Code: Apache License 2.0. See [LICENSE](LICENSE).

Dataset: see [LICENSE_DATASET.md](LICENSE_DATASET.md).
