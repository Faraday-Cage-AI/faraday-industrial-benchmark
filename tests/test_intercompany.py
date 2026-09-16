from copy import deepcopy
from fractions import Fraction
from math import floor
from pathlib import Path
from random import Random

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.intercompany import generate_intercompany, reconcile_intercompany
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.subcontracting import (
    generate_subcontracting,
    reconcile_subcontracting,
)


def fixture():
    transfers = [
        {
            "transfer_id": "A",
            "source_receipt_id": "R",
            "source_shipped_quantity": 4,
            "quantity": 1,
            "sender": "S",
            "receiver": "D1",
            "receipt_mode": "logical",
            "locked_unit_price_cents": 600,
            "status": "active",
        },
        {
            "transfer_id": "B",
            "source_receipt_id": "R",
            "source_shipped_quantity": 4,
            "quantity": 3,
            "sender": "S",
            "receiver": "D2",
            "receipt_mode": "manual",
            "locked_unit_price_cents": 600,
            "status": "active",
        },
    ]
    events = [
        {
            "record_id": tid,
            "event_id": tid,
            "sequence": n,
            "status": "approved",
            "transfer_id": tid,
            "channel": channel,
            "quantity": 1,
        }
        for n, tid, channel in ((1, "A", "logical"), (2, "B", "physical"))
    ]
    return {"cutoff": 10, "transfers": transfers, "receipt_events": events}


def bridge(cost):
    return {"receipts": [{"receipt_id": "R", "cogs_cents": cost, "reversed": False}]}


def test_hand_calculated_partial_delivery_and_elimination():
    result = reconcile_intercompany(fixture(), bridge(1200))
    assert result["group_expense_cents"] == 600
    assert result["group_transit_cents"] == 600
    assert result["reserve_reclassification_cents"] == -600
    assert result["transfers"][1]["receiver_transit_cents"] == 1200
    accounts = {}
    for line in result["journal_lines"]:
        accounts[line["account"]] = accounts.get(line["account"], 0) + line["signed_debit_cents"]
    assert accounts == {
        "IC-receivable": 0,
        "source-dispatch-cost": -1200,
        "intercompany-margin": 0,
        "expense": 600,
        "trade-in-transit": 600,
        "IC-payable": 0,
    }


@pytest.mark.parametrize("cost", [1, 1201, 1604, 3000])
def test_late_cost_changes_never_reprice_receiver(cost):
    result = reconcile_intercompany(fixture(), bridge(cost))
    assert sum(r["locked_price_cents"] for r in result["transfers"]) == 2400
    assert sum(r["receiver_expense_cents"] for r in result["transfers"]) == 1200
    assert sum(r["sender_margin_cents"] for r in result["transfers"]) == 2400 - cost
    assert result["group_expense_cents"] + result["group_transit_cents"] == cost
    assert sum(r["source_cost_cents"] for r in result["transfers"]) == cost


def test_logical_and_physical_receipts_cannot_double_count():
    contract = fixture()
    base = reconcile_intercompany(contract, bridge(1200))
    event = contract["receipt_events"][1]
    contract["receipt_events"] += [
        {**event, "record_id": "DUP", "sequence": 3},
        {**event, "record_id": "WRONG", "event_id": "WRONG", "sequence": 4, "channel": "logical"},
        {**event, "record_id": "EXCESS", "event_id": "EXCESS", "sequence": 5, "quantity": 3},
    ]
    result = reconcile_intercompany(contract, bridge(1200))
    assert result["transfers"] == base["transfers"]
    assert [r["reason"] for r in result["exclusions"]] == [
        "duplicate_event",
        "wrong_receipt_channel",
        "excess_receipt",
    ]


def test_nonpartitioning_transfer_is_rejected():
    contract = fixture()
    contract["transfers"][1]["quantity"] = 4
    with pytest.raises(ValueError, match="partition"):
        reconcile_intercompany(contract, bridge(1200))


def test_exhaustive_partial_receipts_rounding_and_entity_balances():
    # Independent rational arithmetic, including zero cost and negative margin.
    # Check every possible partial receipt, not just the generated happy path.
    for cost in (0, 1, 2, 3, 7, 1201, 2401, 10001):
        for first_received in range(2):
            for second_received in range(4):
                contract = fixture()
                contract["receipt_events"] = [
                    {**event, "quantity": quantity}
                    for event, quantity in zip(
                        contract["receipt_events"], (first_received, second_received)
                    )
                    if quantity
                ]
                result = reconcile_intercompany(contract, bridge(cost))
                first_cost = floor(Fraction(cost, 4))
                expected_expense = first_cost * first_received + floor(
                    Fraction((cost - first_cost) * second_received, 3)
                )
                assert result["group_expense_cents"] == expected_expense
                assert result["group_transit_cents"] == cost - expected_expense
                balances = {}
                for line in result["journal_lines"]:
                    key = (line["transfer_id"], line["entity"])
                    balances[key] = balances.get(key, 0) + line["signed_debit_cents"]
                assert set(balances.values()) == {0}


def test_rejected_business_event_consumes_id_but_draft_does_not():
    contract = fixture()
    event = contract["receipt_events"][1]
    contract["receipt_events"] = [
        {**event, "record_id": "draft", "sequence": 1, "status": "draft"},
        {**event, "record_id": "wrong", "sequence": 2, "channel": "logical"},
        {**event, "record_id": "retry", "sequence": 3},
        {**event, "record_id": "new-id", "event_id": "new", "sequence": 4},
    ]
    result = reconcile_intercompany(contract, bridge(1200))
    assert result["transfers"][1]["received_quantity"] == 1
    assert result["exclusions"] == [
        {"record_id": "draft", "reason": "not_approved"},
        {"record_id": "wrong", "reason": "wrong_receipt_channel"},
        {"record_id": "retry", "reason": "duplicate_event"},
    ]


def test_cutoff_boundary_and_equal_sequence_preserve_input_order():
    contract = fixture()
    event = contract["receipt_events"][1]
    contract["receipt_events"] = [
        {**event, "record_id": "first", "sequence": 10, "quantity": 2},
        {**event, "record_id": "second", "event_id": "second", "sequence": 10, "quantity": 2},
        {**event, "record_id": "future", "sequence": 11},
    ]
    result = reconcile_intercompany(contract, bridge(1200))
    assert result["transfers"][1]["received_quantity"] == 2
    assert result["exclusions"] == [
        {"record_id": "second", "reason": "excess_receipt"},
        {"record_id": "future", "reason": "after_cutoff"},
    ]


def test_generated_subcontracting_corrections_propagate_across_books():
    for seed in range(100):
        rng = Random(seed)
        subcontract = generate_subcontracting(rng)
        costs = reconcile_subcontracting(subcontract)
        contract = generate_intercompany(subcontract, rng)
        result = reconcile_intercompany(contract, costs)
        assert result["group_transit_cents"] > 0
        assert result["reserve_reclassification_cents"] < 0
        changed = deepcopy(costs)
        changed["receipts"][0]["cogs_cents"] += 100
        corrected = reconcile_intercompany(contract, changed)
        assert [r["locked_price_cents"] for r in corrected["transfers"]] == [
            r["locked_price_cents"] for r in result["transfers"]
        ]
        assert corrected["group_transit_cents"] > result["group_transit_cents"]


TASKS = load_tasks(Path(__file__).parents[1] / "data/close-chain/tasks.json") + load_tasks(
    Path(__file__).parents[1] / "data/close-chain-v2/tasks.json"
)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_close_chain_reference_and_replay(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
@pytest.mark.parametrize(
    "mistake", ["wrong_entity", "omit_elimination", "reprice", "expense_transit", "double_payable"]
)
def test_balanced_or_consistent_wrong_close_cannot_publish(task, mistake):
    class WrongClose:
        name = mistake

        def run(self, task, tools):
            reserve_delta = 0

            class Proxy:
                def call(self, name, **arguments):
                    nonlocal reserve_delta
                    arguments = deepcopy(arguments)
                    if name == "create_structured_artifact":
                        content = arguments["content"]
                        if arguments["artifact_type"] == "integrated_recovery_model":
                            impact = content["financial_impact"]
                            inter = impact["intercompany_bridge"]
                            if mistake == "wrong_entity":
                                # Move a balanced sender journal to the wrong entity.
                                for line in inter["journal_lines"]:
                                    if line["entity"] == "PLANT":
                                        line["entity"] = "DISTRIBUTION"
                            elif mistake == "omit_elimination":
                                inter["journal_lines"] = [
                                    r for r in inter["journal_lines"] if r["entity"] != "CONSOL"
                                ]
                            elif mistake == "reprice":
                                inter["transfers"][0]["locked_price_cents"] += 1
                            elif mistake == "expense_transit":
                                reserve_delta = inter["group_transit_cents"] / 100
                                inter["reserve_reclassification_cents"] = 0
                            else:
                                reserve_delta = (
                                    sum(r["locked_price_cents"] for r in inter["transfers"]) / 100
                                )
                            impact["reserve_amount"] += reserve_delta
                        elif arguments["artifact_type"] == "executive_decision_brief":
                            # Preserve cross-artifact reserve agreement: business correctness
                            # must still reject the wrong but internally consistent amount.
                            content["reserve_amount"] += reserve_delta
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    episode = BenchmarkRunner().run_task(task, WrongClose())
    assert not episode.score.strict_success
    assert not next(c for c in episode.score.criteria if c.id == "publication-execution").passed
