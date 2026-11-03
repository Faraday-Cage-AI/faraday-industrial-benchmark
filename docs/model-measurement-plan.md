# Full-suite learned-agent measurement gate

Status: deferred at the user's request on November 3, 2026; no new paid requests
authorized or launched in this completion pass. Current results are algorithmic qualification. Historical model
tables are preserved as reported summaries; their absent raw episodes cannot be
recovered by rerunning a different engine or relabeling a new attempt.

Before execution, record the user's selected model identifiers and total API
spending cap. The research lead role explicitly reserves budget decisions to the
user and prohibits unbudgeted paid runs. Credential availability alone does not
establish a spending limit. No specific provider/model is required by the suite.

The concrete experiment is one attempt on every one of the 249 public tasks per
selected model, in manifest order. Two models therefore require 498 episodes.
All 46 families must be represented. No task selection may depend on pilot scores.
Publish the task mean plus all family slices, strict-success and critical-failure
rates, infrastructure failures, observed API usage/cost and latency. Disclose the
175 fixed distributor fixtures' approximately 70% task weight. Do not infer
private-instance generalization or superiority from this public development run.

Freeze before the first request:

- The archived 0.8.0 engine, complete task manifest, fixtures, schemas and input hashes.
- Exact model identifiers, adapter bytes, system/user prompts or their archived
  generation code, inference settings, tool scope, network policy and SDK versions.
- Per-response output limit, per-episode token/wall-time/tool budgets, concurrency,
  and a request-level pre-reservation mechanism enforcing the approved total cap.
- One attempt per task, all scheduled/failed/interrupted attempts retained, no
  automatic retries that can duplicate ambiguous billable requests, no best-of selection.

Use an isolated external process receiving only the public task and tools; mount
no evaluator source, seeds, fixtures, expected answers or model credentials into
that process beyond what its own provider adapter requires. Built-in references
are evaluator-side qualification and cannot be used as the evaluated agent.

Save each episode and usage log atomically to a new path, then replay the whole
run with the frozen engine. Record omitted/unscheduled tasks if the cost or time
cap is reached. A capped partial run remains a partial result; it never receives
a 249-task full-suite label. Infrastructure failures remain in the record and
are distinguished from business errors. Optional development tracks are separate
experiments with separate versions and coverage.

Accept a full-suite result only when every scheduled attempt is accounted for,
all 249 episode traces and aggregate totals verify, model/configuration evidence
is present, the usage ledger reconciles within its declared estimation limits,
and exclusions or retries are disclosed. Repeated trials, if separately budgeted,
must report all-attempt and per-task stability instead of only the best attempt.
