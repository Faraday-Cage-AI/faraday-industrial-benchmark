# Professional work samples

Reference: [BankerToolBench](https://github.com/Handshake-AI-Research/bankertoolbench),
reviewed September 15, 2026. Its relevant design features are source discovery,
end-to-end professional tasks, multiple deliverables and detailed task-specific
rubrics. This extension uses original synthetic industrial data; no BTB data or
code was copied. It does not claim equivalent practitioner validation or difficulty.

## Implemented: claims-aware operating reviews

`data/professional/tasks.json` adds 24 cases in the existing integrated operating
review family. Unlike the network-recovery variants, these produce four mutually
consistent structured deliverables: recovery model, control register, executive
brief and customer schedule, using the existing revised-source and approval workflow.

The insurance recovery is no longer supplied as a precomputed scalar. Agents must
reconcile loss events, duplicate imports, reversals, pending claims, period cutoff
and coverage exclusions. They apply an aggregate deductible, participation rate,
remaining coverage limit and previous cash receipts in the specified order. Every
intermediate calculation and excluded record must appear in an insurance bridge.
The receivable flows into the reserve and executive brief. Values use integer cents
and a disclosed rounding rule. This is a synthetic contractual recognition policy,
not a representation of generally applicable accounting or insurance law.

Twelve additional finance variants combine the claims problem with incremental
AP expense recognition and payment timing. Agents select the highest approved
invoice revision (not a newer draft), apply service-period cutoff, link credits to
recognized parent invoices, and convert each document separately at rational FX.
Duplicate, unsettled and late payments are excluded from cash settlement. The
deliverable includes a finance bridge: expense, settled cash, and remaining payable.
Only expense adjusts the reserve; payment timing cannot reduce expense. Negative
remaining payable is retained as a prepayment. These formulas are source-disclosed.

```sh
python examples/generate_professional.py
python -m pytest tests/test_claims.py -q
faraday-bench run --tasks data/professional/tasks.json --agent oracle --output runs/professional-oracle.json
```

Tests use a hand-calculated waterfall, full reference workflows, and corrupted
deliverables (missing bridge, a wrong receivable, inconsistent executive reserve).
The reference implementation is not a model score. Paid model runs stay stopped.

`python examples/qualify_professional.py` runs 132 applicable corruption checks
across all 24 cases. All 132 are rejected, with a verified mutation and an artifact
or consistency criterion failure. Controls cover missing claims calculations,
double-counted prior receipts, missing exclusions, inconsistent executive figures,
cash incorrectly reducing expense, ignored credit notes and incorrect settled cash.
Results are recorded in `reports/professional-qualification.json`.

## Native artifact export and separate submission verifier

`examples/capture_professional.py` records submitted tool artifacts from a reference
episode, not hidden evaluator state. `examples/professional_workbook.mjs` exports
that submission to a formula-based XLSX financial review/customer schedule and an
HTML executive report. It requires the optional `@oai/artifact-tool` runtime.
The exporter checks reserve consistency and perturbs/restores an input to verify
recalculation. Both workbook sheets have been visually inspected on one reference
case. The workbook consumes reconciled inputs rather than performing raw-claims
recognition itself. The detailed claims and finance bridges are required in the
tool-produced model, checked again by replay. Desktop Excel behavior has not been
tested. This is a constrained artifact track, not arbitrary spreadsheet grading.

Any harness may author the files independently, following the fixed template below.
The verifier does not require the reference exporter or trust its submission JSON:
it loads case expectations independently and replays/regrades the original episode.
An edited claimed score cannot bypass the workflow check. Native checks are a
separate stage; do not substitute their result for the default workflow leaderboard.

```sh
python examples/verify_native_review.py --task faraday-professional-finance-012 \
  --workbook outputs/01a0a219-professional/operating-review.xlsx \
  --report outputs/01a0a219-professional/executive-report.html \
  --episode runs/native-professional/episode.json
python examples/qualify_native_review.py
```

The workbook must use `Financial review` and `Customer schedule` sheets:

| Location | Contract |
|---|---|
| Financial review B6:B13 | Disposal, inspection, production, supplier expedite, freight, penalties, negative insurance receivable, incremental AP expense; USD |
| Financial review B15 | Formula summing all eight reserve inputs |
| Financial review B17 | Settled AP cash in USD |
| Financial review B18 | Formula for incremental AP expense less settled cash |
| Customer schedule A5:F… | Sorted order ID, requested, committed, formula shortfall, arrival minute (blank if none), status; exactly one row per order |
| Executive HTML report | Case ID, decision status, and `Reserve: USD <amount to two decimals>` as text |

Supported formulas use same-sheet cell references, arithmetic, parentheses and
single-column `SUM` ranges. Alternative equivalent arithmetic is accepted. Formula
caches must agree with independent recalculation; dependency perturbations reject
hardcoded answers masquerading as formulas. Unsupported functions, macros, external
links, malformed archives and unsupported syntax fail closed. The parser is bounded
and never executes workbook code. HTML checks cover factual text, not visual quality
or adversarial styling. Visual/readability assessment is not automated by this track.

The saved reference workbook passes 73 checks. All seven saved-file corruptions
(hardcoded result, stale cache, wrong source amount, wrong cash, constant formula,
cash netted against expense, wrong report) fail. This file qualification uses one
reference case; it must not be described as native-file evaluation of all 24 cases.
The 24 tool workflows each pass and replay exactly, including their detailed bridges.
The original public suite and earlier coupled hard suite also replay unchanged.

Practitioner review and fresh held-out model evaluations would be needed for claims
about real professional difficulty. They are not replaced by successful oracle runs.
