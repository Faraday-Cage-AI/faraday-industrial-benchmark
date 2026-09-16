# Cross-functional recovery — 0.8.0-workforce.1

16 additional seeded synthetic cases in `data/workforce/tasks.json`. This extends
the industrial recovery workflow; it is not a benchmark of every occupation.
It does not establish a claim of being the world's hardest workforce benchmark.

## What changes

The agent must reconcile records, commit a common supplier reservation and eight
contingent branches, obtain approvals, execute the realized branch and reconcile
the ledger. Twelve orders and four customer portfolios share inventory, suppliers,
emissions, customer obligations, carrier contracts, certified labor and liquidity.

Two additional outcomes combine existing disruptions with operational constraints:

- **Port + quality + worker absence:** certified release blocks are scarce. Standard
  inbound orders require both receiving inspection and release labor; other shipped
  orders require release labor. Unqualified overtime is not an authorized workaround.
- **Carrier + quality + cash freeze:** supplier and carrier deposits compete for
  same-day working capital. Payroll and tax reserves are protected. Later customer
  receipts cannot fund earlier dispatches.

Labor and treasury use are per whole order, not per pack. They pool across customers
within a branch, but never across mutually exclusive branches. Scenario limits replace
base limits. Refundable deposits are feasibility constraints, not additional expenses.
The treasury pool is explicitly net of reservation cash and protected reserves.
All rules are disclosed in the source contract; no hidden domain assumptions apply.

Customer exclusions, kit-splitting waivers, nonlinear service credits, minimum carrier
loads and emergency activation fees from the long-tail suite remain binding. Strict
success requires exact worst-case optimization followed by exact aggregate-cost
optimization, and successful approved execution. Numeric partial credit is diagnostic.

## Verification

```sh
python examples/generate_workforce.py
faraday-bench validate --tasks data/workforce/tasks.json
python -m pytest tests/test_workforce.py -q
python examples/qualify_workforce.py
```

The exact solver now tracks labor and cash as separate resource dimensions. It must
retain alternatives that consume the same inventory but differ in staffing or cash;
discarding them solely on freight cost is unsound. Tests compare this search with
exhaustive enumeration of a two-customer slice, exercise resource-limit boundaries,
check units and scenario scope, and run every case through the full reference workflow.
Enumeration shares the business-rule cost function; focused semantic tests complement
that search check. Qualification separately drops labor, cash, or both constraints
and checks the resulting plans against the full contract.

The published qualification report records strict-objective failures in 4/16 cases
when labor constraints are omitted, 14/16 when treasury constraints are omitted,
and 15/16 when both are omitted. These are algorithmic ablations, not LLM scores.
Cases where a constraint is nonbinding remain in the suite.

These are synthetic design cases, not evidence of real-world exception frequencies.
They are fixed seeds without model-performance-based filtering. Public cases can be
studied; credible capability measurement needs held-out scenarios and a frozen harness.
Paid model runs remain stopped. No GPT-5.4/5.5 scores exist for this suite.
