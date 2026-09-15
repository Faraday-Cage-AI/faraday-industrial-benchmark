# Judge Validation Plan v1 (P0-2)

Status: Planned phase, executed **after** the Stage-1 baseline report (see `baseline_experiment_plan_v1.md`, Section 9)
Related documents: `baseline_experiment_plan_v1.md`, `evaluation_methodology.md`, `judge_schema_v2.md`, `baseline_go_no_go_register_v1.md` (judge model/snapshot readiness: GNG-002, GNG-004, GNG-009)

---

## 1. Purpose

The initial public benchmark baseline is scored by an LLM judge whose agreement with human experts has not yet been measured. This plan defines the human validation study that converts the Stage-1 report (published with the explicit limitation *"judge validity not yet human-verified"*) into the Stage-2 revised report.

## 2. Sample Design

A stratified sample of judgements is drawn from the completed 180-task × 6-model baseline. Stratification dimensions:

| Dimension | Strata |
|---|---|
| Layer | Knowledge / Reasoning / Agent |
| Difficulty | 1–2, 3, 4, 5 (collapsed where sparse) |
| Model group | Frontier / open-weight large / Japanese-focused |
| Judge-predicted score band | 0–1 / 2–3 / 4–5 |
| Critical failure | triggered / not triggered |

- Target size: approximately **300 judgements**, allocated to cover every populated cell, with oversampling of critical-failure-triggered and boundary-score (2–3) judgements, where judge errors matter most.
- Sampling is deterministic given a recorded seed and the frozen baseline outputs, so the sample is reconstructable.

## 3. Human Raters and Blinding

- **Raters**: at least **2 independent raters with manufacturing practice experience** (quality, production engineering, or manufacturing management). Rater profiles (years and domain of experience, stated in general terms) are published; identities need not be.
- **Independence**: raters score independently, without seeing each other's scores or the LLM judge's output.
- **Anonymization**: model identities are anonymized for **both** the human raters and the LLM judge (`model_A` … `model_F`). Raters receive: scenario, question, rubric (must-have / nice-to-have / critical failures, plus v1.1 extension fields where present), reference answer, and the anonymized answer — the same information surface as the judge.
- Raters apply the same frozen scoring rules (critical-failure override → score caps → matrix) using a written rater guide derived from `evaluation_methodology.md`.

## 4. Agreement Metrics

Computed between each human rater and the judge, between the two humans, and between the human consensus and the judge:

1. **Weighted kappa** (quadratic weights) on the final 0–5 score.
2. **Critical-failure detection**: precision and recall of the judge's `critical_failure_triggered` against human judgement, with Wilson intervals.
3. **Component-level agreement**:
   - must-have missing counts (exact and ±1 agreement),
   - score-cap application (agreement rate),
   - generic-penalty and structured-output components where applicable.
4. Mean signed score difference (judge − human) overall and per stratum, to quantify systematic over/under-scoring.

Human–human agreement is the reference ceiling; judge–human agreement is interpreted relative to it.

## 5. Disagreement Analysis

All judgements where |judge − human consensus| ≥ 2, or where critical-failure decisions differ, undergo qualitative coding to identify **task types where the judge systematically over- or under-scores**, for example:

- numeric-reasoning tasks (calculation checking),
- safe-deferral / HIL-boundary tasks (does the judge reward confident action over correct deferral?),
- long structured JSON answers,
- answers using non-Japanese-QC framings that are substantively valid,
- generic-but-fluent answers (is the generic penalty actually applied?).

The output is a typology of judge failure modes with frequency estimates, feeding rubric or judge-template revisions for the next benchmark version.

## 6. Second-Judge Sensitivity Analysis

Because the baseline does **not** require provider separation between the judge and evaluated models, this phase includes a second-judge analysis:

- The second judge is **`claude-sonnet-5`**, from a different provider/family than the first judge (`gpt-5.4`). It re-scores the same stratified sample under the identical frozen protocol: the same judgement inputs, anonymization (`model_A`…`model_F`), and scoring rules.
- Decoding follows each judge's provider-native frozen profile (`baseline_experiment_plan_v1.md` Section 4a; `baseline_manifest_spec_v1.md` Section 3.6). For `claude-sonnet-5`: `effort: high` pinned; adaptive thinking as provider default; `temperature` / `top_p` / `top_k` and manual extended thinking / `budget_tokens` are not sent (Sonnet 5 does not support manual thinking budgets or non-default sampling parameters). Schema conformance is enforced via tool use, since Anthropic does not provide OpenAI Structured Outputs; the enforced schema is identical to the first judge's frozen judgement schema.
- Reported: judge–judge weighted kappa, per-stratum score deltas, and specifically whether either judge scores same-family evaluated models differently (self-preference check).
- The disclosed same-provider pair — first judge `gpt-5.4` with evaluated model `gpt-5.5` — is the primary focus of this check; the second judge's own family overlap with evaluated model `claude-opus-4-8` is disclosed and examined symmetrically.

## 7. Outcomes and Publication

- **Stage-2 revised report** adds: agreement statistics (Section 4), disagreement typology (Section 5), second-judge sensitivity results (Section 6), and any resulting reinterpretation of Stage-1 numbers. Stage-1 scores are not silently changed; recalibrations, if any, are reported as such.
- Published artifacts: the rater guide, aggregate agreement statistics, anonymized disagreement typology with counts.
- Private artifacts: raw rater score sheets tied to identifiable answers, rater identities, all answer and judge texts (per the Public Artifact Policy).

## 8. Open Parameters (fixed before this phase starts)

- Final sample size and per-stratum allocation (depends on realized baseline score distribution).
- Rater recruitment channel and compensation.
- The exact flag thresholds for the disagreement analysis (default: |Δ| ≥ 2).
