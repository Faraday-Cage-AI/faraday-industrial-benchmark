# Benchmark development team

For specialized benchmark work, read `team/README.md` and delegate bounded work
to the relevant role when it benefits the assignment. The primary agent acts as
research lead and coordinator unless separate workers are useful. Routine edits
do not need the whole team. Respect the user's requested scope and available
concurrency.

| Agent name | Use for |
| --- | --- |
| `research_lead` | Research direction, priorities, technical tradeoffs, specialist management, and final quality assessment |
| `evaluation_scientist` | Measurement validity, coverage, scoring design, leakage, and interpretation |
| `evaluation_engineer` | Scenarios, graders, reference trajectories, controls, and evaluation runs |
| `environment_engineer` | Simulated state, tools, events, authorization, protocol, and replay |
| `industrial_domain_specialist` | Operational realism, business constraints, source research, and workflow specifications |
| `research_coordinator` | Work breakdown, acceptance criteria, handoffs, and integration |

Shared role definitions live in `team/roles/`; Codex adapters live in
`.codex/agents/` and Claude Code adapters in `.claude/agents/`. These are
benchmark-development assistants, distinct from the agents being evaluated by
the benchmark.

Keep Git branch names neutral and descriptive; never include external vendor,
product, model, or coding-agent names.
