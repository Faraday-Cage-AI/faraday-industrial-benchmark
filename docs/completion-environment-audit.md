# Environment completion audit

Audit date: 2026-11-02. Scope: shared simulator, external-agent JSONL,
tool capabilities, deterministic replay, and aggregate reconstruction.

## Observed defects corrected

1. **Protocol timeouts could hang.** A subprocess could write part of a JSON
   line and leave `readline()` blocked beyond the declared timeout. Writing a
   large start message could also block if the subprocess never read stdin.
   `CommandAgent` now uses nonblocking pipes with deadline and cancellation checks
   for both directions. Unterminated output is capped at 1 MiB. The runner reaps
   a process after terminating or killing it.
2. **Malformed calls bypassed trace and budget.** Non-object JSON arguments were
   rejected inside the protocol without entering the world. Raw dispatch now
   preserves the original payload, records its rejection, and counts it toward
   the same budget used by normal calls and replay.
3. **Finished-episode calls disappeared.** A call after `finish` returned a
   rejection without a trace entry. Those rejections are now recorded.
4. **Runtime failures could not replay.** Runner-injected `agent_error`
   violations changed authoritative state without a corresponding trace entry.
   The evaluator now records a reserved `_agent_error` event and reconstructs it
   during replay. This event is unavailable through the agent tool capability
   surface; an attempted external call receives the ordinary scope rejection.
5. **Trace metadata was not checked.** Replay previously compared only results
   and state hashes, accepting modified trace indices and logical minutes.
   Replay now compares the entire reconstructed tool-call record.
6. **Published primitive types were not enforced.** For example, an approval
   request with an array `reason` partially created an approval before crashing
   on a string operation. Agent-facing dispatch now validates disclosed JSON
   primitive types and typed array members before entering a handler. Semantic
   constraints and authorization remain handler checks; the validator does not
   consult hidden business answers.
7. **Aggregate reconstruction was duplicated.** `summarize_results` now computes
   task, family, and capability aggregates from serialized authoritative
   episode results. Normal execution uses this helper; CLI replay integration is
   assigned to the research lead.
8. **Network allocation could consume stock twice.** After a successful allocation
   exhausted both source DCs, a fresh matching approval allowed the same orders
   to be allocated again, producing stock balances of -60 and -40 in the
   reproduced public instance. Execution now preflights every order and the
   aggregate current stock at each source before any business mutation. Stock
   split across multiple rows is consumed once in total. Repeated allocations,
   post-approval stock loss, and a missing later order reject atomically.

These are evaluator changes in engine 0.8.0. Historical saved results remain
historical measurements; current-engine qualification must use fresh runs.

## Verification evidence

`tests/test_runner_integrity.py` exercises blocked input, partial output,
mid-line cancellation, output bounds, malformed arguments, post-finish calls,
reserved-event forgery, trace metadata tampering, and rejection before partial
approval mutation. It also checks exact replay and score equality for failure
episodes.

The targeted world/protocol/platform/schema/cancellation suite passed 47 tests
before the primitive type guard was added. A full 249-task reference execution
then produced 249 strict successes and 249 exact score-and-trace replays.
After adding the type guard and adapting the historical audit helper, the full
regression suite passed 903 tests in 135.50 seconds. The subsequent allocation
conservation change passed all 28 targeted network/world tests (four new
conservation cases plus the existing world suite). The final integrated
regression result remains the release authority because other team members may
also change scoring contracts. Historical off-trace error reconstruction remains
evidence-gated in `examples/audit_frontier.py`; new traces use ordinary exact
replay, with a regression preserving the legacy path.

After the conservation fix, a fresh 249-task reference pass again produced
249 strict successes and 249 exact score-and-trace replays. The independently
assigned evaluation scientist reviewed both the protocol/type-guard changes
(17 tests run by the reviewer) and conservation changes (28 tests run by the
reviewer), reporting no substantive findings.

## Interpretation and remaining boundary

This establishes tested deterministic behavior and closes the reproduced local
protocol defects. It does not establish hostile-submission isolation. The local
runner intentionally launches cooperative executables with host access; hosted
leaderboard submissions still require the separate evaluator/agent isolation
specified in `docs/threat-model.md`. Reference success demonstrates solvability,
not independent model performance or scenario generalization.
