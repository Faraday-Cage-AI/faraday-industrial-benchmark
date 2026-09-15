# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to the versioning rules described in
[docs/versioning_policy.md](docs/versioning_policy.md).

Note: entries for releases prior to v2.2.0 are intentionally minimal here.
Detailed release notes for earlier versions live under `docs/` (for example
`docs/v2.0.1_release_notes.md`, `docs/v1.1_release_notes.md`); backfilling
them into this file is tracked as a separate task.

## [Unreleased]

### Added

- Baseline research protocol documents ahead of the initial public benchmark
  baseline (P0-1): `docs/baseline_experiment_plan_v1.md` (frozen 6-model
  protocol, pilot gate, statistics, two-stage publication),
  `docs/contamination_policy_v1.md` (exposure statement, detection procedures,
  usage-evidence snapshots), `docs/judge_validation_plan_v1.md` (stratified
  human validation, P0-2), and `docs/baseline_manifest_spec_v1.md` (required
  reproducibility and contamination manifest fields).
- Baseline evaluation status and contamination statement added to
  `dataset_card.md` and `hf/README.md`; the 30-task `evaluation_set_v2.yaml`
  is redefined as a public development subset (pipeline verification only).
- `docs/public_artifact_policy_v1.md`: canonical Public Artifact Policy with a
  limited exception for documented official baseline runs — reproducibility
  metadata (model IDs, providers, dates, snapshots, hashes, decoding profiles,
  aggregated scores) becomes publishable, while raw answers, judge texts,
  credentials, and the anonymization mapping remain private; provider terms
  and model licenses take precedence; not retroactive; private held-out
  evaluations stay stricter. `request_echo` is defined as allowlist-redacted
  execution metadata (never raw request payloads, prompt texts, headers, or
  provider request/response IDs); README and CONTRIBUTING now point to the
  canonical policy document.

- Baseline pipeline foundation (Phase 2A, no network): new `baseline/` package
  (types, redaction, decoding profiles, model config, manifest builder/validator,
  runner, dummy provider) and `scripts/baseline_generate_answers.py`, fully
  separate from the frozen `eval_v2_*` pipeline. Public manifests carry
  provider-request information only as allowlist-typed `request_echo`
  (public_artifact_policy_v1 Section 3.3), enforced structurally and by tests;
  result rows are classified as `completed` / `missing_retry_exhausted` /
  `missing_permanent` for later pilot-gate aggregation. Private run artifacts
  default to the git-ignored `experiments/**/runs/` path. Real provider
  adapters (OpenAI / Anthropic / OpenAI-compatible / Gemini) are Phase 2B+;
  only the dummy provider is runnable, and template configs marked
  `non_runnable` are rejected at execution time.
- Baseline provider adapters and pilot gate (Phase 2B, still no network):
  `baseline/transport.py` (injectable transport; the urllib implementation is
  the only network path and is never exercised by tests),
  `OpenAIResponsesProvider` (reasoning effort, `store: false`, strict
  Structured Outputs for the judge), `AnthropicMessagesProvider` (Opus
  adaptive thinking + effort; temperature / top_p / top_k / budget_tokens are
  never sent — enforced at profile load, body build, and by fake-transport
  tests), `OpenAICompatibleProvider` (env-resolved base URL, temperature 0 /
  top_p 1 / pinned seed, provider extras via explicit allowlist only — no raw
  extra_body passthrough; Gemini `thinking_config` kept as an explicit block
  pending its Go/No-Go). Real providers are constructible only with an
  explicitly injected transport, so real-API execution stays disabled.
  `baseline/pilot.py` + `scripts/baseline_pilot_gate.py` evaluate the pilot
  gate (missing rate ≤ 1%, zero permanent failures, judge parse/required-field
  criteria, cost deviation) from safe aggregates only and print
  GO / NO_GO / NEEDS_REVIEW. Added `judge.template.yaml` (non-runnable) and
  the strict `judgement_v1.schema.json`.
- Provider wire alignment ahead of real-API use: Anthropic `effort` now sent
  as `output_config.effort` (never top-level); the first-pilot Gemini
  OpenAI-compat profile sends `reasoning_effort` only (mutually exclusive
  with sampling params and with `google_thinking_config`); the future-facing
  `google_thinking_config` extra maps to the fixed wire position
  `extra_body.google.thinking_config` (no top-level `thinking_config`,
  `thinking_level` rejected, `include_thoughts: true` forbidden), all
  enforced at profile load and pinned by fake-transport body tests.
- `docs/baseline_go_no_go_register_v1.md`: canonical, dated Go/No-Go decision
  register for all external dependencies preceding the 30-task pilot
  (GNG-001–013: model snapshots, Gemini access path and 7-item minimal probe,
  hosted-OSS stop rules, Swallow/RunPod conditions, publication terms, rate
  limits, budget). Current verdict: CONDITIONAL. The baseline experiment
  plan, manifest spec, judge validation plan, and public artifact policy now
  reference the register as the canonical pre-execution decision record.
- GitHub Actions CI: dataset validation, JSONL export sync check
  (`git diff --exit-code data/v2/test.jsonl`), JSONL validation, and pytest on
  every pull request.
- Test suite under `tests/` covering the dataset validator (positive and
  negative cases), HF export idempotency, index consistency, and the
  placeholder scorer tokenization.
- Contributor tooling: `CONTRIBUTING.md` (new-task procedure), issue templates
  (bug / feature / question), pull request template, `CITATION.cff`,
  `requirements-dev.txt`, and this changelog.

### Changed

- Placeholder scorer upgraded to `rule_based_token_overlap_v2`: tokenization
  now handles Japanese text via character bigrams (v1 was ASCII-only and
  scored all Japanese answers as 1). Scores remain pipeline-validation
  placeholders, not benchmark results.
- Version identifiers untangled across the repository: release version
  (v2.2.0), JSONL schema version (2.0.0), task YAML schema revision, and
  frozen prompt template versions are now documented in
  `docs/versioning_policy.md` and referenced consistently in README, dataset
  cards, and scripts.
- README / dataset cards now state the evaluation implementation status
  explicitly: current scoring is placeholder / experimental, the
  Deterministic / Rubric / Executable Judge architecture is a roadmap, and the
  `eval/` vs `scripts/eval_v2_*` pipelines are documented with a usage guide.
- `examples/simple_eval_answers.jsonl` and `examples/sample_judge_results.jsonl`
  regenerated with a Japanese sample answer and the v2 scorer.
- `benchmark_data/index.yaml` / `index.csv` regenerated with the current
  `scripts/generate_dataset.py` ordering (sorted by task id).

### Fixed

- `scripts/validate_dataset.py`: `difficulty` and `estimated_time_min` no
  longer accept boolean values (bool is an int subclass in Python).
- `scripts/generate_dataset.py`: no longer resets the index task-schema
  revision from `1.1` back to `1.0` on regeneration.

## [2.2.0] - 2026-06-15

### Changed

- Japanese Canonical Normalization: Japanese is now the canonical language of
  the benchmark. The 45 remaining English-only tasks were migrated to Japanese
  canonical form (English-only tasks: 45 -> 0).
- Dataset composition preserved: 180 tasks (Knowledge 60 / Reasoning 60 /
  Agent 60); validation and export pipeline unchanged.
- English is planned as a future translated or derivative distribution.

## Earlier releases

- **2.1.0** - Multilingual architecture planning (see
  `docs/multilingual_architecture_v2_1.md`).
- **2.0.1** - Metadata and documentation correction (see
  `docs/v2.0.1_release_notes.md`).
- **2.0.0** - First stable v2 release: HF JSONL distribution, v2 schema,
  simple evaluation pipeline (see `docs/v2_0_0_architecture.md`).
- **1.1.0-pre** - Frozen pre-release snapshot (see
  `docs/v1.1_release_notes.md`).
- **1.0.0** - Initial public release (see
  `docs/benchmark_release_notes_v1.0.md`).
