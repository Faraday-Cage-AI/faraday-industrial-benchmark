@AGENTS.md

# Claude Code adapters

The six project agent types are defined in `.claude/agents/`. Each loads the
same shared role and collaboration guide as the Codex adapter. Use the agent
types listed in `AGENTS.md` when delegating specialized benchmark work.

For peer consultation, give workers distinct runtime names when supported and
include the current worker roster and remit in their assignments. An agent type
names a reusable role; a runtime name or ID addresses a particular worker.
Workers should use `SendMessage` with valid recipients from the session's roster
or the parent, and relay through the parent when direct messaging is unavailable.
Keep shared-file ownership and consequential decisions visible to the coordinator.

When agent teams are enabled, these definitions can also serve as teammate types.
Only the lead manages the team; teammates should request additional staffing
through the lead. See `team/README.md` for launch examples and the shared handoff
contract.
