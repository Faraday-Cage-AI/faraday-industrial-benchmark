# Versioning Policy

Industrial Agent Benchmark uses versioned dataset and evaluation artifacts so public users can reproduce results and understand compatibility boundaries.

## Version Lines

| Version line | Status | Policy |
|---|---|---|
| v1.0 | Public baseline | Historical baseline. |
| v1.1.0 | Frozen pre-release snapshot | Public snapshot for inspection and compatibility; no active evaluation-result cleanup. |
| v2.0.0 | Superseded | First stable release of the v2 architecture line (HF dataset loading, simple evaluation). |
| v2.0.1 | Superseded | Metadata and documentation correction release. |
| v2.1.0 | Superseded | Multilingual architecture planning release. |
| v2.2.0 | **Current release** | Japanese Canonical Normalization; Japanese is the canonical task language. |

## Version Identifier Taxonomy

The repository uses four distinct version identifiers. They evolve independently and must not be conflated.

| Identifier | Current value | Where it appears | When it changes |
|---|---|---|---|
| Release version | `v2.2.0` | README, dataset card, citations, run manifests (`benchmark_version`) | Every public release. |
| JSONL schema version | `2.0.0` | Record-level `version` field in `data/v2/test.jsonl`; `scripts/export_hf_dataset_v2.py` (`SCHEMA_VERSION`); `scripts/validate_hf_dataset_v2.py` | Only when the JSONL record schema itself changes. Unchanged since v2.0.0. |
| Task YAML schema revision | v1.0 base + v1.1 optional fields | `benchmark_data/**/*.yaml`, `scripts/validate_dataset.py`, `docs/benchmark_spec.md` | Only when task YAML fields are added or redefined. References to "v1.1 fields" name this schema revision, not the release. |
| Prompt template version | `iab_v1_1_answer_prompt_v1`, `iab_v1_1_judge_v2` | `scripts/eval_v2_common.py`, run manifests, `judge_template_v2.md` | Only when prompt content changes. These identifiers (and the literal version strings inside the frozen prompt text they identify) are compatibility identifiers; they are intentionally not renamed on release, so past evaluation runs remain comparable. |

## Compatibility Rules

- Patch updates may clarify documentation or fix validation bugs without changing benchmark meaning.
- Minor updates may add public questions, metadata, or evaluation helpers while preserving documented compatibility.
- Major updates may change dataset layout, evaluation flow, or leaderboard policy.

## Dataset Versioning

Each public dataset release should document:

- dataset version
- schema version
- question count
- split names
- evaluator compatibility
- known limitations

## Evaluator Versioning

Evaluation outputs should record:

- evaluator version
- dataset version
- scoring mode
- timestamp
- local configuration needed for reproduction

Evaluator versions should be stable enough that leaderboard submissions can be compared fairly.

## Artifact Policy

Public versioned artifacts may include:

- benchmark questions
- public metadata
- public schemas
- evaluator scripts
- aggregate public leaderboard summaries

Public versioned artifacts must not include:

- raw model answers
- private result directories
- unpublished judge outputs
- provider credentials
- internal model-name mappings

## v1.1.0 Freeze

v1.1.0 remains available as a frozen pre-release benchmark snapshot. New architecture, dataset-distribution work, simple evaluation design, and leaderboard policy belong to v2.0.0.
