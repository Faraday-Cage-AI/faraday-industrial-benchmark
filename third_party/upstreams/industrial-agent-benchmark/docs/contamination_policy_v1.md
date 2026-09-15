# Contamination Policy v1

Status: Active for all official baseline runs of Industrial Agent Benchmark v2.2.0
Related documents: `baseline_experiment_plan_v1.md`, `baseline_manifest_spec_v1.md`

---

## 1. Purpose and Scope

This policy defines how Industrial Agent Benchmark records, detects, and reports the risk that evaluated models were exposed to the public benchmark data before evaluation. It applies to every official baseline run and to every public report of baseline results.

## 2. Definitions

- **Exposure**: the benchmark data being publicly retrievable (GitHub, Hugging Face) during a model's training data collection window.
- **Contamination**: benchmark tasks, reference answers, or rubrics actually present in a model's training data.
- **Memorization signal**: measurable evidence in model outputs consistent with contamination (verbatim reproduction, abnormal reference-answer overlap, benchmark self-reference).
- **Diagnostic baseline**: results on publicly available tasks, reported without claims of contamination-free generalization.

## 3. Exposure Status Statement

The following statement is the canonical exposure disclosure. It must appear in the baseline experiment plan, in this policy, and in every public baseline results report.

> Industrial Agent Benchmark v2.2.0 was publicly accessible but had not been formally announced or promoted when the initial baseline protocol was initiated. We therefore consider contamination risk to be low but not provably absent. Results on the public 180-task set are reported as a diagnostic baseline on publicly available tasks, not as evidence of contamination-free generalization.

(日本語) Industrial Agent Benchmark v2.2.0 は、初期ベースラインプロトコル開始時点で公開状態にあったが、正式な告知・広報は行われておらず、実際の利用を示す証拠も確認されていない。したがって汚染リスクは「低いが、皆無とは証明できない(low but not provably absent)」と位置付ける。公開180問での結果は「公開済み問題集合における診断的ベースライン」として報告し、汚染のない汎化性能の証拠としては主張しない。

## 4. Risk Assessment

- The dataset has been publicly retrievable on GitHub and Hugging Face.
- No formal announcement, promotion, or publication has occurred at protocol initiation time.
- No evidence of third-party usage has been observed.
- Therefore the working risk classification is **low but not provably absent**. This classification is a statement about evidence, not a guarantee; it must be re-assessed whenever the benchmark is announced, promoted, or shows usage growth.

## 5. Required Manifest Fields

Every official baseline run must record (see `baseline_manifest_spec_v1.md` for the schema):

1. Experiment start timestamp (UTC).
2. Dataset git commit hash.
3. SHA-256 of `data/v2/test.jsonl`.
4. Hashes of all experiment configuration files.
5. For every evaluated model: official model ID, provider, snapshot/version identifier, and retrieval or execution date.
6. Where ascertainable: the model's public release date and training data cutoff, each with its source and the date the source was consulted. Unknown values are recorded explicitly as `unknown`, never omitted.

## 6. Memorization Detection Procedures

For every evaluated model, the following indicators are computed over all 180 answers and reported in aggregate:

1. **Reference-answer n-gram overlap**: character n-gram overlap rate between each answer and the task's public reference answer. Answers above the flag threshold are logged individually (privately) and counted publicly. The threshold is fixed in the experiment configuration before the baseline runs.
2. **Benchmark self-reference**: scan of answers for mentions of the benchmark by name ("Industrial Agent Benchmark", repository/dataset identifiers) or references to task IDs, rubrics, or reference answers as known artifacts.
3. **Abnormal verbatim reproduction**: detection of long verbatim spans from task scenarios, rubrics, or reference answers that the prompt did not contain.

Publicly reported: per-model aggregate rates and counts. Kept private: the matched text of individual flagged answers.

These indicators are evidence of memorization when positive; their absence is **not** proof of no contamination, and reports must not claim otherwise.

## 7. Usage-Evidence Snapshot Procedure

At baseline initiation (before the first pilot answer is generated), capture and archive as circumstantial evidence of the usage state:

- GitHub Insights: traffic (views, unique visitors), clones, stars, forks.
- Hugging Face dataset metrics: download counts and any available usage statistics.

Capture method: screenshots plus raw API responses where available, stored in a private archive with capture timestamps. Public reports cite the aggregate numbers and capture dates only. If a metric is unavailable at the required granularity, record that unavailability explicitly.

## 8. Claim Limitations

Public reports of results on the 180 public tasks must:

- Use the phrase *diagnostic baseline on publicly available tasks* (公開済み問題集合における診断的ベースライン) or equivalent.
- Include the Section 3 statement verbatim.
- Not describe the results as contamination-free, held-out, or unseen-task performance.
- Present memorization indicators alongside scores.

## 9. Relationship to the Private Held-out Split

A private held-out split of 30–50 tasks is planned as an independent workstream (P0-3). Held-out tasks will be **newly authored**, not drawn from the existing 180 public tasks. Completion of the held-out split is explicitly **not** a precondition for the initial public benchmark baseline.

## 10. Reporting and Versioning

- Every baseline results report must include: the Section 3 statement, the manifest fields of Section 5, the detection aggregates of Section 6, and the usage-evidence summary of Section 7.
- This policy is versioned (`contamination_policy_v1`). Material changes require a new version, and reports must cite the version in force at run time.
