# Prospective close-chain V2 pilot

The first fixed case, `faraday-close-chain-001` (seed 91901), is selected before
any model response. Run one attempt each for GPT-5.4 and GPT-5.5. This two-attempt
pilot qualifies the larger workflow and execution interface; it is not an
eight-case benchmark result or a general model ranking.

Matched settings: xhigh; tool-only, without code interpreter; 128,000 output
tokens per response; 400,000 output tokens per episode; 5,400-second episode
timeout. The existing background adapter uses a 1,800-second generation deadline,
60-second HTTP operations and up to three consecutive failed polling reads;
generation is submitted once, with no automatic generation retry. These limits
must be disclosed if they affect completion. Neither prompt nor business answers
are customized for either model.

Primary outcome: strict end-to-end success. Also report approved publication,
cross-artifact consistency, individual business failures, raw partial-credit
score, elapsed simulated and wall time, usage, truncation and infrastructure
errors. A high partial-credit score is not successful publication. A truncated
response is not evidence that a business decision was wrong.

Before the first call, require the complete regression to pass; freeze task,
package and adapter hashes and archive the source plus audit scripts. During
measurement do not edit package modules, tasks or adapter. Replay both traces,
verify their saved scores and final state hashes, and inspect any actual failure.
Do not rerun simply because a score is high or low. Preserve failed or excluded
pilot attempts with their original settings and reasons. If a correction is
needed, version it separately instead of silently regrading.

This pilot alone cannot establish "insane" difficulty. A full, separately
reported coverage check and broader independent cases are necessary before
making strong difficulty or model-ranking claims. Prior decision-v3 attempts
must not be pooled with this workflow or these larger inference budgets.
