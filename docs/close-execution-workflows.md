# Stateful close execution

`0.14.0-close-execution.1`, eight fixed cases in
`data/close-execution/tasks.json`. This is a separate, unmeasured extension of
close-chain V2, not a replacement or a pooled model result.

The preceding tier requires deriving a coherent recovery plan and accounting
bridge. This tier also requires carrying it out across entity ledgers:

1. Derive the corrected subcontracting costs, receipt quantities and eliminations.
2. Post each sender journal through an approval-bound execution.
3. Investigate a receiver exception surfaced after its sender commits. Reconcile
   partial receipt evidence instead of accepting the receiver's full-receipt request.
4. Release that hold with the correct received/in-transit quantities, then post
   receiver journals. Previously committed sender entries remain intact.
5. Post consolidation entries only after both corresponding entity postings.
6. Read the actual posting receipts, reconcile the completed ledger, and publish
   the four consistent operating-review deliverables with separate approval.

One sender posting commits but loses its acknowledgement. A failed response does
not imply rollback. The agent can inspect the live ledger and continue, or safely
retry with fresh approval and exactly the same idempotency key and payload.
Changing the key cannot create another posting. Reusing a key with different
business values is rejected. Incorrect journals and premature steps mutate no
ledger state. A balanced but economically wrong journal is insufficient.

## Public contract and boundaries

All action names, payload requirements, dependency rules and recovery semantics
are disclosed in the program-office delivery contract. Stage metadata and live
posting receipts are available through `get_incident`; expected journal values
and hold answers are not. The source evidence and disclosed arithmetic determine
the correct values. The same minute-300 finish target, 900-minute hard horizon
and 400-call cap apply. Earlier versions remain unchanged.

This is a deterministic synthetic transaction workflow. It does not connect to
production ERP systems, simulate every distributed-system failure, or establish
model difficulty merely by adding steps. No paid model attempts exist for this
version yet. Its reference trajectory is qualification, not a leaderboard result.

## Verification

`tests/test_close_execution.py` covers all eight full reference trajectories and
exact replay, an actual lost-acknowledgement commit followed by safe retry,
duplicate-key conflicts, prerequisite rejection, hold resolution, incorrect
balanced journals, and refusal to publish correct artifacts without execution.
Run `pytest tests/test_close_execution.py` for this targeted qualification.
