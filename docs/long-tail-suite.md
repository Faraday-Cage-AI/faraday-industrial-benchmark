# Long-tail contracts — 0.7.0-tail.1

24 deterministic synthetic cases, separately versioned in `data/long-tail/tasks.json`.
These extend the coupled hard suite rather than replacing previous episodes or scores.
They are designed operational exceptions, not proprietary customer incidents or a
sample from an estimated real-world failure distribution.

## Binding exceptions

Each case has twelve whole orders, four customer contracts and six disruption outcomes.
One supplier reservation must support every branch before the outcome is disclosed.

- Compound port and quality disruptions disqualify standard freight for one customer,
  without closing that lane for other customers.
- Emergency amendments waive a customer's installation-kit pairing rule in one
  scenario only. The minimum-service floor and other base obligations still apply.
- Scenario-specific service-credit schedules replace ordinary schedules. Credits
  remain additional to individual deferral penalties.
- Emergency carriers impose minimum total dispatch loads across customers. Sending
  zero packs is legal; sending a positive quantity below the minimum is not.
- Emergency activation fees replace ordinary fees and apply once per used mode,
  not once per order or customer.

Affected customers, dispatch thresholds, fees and underlying operating data vary by
seed. These interact with stock reconciliation, deadlines, emissions, shared capacity,
mandatory orders, commercial revisions, approvals and exact committed execution.
All operative terms are disclosed in authoritative GRC records.

Strict success requires every criterion and exact lexicographic optimization:
first worst-case cost, then aggregate scenario cost among worst-case ties.
Partial-credit averages are diagnostic, not a substitute for strict success.

## Reproduction and controls

```sh
python examples/generate_long_tail.py
faraday-bench validate --tasks data/long-tail/tasks.json
python -m pytest tests/test_long_tail.py -q
python examples/qualify_long_tail.py
faraday-bench run --tasks data/long-tail/tasks.json --agent oracle --output runs/long-tail-oracle.json
```

The generator uses fixed seeds and does not filter cases based on model performance.
Tests exercise the entire tool/approval/execution workflow in every case; verify
override scope, replacement semantics and dispatch boundaries; and compare the
dynamic program against exhaustive assignment enumeration for a two-customer slice.
The latter checks optimizer search independently, but shares the business-rule cost
function; focused rule tests provide separate coverage of those semantics.

`reports/long-tail-qualification.json` records three algorithmic controls: an optimizer
that ignores customer amendments, one that ignores carrier amendments, and one that
ignores both. Their plans are evaluated against the full contract. These controls
measure the consequences of dropping constraints; they are **not LLM results**.

On the 24 published seeds, ignoring customer amendments fails the exact contract
objective in 22 cases; ignoring carrier amendments fails in 4; ignoring both fails
in 22. Some amendments do not change the optimal plan on every seed. These are
reported rather than filtered out to inflate difficulty.

This suite has not been measured against GPT-5.4 or GPT-5.5. Paid model runs remain
stopped. No claim about their failure rate, or superiority to other benchmarks, follows
from oracle solvability or control failures. Public seeds can be studied; future model
comparisons should freeze the harness and use separately held-out seeds and profiles.
