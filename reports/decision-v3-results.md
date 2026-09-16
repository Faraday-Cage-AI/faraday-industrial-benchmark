# Joint-decision v3: completed development comparison

All 16 scheduled attempts completed. The frozen tasks, package source, adapter,
measurement settings, final state hashes and scores were verified. Every episode
has an exact tool-trace replay; none was excluded or replaced.

| Model | Mean score | Strict success | Feasible recovery executed |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 73.37 | 3/8 | 6/8 |
| GPT-5.5 | 94.88 | 6/8 | 8/8 |

One attempt per public case; eight related synthetic variants; tool-only, no
code interpreter. Both models used xhigh, 65,536 output tokens per response,
200,000 per episode and a 3,600-second episode timeout. These observations are
not a held-out model ranking or a comparison against BankerToolBench scores.

## What failed

GPT-5.4 submitted and executed feasible, reconciled plans on cases 001–006.
Its exact optimization misses were:

- 001: worst-case cost $209.25 (1.23939%) above optimum.
- 002: optimal worst-case cost, but aggregate scenario cost $339.70 above the
  lexicographic tie-break optimum.
- 006: worst-case cost $300.00 (1.16390%) above optimum. Its lower aggregate
  cost does not compensate under the disclosed worst-case-first objective.

Five GPT-5.4 episodes contained an incomplete API response. On 007 and 008,
the final response exhausted the per-response token limit and the adapter ended
without a policy or a finish call; these are resource-limited outcomes, not
demonstrated infeasible business decisions. Cases 001, 003 and 005 also contained
an incomplete response but continued; 003 and 005 ultimately passed strictly.

GPT-5.5 executed feasible, reconciled plans on all eight cases without recorded
API incompleteness. Its exact optimization misses were:

- 005: optimal worst-case cost, aggregate tie-break $18.00 above optimum.
- 008: worst-case cost $601.85 (3.14694%) above optimum.

No completed plan lost points because of a hidden deadline, ledger annotation,
critical violation or missing operational execution. The 79.52 score reflects
the disclosed binary objective criterion and associated economic check; it does
not mean a 20.48% business loss. Synthetic economic penalties are not actual
operational losses. Report the objective gaps alongside strict success.

## Interpretation

This tier tests more coupled decision-making than its relaxed hindsight ablation:
the ablated policy is rejected on every seed, and the optimal two-part objective
changes on six seeds. However, GPT-5.5's 6/8 strict successes and 8/8 feasible
recoveries do not support a claim of extreme workforce difficulty. One strict
miss is a small tie-break error. Broader end-to-end work and additional decision
stages need separate, prospectively specified versions, not retrospective
changes to this run or deletion of successful cases.

Logged response cost estimates total $19.2939 for GPT-5.4 and $35.5682 for
GPT-5.5 ($54.8621 combined). These are not invoices and exclude unlogged usage.

## Evidence

- [Frozen run](../runs/decision-v3-background-20260915/frozen-manifest.json)
- [All-episode replay audit](decision-v3-audit.json)
- [Scores, execution diagnostics and usage](decision-v3-models.json)
- [Committed-policy objective gaps](decision-v3-objective-gaps.json)
- [302-test regression report](decision-v3-regression.xml)
- [Eight-case qualification](decision-v3-qualification.json)

The source archive is retained in the run directory. Nothing in this report
changes historical scores or presents candidate researched extensions as measured.
