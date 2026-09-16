# Subcontracting close and dependent recovery planning

Current candidate `0.12.0-subcontracting.2`: eight fixed seeds in
`data/subcontracting-v2/tasks.json`. V1 remains in `data/subcontracting/tasks.json`.
This is a new workflow extension, not a change
to the frozen decision-v3 model run or a claim of proven frontier-model difficulty.
No models have yet been measured on this tier.

V2 separates evidence into WMS component balances, QMS opening quality states,
SCM event history and ERP valuation/cutoff rules. The original SCM extract is
incomplete; its authoritative revision contains later business records. Agents
must join on lot ID and cite the current extracts. Historical event sequence is
separate from the live simulation clock.

The eight cases cover four causal variants twice each: a late finished-stock
quality release followed by shipment; a reversal that was not approved, followed
by correction and shipment; a component hold that blocks a correction until a
new retry after release; and a receipt corrected before reversal, followed by
a separate new receipt using released inspection components. These changes alter
numeric availability or financial results on every seed, not just exclusion labels.

## Coupled work

Reconstruct a subcontractor's stock and valuation from a shuffled event log,
not a precomputed availability field. Process partial receipts, pack-unit
conversion, service FX, prior shipments, subsequent consumption adjustments,
revision replacement, quality holds and receipt reversal in event order.
Separate duplicate messages, stale revisions, future transactions, draft
corrections, invalid reversals and impermissible consumption. Invalid business
events are atomic: a partially processed receipt cannot consume its first
component before failing on a second, inspected component.

Late corrections change the final cost of already shipped units. Components
supplied by the buyer are not a new payable; service accrual is separate.
Inspection stock remains valued but is unavailable. A reversal restores the
current corrected component consumption and reverses service accrual without
creating a second finished-goods receipt. Revision deltas replace earlier
document deltas, rather than accumulating blindly.

The result is an input to the operating review, not an isolated arithmetic
appendix. Released unshipped finished goods cap nominal MES recovery capacity.
That cap changes production quantity, customer commitments, route allocations,
premium freight, shortage penalties and production expense. Only subcontracting
COGS enters the incident reserve; inventory and service payable are not added
again. All four final deliverables must agree before approved publication.
Existing claims, AP/cash reconciliation, receipt-cost propagation, changing
source versions and exception-resolution requirements remain active.

## Provenance and synthetic boundaries

[SAP's subcontracting lesson](https://learning.sap.com/courses/detailing-subcontracting-and-supplier-consignment/outlining-subcontracting_af403e3e-188d-4dbb-bde1-632253739fa6)
describes supplied components as the procurer's valuated special stock, coupled
finished-goods receipt and component consumption, restrictions on inspection
stock, and subsequent adjustments after late consumption reports. It explicitly
distinguishes subcontracting from external processing.

The event format, revision precedence, reversal restrictions, FX rounding,
final-cost allocation, cutoff and downstream supply cap are synthetic benchmark
rules, disclosed in every case. They are not claims about universal SAP posting
behavior. Data and amounts are generated originally; vendor examples are not
copied. No closed-period, tax or legal compliance behavior is claimed.

## Verification

`tests/test_subcontracting.py` includes a hand-calculated stock/value example,
atomic rejection, revision and cutoff ordering, units and quality-release
checks, 100-seed conservation/exception coverage, eight full reference workflows
with exact replay, and 32 deliberately wrong operating-review submissions.
The wrong submissions respectively double-count payable, inflate availability,
misstate late COGS or inflate production; none may publish.

V1's full regression passed 347 tests. The combined V1/V2 qualification passes
94 tests, including 16 reference workflows/replays, 64 rejected submissions,
eight numeric late-history impact checks and coverage of all four event sequences.
The full V2 regression passed all 396 tests (`reports/subcontracting-v2-regression.xml`).
These are correctness checks, not model difficulty results.

Run `python examples/generate_subcontracting.py` to reproduce the fixed manifest.
Use the standard runner with `--tasks data/subcontracting-v2/tasks.json`.
The previous model results remain in `reports/decision-v3-results.md`; they
must not be attributed to this new tier. Full regression qualification and a
prospectively frozen measurement are required before capability claims.
