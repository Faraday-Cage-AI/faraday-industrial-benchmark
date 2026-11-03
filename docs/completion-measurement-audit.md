# Completion measurement audit

Audit date: 2026-11-02 (America/Los_Angeles). Scope: the v0.7.0, 249-task
public suite and its reporting contracts. This is an independent measurement
review, not a claim of comprehensive industrial validity or a new model run.
Observed issues below describe the baseline inspected before completion fixes;
resolution evidence must be appended rather than erasing the observations.

## Assessment

The public manifest contains 249 development tasks in 46 families. The saved
qualification report records 249 strict reference successes, no-op 10.76,
read-only 11.75, and unauthorized-write 0.00. These are qualification controls,
not learned-agent results. README and the benchmark card correctly identify the
six-model table as historical v0.6.0 (74 tasks). It cannot establish current-suite
performance. Existing optional decision-v3 model results apply to their separate
eight-case contract and must stay separate.

The suite supports testing against its disclosed synthetic contracts, subject to
the defects and limits below. Current evidence does not support “fully accurate,”
complete industrial coverage, independent derivability of every reference answer,
a secure hosted leaderboard, or a current full-suite model ranking.

## Observed defects and acceptance criteria

### P1: fabricated final citations can receive strict success

`grader._check` handles `finish_evidence` by counting entries, without checking
whether they identify records. `world._tool_finish` already deduplicates entries,
so duplicate evidence is not the bypass. In an otherwise unchanged reference
trajectory, replacing finish evidence with 30 distinct strings `fake-record-0`
through `fake-record-29` yielded 100.00 and strict success on every one of the
28 tasks in 14 families using this check. This directly contradicts their public
requests for supporting record IDs.

An additional 34 tasks in 17 core families have no final-evidence criterion.
Replacing all their final citations with one nonexistent identifier also preserves
strict success. They may have correct operational state, but their final citation
quality is unmeasured. Do not conflate this with complete failure of the underlying
business work.

Reproduction: wrap `OracleAgent` with a tool proxy that passes calls unchanged
except `finish`, whose `evidence` argument is replaced as above, and run through
`BenchmarkRunner`. Select count-only tasks by constructing `IndustrialWorld` and
checking for `check == "finish_evidence"` in its criteria.

Acceptance: count distinct identifiers of real business records; fabricated IDs
must not satisfy evidence requirements. Require such a check wherever the task
promises auditable supporting IDs, or explicitly disclose the unmeasured behavior.
Test genuine identifiers, false identifiers, duplicates, and mixed sets. The
recall-finance reference currently cites a period key without an `id` field:
resolve legitimate business keys or replace it with a real journal/approval ID,
rather than treating arbitrary scalar values as records. Preserve historical
scores and version changes to scoring separately.

### P1: replay can certify a tampered headline

`cli.cmd_replay` compares authoritative per-episode task contracts, scores,
state hashes, final answers, and applied events. It does not validate saved
`summary`, `family_summaries`, or `capability_summaries`.

Reproduction: generate a one-task `NoopAgent` run (episode score 10), change its
headline mean to 100 and strict successes to 1, clear family/capability summaries,
and call `cmd_replay` against the original manifest. It returns exit code 0 and
`exact_match: true`. No episode trace needs to change.

Acceptance: recompute aggregate fields from replayed episodes and reject any
changed or absent summary. Also reject duplicate or missing expected task IDs
when certifying full-suite coverage. A trace replay for a subset must be labeled
as that subset; a file name or editable top-level label does not certify coverage.

### P1: scoring deadlines and efficiency allowances are undisclosed in core tasks

For `faraday-quality-001`, the public task reveals a 60-minute horizon and a
30-call budget. Its `get_incident` response omits the actual 24-minute economic
finish target and 18-call efficiency allowance. `grader._economic_score` uses
the former as a strict-success gate; `efficiency_target` supplies the latter.
The public metadata therefore cannot distinguish the scored finish target from
the hard horizon. The earlier decision-contract audit already explains why a
hidden deadline invalidates a capability interpretation.

Acceptance: expose a structural scoring contract generated from actual evaluator
parameters, including target time, call allowance, clock costs, point components,
and strict-success conditions, while keeping expected instance answers sealed.
Audit every public family, not just a selected optional tier. Assert public versus
actual equality and exact-target versus one-minute-late behavior.

### P2: reference-oracle characterization overstates its independence

`agents.OracleAgent` says it uses “only agent-visible tool results.” All 175
Distributor Operations trajectories instead read evaluator-side fixture answers:

- `distributor.erp_buy._oracle`: fixture `oracle` plans;
- `distributor.erpbench100.reference_run`: `expected_answer` and `oracle_plan`;
- `distributor.gdpval_work.oracle`: `grader_fixture(...)["truth"]`, plus required
  read/table lists, submitting truth directly as artifact content.

The writes themselves use public tools, which demonstrates that a known solution
can execute under the contract. This does not independently show that an agent can
derive that solution from its visible records. It is not evidence that subprocess
agents receive hidden truth: these are evaluator qualification trajectories.

Accurate wording: “Distributor reference trajectories execute protected actions
through public tools using evaluator-side fixture answers and plans. Their scores
validate fixture/evaluator consistency and executability; they do not independently
establish derivability from agent-visible evidence.”

Acceptance: correct the agent docstring and benchmark card/qualification language.
For the stronger claim, implement independent reference calculation using only
visible inputs and test it with evaluator fixtures inaccessible. Reconstructing
175 reference solutions is a separate substantive solver/parser effort; renaming
or hiding their current fixture reads does not meet that criterion.

### P2: confirmed-pass material can be held without a score consequence

For `faraday-quality-001`, an otherwise normal oracle trajectory plus
`place_quality_hold` on confirmed-pass `LOT-5175-C` immediately before finish
returned success and still scored 100 with strict success (minute 20, inside the
24-minute target). `records_cover` verifies that all affected lots are held but
does not reject additional held lots; the economic mitigation check uses the
same subset condition. This is a scoring blind spot for unnecessary operational
containment, separate from the domain review's AP-hold reproduction.

Acceptance: specify whether precautionary holds of confirmed-pass scope are
allowed. If the task requires exact exposure containment, extra active holds
must fail an explicit criterion, with wrong-scope and correct-scope controls.
If intentionally permitting conservative holds, disclose that overcontainment
cost and final scope precision are unmeasured; avoid claiming least-disruptive
containment from this score.

### P1: historical learned-agent raw artifacts are absent from the checkout

README labels six v0.6.0 model scores as verified, but this checkout has no
corresponding per-episode traces or frozen configurations. The only learned-agent
run under `runs/` is `faraday-platform-gpt4o-optimized-full.json`, which identifies
v0.3.0 and 52 tasks. `reports/decision-v3-results.md` links
`runs/decision-v3-background-20260915/frozen-manifest.json` and claims a retained
source archive, but that entire directory is absent. The retained decision-v3
summary and audit JSON point to missing raw episode reports.

Acceptance: restore the actual original archives/traces with hashes and a replay
command, or label these as historical reported summaries whose raw replay
artifacts are unavailable in this checkout. Preserve the original numbers and
previous audit assertions as historical evidence; do not substitute a new run
for the missing original evidence or describe the current review as independently
verifying it. Optional-track measurements remain separate from the full suite.

### P2: default run provenance is incomplete

`runner.run_suite` saves task public descriptors, traces, state hashes, an agent
name, and runtime benchmark version. It does not bind the source tree, manifest
bytes, tool schemas, policy/adapter, inference settings, attempts, exclusions, or
execution environment. Private seeds are appropriately absent from public task
descriptors, but reproduction still needs an evaluator-side manifest or private
seed commitment. The CLI replays by looking up IDs in a separately supplied task
manifest. Source distributions changing under the same version can change grading.

Acceptance: freeze source/manifest/schema hashes, exact agent configuration,
attempt policy, runtime environment, and commands alongside each measurement.
Store private replay inputs securely or identify the public manifest by hash.
Make missing metadata visible in historical results rather than filling it with
invented values. A provenance envelope improves repeatability; it does not by
itself prove that historical agent configuration was correct.

## Coverage, sampling, and interpretation limits

- The plain mean is a task-weighted score: 175/249 (70.28%) Distributor Operations
  tasks dominate it, and 82/249 (32.93%) share buy-to-fulfill family structure.
  Report family slices and macro-family diagnostics alongside the unchanged
  official task-weighted aggregate. Do not retrospectively change weighting to
  obtain a preferred ranking.
- Distributor fixtures are fixed. A new seed reuses the same scenario and is not
  independent held-out coverage. Neither repeated identical oracle runs nor
  seeds over fixed fixtures justify a confidence interval for novel industrial
  work. Use task/family clusters when quantifying uncertainty and disclose the
  target population rather than pretending all rows are independent.
- GDPval conversion scores mechanical structured fields and excludes 157/1,189
  source rubric items. It does not establish native spreadsheet/file authoring,
  presentation quality, or free-form professional judgment. The card already
  discloses this; preserve that qualification in results.
- No-op/read-only/unsafe controls establish coarse discrimination only. Add
  plausible incomplete and overbroad-but-approved actions, wrong values, stale
  source selection, and false citations. Oracle success alone cannot detect a
  shared reference/grader error. The domain review independently reproduced
  overbroad receiving/AP holds scoring 100 (coordinate that fix separately).
- Structured document facts do not establish visual PDF/CAD/BIM interpretation,
  plant safety, regulatory compliance, or real-world ROI. No bounded test pass can
  establish complete industrial coverage.
- The local arbitrary-executable runner is cooperative and unsandboxed. The
  threat model explicitly requires separate isolated agent and evaluator runtimes
  for a public leaderboard. Do not describe local protocol isolation as secure
  submission isolation.

## Verification performed

Read current manifests, benchmark card, scoring, tracks, threat model,
decision-contract audit, runner, grader, models, core scenarios, distributor
reference code, qualification tests, and saved qualification/reference reports.
Executed the false-final-evidence controls through the real runner and the
aggregate-tampering replay reproduction using `PYTHONPATH=src python3`.
No paid inference was launched; no historical reports were overwritten.

## Resolution review

Independent review of the environment engineer's runner/world/tool-schema patch
found no substantive concern in its current scope. The reviewer ran
`.venv/bin/python -m pytest -q tests/test_runner_integrity.py tests/test_replay_and_protocol.py tests/test_command_schema.py`:
17 tests passed. These checks cover malformed calls, timeout/cancellation, failure
replay, post-finish calls, and trace index/clock tampering. They do not close the
separate headline-aggregate validation defect.

The environment engineer also reproduced repeated allocation under a fresh
approval consuming stock twice, and implemented full preflight of current
inventory and order state before any mutation. The independent reviewer accepted
the conservation fix and ran
`.venv/bin/python -m pytest -q tests/test_network_conservation.py tests/test_world.py`:
28 tests passed, including repeat execution, changed stock after approval, split
stock rows, and atomic rejection of a missing later order.

### Integrated v0.8.0 review (2026-11-03)

The reviewer inspected the integrated grader, universal final-evidence gate,
public scoring contract, provenance envelope, authoritative verification helper,
CLI delegation, and distributor corrections. Findings below distinguish corrected
contracts from continuing limitations:

- **Citation bypass corrected:** all 28 former count-only tasks now reject both
  30 fabricated distinct IDs and 30 repetitions of one genuine ID: zero strict
  successes in either control (mean 97.43 because other completed work still
  earns points). The integrated completion test also verifies fabricated final
  citations cannot strictly pass any of the 249 public tasks, including those
  previously missing a citation criterion. The resolver excludes agent-authored
  content, citations, payloads and audit details as fabricated record registries.
  Its scope remains identifier existence, not proof that every cited record is
  relevant to a particular narrative claim.
- **Headline replay corrected:** authoritative reconstruction rejects cleared or
  changed summary, family and capability dictionaries, duplicate episodes,
  changed agent labels and changed manifest fingerprints. A correct two-task run
  replayed against the 249-task manifest succeeds as a two-task run while clearly
  reporting `covers_supplied_manifest: false`. A selected-episode verification
  explicitly identifies that scope; it is not whole-suite trace verification.
- **Public thresholds corrected:** actual runtime inspection confirmed all 249
  published time targets, efficiency allowances and final-evidence minima match
  the evaluator. The helper exposes thresholds and structural rules, without
  expected instance answers, optimal objective values, record IDs or reference
  assignments. Quality completion at minute 24 strictly passes with 100;
  completion at minute 25 scores 99.72 and fails strict success. Clock costs
  should remain derived from shared runtime constants to avoid future drift.
- **Overcontainment corrected:** the quality exact-scope criterion and the
  receiving/AP active-hold checker reject unnecessary hold scope. The latter
  also rejects duplicate active coverage while ignoring closed historical holds.
  These targeted fixes do not establish that every family's side effects have
  been exhaustively audited.
- **Cash timing corrected:** invoice dates and calendar-day payment convention
  are public, the importer generates the same convention as the evaluator, and
  the corrected sealed artifact uses actual calendar-quarter receipts. Both
  terms landing in the next quarter is explicitly disclosed; within-quarter
  liquidity differences remain unmeasured. The old Net-60 two-quarter lag fails.
- **Reference characterization corrected in code:** `OracleAgent` now explicitly
  identifies the distributor evaluator-side answer/plan dependency. The stronger
  independent derivability claim remains unsupported; documentation must retain
  that limitation.
- **New provenance improved:** recursively hashed source/fixture files, private
  task-manifest digest, public contracts, tool schemas, runtime and declared
  attempt policy now bind new runs to their local inputs. Generic executable
  model settings are accurately marked unspecified. A command digest does not
  hash every referenced external script/model or recover its configuration;
  these fingerprints are self-reported, not an identity attestation or a source
  archive. Frozen inputs and complete learned-agent settings still need to
  accompany any reproducible model comparison.

The independent reviewer ran
`.venv/bin/python -m pytest -q tests/test_completion_integrity.py tests/test_distributor_corrections.py tests/test_distributor_erpbench100.py tests/test_distributor_gdpval.py`:
240 tests passed and one integration assertion failed because its distributor
check-name convention did not yet allow the new shared `finish_record_evidence`
criterion. The failure was reported for parent integration; it is not a defect in
the calendar/AP business correction. Final full-suite regression and fresh
qualification results remain the integrating lead's responsibility.

Historical raw model artifacts remain unavailable in this checkout. None of the
fixes supplies a current full-suite learned-agent result, complete industrial
coverage, or independent calculation of all distributor reference answers.
A passing regression suite is necessary evidence but cannot establish those
stronger claims.
