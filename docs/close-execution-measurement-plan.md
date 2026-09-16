# Prospective close-execution comparison

Run all eight fixed cases in `data/close-execution/tasks.json`, version
`0.14.0-close-execution.1`, in manifest order. One attempt each for GPT-5.4 and
GPT-5.5: sixteen attempts total. This plan is recorded before the first response.

Both models use xhigh reasoning, the same tool-only background adapter, no code
interpreter, 128,000 output tokens per response, 400,000 output tokens per episode,
and a 5,400-second episode timeout. Each individual background generation has
a 1,800-second deadline. HTTP operations time out after 60 seconds; three
consecutive failed polling reads terminate observation. No automatic generation
retry or score-based replacement attempts. Preserve all failed/interrupted runs.

Freeze package, adapter and manifest hashes; archive source and audit/report
scripts. Do not change these inputs during measurement. Replay completed traces
and verify score and final-state hashes before publishing results.

Primary metric: strict end-to-end success. Also report publication, close-ledger
reconciliation, exception and recovery errors, raw partial credit, token usage,
wall time and infrastructure/resource failures. Do not treat a missing response
or truncation as evidence of an incorrect business decision. Report all eight
case outcomes per model, not just difficult or favorable cases.

These are public development cases, not held-out generalization evidence.
Do not pool results with earlier benchmark versions or infer a general model
ranking from this small suite. A high score remains a valid result; the objective
is meaningful workflow difficulty, not a predetermined model failure rate.
