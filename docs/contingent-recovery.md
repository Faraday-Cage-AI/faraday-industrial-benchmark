# Contingent network recovery (v0.6)

This track tests decisions under uncertainty, not compliance with a prescribed
allocation algorithm. It complements the v0.5 document-reconciliation track.

## Work product and sequence

1. Reconcile ten synthetic source extracts, including signed WMS movements,
   ownership, quarantine, cancellations, unconfirmed supply, and blocked lanes.
2. Incorporate commercial amendments at logical minutes 5 and 10.
3. Choose a common pair of supplier reservation tiers and submit four contingent
   whole-order allocation branches. Read back and approve the version-cited policy.
4. Commit by minute 60. The disruption is not revealed until minute 80.
5. Execute exactly the committed branch for the revealed outcome. Post a ledger
   with correct accounts, operating costs, and the reservation fee counted once.
6. Notify the responsible functions and close with record evidence.

Changing reservations after revelation is rejected. A second reservation or
execution is rejected. Scoring inspects the committed artifact, not an uncommitted
draft that happens to contain a correct answer.

## Decision problem

Ten orders each use stock, standard supply, express supply, or deferral. Orders
cannot be split. Two supplier tiers yield nine first-stage portfolios. Four
published scenarios change capacity, timeliness, carrier availability, and
deferral penalties. The disrupted carrier varies between seeds; there is no
universally preferred supplier portfolio.

Every branch must satisfy eligible stock, reserved capacity, mandatory orders,
allowed modes, due dates, and an emissions cap. Tier fees must fit the reservation
cash budget. Monetary conversion is rational FX with per-order half-up rounding.
Mutually exclusive scenario costs are not added together.

The objective is to minimize the maximum total cost across all scenarios.
Strict success requires all workflow criteria and cost no more than 102% of the
exact optimum. Business execution checks feasibility; it does not disclose the
optimum or prescribe a better allocation. Alternative optimum ties and allocation
row ordering are accepted. The exact dynamic program is evaluator/reference-agent
code, not an agent tool. It is public for auditability; an evaluated agent must
not access it or hidden evaluator state during a scored run.

There are 4^10 unconstrained assignments per branch, but this is not a measure of
model difficulty: resource-based dynamic programming prunes the search efficiently.

## Evidence so far

The reference solver strictly passes all eight public episodes. Tests check
additional procedural seeds, exact replay, malformed allocations, timing,
feasibility, and agreement with exhaustive enumeration on smaller instances.

Run `python examples/contingent_ablation.py` to reproduce a 32-seed development
control. It chooses capacity optimally for the normal scenario, then grants that
reservation optimal recourse in every scenario. It misses the 2% tolerance on
29/32 seeds. The robust optimizer selects five different portfolios. These are
algorithmic controls, **not GPT-5.4 or GPT-5.5 measurements**.

## Model evaluation protocol

Use fresh securely configured credentials; never commit keys or paste them into
reports. Evaluate both models with the same tools, reasoning setting, token
budget, time budget, and repeat count. Report exact model identifier, adapter and
benchmark commits, costs, latency, strict pass rate, feasibility, and regret.
Publish per-family results rather than burying this track in the easier suite mean.

Separate public development episodes from preregistered, private procedural seeds.
Freeze the harness before test runs and report all attempts. Do not optimize against
the final test set. Runs must isolate the agent from evaluator modules, task seeds,
reference solutions, and reports. Declare whether local computation tools are
available; do not compare a calculator-equipped agent against one denied computation
without clearly marking the difference. The bundled simple Responses adapter is a
tool-only baseline, not the strongest possible agent harness.

Handshake's [BankerToolBench](https://joinhandshake.com/research/benchmarks/bankertool-bench/)
motivates evaluating substantial professional work products. This track uses
independently authored synthetic industrial records and executable state; it does
not reproduce Banker's datasets or claim equivalent human effort or greater model
difficulty. Expert validation and model baselines remain necessary.
