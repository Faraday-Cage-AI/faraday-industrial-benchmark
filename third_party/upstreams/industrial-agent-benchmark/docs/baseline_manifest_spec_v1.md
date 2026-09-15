# Baseline Manifest Specification v1

Status: Normative for all official baseline runs
Related documents: `baseline_experiment_plan_v1.md`, `contamination_policy_v1.md`, `baseline_go_no_go_register_v1.md`, `versioning_policy.md`

---

## 1. Purpose

Every official baseline run produces a manifest that makes the run reproducible and its contamination context auditable. This document defines the required fields, their public/private classification, and validation rules. The manifest is machine-readable JSON.

## 2. Top-Level Structure

```json
{
  "experiment_id": "baseline_v2_2_0-run-01",
  "protocol": { ... },
  "dataset": { ... },
  "models": [ ... ],
  "judge": { ... },
  "contamination": { ... },
  "created_at": "<UTC ISO 8601>"
}
```

## 3. Required Fields

### 3.1 `protocol` (public)

| Field | Description |
|---|---|
| `experiment_plan_version` | e.g. `baseline_experiment_plan_v1` |
| `contamination_policy_version` | e.g. `contamination_policy_v1` |
| `answer_prompt_template_version` | frozen template ID |
| `answer_system_prompt_version` | frozen system prompt ID |
| `judge_prompt_template_version` | frozen judge template ID |
| `scoring_rules_version` | version of the critical/cap/matrix rules |
| `decoding_profiles_hash` | SHA-256 of the frozen per-model decoding profile file (`decoding_profiles`, Section 3.6); the blanket "temperature 0.0 for all models" rule is superseded |
| `retry_policy` | retry policy summary |
| `config_hashes` | SHA-256 of every experiment configuration file |
| `started_at` | experiment start timestamp (UTC) |

### 3.2 `dataset` (public)

| Field | Description |
|---|---|
| `release_version` | `v2.2.0` |
| `git_commit` | dataset repository commit hash |
| `test_jsonl_sha256` | SHA-256 of `data/v2/test.jsonl` |
| `task_count` | 180 |
| `dev_subset` | identifier of the public development subset (30 tasks) and its role restriction |

### 3.3 `models[]` (public, one entry per evaluated model)

| Field | Description |
|---|---|
| `public_model_id` | official model ID as published by the provider |
| `provider` | provider name |
| `snapshot` | version/snapshot identifier |
| `access_path` | API / hosted / local; for open-weight models: precision and quantization |
| `run_date` | retrieval or execution date |
| `release_date` | public release date, with `source` and `source_consulted_at`; `"unknown"` if not ascertainable |
| `training_cutoff` | training data cutoff, with `source` and `source_consulted_at`; `"unknown"` if not ascertainable |
| `inference_settings` | the model's frozen decoding profile as applied: see Section 3.6 |

Note: publishing `public_model_id`, `provider`, `run_date`, and `inference_settings` for official baseline runs is authorized by the limited exception in `public_artifact_policy_v1.md` Section 3, subject to provider/license terms taking precedence (see Section 5).

### 3.4 `judge` (public)

| Field | Description |
|---|---|
| `judge_model_id`, `provider`, `snapshot`, `run_date` | as for evaluated models (first judge: `gpt-5.4`) |
| `family_overlap_disclosure` | explicit statement of any provider/family overlap with evaluated models (required even if "none"); for this baseline: `gpt-5.4` (judge) and `gpt-5.5` (evaluated) share a provider |
| `anonymization` | statement that the judge received only `model_A`…`model_F` keys |
| `structured_output` | output-enforcement mode (OpenAI Structured Outputs, strict), judgement JSON schema file name and SHA-256 |
| `inference_settings` | the judge's frozen decoding profile as applied: see Section 3.6 |

### 3.5 `contamination` (public aggregates; individual flagged texts private)

| Field | Description |
|---|---|
| `exposure_statement_version` | reference to `contamination_policy_v1` Section 3 |
| `ngram_overlap` | per-model aggregate overlap rate with reference answers, flag threshold, flagged-answer count |
| `self_reference_count` | per-model count of benchmark self-references |
| `verbatim_reproduction_count` | per-model count of abnormal verbatim spans |
| `usage_evidence` | GitHub Insights and Hugging Face metrics: aggregate values, capture timestamps, capture method; `"unavailable"` recorded explicitly where applicable |

### 3.6 `inference_settings` — provider-native decoding blocks (public)

Every evaluated model and the judge record a decoding block. The protocol does **not** claim full determinism for any model; variance is measured by repeated runs (`baseline_experiment_plan_v1.md`, Section 4a.1).

**Common fields (all models):**

| Field | Description |
|---|---|
| `api_type` | `responses` / `messages` / `chat_completions` |
| `decoding_profile_id` | identifier of the frozen profile applied |
| `request_echo` | **redacted execution metadata** capturing the setting values actually sent, restricted to the allowlist in `public_artifact_policy_v1.md` Section 3.3 (provider kind, API kind, official model ID, decoding profile ID/hash, sampling/reasoning/thinking values sent, params not sent, max output tokens, structured-output flag, schema hash, retry policy summary). It is **not** a raw request payload: no prompt texts, no request bodies, no HTTP headers, no provider request/response IDs, no account or internal log identifiers. If raw payloads are stored at all, they are private run artifacts. |
| `params_not_sent` | parameters **deliberately not sent** (recorded by name); distinct from parameters merely unmentioned |
| `max_output_tokens` | fixed value |
| `determinism_claim` | fixed literal `"not_claimed_measured_by_repeats"` |

**OpenAI (`gpt-5.5` evaluated, `gpt-5.4` judge):**

| Field | Description |
|---|---|
| `reasoning_effort` | pinned value |
| `structured_outputs` | judge only: strict schema enforcement flag + schema SHA-256 |
| `seed_supported` / `seed_value` | verification result on experiment start day; `seed_value` only if supported |
| `system_fingerprint_sample` | response-side backend-configuration fingerprint values observed, for variance analysis (a backend configuration marker, not a provider request/response ID or account identifier — those are never published) |

**Anthropic — `claude-opus-4-8` (evaluated):**

| Field | Value / rule |
|---|---|
| `thinking` | `"adaptive"` — explicitly enabled; a run without adaptive thinking enabled is invalid for this baseline |
| `effort` | `"high"` — pinned |
| `params_not_sent` | must include `temperature`, `top_p`, `top_k` |

**Anthropic — `claude-sonnet-5` (second judge, P0-2):**

| Field | Value / rule |
|---|---|
| `effort` | `"high"` — pinned |
| `thinking` | recorded as `"provider_default_adaptive"` (not explicitly set) |
| `params_not_sent` | must include `temperature`, `top_p`, `top_k`, and manual extended thinking / `budget_tokens` |
| Constraint note | Sonnet 5 does not support manual thinking budgets or non-default sampling parameters; profiles must not attempt to set them |

Manifests use these exact setting names; generic phrasings such as "thinking type / budget" are not used.

**Google (`gemini-2.5-pro`):**

| Field | Description |
|---|---|
| `thinking_config` | pinned reasoning/thinking settings |
| `access_path` | `openai_compatible` **only if** the pre-pilot verification confirmed the frozen settings can be applied and required response metadata retrieved reproducibly via that endpoint; otherwise `native` (GeminiNativeProvider). Evaluation must not run with uncontrolled decoding settings. |
| `access_path_verification` | date and result of the pre-pilot Go/No-Go check (canonical record: `baseline_go_no_go_register_v1.md`, GNG-005) |

**Hosted open-weight (`Qwen3-235B-A22B-Instruct-2507`, `Llama-4-Maverick-17B-128E-Instruct`):**

| Field | Description |
|---|---|
| `temperature` / `top_p` | `0` / `1` |
| `seed_value` / `seed_honored` | pinned seed and the verification result (same-input repeat test) |
| `hosting_provider`, `hosted_model_id` | serving provider and its model identifier |
| `hf_repo`, `hf_revision` | Hugging Face repository and exact revision (commit hash) — adoption requires the provider can supply this |
| `quantization` / `serving_precision` | as disclosed by the provider — adoption requires disclosure |

**vLLM on cloud GPU (`Qwen3-Swallow-32B-RL-v0.2`):**

| Field | Description |
|---|---|
| `sampling_params` | full set (temperature 0, top_p 1, seed, max_tokens) |
| `environment` | GPU type/count, driver + CUDA versions, cloud instance type and region, container image digest, vLLM / PyTorch / Python versions, launch command line, `hf_repo` + `hf_revision`, dtype, tensor parallel size |

## 4. Validation Rules

- All required fields must be present; unknown values are the literal string `"unknown"`, never omitted or null.
- Timestamps are UTC ISO 8601.
- The manifest is written before answer generation (protocol/dataset/models/judge sections) and completed after scoring (contamination aggregates).
- The published manifest must be byte-identical to the archived one except for explicitly private fields, which are replaced by `"<private>"`.
- The public manifest's `request_echo` must contain **only** allowlisted fields (`public_artifact_policy_v1.md` Section 3.3). The implementation phase must include tests that fail if a public manifest emits any `request_echo` field outside the allowlist.

## 5. Public / Private Classification

The canonical classification is `public_artifact_policy_v1.md` (Section 3.1 publishable / Section 3.2 private). For this manifest:

**Public**: everything in Section 3 except the items below. Publication is conditional on prior confirmation of provider terms of service, hosting provider terms, and model licenses; where those terms restrict publication, they take precedence and the affected fields are withheld or reduced to a compliant form.

**Private** (never published or committed; `public_artifact_policy_v1.md` Section 3.2):

- The anonymization mapping (`model_A`… ↔ real model).
- Raw answer texts, full answer prompts and request payloads, and judge input/output texts (including raw `judge_summary` / `evidence_summary`).
- Individual flagged answer texts from contamination detection.
- Raw usage-evidence captures (screenshots, raw API responses) — archived privately; aggregates appear in the manifest.
- API keys, credentials, endpoint secrets, billing details, account and internal rate-limit information.
- Detailed cloud-GPU connection information (e.g., RunPod); provider-side logs and internal identifiers not suitable for publication.
- All development / trial run outputs, including development-subset scores.

This classification applies to documented official baseline runs only; it is not retroactive, and future private held-out evaluations (P0-3) follow a stricter non-disclosure posture.
