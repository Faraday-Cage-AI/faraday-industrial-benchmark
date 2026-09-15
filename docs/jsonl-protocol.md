# External-agent JSONL protocol

Protocol identifier: `faraday-industrial-jsonl/1`.

The agent executable communicates through stdin and stdout. Each line is exactly
one JSON object. Logs must go to stderr.

## Start

Runner to agent:

```json
{"type":"start","protocol":"faraday-industrial-jsonl/1","task":{"id":"...","prompt":"..."},"tools":[...]}
```

The task excludes its procedural seed. Its public fields include the workflow
family, available tool names, required notification roles, and any exact
controlled-plan action labels. Every task includes `workflow_stages`, a
topologically ordered dependency graph of stage IDs and objectives. Focused
tasks use a common five-stage lifecycle; composite tasks publish richer
workflow-specific graphs. The accompanying `tools` array contains only the
family-scoped JSON Schema-shaped input contracts. The complete catalog and
scopes are committed by the exported platform-harness contract.

## Tool call

Agent to runner:

```json
{"type":"tool_call","id":"call-1","name":"get_incident","arguments":{}}
```

Runner to agent:

```json
{"type":"tool_result","id":"call-1","name":"get_incident","result":{"ok":true,"incident":{"id":"INC-..."},"clock_minute":1}}
```

Call IDs are echoed for correlation. Calls are currently sequential. An invalid
tool or argument payload returns `ok:false` and still counts toward the budget.
An attempted call beyond the budget is returned and recorded as a rejected trace
entry so exact replay enforces the same boundary.

`wait` accepts either a minute duration or `until_next_event:true`; the latter
advances logical time exactly to the next pending external event.

## Final

Agent to runner:

```json
{"type":"final","summary":"Contained the affected lots...","evidence":["INC-...","QH-001"]}
```

The runner persists the final response and closes the process. Exiting, timing
out, or emitting invalid JSON before `final` records an agent error and fails the
unfinished criteria.
