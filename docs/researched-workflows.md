# Source-inspired industrial exceptions and frozen model evaluation

Research date: September 15, 2026. These cases are original synthetic work samples,
not copies of vendor datasets, accounting guidance, or full ERP emulators. Sources
inform operational distinctions; the exact evaluable rules are stated in each case.

## Research findings and implementation boundaries

| Primary source | Relevant distinction | Benchmark treatment |
|---|---|---|
| [Oracle 26A receipt adjustment propagation](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fapma/receipt-cost-adjustment-and-propagation.html) | A later cost change can affect consumed stock and remaining inventory; propagation depends on configuration, with special handling for logical nodes. | Implemented a quantity-conserving cost tree, signed price changes, logical pass-through, and explicit stopping rules. Synthetic stop rule expenses the stopped quantity; it is not a claim that every Oracle configuration does this. |
| [Microsoft quarantine orders](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quarantine-orders) | Reported-as-finished and physically returned to the regular warehouse are separate states. WMS use has additional applicability limits. | Implemented separate availability and valuation: released-but-not-returned stock is unavailable but still valued. Does not emulate all warehouse configurations. |
| [Oracle EBS consigned material](https://docs.oracle.com/cd/E18727_01/doc.121/e13470/T260819T260823.htm) | Goods can be physically received while owned by a supplier; retroactive pricing can affect consumption advice. | Implemented supplier-owned exclusion from buyer revaluation. Consumption-advice lifecycle and retroactive consignment pricing are research candidates, not yet implemented. This source describes EBS, not current Fusion behavior. |
| [Oracle Fusion invoice matching](https://docs.oracle.com/en/cloud/saas/financials/25d/fappp/matching-invoice-lines.html) | Receipt matching and consumption-advice matching differ from matching a purchase order. | Candidate for a future receipt/invoice matching workflow; current AP bridge handles approved revisions and credit-note dependencies, not full matching. |
| [Microsoft engineering change management](https://learn.microsoft.com/en-us/dynamics365/supply-chain/engineering-change-management/engineering-change-management) | Change impact spans open orders and inventory; notification ownership differs for production resources. | Candidate extension to the existing engineering families; not added to this research manifest. |

SAP valued-stock-in-transit documentation was also searched, but the fetched page
had no readable body. Its search snippet is not treated as a verified implementation
specification.

### Additional researched exception candidates (not in the frozen suite)

- [Microsoft catch-weight warehouse processing](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/catch-weight-processing): receiving and issuing weights can differ, and capture timing and variance policy affect adjustments. A future case should reconcile handling-unit count, actual mass, nominal conversion, remaining-stock tolerances and the adjustment ledger. The same documentation explicitly excludes several combinations, including manual quarantine orders and batch balancing. Do not combine these features into a supposedly authentic Dynamics workflow. Such a cross-system synthetic workflow would need its own explicit contract.
- [Oracle outside processing](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faims/how-outside-processing-is-managed-and-executed.html): a candidate supplier-operation workflow spanning production and procurement. Detailed exception transitions still need specification and independent qualification before implementation.
- [Microsoft invoice matching validation](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/tasks/set-up-accounts-payable-invoice-matching-validation): a candidate extension for matching-policy and tolerance configuration. Do not mistake the current approved-document bridge for a full matching engine.

These are a research backlog, not additional measured benchmark coverage. The active
evaluation remains frozen; adding cases after seeing model outputs would require a
new version and separately reported results.

## New suite: 0.10.0-researched.1

Eight fixed-seed tasks in `data/researched/tasks.json` add a separate cost subledger
to the professional operating-review workflow. They combine insurance claims, AP
revisions, credit notes, FX, payment cutoff and the new receipt/transfer cost tree.
The agent must disclose the node-level bridge and propagate only the expense
adjustment into the reserve and executive brief. Inventory value and supplier
liability must reconcile without being misclassified as incident expense or AP cash.
The quarantine availability figures concern this separate cost subledger, not a
new fulfillment allocation pool. No hidden rules or undisclosed vendor knowledge
are required. The native-file template from 0.9 has not been extended for this new
bridge; this evaluation is the tool-based structured-deliverable track.

Reproduction:

```sh
python examples/generate_researched.py
python -m pytest tests/test_cost_propagation.py -q
```

All eight reference workflows pass and replay exactly. A 100-seed property check
verifies signed adjustment conservation, logical-node traversal, ownership exclusion
and quarantine availability. This is feasibility/grader evidence, not model difficulty.
The saved qualification report `reports/researched-qualification.json` additionally
records eight positive controls and 32 rejected corruptions: missing cost bridge,
inventory misclassified as expense, quarantined stock marked available, and an
unbalanced supplier-liability adjustment. These are deterministic controls, not
model attempts.

## Measurement protocol

The first pilot selects tasks 001 and 002 before observing outputs. Both GPT-5.4 and
GPT-5.5 use the same tool-only harness, `xhigh` reasoning, 32,768 output tokens per
response, 100,000 output tokens per episode and a 1,800-second episode timeout.
No code interpreter, search or reference solver is exposed. Source and manifest
hashes are recorded in `runs/researched-20260915-pilot/frozen-manifest.json` before
requests begin. Do not change task/grader/harness code during this run.

Report strict success, partial-credit diagnostic scores, failed criteria, usage and
latency per episode. Record interruptions, truncation and infrastructure failures
separately. Never call a truncated or interrupted run evidence of intrinsic task
inability. These are public-development cases, not a private holdout or a statistical
estimate of real-world reliability. Four pilot episodes are not the full eight-case
comparison. No outcome-based case filtering or silent reruns are permitted.

The first launch failed before API requests because the local benchmark environment
lacked python-dotenv. The resumed launch uses the existing system dotenv installation
and the benchmark virtual environment for the Responses adapter. This setup failure
is not a model attempt.

### Pilot audit and revised frozen protocol: 0.10.0-researched.2

The first completed GPT-5.5 pilot attempt scored 65.63 but exhausted 100 tool calls
while revising its exception register. Audit found that the exact customer status
labels were not disclosed and the cash duplicate reason was described ambiguously.
The pilot was stopped; two live episodes were interrupted. All three saved attempts
are excluded via the pilot's cancellation manifest. They are diagnostic evidence,
not a model capability comparison. No difficulty claim is based on their scores.

The revised manifest is `data/researched-v2/tasks.json`. It retains all eight seeds
and business calculations, and explicitly supplies status labels, cash exclusion
labels, citation requirements, and the requirement to read but reject legacy sources.
It allows 300 tool calls and a 600-minute simulated review horizon, so revisions are
not artificially constrained by the original 100-call ceiling. Business due dates
and the minute-40 source cutoff are unchanged. API settings remain matched and
unchanged. The revised eight-case comparison is a new version, not a silent rerun
or a result pooled with the pilot. No cases are filtered based on model outcomes.

All eight revised reference workflows pass and replay exactly; all 32 revised
negative controls are rejected (`reports/researched-v2-qualification.json`).

Before publishing the revised comparison, verify complete paired coverage, source
and adapter hashes, inference settings, exact tool replay, final state hashes and
independently recomputed scores:

```sh
python examples/audit_frontier.py runs/researched-v2-20260915 \
  --tasks data/researched-v2/tasks.json --output reports/researched-v2-model-audit.json
python examples/summarize_frontier.py runs/researched-v2-20260915 \
  --output reports/researched-v2-model-results.json
```

The audit deliberately fails while attempts are missing. Seven reporting-integrity
tests cover a valid synthetic report plus missing attempts, interruptions, changed
settings, altered scores, altered traces and incomplete source freezes. These tests
do not call a model. Agent execution errors can make exact replay unavailable because
the runner records those outside the tool trace; if observed, document that limitation
explicitly instead of silently discarding the attempt or claiming the audit passed.

For cumulative output-cap exits only, the audit can reconstruct the known runner
exit marker before the final failed `finish` call. This requires usage evidence at
or above the frozen cap, the exact expected exit message, matching pre-exit logical
time, every tool result and state hash, and a matching independently recomputed
score. It is labelled `token_cap_exit_reconstructed`, not `exact_tool_replay`.
Two additional tests verify rejection below the cap and successful reconstruction
at the cap. Other infrastructure errors are not automatically explained this way.

### V2 withdrawal and V3 fairness gate

V2 was stopped after its first pair of attempts reached the output-token cap.
GPT-5.4's partial score was 78.83 and GPT-5.5's was 74.99; neither establishes a
model ranking. Their financial field checks passed, but publication was obstructed
by exception-register mismatches. Review found an additional defect: corrected
exception records did not supersede old active rows, making some corrections
impossible to publish. Nested case IDs were implied rather than fully specified,
and exact-content matching rejected additional audit metadata. All four saved V2
attempts (including the interrupted second pair) are excluded by its cancellation
manifest. Remaining cases never started. Do not pool V1 or V2 with V3 results.

V3 (`data/researched-v3/tasks.json`, version `0.10.0-researched.3`) keeps the same
eight seeds, business calculations and generous V2 budgets. It adds:

- Complete nested structural schemas and field-level structural error feedback.
  Neither contains solved business values or an answer-oracle tool.
- A disclosed annotation allowlist: `id`, `created_minute`, `supersedes`, `notes`,
  `metadata`. Other unexpected fields and wrong required values still fail.
- Explicit latest-resolution semantics per `(case_id, exception_id)`. Corrections
  supersede prior active records while preserving historical records and tool traces.
- Resolution changes invalidate outstanding publication approvals for that case;
  a corrected package requires fresh approval. Unknown exception IDs are rejected
  before state changes, and the previously implied source order is now explicit.
- Recovery controls for every seed: a deliberately incorrect resolution can be
  corrected immediately, or after a failed publication, and then published.
- Publication is atomic across the four artifacts: all content and citation checks
  pass before any artifact is marked published. A failed final-artifact check cannot
  leave the first three artifacts partially published.

The V3 qualification report is `reports/researched-v3-qualification.json`. The
model run must use a fresh frozen directory and identical settings for both models.
These fairness changes remove artificial traps; they do not lower the business
correctness requirements or justify claiming that either model will fail.

The V3 run directory is `runs/researched-v3-20260915`, with eight preselected tasks
per model and a fresh frozen manifest. To audit and summarize it, use the commands
above with this directory, `--tasks data/researched-v3/tasks.json`, and V3 report
filenames. Older excluded directories must not be included in the comparison.

The frozen V3 implementation passed 244 regression tests with zero failures,
errors or skips (`reports/researched-v3-regression.xml`). This includes 28
artifact-contract and recovery tests. Qualification remains eight positive
reference cases and 32 rejected cost-bridge corruptions. These are implementation
checks, not evidence of model difficulty.

## Additional researched exceptions — not in the frozen decision-v3 run

Reviewed 2026-09-15. These are candidate extensions, not implemented coverage or
measured model failures. Keep them separate from the running eight-case manifest.

### Subcontractor consumption corrections

[SAP's subcontracting lesson](https://learning.sap.com/courses/detailing-subcontracting-and-supplier-consignment/outlining-subcontracting_af403e3e-188d-4dbb-bde1-632253739fa6)
explains that supplied components remain the procurer's valuated inventory in
vendor-related special stock. Finished-goods receipt also consumes components;
late reports of excess or reduced consumption require subsequent adjustment.
Consumption draws from unrestricted rather than inspection stock. The lesson
explicitly distinguishes subcontracting from external processing.

Candidate synthetic work sample: reconcile partial receipts, supplier statements,
quality status and component consumption; distinguish late corrections from a
second receipt; produce mutually consistent stock, valuation and exception
ledgers. Test that a correction neither creates duplicate finished goods nor
consumes inspection stock. Exact posting conventions, reversal precedence and
cost-allocation policy must be disclosed and independently qualified; they are
not established by this lesson alone.

### Transfer price versus propagated sending cost

[Oracle's 26b worked example](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26b/fapma/example-of-accounting-of-interorganization-transfers-with-cost.html)
describes an expense-destination transfer across profit-center business units
using financial orchestration. Its established transfer price stays fixed;
the sending-cost adjustment changes interorganization gain/loss. Logical receipt
events replace manual receipt events when a destination receipt is not required.
This is not a rule that every transfer reprices destination inventory.

Candidate synthetic work sample: discriminate same-unit inventory propagation
from the documented cross-unit expense-destination treatment, reconcile separate
subledgers, and avoid counting logical and physical receipt records twice. Wrong
but balanced journals must fail when posted to the wrong entity or cost basis.
Closed-period treatment requires a separate authoritative source and is not
claimed here. Use original synthetic amounts, not copied vendor example data.
