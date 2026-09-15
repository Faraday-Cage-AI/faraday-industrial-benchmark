# Baseline Go/No-Go Decision Register v1

Status: **Canonical decision record for all external dependencies that must be
resolved before the 30-task pilot starts.** Where other baseline documents
mention pre-execution external conditions (provider verification, adoption
conditions, terms confirmation), this register is the canonical, dated record
of those decisions. Related documents: `baseline_experiment_plan_v1.md`,
`baseline_manifest_spec_v1.md`, `judge_validation_plan_v1.md`,
`public_artifact_policy_v1.md`, `contamination_policy_v1.md`.

Investigation basis: official primary sources reviewed on **2026-07-05**
(OpenAI model/pricing pages, Anthropic model documentation, Gemini API
documentation and terms, Hugging Face model cards for the three open-weight
models, RunPod pricing). Items not confirmable from those sources are marked
`pending_*`; nothing below is inferred from third-party summaries.

---

## 1. Status Vocabulary

| Status | Meaning |
|---|---|
| `verified` | Confirmed from official primary sources; no further action needed before config freeze |
| `pending_human` | Requires a human to read/confirm/approve (terms, budget, account state) |
| `pending_probe` | Requires the approved minimal probe (a few paid requests) to resolve |
| `conditional` | Partially verified; adoption depends on a documented remaining condition |
| `blocked` | A hard precondition failed or is unmet; execution must not start for this item |
| `excluded` | The model/path is dropped from the initial baseline; reason and date recorded publicly |

## 2. Decision Register

Owner `HU` = human decision-maker; `PR` = minimal probe (after human approval);
`DOC` = resolved by documentation review (done). `public_record` states what is
published about the decision (per `public_artifact_policy_v1.md` Section 3).

| decision_id | category | decision | owner | evidence_required | verification_date | status | go_condition | no_go_condition | fallback | public_record | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GNG-001 | GPT-5.5 evaluation model | Adopt `gpt-5.5-2026-04-23` (dated snapshot) via Responses API | DOC | Dated snapshot, reasoning-effort levels, Structured Outputs support | 2026-07-05 | `verified` | Snapshot frozen in config | Snapshot unavailable at run time | — | Manifest models[] entry | Effort levels none/low/medium/high/xhigh confirmed; seed support unverified (recorded at run start per manifest spec §3.6) |
| GNG-002 | GPT-5.4 first judge | Adopt gpt-5.4 as first judge with a dated snapshot | HU | Dated snapshot ID re-confirmed on the official model page; strict Structured Outputs support | — | `pending_human` | Snapshot string confirmed and frozen | No dated snapshot or no strict schema support | Re-select judge (protocol revision, new experiment ID) | Manifest judge block | Existence confirmed 2026-07-05; retrieved snapshot string had an implausible year and must be re-read by a human |
| GNG-003 | Claude Opus 4.8 | Adopt `claude-opus-4-8` (dateless pinned snapshot per official versioning) | DOC | Pinned-snapshot semantics; adaptive thinking + `output_config.effort` support | 2026-07-05 | `verified` | Profile sends `thinking: adaptive` + `output_config.effort: high` | Adaptive thinking not explicitly settable | — | Manifest models[] entry | Official docs: extended thinking No / adaptive thinking Yes; effort default high; training cutoff Jan 2026 (recorded for contamination context) |
| GNG-004 | Claude Sonnet 5 second judge | Adopt `claude-sonnet-5` for P0-2 second-judge analysis | DOC | Pinned ID; no manual thinking budgets; tool-use schema enforcement path | 2026-07-05 | `verified` | Profile sends `output_config.effort` only | — | — | Manifest judge block (P0-2) | Wire placement of effort aligned in implementation (fake-transport tested); tool-use schema enforcement implemented in a later phase |
| GNG-005 | Gemini 2.5 Pro access path | Use the official OpenAI-compatibility endpoint with a `reasoning_effort`-only profile, subject to probe | PR | Probe items in Section 3.3 | — | `pending_probe` | Section 3.4 GO conditions | Section 3.4 exclusion conditions | Native provider, else exclusion (Section 3.4) | Manifest `access_path` + `access_path_verification`; exclusion recorded publicly if taken | Compat layer documented as beta; probe budget approval required first |
| GNG-006 | Qwen3-235B hosted provider | Adopt only if a hosted provider discloses all required metadata (Section 4) | HU | All six mandatory disclosures (Section 4.1) | — | `pending_human` | All six disclosures concrete | Any of the six `unknown` (Section 4.2 stop rule) | Alternative hosted provider; else `excluded` with public record | Manifest models[] entry incl. `hf_revision`, quantization | Model itself Apache-2.0 (verified 2026-07-05); provider not yet selected |
| GNG-007 | Llama 4 Maverick hosted provider | Same as GNG-006, plus Llama 4 Community License attribution | HU | Section 4.1 disclosures + license acceptance + attribution plan | 2026-07-05 (license only) | `pending_human` | Disclosures complete and "Built with Llama" attribution included in publications | Section 4.2 stop rule, or license not accepted | Alternative provider; else re-select the open-weight control (protocol revision) | Manifest entry + required attribution in reports | Gated repo; license copy and notice obligations confirmed from the official model card |
| GNG-008 | Swallow / vLLM / RunPod | Self-serve `tokyotech-llm/Qwen3-Swallow-32B-RL-v0.2` on vLLM, cloud GPU | HU | Section 5 GO conditions | 2026-07-05 (model, license, GPU pricing) | `conditional` | Section 5.1 all satisfied | 80GB-class GPU unavailable and quantized fallback rejected | Alternative GPU class/region; else `excluded` with public record | Manifest vLLM environment block (public subset per Section 5.2) | License Apache-2.0 verified; VRAM requirement is an estimate until load test |
| GNG-009 | Judge execution readiness | Run the judge in the 30-task pilot | HU | GNG-002 resolved; judgement schema frozen (done); judge cost estimate approved | — | `pending_human` | Judge snapshot frozen + cost approved | Judge snapshot undetermined | Answers-first pilot (pilot gate then caps at NEEDS_REVIEW, not GO) | Judge block in manifest | Schema `judgement_v1.schema.json` and provider path already implemented and tested offline |
| GNG-010 | Result publication terms and licenses | Confirm named-result publication is permitted by every provider's terms and each model license | HU | Human read-through of OpenAI Sharing & publication policy, Anthropic commercial terms, Gemini prohibited-use policy, hosted provider terms | — | `pending_human` | All confirmations dated and recorded here | Any terms prohibit named publication → affected model `excluded` or withheld (terms take precedence, policy §4) | Withhold/reduce affected artifact per policy §4 | Confirmation dates recorded in this register + manifest | Gemini API terms reviewed 2026-07-05: no benchmark-publication restriction found; paid tier does not train on prompts |
| GNG-011 | Model snapshot / revision freeze | Freeze one identifier per model + judge before the pilot | HU | OpenAI dated snapshot; Anthropic pinned IDs; HF commit hashes; Gemini stable-version semantics | 2026-07-05 (partial) | `conditional` | Every slot has a frozen identifier recorded in config hashes | Any slot unfreezable (notably Gemini stable-version drift risk without version metadata) | Exclude the unfreezable slot | Manifest `snapshot` / `hf_revision` fields | Anthropic dateless IDs are documented pinned snapshots; Gemini "stable" is weaker — record retrieval date + any version metadata |
| GNG-012 | Rate limits | Record tier, RPM/TPM/daily caps per provider; confirm pilot feasibility | HU | Console-confirmed limits for each account | — | `pending_human` | Limits recorded; pilot schedule fits within them | Limits make the pilot infeasible in its window | Serial/slowed execution (timestamps recorded); batch APIs out of scope for the pilot | Aggregate feasibility note (no account internals published) | Account-specific limits are private; only feasibility is public |
| GNG-013 | Budget approval | Approve a cost ceiling ≥ 2× the estimate (aligned with the pilot-gate abort criterion) | HU | Estimate computed with confirmed unit prices + thinking-token billing treatment | — | `pending_human` | Ceiling approved and recorded | Ceiling below estimate | Reduce model count / repeats (protocol revision) | Aggregate cost figures only if published; billing details private | Confirmed 2026-07-05: GPT-5.5 $5/$30 per MTok; Opus 4.8 $5/$25; Sonnet 5 $3/$15 (intro $2/$10 through 2026-08-31); Gemini and hosted OSS prices unverified |

## 3. Gemini 2.5 Pro — Definitive Treatment

### 3.1 First-baseline profile (decided)

- The initial-baseline Gemini profile sends **`reasoning_effort: high` only**
  over the official OpenAI-compatibility endpoint.
- This is a **conservative protocol choice for the initial baseline**; it does
  **not** assert that the Google API generally forbids combining sampling
  parameters with reasoning settings.
- `reasoning_effort` and `thinking_budget` / `thinking_level` are **not
  combined**; the profile loader rejects such profiles.
- `google_thinking_config` is a **future extension only** and is not used in
  the initial 30-task pilot. Its wire form, when used, is
  `extra_body.google.thinking_config` (never a top-level `thinking_config`);
  `thinking_level` is rejected for `gemini-2.5-pro` profiles and
  `include_thoughts: true` is forbidden in baseline profiles.

### 3.2 What the probe does NOT require

The initial probe does **not** require demonstrating output differences caused
by setting values as positive evidence. Setting-difference behavior is treated
as informative, not gating.

### 3.3 Minimal probe checklist (7 items, after budget approval)

1. Model ID returned in responses (matches `gemini-2.5-pro`).
2. Usage metadata retrieval.
3. Finish-reason retrieval.
4. Actual response shape (fields needed by the manifest).
5. Rate-limit behavior.
6. Billing display for the probe requests.
7. **Acceptance** of `reasoning_effort` (request is not rejected).

Probe inputs are self-authored prompts, never benchmark task text. A probe
cost ceiling is approved by a human beforehand (recorded under GNG-013).

### 3.4 GO / switch / exclusion conditions

- **GO (compat endpoint)**: all 7 probe items pass, and GNG-010 confirms
  publication terms. `access_path: openai_compatible` +
  `access_path_verification` (date, result) recorded in the manifest.
- **Switch to native provider**: the compat endpoint fails item 1–4 or 7
  (metadata or acceptance failure). A `GeminiNativeProvider` is implemented
  and verified against the native API before any Gemini evaluation runs.
- **Exclude from the initial baseline** (recorded publicly with reason and
  date): (a) neither compat nor native path yields the required metadata and
  accepted frozen settings; or (b) publication terms prohibit named results;
  or (c) no version/retrieval metadata can be recorded to mitigate
  stable-version drift. Evaluation must not start with uncontrolled decoding
  settings (`baseline_experiment_plan_v1.md` Section 4a.4).

## 4. Hosted Open-Weight Adoption — Stop Rules (GNG-006 / GNG-007)

### 4.1 Mandatory disclosures

A hosted provider is adoptable only if all of the following are concrete
(documented or contractually stated) at config-freeze time: serving model ID;
source repository (must match the official HF repo); revision / commit hash;
quantization (and serving precision); provider terms (including data
retention/training use); result publication terms.

### 4.2 Stop rule

If **any** of the six items above is `unknown`, adoption of that model into
the official initial baseline **stops**. This rule is also enforced
mechanically: the baseline config loader and manifest validation reject
hosted-OSS entries with unknown adoption-condition fields.

### 4.3 Change recording

- **Provider change (same model)** is an *access-path change*: recorded in
  the manifest (`access_path`, `access_path_verification`) and in this
  register, without a protocol revision.
- **Model substitution** (replacing the model itself) requires a **new
  experiment ID or protocol revision** and a public substitution record
  (original model, reason, decision date, decided-by).

## 5. Swallow / vLLM / RunPod (GNG-008)

### 5.1 GO conditions

1. HF revision pinned by commit hash (`tokyotech-llm/Qwen3-Swallow-32B-RL-v0.2`);
   no `main`-tracking downloads.
2. The **private** run record captures: GPU model and count, driver version,
   CUDA version, container image digest, vLLM version, PyTorch version,
   Python version, tokenizer and transformers versions, dtype, tensor-parallel
   size, and the full launch command line.
3. The **public** manifest carries only the reproducibility subset of that
   environment information (`baseline_manifest_spec_v1.md` Section 3.6 vLLM
   block).
4. GPU configuration, region, and prices are recorded **as of the execution
   date**; no fixed prices are baked into protocol documents (observed
   2026-07-05 market prices inform the budget estimate only).
5. The 80GB-class GPU requirement is an **estimate** (bf16 33B weights ≈ 66 GB
   plus KV cache); before execution, the chosen vLLM version's model support
   and actual load feasibility are confirmed, and observed VRAM is recorded.

### 5.2 Never published

Pod ID, endpoint URL, IP address, SSH keys, API keys, account identifiers,
and billing statements (per `public_artifact_policy_v1.md` Section 3.2).

### 5.3 Fallbacks

Same-class alternative GPU or region change (recorded, no protocol impact).
If no 80GB-class GPU is obtainable and the quantized fallback (AWQ) is
rejected, Swallow is `excluded` from the pilot with a public record.

## 6. Pilot Start Verdict Criteria

The 30-task pilot may start only under **GO**. Verdicts:

- **GO** — all of:
  1. IDs/snapshots of every required model and judge are frozen (GNG-001–004,
     011; GNG-002 resolved).
  2. Publication terms confirmed for every provider in scope (GNG-010).
  3. Hosted OSS: required metadata fully obtainable (Section 4.1), or the
     slot is `excluded` with a public record.
  4. Gemini: adopted (Section 3.4 GO) or `excluded` — decided, not pending.
  5. API tiers, rate limits, and the budget ceiling are recorded
     (GNG-012, GNG-013).
  6. RunPod configuration decided, or Swallow `excluded` (GNG-008).
  7. **Runnable real-model configs are created only after** conditions 1–6
     hold; no runnable config exists before GO.
- **CONDITIONAL** — documentation review is complete but the minimal probe
  (GNG-005) or human terms/budget confirmations (GNG-002, 009, 010, 012, 013)
  remain. Implementation may proceed on fake-transport tests only.
- **BLOCKED** — any of: provider wire specification and the implementation
  are not aligned; revision / quantization / publication permission is
  `unknown` for a slot that has not been excluded; budget unapproved; API
  access undetermined. No real-API call is made while BLOCKED.
- **EXCLUDED** (per model) — a model that fails its conditions is dropped
  from the initial baseline; the exclusion reason, date, and whether a
  substitute exists are recorded publicly (manifest + this register), and the
  baseline proceeds with the remaining models.

**Current verdict (2026-07-05): CONDITIONAL** — documentation review complete
(GNG-001, 003, 004 verified; GNG-008, 011 conditional); pending items are
GNG-002, 005 (probe), 006, 007, 009, 010, 012, 013.

(日本語) 本レジスタは、30問パイロット開始前に解決すべき外部依存の正典記録である。現時点の判定は CONDITIONAL — 文書調査は完了(GPT-5.5・Opus 4.8・Sonnet 5 は verified)だが、gpt-5.4 スナップショット再確認、Gemini 最小プローブ、hosted OSS 提供者選定、公開規約の人間確認、レート制限・予算承認が残る。実モデル用 runnable config はこれら全ての解決(GO)後に初めて作成する。

## 7. Versioning

This register is versioned (`baseline_go_no_go_register_v1`). Status changes
are recorded by updating the table with a new `verification_date`; material
rule changes require a new version. The register in force at pilot start is
cited by the run manifest's protocol section.
