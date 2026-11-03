# Operational accuracy and coverage audit

Audit date: 2026-11-02 (America/Los_Angeles). Scope: current v0.7.0 public
suite, representative distributor contracts and core engineering/supply-chain
coverage. This is a code and fixture review by the industrial domain specialist;
it is not validation by human ERP, warehouse, accounting, or plant practitioners.

## Observed defects requiring correction

### P1: Net payment days are incorrectly treated as whole quarters

`distributor/gdpval_checks.py::_terms_scenarios`, cash branch, uses
`lag = 1 if term == 30.0 else 2` and places each quarter's entire wholesale
revenue in the quarter `lag` quarters later. The importer repeats that formula
in `examples/distributor_import/gdpval.py::t02_terms_scenarios`.

Task `faraday-gdpval-002` supplies quarterly shipment totals and Net 30/60
terms but no invoice dates or shipment-distribution convention. Its public
submission contract requests receipt quarters Q1–Q6 without disclosing the
checker's day-to-quarter conversion. Thus a 60-day term is scored as a
six-month displacement, and a reasonable calendar model can fail. For example,
if shipments are invoiced at quarter end, both 30- and 60-day terms fall in the
following quarter, although on different dates within it.

Observed reproduction (`PYTHONPATH=src python3`): load
`gdpval_work.grader_fixture('faraday-gdpval-002')`, select its check with
`aspect == 'cash'`, deep-copy `truth`, and replace every scenario's receipts
with `{f'Q{i+2}': scenario['wholesale_revenue'][f'Q{i+1}'] for i in range(4)}`.
`gdpval_checks.evaluate(check, content)` rejects the Net 60 scenario. The
committed Net 60 reference places Q1 revenue in Q3 and Q4 revenue in Q6.

Acceptance: state a defensible synthetic invoicing/date convention in the public
contract, calculate receipt dates by adding actual payment days, aggregate those
dates to the declared period, regenerate task/grader fixtures and provenance,
and test calendar boundaries and both terms. If quarterly output is retained,
disclose that it may not distinguish the two terms' within-quarter timing.
Changing only the checker would leave the source importer unreproducible.

### P1: Unnecessary AP holds still receive a perfect result

`distributor/erpbench100_checks.py::_receiving_ap_match` tests that expected
held lines are a subset of the union of all held lines. Additional held lines
and duplicate hold records do not make the state verdict forbidden.

Observed reproduction (`PYTHONPATH=src python3`): select
`faraday-erpbench100-005` from `data/distributor-erpbench100/tasks.json`, create
`IndustrialWorld(task)` and call:

```python
fixture = erpbench100.task_fixture(task)
erpbench100.reference_run(task, ToolClient(world), extra_steps=({
    'action': 'hold_dist_tenant_supplier_invoice',
    'target': fixture['truth']['invoice_number'],
    'payload': {
        'hold_name': 'Price',
        'lines': [1, 2, 3, 4],
        'reason': 'hold every line including lines with no exception',
    },
},))
score = grade_episode(world)
```

The extra write is approved and executed through public tools. The observed
result is `score=100.0`, `strict_success=True`, with no failed criteria, even
though only line 2 requires a hold. This mislabels unnecessary containment as
perfect execution and can delay payment on unaffected invoice lines.

Acceptance: require exact effective hold coverage and reject excess or duplicate
effective holds; preserve legitimate required holds and approved non-hold cases.
Include a negative control for this public-tool sequence and for duplicates.

## Findings that limit claims rather than imply implementation defects

- The suite is broad: manifests and documentation cover manufacturing, finance,
  engineering-document review, supply planning, logistics and distribution. This
  audit does not establish exhaustive industrial coverage. `docs/workflow-coverage.md`
  correctly describes structured facts rather than native drawing perception,
  CAD geometry, tolerance-stack computation, or BIM coordination.
- All 175 distributor tasks have fixed fixtures; their new seeds are not new
  business instances. Their roughly 70% weight in the 249-task mean and the
  82 buy-to-fulfill episodes' concentration must remain visible in results.
- GDPval output is a structured work product, not native spreadsheet/document
  production. The 157 unscored rubric items include narrative and presentation;
  the measured construct is narrower than the original work sample.
- Distributor reference paths use sealed fixture plans/answers:
  `erpbench100.reference_run` reads `oracle_plan`/`expected_answer`,
  `gdpval_work.oracle` submits `grader['truth']`, and `erp_buy._oracle` reads the
  fixture oracle. They operate through public tools but do not independently
  derive their decisions from only public evidence. Oracle 100 establishes
  fixture execution consistency, not evidence of autonomous calculation,
  discoverability, or real-world realism. The measurement reviewer independently
  reached the same conclusion.
- Human practitioner review remains outstanding. Synthetic approval policies,
  exact disposition catalogs and chosen costs should remain explicitly modeled
  company policies rather than universal operational requirements.

## Verification and handoff

Commands actually run: Python checks above; fixture and importer inspection;
review of benchmark card, workflow coverage, scoring, track, provenance notices,
source contract modules and distributor negative-control tests. The first Python
invocation failed because the package was not on the default interpreter path;
re-running with `PYTHONPATH=src` succeeded. No paid evaluations, production code
changes, source-data changes, or external service actions were performed.

The research lead owns prioritization and integration. The evaluation engineer
should implement the two corrections and meaningful regression controls; the
evaluation scientist should independently review the changed scoring contracts.
The audit remains a record of the observed pre-fix state; integration should add
links to the fixes and validation evidence rather than erase the findings.
