# Contributing

Contributions are welcome when they improve validity rather than merely increase
task count.

## Scenario requirements

A new scenario family must include:

- independently authored synthetic records;
- at least one changing or agent-triggered event;
- an employee-style request that does not reveal the solution path;
- deterministic outcome and trace criteria;
- an authorization boundary where relevant;
- an economic contract with documented assumptions;
- a reference trajectory using only agent-visible tools;
- no-op, incomplete, unsafe, timing, and reproducibility tests;
- documentation of intended scope and limitations.

Do not contribute copied customer data, vendor payloads, screenshots, manuals,
certification content, personal data, or confidential operating procedures.

## Third-party compatibility tracks

Do not place third-party material in Faraday-native task, source, test, or report
directories. A proposed upstream snapshot must have explicit redistribution
terms for both code and data, retain its original namespace and files, pin an
exact commit, update `third_party/manifest.json` and `THIRD_PARTY_NOTICES.md`, and
pass `faraday-bench upstreams --verify`. Restricted, private, noncommercial, or
ambiguous material remains reference-only. Compatibility-track scores are never
pooled into the Faraday-native aggregate.

One owner-approved exception exists: the GDPval-derived distributor tasks commit
reference data, expected deliverables, and rubrics as grader-only material even
though GDPval declares no license (see NOTICE and THIRD_PARTY_NOTICES.md). Do not
extend that exception to other sources without the same explicit decision.

## Development

```bash
python3 -m pip install -e '.[dev]'
faraday-bench validate
python3 -m pytest -q
faraday-bench qualify
```

All reference episodes must strictly pass, every unauthorized-write control must
score zero, and saved reference traces must replay exactly.

## Development assistants

The [benchmark development team](team/README.md) defines a research lead and five
specialist roles with project-scoped Codex and Claude Code subagent adapters.
Use the shared role files when configuring another harness; keep benchmark
methodology and domain knowledge there rather than duplicating them in harness
configuration.

## Reporting evaluator problems

Treat leaked held-out seeds, grader bypasses, nondeterminism, and incorrect safety
contracts as integrity issues. Provide a minimal reproduction privately to the
maintainers before publishing an exploit against an active leaderboard round.
