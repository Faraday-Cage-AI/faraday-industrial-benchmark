# Decision contract audit — required before the next paid run

The v2 first-case traces reproduce their saved scores. Both models passed every
business criterion. GPT-5.5 finished at minute 272, losing economic credit against
an undisclosed target of 260 and receiving strict_success=false. This is not a
valid basis for a capability ranking. Its first ledger contained all correct
business values plus case/policy references and a reconciliation annotation, but
was rejected by exact-object comparison with an opaque error.

The v2 run is stopped. Completed first cases remain diagnostic results. Interrupted
second cases are excluded; 003–008 were never started. Both active background
requests returned confirmed cancellation. Original frozen source archives and
scores are preserved; they must not be silently regraded.

Before any further measurement:

1. Publish every scoring condition, weight, timeliness target, tool-clock cost,
   efficiency target and strict-success condition from actual evaluator parameters.
   Keep optimal objective values and reference assignments private.
2. Publish complete structural schemas, including array/object shapes, field
   types, optional audit annotations and unknown-field behavior.
3. Validate shape on artifact creation, returning field paths and error kinds,
   not hidden reference values. Do not force business-value guesses to diagnose
   an extra-field or wrong-shape error.
4. Accept harmless ledger annotations. Validate optional case/policy references;
   do not allow wrong amounts, accounts, reservation IDs or allocations.
5. Test every declared threshold against actual grading, including exact deadline
   and one-minute-late cases. Check every criterion appears in the public contract.
6. Test corrected submissions, wrong-value negatives, false/partial evidence IDs,
   extra annotations and full eight-case replay. Audit remaining exact-object
   comparisons for equivalent hidden formatting requirements.
7. Preserve seed selection and optimization problems. Prove their objectives are
   unchanged; version the public-contract correction separately.
8. Only then freeze once and measure both requested models across all eight cases.

The versioned `public-decision-contract-v3` implementation now exposes the
scoring contract and structural schemas in the required GRC source reads.
The finish target (260), hard horizon (600), tool costs, weights, strict-success
conditions and efficiency allowance are derived from evaluator parameters.
Shape validation returns field paths before creating an artifact. Ledger audit
annotations are accepted, while optional case/policy references and all business
values remain checked. Policy allocation rows explicitly allow only order_id and
mode, matching their business validator; ledger allocation rows also allow the
documented annotations.

`tests/test_decision_contract.py` covers all eight public contracts, annotated
workflows with a rejected-then-corrected submission, exact trace replay, finish
at minute 260 versus 261, and wrong ledger values/references. The v3 qualification
report reproduces all eight v2 objectives and hindsight-ablation results exactly.
All 302 regression tests passed (`reports/decision-v3-regression.xml`), including
19 contract tests. Both saved v2 first-case traces still replay exactly. The new
eight-case matched run is frozen at `runs/decision-v3-background-20260915`.
All 16 attempts are now complete with exact trace, score and final-state replay
(`reports/decision-v3-audit.json`). No attempts were excluded. See
`reports/decision-v3-results.md` for resource limitations and objective gaps.
This correction improves validity; it does not itself increase task difficulty.
