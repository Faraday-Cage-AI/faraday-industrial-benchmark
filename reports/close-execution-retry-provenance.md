# Infrastructure-interrupted batch and authorized rerun

Original batch: `runs/close-execution-20260916`.
Authorized rerun: `runs/close-execution-retry-20260916`.

The user explicitly requested rerunning interrupted attempts after the original
launcher terminated. All sixteen original reports and traces are preserved.
The first case ran for approximately 43 minutes per model before transport
failures. Remaining cases failed at initialization, with one recorded tool call.
Launcher output reported APITimeoutError/APIConnectionError. These attempts are
infrastructure-affected, not completed capability measurements. Their raw scores
must not be represented as completed-task scores or evidence of model ranking.

The original reports' generic runner error markers are not a reliable root-cause
diagnosis: some say the 5,400-second deadline was exceeded although recorded wall
time is much shorter. Preserve this discrepancy; do not silently rewrite reports.

Before rerun, all source, adapter and task hashes matched the original freeze.
Authenticated model retrieval succeeded for both exact model IDs using the
benchmark virtual environment's SDK. The old unconfirmed GPT-5.5 background
response was retrieved and confirmed completed; it was not used to resume or
retroactively score the abandoned episode. An initial system-Python urllib probe
failed local CA verification; the actual benchmark SDK's verified TLS succeeded.
This does not establish the root cause of the original connectivity interruption.

Rerun all eight cases per model, once, from clean states with exactly the original
prompts, tools, grader and settings: xhigh, 128,000 response output, 400,000 episode
output, 5,400-second episode timeout and the unchanged background adapter.
No selection is based on a score. This is batch attempt 2; the unchanged launcher's
`measurement.attempt=1` means the first local attempt inside its new directory,
not the first historical attempt. This document supplies the cross-batch mapping.

Report the rerun separately. Include the original batch's 16 infrastructure-
affected attempts in reliability accounting and its recorded usage in cumulative
cost accounting; unknown usage from failed/unobserved requests remains unknown.
Do not average interrupted partial scores into completed-case model averages.
Do not silently discard fresh rerun failures or automatically replace them.

## Third batch, explicitly requested by the user

The second batch also terminated with transport errors on both first cases;
remaining cases failed at initialization. Preserve all sixteen reports at
`runs/close-execution-retry-20260916`. Both unconfirmed background responses were
subsequently retrieved and confirmed completed. Authenticated SDK connectivity
checks again succeeded for both models before the third launch.

Third batch: `runs/close-execution-retry2-20260916`. Same sixteen planned attempts,
same frozen tasks/package/adapter and model budgets. The launcher now uses
`--stop-on-agent-error`: each model stops scheduling later cases after a recorded
agent execution error, rather than consuming the rest of its queue during an
outage. This scheduling change does not change an episode's prompt or grading.
The batch is wrapped in macOS `caffeinate -i` to inhibit idle sleep while running;
this cannot prevent lid-close sleep or a network outage. It is not a claim that
sleep caused the previous failures. Third-batch results remain separate, with
both prior batches retained in infrastructure and cumulative usage accounting.
