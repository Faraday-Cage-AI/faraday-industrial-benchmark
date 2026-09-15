# Architecture

```text
task manifest ──> seeded scenario builder ──> isolated IndustrialWorld
                                                │
agent <──── JSONL or in-process tools ───── ToolClient
  │                                             │
  └──────── tool calls / final answer ──────────┘
                                                │
                           state + events + trace hashes
                                                │
                                        deterministic grader
                                                │
                                      JSON run + HTML report
```

## Isolation boundary

`IndustrialWorld` owns plant-floor, ERP back-office, transportation, warehouse,
distribution-network, trade, planning, and controlled engineering-document state,
pending events, policy,
evaluator contracts, and economics. `ToolClient` exposes only declared tools. An external process receives
the task's public fields and tool schemas; it never receives the seed, grader
criteria, event queue, or authoritative world state.

Every task publishes a topologically ordered workflow-stage DAG. Focused tasks
use a common investigation-to-finish lifecycle, while composite tasks publish a
deeper workflow-specific graph. The DAG states operational dependencies without
revealing scenario values or grader checks. Scenario policy can require a
specific upstream protected action to have executed before a downstream approval
becomes evidence-ready.

Frontier operating-review tasks add a versioned data-room layer. File inventory
returns metadata only; evidence is created by reading individual sections at a
specific version. Scheduled revisions replace authoritative section contents and
are recorded independently in the audit log. The agent persists each exception
resolution, creates four structured artifacts, reads them back, and packages them.
Publication revalidates the exact exception set, artifact fields, citations, and
package membership after approval rather than treating approval as correctness.

For a hosted leaderboard, run the world and grader in a separate container or
service account from the submitted agent. The local in-process interface exists
for development convenience and is not a security boundary against hostile code.

## Logical time

Reads consume one minute and writes consume two. `wait` either advances by an
explicit duration or, with `until_next_event`, exactly to the next pending event.
When time crosses an event timestamp, the event mutates authoritative state
before execution continues. Approval decisions that occur during the modeled
request latency are applied before `request_approval` returns, so its response
reports the current status. This makes sequence matter while preserving exact
reproducibility.

## State integrity

Every tool call stores its arguments, returned payload, logical minute, and a
SHA-256 hash of canonical post-call state. `faraday-bench replay` reconstructs the
world from the task and repeats every call, checking result equality and state
hash equality at each step. It then re-grades the reconstructed world and checks
the submitted public task, episode score, final answer, applied events, and
initial/final state commitments. Calls rejected at the tool-budget boundary are
also first-class trace records and are reproduced through the same boundary
during replay.

## Extending the suite

Add a scenario builder returning:

1. Synthetic initial state
2. Scheduled events
3. Weighted deterministic criteria
4. Economic mitigation checks

Register it in `scenarios.BUILDERS`, add at least two public task descriptors,
implement a reference trajectory, and add negative-control and event-timing tests.
