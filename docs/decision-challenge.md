# Joint-decision challenge (0.11.0-decision.3, qualification)

**V3 measurement complete and audited.** GPT-5.4 scored 73.37 with 3/8 strict
successes; GPT-5.5 scored 94.88 with 6/8. All 16 traces and scores replay exactly.
Read the [results and limitations](../reports/decision-v3-results.md): token limits
affected some GPT-5.4 outcomes, and one GPT-5.5 miss was an $18 aggregate tie-break.
These results do not establish extreme workforce difficulty.

The v2 audit found an undisclosed
timeliness target and opaque ledger-shape rejection. The completed pair passed
all business criteria and is diagnostic only, not a model ranking. See the
[required contract audit](decision-contract-audit.md) before running more models.

The v3 candidate is `data/decision-challenge-v3/tasks.json`. It preserves the
eight business problems and adds a public scoring contract, complete artifact
shapes, field-level shape errors, and explicit ledger annotation handling.
Finish by simulated minute 260 for full economic credit; the hard horizon remains
600. This is a validity repair, not evidence of an additional difficulty increase.
All 302 regression tests passed, including 19 public-contract tests. The matched
eight-case run is now `runs/decision-v3-background-20260915`, with a frozen source
archive, task and adapter hashes, and the same higher budgets documented below.
The full v3 development comparison is now available in the linked results report.

Eight fixed-seed public development cases extend the workforce suite. They are
not a held-out leaderboard and have not yet established frontier-model difficulty.

## Work required

Reconcile conflicting enterprise records, then jointly choose supplier capacity
reservations and irrevocable early-release modes before the disruption is known.
Prepare feasible recourse for eight disclosed outcomes, obtain authorization,
commit before the firming deadline, and execute only the realized branch with a
reconciled financial ledger and evidence trail.

Twelve orders compete for inventory, supplier capacity, emissions, certified
labor and treasury deposits. Customer service floors, paired installation kits,
qualification restrictions, carrier minimum loads, nonlinear service credits and
emergency activation charges interact. Two disclosed orders have a common mode
across every outcome, including any decision to defer; kit rules can bind their
partners as well. Other orders may adapt after the outcome is revealed.

The objective is minimum worst-case total cost, then minimum aggregate scenario
cost. All optimal ties are accepted. The public feasibility validator does not
return an optimal solution. Feasible but suboptimal policies can be committed;
optimality is graded separately. Deadlines are disclosed: commit by minute 180,
outcome at minute 200, horizon 600, at most 300 tool calls.

## What the design borrows

[BankerToolBench](https://joinhandshake.com/research/benchmarks/bankertool-bench/)
emphasizes end-to-end professional work, source navigation, multi-file
deliverables and practitioner-defined usefulness. This tier borrows the principle
of grading completed work, not merely an answer. It does not reproduce BTB's
investment-banker validation, native Office deliverables or task-duration claims.
No BTB task data or code is incorporated by this extension.

[Microsoft's master-planning documentation](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/master-plans)
describes freeze, firming and capacity time fences. The benchmark's common early
release is an explicitly synthetic no-cancellation contract inspired by that
planning distinction, not a claim that every ERP forbids all changes inside a
time fence. Other inherited exceptions are documented in
[the workforce suite](workforce-suite.md) and [long-tail suite](long-tail-suite.md).

## Qualification and limitations

All eight oracle workflows pass and replay exactly. The expanded v2 regression run
passes 283 tests, including commitment deadlines, batch auditing, timeout-marker
reconstruction and background transport. Summary tests verify that incompatible
settings cannot be pooled and incomplete responses remain visible. A reduced three-order, two-outcome exhaustive
enumeration independently checks the joint optimizer without using its dynamic
programming algorithm. Tests reject missing/extra early-release IDs, unknown
modes and declarations inconsistent with branch allocations, and accept reordered
allocation rows.

The hindsight ablation solves branches without the early-release constraint and
then checks that policy against the real contract. Its selected policy is rejected
on 8/8 fixed seeds. This is algorithmic evidence, **not a model failure rate**.
The joint constraint changes the optimal two-part objective on 6/8 cases; it
increases worst-case cost on two and changes the aggregate tie-break on four.
Cases 003 and 006 retain the same objective despite different feasible policies;
do not interpret every rejection as a strict increase in optimal cost. All seeds are
retained, without filtering on model performance.

The earlier operating-review V3 baseline was stopped after two completed cases
per model. Those four results are retained; only interrupted third-case attempts
are excluded. That near-ceiling partial baseline is not pooled with this tier.
All four saved baseline traces and scores reproduce exactly after the new tier
was added. See [the partial baseline report](../reports/researched-v3-partial-models.json).

A one-case-per-model pilot was started in `runs/decision-v1-pilot-20260915`.
The package source, adapter and eight-case task manifest were frozen before the
first call. GPT-5.4's first attempt ended at 22.56 after an incomplete 32,768-token
API response, without a submitted policy. GPT-5.5's pilot also scored 22.56 and
ended at its 1,800-second episode timeout without a policy. These are resource-
limited attempts, not evidence of incorrect business decisions. The diagnostic pilot
will be preserved separately from any higher-budget comparison; do not pool runs
with different budgets. The launcher now records configurable budgets in its
freeze, and the collection auditor rejects batches with different settings.

The full eight-case comparison was started in `runs/decision-v1-extended-20260915`.
Both models use xhigh, 65,536 output tokens per response, 200,000 per episode,
and a 3,600-second episode limit. The separately frozen extended adapter sets a
1,800-second request timeout and disables automatic retries, while preserving the
same prompts and tool protocol. It also records the provider's incomplete reason.
The original adapter remains unchanged for reproducibility of earlier runs.
No task or grading changes were made between the pilot and this comparison.

This synchronous comparison was stopped after both first-case adapters emitted
`APITimeoutError`. Those two outcomes remain infrastructure diagnostics; only
the two interrupted second-case attempts are excluded. Cases 003–008 never
started, so this is not a completed comparison. The observed sanitized errors
were returned by launcher session 59048 before its orderly shutdown.

A separately frozen background-request adapter is being qualified on case 001
for both models in `runs/decision-v1-background-pilot-20260915`, using the same
higher budgets. It submits once and polls the returned response ID, retries only
reads, logs request status, and attempts cancellation on interruption. Four offline
tests check single submission, transient-read recovery, cancellation and deadline
handling. This follows the documented
[background request pattern](https://developers.openai.com/api/docs/guides/background).
It does not change the task, grading, tools available to the agent, or prompts.

The background pilot completed and both traces replay exactly. GPT-5.4 scored
99.69 with strict success. GPT-5.5 scored 90.40 without strict success, but **both
models found and executed the optimal policy**. GPT-5.5's exception IDs and reason
codes were correct; extra explanatory `reason` fields caused exact-dictionary
comparison to fail. Its final citations also included descriptions around valid
IDs. These deductions do not establish inferior operational reasoning.

Original scores and the version-1 source archive are preserved. A separate
`data/decision-challenge-v2/tasks.json` contract is being verified: it explicitly
accepts `reason`, `notes` and `metadata` annotations without relaxing required
business values, and counts unique existing evidence IDs at token boundaries in
annotated citations. Wrong codes, invented IDs, duplicate exceptions and partial
ID matches remain invalid. No seed, optimization objective or operating constraint
was changed. The remaining cases have not been measured under this new contract.

After all 283 tests passed, the full v2 comparison was started in
`runs/decision-v2-background-20260915`: all eight fixed seeds, both requested
models, one attempt each, with the background adapter and the same higher budgets.
The manifest freezes all package modules, the adapter, task file and inference
settings. A source archive is saved beside it. The background adapter uses a
1,800-second generation deadline, 60-second individual HTTP calls, and at most
three consecutive failed retrievals; it never automatically resubmits generation.
Final results are not yet available. Do not combine v1 and v2 attempts.

Pilot costs cover only returned-response usage. In-flight requests killed by a
timeout, and any automatic retries in the legacy adapter, may incur costs that
are not present in the saved usage log. Do not treat the estimate as a complete bill.

### Interpretation fixed before the full comparison finishes

- Report all sixteen scheduled attempts, not best-of retries or selected cases.
- Primary outcomes are the existing score and strict success; additionally show
  feasibility, objective correctness, execution and reconciliation as diagnostics.
- Show response truncation, episode limits and infrastructure failures separately.
  A low score caused by a resource limit is not proof of bad operational reasoning.
- Replay every completed trace and verify saved scores and final state hashes.
  Check the frozen task, source, adapter and measurement settings before reporting.
- Keep the eight fixed public seeds, including nonbinding and easy cases. Do not
  modify the suite in response to a particular model's answers during measurement.
- Single attempts on correlated public variants do not support a broad model
  ranking, a statistical comparison with BTB, or a claim of workforce coverage.
- This is a tool-only track with no Python solver exposed to the agent. Results
  must not be presented as measuring every possible coding-enabled harness.

Reproduce qualification:

```sh
PYTHONPATH=src .venv/bin/python examples/qualify_decision_challenge.py --tasks data/decision-challenge-v2/tasks.json --output reports/decision-v2-qualification.json
.venv/bin/pytest -q tests/test_firm_release.py tests/test_decision_annotations.py
```

Results: [v2 algorithmic qualification](../reports/decision-v2-qualification.json).
Use `--tasks data/decision-challenge-v2/tasks.json` to select the current tier.
The v1 task manifest and original reports remain available for historical replay.
