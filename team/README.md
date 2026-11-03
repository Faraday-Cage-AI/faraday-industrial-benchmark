# Benchmark development team

The shared role files define a research lead and five benchmark-development
specialists. They are ordinary Markdown so another harness can load the same
instructions. Codex adapters under `.codex/agents/` and Claude Code adapters under `.claude/agents/`
register the same specialist names and tell each one to read this guide and its
role before working. Edit the shared role file to change a specialist's working
method; edit an adapter only to change its discovery description or harness
settings.

| Agent | Shared definition |
| --- | --- |
| `research_lead` | [Research lead](roles/research-lead.md) |
| `evaluation_scientist` | [Evaluation scientist](roles/evaluation-scientist.md) |
| `evaluation_engineer` | [Evaluation engineer](roles/evaluation-engineer.md) |
| `environment_engineer` | [Environment engineer](roles/environment-engineer.md) |
| `industrial_domain_specialist` | [Industrial domain specialist](roles/industrial-domain-specialist.md) |
| `research_coordinator` | [Research coordinator](roles/research-coordinator.md) |

The research lead owns direction, priorities, technical tradeoffs, and final
quality assessment within the user's objective. The coordinator owns delivery
logistics, dependencies, handoffs, and integration. The primary agent normally
performs both roles; delegate to `research_lead` for a bounded research decision
or complete workstream when useful. A lead subagent has only the authority and
delegation capabilities granted by its parent and harness.

## Use in Codex

Open a Codex session in this repository and ask for a specialist explicitly:

> Use research_lead to assess the next improvement to distributor evaluation
> validity. Review the current evidence, consult relevant specialists within the
> available concurrency, and return a prioritized recommendation with acceptance
> criteria. Do not edit files or launch paid evaluations.

> Use evaluation_scientist to review whether the distributor aggregate supports
> our capability claims. Return findings with file references and acceptance
> criteria; do not edit files.

> Use industrial_domain_specialist to specify a receiving/AP exception workflow,
> then have evaluation_engineer implement the agreed contract. Have
> evaluation_scientist review the scoring independently.

Adapters omit model and reasoning overrides so specialists inherit the session's
settings. Permissions and available integrations also follow the parent session;
role instructions about file ownership are working agreements, not sandbox
enforcement. Native definitions require a Codex version that supports custom
agents. If a session does not discover newly added definitions, start a new
session. If native custom agents are unavailable, the parent can delegate to a
general worker with an explicit instruction to read this guide and the role file.

## Use in Claude Code

Start a Claude Code session in this repository. `CLAUDE.md` imports the shared
project rules from `AGENTS.md`; the six `.claude/agents/*.md` definitions use
the same agent names as Codex. For example:

> Use evaluation_scientist to review our scoring methodology. Consult
> industrial_domain_specialist about workflow realism and return findings with
> file references. Keep this review read-only.

The adapters set `model: inherit` and leave tools and permissions at the session's
defaults. They instruct workers to use Claude's `SendMessage` with actual runtime
names or IDs from the sibling roster or parent. The roster may omit agents
started later; ask the parent for an updated recipient rather than guessing.
Messages to completed subagents may resume them, so keep follow-up work within
the assignment and budget. If direct communication is unavailable, use the
parent-routed fallback in the shared communication contract.

To use the definitions as a coordinated agent team, launch explicitly with:

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude
```

Then ask:

> Create a team with evaluation_scientist and industrial_domain_specialist as
> teammate types to review scoring validity and workflow realism. Give them
> distinct names, have them consult each other directly, and consolidate their
> findings. Do not edit files.

Agent teams are experimental; the lead manages staffing and teammates do not
create nested teams. Creating these adapters does not enable agent teams in
project or user settings. Start a new session after adding the first project
`agents` directory so Claude discovers it. Validate adapter frontmatter locally
with `claude plugin validate .claude/agents`.

## Add another harness

Create its native agent definition with the same name, a short routing
description, and instructions to read this guide and the role file relative to
the repository root. No shared role assumes a particular model or tool API.

## Assignment and handoff contract

Give each worker a concrete objective, relevant paths or artifacts, allowed
edits, acceptance criteria, and any run budget. Supply only the context needed
for the assignment. If information is missing, inspect the repository first;
state assumptions and escalate only decisions that materially block the work.

Return a concise handoff with:

- **Outcome:** completed work or findings, and whether the acceptance criteria hold.
- **Evidence:** source paths and symbols, citations, or saved result artifacts.
- **Changes:** edited files, or an explicit statement that no files changed.
- **Verification:** commands actually run, results, and checks still outstanding.
- **Open issues:** material assumptions, limitations, and blocking decisions.
- **Next owner:** the next concrete action and responsible role, when needed.

Review assignments return prioritized actionable findings with location, impact,
evidence or reproduction, and proposed acceptance criteria. Distinguish observed
defects from hypotheses. Implementation assignments deliver the change and its
verification rather than just a plan.

## Collaboration

The default sequence for a new family is domain specification, measurement
review, implementation, independent review, then coordinator integration. Use
only the stages the change needs. Parallelize independent investigation or
separate implementation areas. Give concurrent editors disjoint file ownership
or separate worktrees; assign one owner to shared registration and manifest
edits. Workers should report needed cross-boundary changes to the coordinator.
Nested delegation must fit the parent's assignment and available concurrency.

Use an independent reviewer for substantive scoring changes when available. If
the author also performs the review, disclose that limitation. Specialists
recommend decisions within their remit; the coordinator resolves conflicting
recommendations against the user's objective and the evidence. When a separate
research lead is assigned, route research direction, measurement tradeoffs, and
final quality decisions to that lead; the coordinator resolves delivery and
ownership conflicts. Escalate decisions outside the assignment to the parent.

### Direct specialist communication

Consult another assigned specialist directly when their expertise can resolve a
concrete question, clarify an interface, or review a proposed decision. Discover
the current team through the harness's agent roster or the coordinator; role
names identify specialties, while live agent identifiers address messages.
Contact an existing worker before asking for another worker with the same remit.

Keep each exchange actionable: state the question or requested decision, relevant
file or artifact references, constraints, and the answer needed to proceed.
Workers have separate contexts, so include the necessary evidence rather than
assuming they saw your conversation. Use messages for clarifications and updates;
assigning new work or waking an idle worker must remain within the parent's
assignment and concurrency limits.

Continue independent work while a reply is pending. If the answer blocks the
assignment, report the dependency to the parent or coordinator and use the
harness's supported wait mechanism. Avoid circular waits and acknowledgement-only
exchanges. If peer discovery, direct messaging, or waking a worker is unavailable,
send the question and intended recipient to the parent for relay.

Report consequential decisions, disagreements, and proposed scope or shared-file
changes to the coordinator. Direct consultation does not reassign file ownership
or expand authority. Include relevant peer conclusions in the final handoff and
record accepted lasting decisions in shared project documents; messages alone
are not durable project memory.

## Project knowledge and integrity

Start with `README.md`, `CONTRIBUTING.md`, and the role's relevant references.
Treat version and task counts as facts to verify in current manifests and code,
not constants in these instructions. When documentation and execution disagree,
report the discrepancy rather than silently selecting the convenient result.

Use existing `docs/`, source, tests, and saved reports as durable project memory.
Propose enduring lessons in the handoff; the coordinator incorporates accepted
decisions into the appropriate document. Do not depend on private harness memory
or append raw chat transcripts to project instructions. Save a longer assignment
brief or report under `team/assignments/` only when useful for a future handoff;
include objective, owner, status, evidence, and remaining work. Keep held-out data
and secrets out of these files.

Preserve benchmark boundaries: synthetic industrial systems, agent-visible
reference trajectories, sealed instance answers, and reproducible grading.
Inspect `docs/threat-model.md` when changing those boundaries. Benchmark authors
may inspect evaluator code to develop and audit it; evaluated agents must not
receive hidden state, seeds, reference answers, or grader-only material.

Keep historical results intact and label new measurements by benchmark version,
task coverage, agent configuration, and attempt policy. Follow current provenance
and track rules in `docs/benchmark-tracks.md`, `THIRD_PARTY_NOTICES.md`, and
`NOTICE`, including documented exceptions. A modeled approval inside a task is
separate from permission to act in an external service. Follow the user's
existing authorization and run budget for paid evaluations and external actions.
