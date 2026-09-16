from copy import deepcopy
from random import Random

from faraday_industrial_benchmark.finance_tail import convert, generate_finance, reconcile_finance


def test_signed_rounding():
    assert convert(1, [1, 2]) == 1
    assert convert(-1, [1, 2]) == -1
    assert convert(3, [1, 2]) == 2


def test_manual_credit_revision_and_cash_bridge():
    contract = generate_finance(Random(1), "Q1")
    for row in contract["documents"]:
        row["amount_minor"] = 100
    contract["fx"]["EUR"] = [3, 2]
    contract["documents"][1]["amount_minor"] = 201
    contract["documents"][5]["amount_minor"] = 11
    for row in contract["payments"]:
        row["amount_minor"] = 21
    result = reconcile_finance(contract)
    # Approved revision 201*1.5=302, USD invoice 100, credit 11*1.5=17.
    assert result["expense_cents"] == 385
    assert result["settled_cash_cents"] == 32
    assert result["remaining_payable_cents"] == 353
    assert [r["reason"] for r in result["exclusions"]] == [
        "superseded_revision",
        "unapproved",
        "outside_service_period",
        "unrecognized_parent",
    ]
    assert [r["reason"] for r in result["cash_exclusions"]] == [
        "duplicate_payment",
        "after_cash_cutoff",
        "unsettled",
    ]
    # Credit-parent recognition must not depend on document order.
    reversed_contract = deepcopy(contract)
    reversed_contract["documents"].reverse()
    assert reconcile_finance(reversed_contract)["ledger"] == result["ledger"]
    # Payment timing changes liquidity, never expense recognition.
    contract["cash_cutoff_day"] = 29
    assert reconcile_finance(contract)["settled_cash_cents"] == 0
    assert reconcile_finance(contract)["expense_cents"] == 385
    contract["cash_cutoff_day"] = 30
    contract["payments"][0]["amount_minor"] = 1000
    assert reconcile_finance(contract)["remaining_payable_cents"] == -1115
