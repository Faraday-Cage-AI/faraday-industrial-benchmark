# Benchmark threat model

## Protected assets

- Held-out task seeds and generated state
- Evaluator criteria and best-known actions
- Authoritative industrial-enterprise state and event queue
- Other submissions and unpublished results
- Integrity of traces, scores, and leaderboard metadata

## Threats and mitigations

| Threat | Required mitigation |
|---|---|
| Reading hidden state or grader files | Separate agent and evaluator containers; mount no benchmark source into the agent |
| Memorizing public tasks | Use private procedural seeds, rotate rounds, publish seed commitments |
| Grader gaming through keywords | Grade state and typed trace records; never score final prose by keyword stuffing |
| Forging tool results | Tools execute in the evaluator service; submissions cannot submit their own traces |
| Guessing a tool hidden from the workflow | Enforce family tool scopes at execution and replay, record the rejection, and treat an out-of-scope protected write as a critical boundary attack |
| Changing an action after approval | Bind action, target, and payload to the approval; reject conflicting or additional execution fields as a critical failure |
| Forging platform optimization results | Faraday-Platform replays every submitted tool call and post-call state hash with the authoritative benchmark before recording or promoting an epoch |
| Retrying until lucky | Declare attempt policy; default to one attempt per task |
| Prompt or model swapping | Pin and publish model, prompt/policy hash, runtime, and tool schema version |
| Denial of service | CPU, memory, wall-time, output-size, and tool-call limits |
| Network exfiltration | Disable network unless the benchmark round explicitly evaluates browsing |
| Supply-chain code execution | Review or sandbox submission images and run them without evaluator credentials |
| Hidden-set leakage | Limit operator access, log downloads, use canary records, rotate compromised sets |

## Local versus hosted execution

The local runner assumes cooperative code. `--agent-command` launches an arbitrary
local executable and is not a secure sandbox. A public leaderboard must isolate
submissions with containers or microVMs, a read-only root filesystem, no host
sockets, no evaluator mount, no credentials, and tightly controlled network egress.

## Operational safety

Faraday Industrial Benchmark must remain synthetic. Never point its agent tools at
a production ERP, HCM, payroll, treasury, MES, historian, PLC, robot, safety
instrumented system, or physical plant.
