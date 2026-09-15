# Coupled hard suite — 0.7.0-hard.1

This is a separate eight-case challenge manifest at `data/challenge/tasks.json`.
It does not silently replace v0.6 episodes or retroactively change model scores.

## What is harder

| Constraint | v0.6 contingent track | Coupled hard suite |
|---|---|---|
| Whole orders | 10 | 12 |
| Disruption outcomes | 4 | 6, including simultaneous port/quality and carrier/quality failures |
| Customer obligations | Per-order mandatory service | Four customer portfolios, each with a minimum service floor |
| Installation kits | Independent orders | Two paired kits: components must use the same fulfillment mode or both defer |
| Service penalties | Linear per-order penalties | Linear penalties plus nonlinear customer service credits |
| Freight charges | Per-order dispatch charges | Per-order charges plus each used mode's activation fee counted once |
| Optimization | Worst-case cost within 2% | Exact minimum worst-case cost; then exact minimum aggregate cost among ties |
| Execution | Commit before reveal, then execute | Same; no relaxing approvals or allowing hindsight |

All constraints and fee formulas are disclosed in the authoritative GRC source.
Agents must satisfy all six scenarios, including compounds, under a common supplier
reservation. The additional customer contracts make independent order ranking
insufficient: an apparently cheap assignment can break a kit or service floor.
Activation fees and nonlinear credits also invalidate naive per-order arithmetic.

The headline result for this track is **strict success**, not mean partial-credit
score. Every required criterion must pass. Alternative exact optimum ties and
allocation row order remain accepted. Token limits are not reduced to create failures.

## Reproduce without paid models

```sh
faraday-bench validate --tasks data/challenge/tasks.json
faraday-bench run --tasks data/challenge/tasks.json --agent oracle --output runs/coupled-hard-oracle.json
python examples/qualify_coupled.py
python -m pytest tests/test_coupled.py -q
```

The reference solver performs group-level enumeration and resource-state dynamic
programming. Tests compare it with independent exhaustive assignment enumeration
on small cases, check nonlinear charges and kit rules, and solve all public cases.
Qualification also tries an exact optimizer that ignores customer coupling; that
control is distinct from an LLM baseline.

## Measurement boundary

GPT-5.4/5.5 runs on v0.6 were stopped at the user's request. Interrupted episodes
must not be counted as model failures. This new suite has **not** been measured
against either model. It adds substantive constraints and stricter success rules;
it does not establish that any specific model will fail.

Use fresh private seeds and a frozen harness for a defensible follow-up evaluation.
Report tool-only and computation-enabled harnesses separately. Retain all attempts,
including truncations, and distinguish infrastructure failures from task failures.
