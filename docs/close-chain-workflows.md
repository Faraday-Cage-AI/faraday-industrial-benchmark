# Linked subcontracting and intercompany close

Current candidate `0.13.0-close-chain.2`, eight fixed seeds at
`data/close-chain-v2/tasks.json`. The unmeasured V1 remains at
`data/close-chain/tasks.json`. V2 retains the same business problems, but publishes
the scoring contract, extends the disclosed finish target to minute 300 and hard
horizon to 900, permits 400 calls, and accepts annotated exact evidence IDs.
It retains the distributed subcontracting events,
four lifecycle variants, claims, AP, receipt-cost propagation, constrained supply,
customer allocations and four-artifact operating review. No model scores exist
for this candidate; earlier decision-v3 results are a separate track.

The program-office delivery contract publishes every criterion's ID, weight,
dimension and check type, economic checks, scoring formulas, tool-clock costs,
efficiency allowance, strict-success conditions and evidence requirements. Solved
leaf values and required exception answers are not published. This corrects the
inherited undisclosed minute-140 economic target before any paid measurement.
Difficulty must come from the workflow, not timing or formatting surprises.

## New dependency chain

Late consumption corrections change subcontracting receipt value and previously
shipped cost. The shipped cost then allocates to intercompany transfers; agreed
transfer prices stay fixed. Logical and physical receipt channels are distinct,
and duplicates, drafts, cancelled transfers, excessive receipts and after-cutoff
records cannot create extra received quantity. Partial delivery divides each
receiver's transfer-price valuation into expense and trade-in-transit assets.

The agent must produce balanced sender and receiver journals plus consolidation
eliminations. Eliminating balances alone is insufficient: internal margin must
also be removed from expense and remaining transit value. Corrected source cost,
not transfer price, determines consolidated values. Because the base incident
reserve already includes subcontracting dispatched cost, goods still in transit
must be reclassified out of expense. The corrected reserve must agree between
the detailed model and executive decision brief.

The grader rejects a balanced journal posted to the wrong entity and a wrong
reserve repeated consistently across deliverables. Balance and consistency are
necessary, not sufficient, for business correctness.

## Source and boundaries

[Oracle's 26b interorganization example](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26b/fapma/example-of-accounting-of-interorganization-transfers-with-cost.html)
illustrates an expense-destination transfer across profit-center units with a
fixed transfer price. A subsequent sending-cost adjustment changes gain/loss
rather than that price. It also distinguishes logical from manual receipt events.

The benchmark's partial-receipt allocation, signed-debit account labels,
consolidation entries, rounding remainders and reserve reclassification are
explicit synthetic rules. They are not a certified Oracle implementation or
financial-reporting guidance. All amounts are synthetic reporting-currency cents;
no tax, closed-period, or statutory consolidation behavior is claimed. Subcontracting
provenance and its synthetic boundaries remain in
[the preceding tier](subcontracting-workflows.md).

## Qualification

Tests cover an independently hand-calculated partial delivery and elimination,
negative sender margins, rounding conservation, locked-price invariance under
late recosting, duplicate channel rejection, quantity partitioning and 100 seeded
cross-module propagation checks. Eight complete reference workflows replay
exactly. Forty deliberately incorrect final packages cover wrong entities,
missing elimination, repricing, expensing in-transit goods, and double-counted
internal payables; none may publish.

Combined V1/V2 qualification passes 114 tests, including reference/replay and
negative-package checks on all sixteen cases, exact deadline boundaries at 300
and 301, public-rubric metadata checks and proof that V2 preserves V1's business
answers. See `reports/close-chain-v2-qualification.xml`.

Reproduce the manifests with `python examples/generate_close_chain.py`; run the
current candidate with `--tasks data/close-chain-v2/tasks.json`.
Qualification establishes implementation correctness, not "insane" model
difficulty. A separately frozen model comparison is still needed for that claim.
