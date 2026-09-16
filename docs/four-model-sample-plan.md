# Four-model sample: $100 maximum authorization

Requested models: `gpt-5.4`, `gpt-5.5`, `claude-opus-4-7`,
`claude-sonnet-4-6`. No substitutions. This is a new experiment, separate from
all prior spending and interrupted runs.

Use the corrected `data/close-execution-v2/tasks.json` population of eight cases.
Before any paid response, select two without replacement using
`random.Random(20260916).sample(range(8), 2)`, sorted: indices 0 and 5,
`faraday-close-execution-001` and `faraday-close-execution-006`.
Do not reselect based on earlier case results. These are whole workflows, not
cherry-picked successful steps. All four models receive exactly those cases.

Reserve at most $90 for requests, leaving $10 of the authorized $100 unused as
headroom. Allocate $22.50 per model and $11.25 per model-case. No transfers between
models or cases, automatic reruns, silent retries, or overspend after interruption.
Before every paid request, persist a conservative input/output cost reservation.
Unknown charges remain reserved. Reconcile only confirmed provider usage. Abort
before submission when a request cannot fit. The reservation ledger must be wired
into both provider adapters and integration-tested before any paid launch.

The request budget is not a promise that every model will complete both cases.
Report budget exhaustion separately from business mistakes. Provider tokenizers
and reasoning controls differ: equal dollars are a cost-constrained comparison,
not equal inference compute. Record the exact provider settings before launch.

Primary outputs: completed strict success, publication and execution status,
dimension-balanced diagnostic scores, actual costs, and infrastructure/resource
failures. Preserve the exact frozen version and all traces. Do not retroactively
regrade old paid attempts with the revised grading rules.

Extrapolate total cost to this eight-case population as eight times each model's
mean cost on the two sampled cases, explicitly conditional on the chosen budget.
If a case stops at its budget, this estimates capped-run cost, NOT the cost to
finish. Report per-case costs and the broad uncertainty from n=2. Do not present
two cases as an accurate general capability ranking or extrapolate to the full
multi-family benchmark. Report observed success counts with uncertainty rather
than fabricating outcomes for the six unsampled cases.

Launch gates: complete regression, subprocess schema parity, semantic exclusion
tests, independent numerical controls, provider adapter/budget integration tests,
authenticated availability for all four exact models, and secure local keys.
The pasted Anthropic credential is not stored in this repository; a replacement
must be supplied locally as ANTHROPIC_API_KEY. No paid sample has started.
