# Baseline Experiment Plan v1 — Initial Public Benchmark Baseline

Status: **Frozen protocol draft** (becomes frozen when committed and referenced by the first baseline run manifest)
Applies to: Industrial Agent Benchmark **v2.2.0**, all **180 public tasks**
Related documents: `contamination_policy_v1.md`, `judge_validation_plan_v1.md`, `baseline_manifest_spec_v1.md`, `baseline_go_no_go_register_v1.md`, `versioning_policy.md`, `evaluation_methodology.md`

---

## 1. Purpose and Claims

This document fixes the research protocol for the **initial public benchmark baseline** of Industrial Agent Benchmark v2.2.0 before any baseline evaluation is executed.

What this baseline **is**:

- A diagnostic baseline of 6 models on the 180 publicly available tasks.
- The first published evidence of score distributions, layer/category/difficulty breakdowns, and model discrimination for this benchmark.
- A research artifact with a versioned, reproducible protocol.

What this baseline **is not**:

- It is **not an official leaderboard**. Initial public benchmark baseline results are research artifacts, not an official leaderboard. No leaderboard policy or infrastructure is created for this baseline.
- It is **not** evidence of contamination-free generalization. See `contamination_policy_v1.md` for the exposure status statement and claim limitations.
- It is **not** a certification of any model's fitness for manufacturing use.

(日本語) 本ベースラインは公開済み180問に対する「診断的ベースライン」であり、公式リーダーボードではなく、汚染のない汎化性能の証拠として主張しない。

## 2. Evaluated Models

The initial baseline evaluates the following **6 models**:

| Slot | Role | Model | Access path | Adoption condition |
|---|---|---|---|---|
| 1 | Frontier (Anthropic) | `claude-opus-4-8` | Anthropic API (Messages) | — |
| 2 | Frontier (OpenAI) | `gpt-5.5` | OpenAI API (Responses) | — |
| 3 | Frontier (Google) | `gemini-2.5-pro` | Gemini API | Pre-pilot Go/No-Go on decoding control (Section 4a.4) |
| 4 | Open-weight base | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Hosted provider | Adopted **only if** the hosted provider can record the exact model revision, quantization, and serving path in the manifest at experiment start |
| 5 | General-purpose open-weight control | `meta-llama/Llama-4-Maverick-17B-128E-Instruct` | Hosted provider | Same hosted-provider condition as slot 4 |
| 6 | Japanese-specialized control | `tokyotech-llm/Qwen3-Swallow-32B-RL-v0.2` | vLLM on cloud GPU (e.g., RunPod), not a local workstation | Cloud GPU environment recorded per `baseline_manifest_spec_v1.md` |

Mid-tier models from the same providers and small models are **sensitivity-analysis slots**, considered only after the 30-task pilot, and reported separately from the 6-model baseline if run.

For every model the manifest records: official model ID, provider, snapshot/version identifier, access path, retrieval or execution date, and (where ascertainable) public release date and training data cutoff (`baseline_manifest_spec_v1.md`).

### 2.1 Interpretation Constraints

- `Qwen3-235B-A22B-Instruct-2507` and `Qwen3-Swallow-32B-RL-v0.2` differ in **scale, architecture, post-training, and inference path**. In this initial baseline, score differences between them are **not** claimed as a causal effect of Japanese-language adaptation. Their comparison is reported as an **exploratory model-family comparison** only.
- A more direct analysis of Japanese adaptation is a candidate for a **future sensitivity analysis** comparing `Qwen/Qwen3-32B` against `tokyotech-llm/Qwen3-Swallow-32B-RL-v0.2` in the **same inference environment**.
- `Llama-4-Maverick-17B-128E-Instruct` is framed as a **general-purpose open-weight control** (not an "English-oriented control"); language-related observations involving it are likewise exploratory, not causal claims.

(日本語) Qwen3-235B と Qwen3-Swallow-32B-RL の差は、規模・アーキテクチャ・後学習・推論経路が異なるため、日本語適応の因果効果として主張せず、探索的なモデルファミリー比較として報告する。日本語適応の直接分析は、同一推論環境での `Qwen/Qwen3-32B` と `Qwen3-Swallow-32B-RL-v0.2` の比較を将来の感度分析候補とする。

## 3. Dataset and Subset Definitions

- **Primary evaluation set**: all 180 tasks in `data/v2/test.jsonl` at a fixed git commit, with the file's SHA-256 recorded in the manifest.
- **Public development subset**: the 30 tasks listed in `evaluation_set_v2.yaml` are redefined for this experiment as a *public development subset* used only for:
  1. pipeline verification,
  2. API cost estimation,
  3. answer-format and JSON-output stability checks,
  4. judge behavior checks.

  Scores obtained on the development subset are **never** reported as benchmark results, in any form. (The YAML file's own description text is unchanged in this phase; this document is the authoritative definition.)

## 4. Frozen Protocol Elements

The following are frozen before the first baseline answer is generated. Any change requires a new experiment ID:

1. Dataset: git commit hash, `data/v2/test.jsonl` SHA-256, task count (180).
2. Answer prompt template (body + version ID), with a machine-checked guarantee that reference answers and rubrics do not leak into prompts.
3. Answer system prompt (body + version ID).
4. Per-model provider-native decoding profiles (Section 4a), max output tokens, retry rules.
5. The 6 evaluated model identities and snapshots (Section 2).
6. Judge model identity (`gpt-5.4`) and snapshot; judge prompt template (body + version ID); judge output JSON schema.
7. Scoring rules: critical-failure override → must-have score caps → scoring matrix, per `evaluation_methodology.md` (versioned).
8. Anonymization procedure for judge inputs (Section 6).
9. Missing-data rules (Section 7).
10. Statistical specification (Section 8).
11. Hashes of all experiment configuration files.
12. Contamination recording items and usage-evidence snapshot procedure (`contamination_policy_v1.md`).

## 4a. Decoding Policy — Provider-Native Controlled Decoding

The earlier blanket rule "temperature 0.0 for all models" is **replaced** by provider-native controlled decoding. Each model runs under a frozen, per-model decoding profile that minimizes output variance using only mechanisms the provider officially supports. Parameters a provider does not support are **not sent**; the manifest distinguishes between *parameters actually sent* and *parameters deliberately not sent* (`baseline_manifest_spec_v1.md`).

### 4a.1 Determinism Claim

**No model is claimed to be fully deterministic.** Reproducibility is defined as statistical reproducibility under the same frozen profile and snapshot. Output variance is measured empirically via 3 repeated runs on the 30-task development subset per model (Section 8) and reported as measurement error in all baseline reports.

### 4a.2 OpenAI profiles

- `gpt-5.5` (evaluated): reasoning effort pinned to a fixed value recorded in the profile; max output tokens fixed.
- `gpt-5.4` (judge): reasoning effort pinned; **Structured Outputs** (strict JSON schema) enforced for all judgements; the schema file and its SHA-256 are frozen protocol elements.
- Seed parameter support is verified on experiment start day; the result (supported/ignored) is recorded in the manifest.

### 4a.3 Anthropic profiles

- **`claude-opus-4-8`** (evaluated):
  - `thinking: adaptive` is **explicitly enabled**. Running Opus 4.8 without adaptive thinking enabled is **not permitted** in this baseline.
  - `effort: high` is pinned.
  - `temperature`, `top_p`, and `top_k` are **not sent** (recorded as deliberately-not-sent).
- **`claude-sonnet-5`** (second judge, P0-2):
  - `effort: high` is pinned.
  - Adaptive thinking is **provider default** and is recorded as such (not explicitly set).
  - Manual extended thinking / `budget_tokens` are **not sent**. Note: Sonnet 5 does **not** support manual thinking budgets or non-default sampling parameters; profiles must not attempt to set them.
  - `temperature`, `top_p`, and `top_k` are **not sent** (recorded as deliberately-not-sent).
- Profiles and manifests use these **exact setting names**; generic phrasings such as "thinking type / budget" are avoided.

### 4a.4 Google profile and Go/No-Go condition

- `gemini-2.5-pro`: thinking/reasoning configuration is pinned in the frozen profile.
- **Go/No-Go (pre-pilot)**: the OpenAI-compatible endpoint is used **only if** it can (a) apply the frozen thinking/reasoning settings and (b) return the response metadata required by the manifest, reproducibly. If it cannot, a native `GeminiNativeProvider` is implemented instead. **Gemini evaluation must not start while its decoding settings cannot be controlled.** This verification is a mandatory item of the pre-pilot Go/No-Go check (Section 5).

### 4a.5 Open-weight profiles (hosted Qwen3-235B / Llama 4 Maverick; vLLM Swallow)

- `temperature: 0`, `top_p: 1`; seed pinned where the serving stack supports it.
- Hosted providers: whether `temperature`/`top_p`/`seed` are honored is verified (documentation plus a same-input repeat test) and recorded.
- vLLM (Swallow): full sampling parameters and the serving environment are recorded per `baseline_manifest_spec_v1.md`.

## 5. Pilot Gate (30-task public development subset)

**Pre-pilot Go/No-Go**: before the pilot starts, the Gemini decoding-control verification (Section 4a.4) and the hosted-provider adoption conditions for slots 4–5 (Section 2) must be resolved. If a slot fails its condition, its documented alternative is substituted before the pilot; the pilot does not start with an unresolved slot. The canonical, dated record of these and all other pre-execution external dependencies (snapshots, terms confirmations, rate limits, budget) is `baseline_go_no_go_register_v1.md`; the pilot starts only under that register's GO verdict.

The pilot runs all 6 models on the 30-task development subset before the 180-task baseline.

**Pass criteria (all must hold):**

- Permanent failures / empty answers after retries: **0**. Transient API failures are acceptable if resolved by retry.
- Answers that still fail after retries are recorded as **missing**, never given a fabricated score.
- **Missing rate ≤ 1% of all answers.** If missing exceeds 1%, do not proceed to the 180-task baseline.
- Even at ≤ 1%, missing counts are reported per model and per provider.
- Prompt leakage check violations: 0.
- Judge JSON parse success ≥ 97% (100% after one re-judge attempt); required judge fields never absent.
- Human spot check of 20 stratified judgements: at most 2 clear scoring defects (missed/false critical failure, unapplied score cap).
- Measured token usage within ±50% of the cost estimate.

**Abort criteria (any one triggers redesign instead of proceeding):**

- Judge undecidable rate (parse failure + missing required fields) > 10%.
- Aggregate critical-failure trigger rate of 0% or > 60% across all models (judge malfunction signal).
- 5 or more scoring defects in the spot check, or evidence of systematic bias for/against a specific model.
- Measured cost more than 2× the estimate.
- Discovery of provider terms-of-service obstacles to publishing named results.

## 6. Judge Protocol

- A single fixed judge model (`gpt-5.4`) scores all answers under its frozen decoding profile (Section 4a.2), with Structured Outputs enforcing the frozen judgement JSON schema, using the frozen judge template and the deterministic scoring rules.
- The judge shares a provider with evaluated model `gpt-5.5`; per the disclosure rule below, this overlap is disclosed in the official report and is the primary target of the P0-2 self-preference check.
- **Anonymization**: the judge receives only anonymized keys `model_A` … `model_F`. The key-to-model mapping is generated once, stored privately, and never included in judge inputs or public artifacts.
- **Provider separation is not required.** If the judge shares a provider or model family with any evaluated model, the official baseline report must disclose this explicitly, and the affected pairs are flagged in the results tables.
- Judgement order is shuffled across (task × model) to avoid ordering effects.
- A second-judge stratified sensitivity analysis is planned as part of judge validation (P0-2); see `judge_validation_plan_v1.md`.

## 7. Missing-Data Rules

- Retry policy: transient errors (HTTP 408/409/425/429/5xx, timeouts, truncated JSON) are retried with exponential backoff; permanent errors are not.
- An answer missing after retries is recorded with `error` populated and excluded from score averages; aggregate tables report both `n_scored` and `n_missing` per model.
- A judgement that cannot be parsed after one re-judge attempt is recorded as missing (no placeholder score).
- Missing rates are reported per model, per provider, and per layer.

## 8. Statistical Specification

- **Point estimates**: mean final score (0–5) per model, overall and by layer, category, difficulty, and domain; critical-failure rate; score-cap rate.
- **Confidence intervals**: nonparametric bootstrap over **tasks** (resampling unit = task, 10,000 resamples, percentile method, 95%). Wide CIs for small categories (n = 3–14) are reported as-is.
- **Critical-failure rates**: Wilson score intervals.
- **Pairwise model comparisons**: paired bootstrap over tasks for score differences; permutation tests; Holm correction for multiple comparisons. Differences with CIs are the primary report; significance stars are secondary.
- **Discrimination analysis**: bootstrap rank stability, variance decomposition (between-model vs within-task), item–total correlation to identify low-discrimination tasks.
- **Stability**: 3 repeated runs on the 30-task development subset per model quantify decoding/API nondeterminism. Because no model is claimed to be fully deterministic (Section 4a.1), this measurement is a mandatory part of the protocol, and its results are reported as measurement error alongside the single-run 180-task results.

## 9. Two-Stage Publication

1. **Stage 1 — Initial report**: published after the 180-task baseline, explicitly labeled *"judge validity not yet human-verified"*. All claim-limitation language from `contamination_policy_v1.md` applies.
2. **Stage 2 — Revised report**: published after judge validation (P0-2, `judge_validation_plan_v1.md`) completes, adding agreement statistics and any recalibration notes.

(日本語) ベースラインレポートは二段階で公開する。初版は「Judge の人間妥当性検証前」という限定付き、改訂版は Judge 妥当性検証(P0-2)完了後に公開する。

## 10. Public and Private Artifacts

This baseline operates under **Public Artifact Policy v1** (`public_artifact_policy_v1.md`), whose Section 3 defines the limited exception for documented official baseline runs. The lists below summarize that exception; the policy document is canonical. Publication of named results is conditional on prior confirmation of provider terms of service, hosting provider terms, and model licenses; **where such terms restrict publication, they take precedence over the policy exception.**

**Published for official baseline runs:**

- This plan and its companion policy documents.
- Experiment configuration: official evaluated-model IDs, providers, execution dates, and primary inference settings (frozen decoding profiles including parameters sent and deliberately not sent, max tokens, access path, precision/quantization for open-weight models).
- The public manifest fields defined in `baseline_manifest_spec_v1.md`.
- `scores_matrix` (task ID × model final scores only), aggregate metrics with CIs, pairwise comparisons, stability data.
- Contamination indicator **aggregates** (per-model n-gram overlap rates, self-reference counts, verbatim-reproduction counts).
- Analysis scripts.

**Remaining private (per `public_artifact_policy_v1.md` Section 3.2):**

- Development / trial runs (including all development-subset scores).
- The anonymization mapping.
- Raw answer texts; full answer prompts and request payloads; judge input and output texts (including raw judge summaries and evidence text).
- API keys, endpoints, billing details, account and internal rate-limit information.
- Raw usage-evidence captures (GitHub/HF metrics screenshots and API responses) — archived privately; aggregate numbers appear in the report.
- Texts flagged by n-gram overlap detection; detailed cloud-GPU connection information.

The exception does not extend to future private held-out evaluations (P0-3), which follow a stricter non-disclosure posture, and is not retroactive to past runs or previously published artifacts.

## 11. Execution Order

1. Freeze this plan and companion documents (this phase).
2. Pipeline implementation (separate phase; no code is changed by this document).
3. 30-task pilot → gate decision (Section 5).
4. 180-task × 6-model initial public benchmark baseline.
5. Statistics, aggregation, Stage-1 report.
6. Judge validation (P0-2) → Stage-2 revised report.
7. New private held-out tasks (P0-3) — created as **new tasks**, not drawn from the existing 180; explicitly *not* a precondition for this baseline.
