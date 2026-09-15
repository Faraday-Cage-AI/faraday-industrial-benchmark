# Public Artifact Policy v1

Status: **Canonical policy document.** The short "Public Artifact Policy" lists in `README.md` and `CONTRIBUTING.md` are summaries; where they differ from this document, this document prevails. Related documents: `baseline_experiment_plan_v1.md`, `baseline_manifest_spec_v1.md`, `contamination_policy_v1.md`, `versioning_policy.md`.

---

## 1. Purpose

This policy defines what may and may not be committed to the repository or otherwise published. It protects raw model outputs, judge texts, credentials, and internal mappings, while — through one limited exception — allowing the reproducibility information required to run and publish an official *initial public benchmark baseline*.

## 2. Base Policy

Unless covered by the limited exception in Section 3, do **not** commit or publish:

- raw model answers
- outputs under `results/`, `results_v2/`, `datasets/results/`, `experiments/**/runs/`
- judge inputs or judge outputs
- provider-specific evaluation results
- internal model-name mappings
- private reports
- API keys, `.env`, tokens, credentials

## 3. Limited Exception — Documented Official Baseline Runs

This exception applies **only** to official baseline experiments that are documented under a frozen protocol, specifically runs executed under `baseline_experiment_plan_v1.md` and recorded per `baseline_manifest_spec_v1.md` (or successor versions of those documents). It exists so that official baseline results are reproducible and auditable.

### 3.1 Publishable for official baseline runs

- Official model IDs of the evaluated models.
- Model providers.
- Execution dates and the experiment start timestamp.
- Model snapshot, revision, or retrieval date.
- Dataset git commit hash.
- SHA-256 of `data/v2/test.jsonl`.
- Hashes of experiment configuration files and decoding profiles.
- Primary inference settings.
- The publishable setting values of provider-native decoding profiles.
- `request_echo` as **redacted execution metadata** (allowlist defined in Section 3.3) — not raw request payloads.
- The list of parameters deliberately not sent.
- Judge model ID, judge schema hash, and the judgement protocol version.
- Aggregated scores, confidence intervals, and per-model / per-layer aggregates.
- Aggregated contamination signals (per `contamination_policy_v1.md`).
- The experiment protocol documents and the public manifest.

### 3.2 Still private, even for official baseline runs

- Raw answer texts.
- Full answer prompts, prompt transcripts, and full request payloads (entire request bodies).
- System prompt texts and user prompt texts; any payload text containing scenario, question, reference answer, or rubric content; tool input texts.
- Judge input texts.
- Judge output texts, including raw `judge_summary` and `evidence_summary`.
- HTTP headers.
- API keys, credentials, and endpoint secrets.
- Provider request IDs, provider response IDs, account identifiers, and provider-internal log identifiers.
- Billing details, account information, and internal rate-limit information.
- The `model_A`–`model_F` anonymization mapping.
- Raw GitHub Insights screenshots and raw Hugging Face metrics API responses (aggregates may be published per `contamination_policy_v1.md`).
- Texts or per-item records flagged by n-gram overlap detection.
- Artifacts of in-progress development runs, failed runs, and unpublished trials.
- Detailed connection information for cloud GPU environments (e.g., RunPod).
- Provider-side logs and internal identifiers not suitable for publication.

### 3.3 `request_echo` Publication Boundary

`request_echo` does **not** mean storing or publishing raw request payloads. The `request_echo` included in a public manifest is **redacted execution metadata**, restricted to the following allowlist:

- provider kind
- API kind (`responses` / `messages` / `chat_completions`)
- official model ID
- decoding profile ID / hash
- the sampling / reasoning / thinking setting values actually sent
- the list of parameters deliberately not sent
- max output tokens
- whether structured output was enabled
- schema hash
- retry policy summary

Everything outside this allowlist — in particular system prompt texts, user prompt texts, payload texts containing scenario / question / reference answer / rubric content, tool input texts, entire request bodies, HTTP headers, API keys, endpoint secrets, provider request IDs, provider response IDs, account identifiers, and provider-internal log identifiers — is **never** included in a public `request_echo`.

If a raw request payload is stored at all, it is a **private run artifact** governed by Section 3.2 and the base policy. Implementations must include tests verifying that public manifests contain no `request_echo` fields outside this allowlist.

## 4. Scope Clarifications

1. The exception applies **only** to documented official baseline experiments as defined in Section 3. 
2. The initial public benchmark baseline is **not an official leaderboard**; publishing its results under this exception creates no leaderboard obligation or infrastructure.
3. Publication of any result under this exception is conditional on prior confirmation of each provider's terms of service, each hosting provider's terms, and each model's license. The dated record of these confirmations is `baseline_go_no_go_register_v1.md` (GNG-010).
4. **Where a provider's or license's terms restrict publication, those terms take precedence over this policy exception.** The affected artifact is then withheld or reduced to a compliant form.
5. Development experiments, local trials, internal comparisons, and non-official runs (including runs using the legacy Fugu-compatible pipeline) remain governed by the base policy (Section 2) in full.
6. Future private held-out evaluations (P0-3) will follow a **stricter** non-disclosure posture than this public baseline; nothing in this exception extends to held-out tasks, answers, or results.
7. This revision is **not retroactive**: it does not apply to previously published artifacts or past runs, and it does not require re-publication or re-classification of any existing artifact.
8. This exception is versioned with, and interpreted against, `baseline_experiment_plan_v1.md` and `baseline_manifest_spec_v1.md`.

(日本語) 本例外は、凍結プロトコル下で文書化された正式 baseline 実験にのみ適用される。initial public benchmark baseline は公式リーダーボードではない。公開はプロバイダ規約・ホスティング規約・モデルライセンスの事前確認を前提とし、規約上の制約がある場合は本例外より規約を優先する。開発run・非正式runには従来ポリシーを全面適用し、将来の private held-out 評価には本 baseline より厳格な非公開方針を維持する。本改訂は過去の成果物・過去runに遡及しない。

## 5. Versioning

This policy is versioned (`public_artifact_policy_v1`). Material changes require a new version. Reports and manifests cite the policy version in force at run time.
