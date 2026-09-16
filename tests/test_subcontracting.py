from copy import deepcopy
from pathlib import Path
from random import Random

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.subcontracting import (
    generate_subcontracting,
    reconcile_subcontracting,
)

TASKS = load_tasks(Path(__file__).parents[1] / "data/subcontracting/tasks.json") + load_tasks(
    Path(__file__).parents[1] / "data/subcontracting-v2/tasks.json"
)


def fixture():
    def event(n, kind, **fields):
        return {
            "record_id": f"ROW-{n}",
            "event_id": f"EVT-{n}",
            "sequence": n,
            "status": "approved",
            "kind": kind,
            **fields,
        }

    def receipt(n, rid, quantity, a, b, service):
        return event(
            n,
            "receipt",
            receipt_id=rid,
            quantity=quantity,
            service_foreign_cents=service,
            components=[
                {"lot_id": "A", "quantity": a, "uom": "each"},
                {"lot_id": "B", "quantity": b, "uom": "each"},
            ],
        )

    return {
        "cutoff": 20,
        "fx_numerator": 3,
        "fx_denominator": 2,
        "uom_multipliers": {"each": 1, "pack10": 10},
        "opening_lots": [
            {
                "lot_id": "A",
                "quantity": 100,
                "unit_cents": 100,
                "owner": "buyer",
                "quality": "released",
            },
            {
                "lot_id": "B",
                "quantity": 50,
                "unit_cents": 200,
                "owner": "buyer",
                "quality": "released",
            },
            {
                "lot_id": "C",
                "quantity": 50,
                "unit_cents": 200,
                "owner": "supplier",
                "quality": "released",
            },
            {
                "lot_id": "D",
                "quantity": 20,
                "unit_cents": 500,
                "owner": "buyer",
                "quality": "inspection",
            },
        ],
        "events": [
            receipt(1, "R1", 10, 20, 10, 1000),
            event(2, "ship", receipt_id="R1", quantity=4),
            event(
                3,
                "correction",
                receipt_id="R1",
                lot_id="A",
                document_id="ADJ",
                revision=1,
                delta=5,
                uom="each",
            ),
            event(
                4,
                "correction",
                receipt_id="R1",
                lot_id="A",
                document_id="ADJ",
                revision=2,
                delta=-2,
                uom="each",
            ),
            receipt(5, "R2", 8, 16, 8, 800),
            event(6, "quality", target_type="finished", target_id="R2", quality="inspection"),
            receipt(7, "R3", 4, 8, 4, 400),
            event(8, "reverse", receipt_id="R3"),
        ],
    }


def test_hand_calculated_late_recost_and_reversal():
    result = reconcile_subcontracting(fixture())
    assert result["available_finished_quantity"] == 6
    assert result["closing_owned_component_value_cents"] == 23000
    assert result["finished_inventory_cents"] == 7580
    assert result["cogs_cents"] == 2120
    assert result["service_payable_cents"] == 2700
    assert result["opening_owned_component_value_cents"] == 30000
    assert result["receipts"][2]["reversed"]
    assert result["receipts"][2]["on_hand"] == 0
    assert result["receipts"][1]["available_quantity"] == 0
    assert result["receipts"][1]["inventory_cents"] == 4400


def test_failed_receipt_is_atomic():
    contract = fixture()
    base = reconcile_subcontracting(contract)
    bad = deepcopy(contract["events"][0])
    bad.update(record_id="BAD", event_id="BAD", sequence=9, receipt_id="BAD")
    # First component could be deducted before the second component is rejected.
    bad["components"][1]["lot_id"] = "D"
    contract["events"].append(bad)
    result = reconcile_subcontracting(contract)
    assert result["components"] == base["components"]
    assert result["receipts"] == base["receipts"]
    assert result["exclusions"] == [{"record_id": "BAD", "reason": "component_on_inspection"}]


def test_rejected_events_never_change_valid_balances():
    contract = fixture()
    base = reconcile_subcontracting(contract)
    extras = [
        {**contract["events"][3], "record_id": "DUP", "sequence": 9},
        {**contract["events"][2], "record_id": "OLD", "event_id": "OLD", "sequence": 10},
        {
            **contract["events"][2],
            "record_id": "REVERSED",
            "event_id": "REVERSED",
            "sequence": 11,
            "receipt_id": "R3",
        },
        {
            **contract["events"][1],
            "record_id": "HELD",
            "event_id": "HELD",
            "sequence": 12,
            "receipt_id": "R2",
        },
        {
            **contract["events"][7],
            "record_id": "SHIPPED",
            "event_id": "SHIPPED",
            "sequence": 13,
            "receipt_id": "R1",
        },
        {
            **contract["events"][2],
            "record_id": "DRAFT",
            "event_id": "DRAFT",
            "sequence": 14,
            "status": "draft",
        },
        {**contract["events"][2], "record_id": "FUTURE", "event_id": "FUTURE", "sequence": 30},
    ]
    contract["events"] += extras
    # Input order is not chronology.
    contract["events"].reverse()
    result = reconcile_subcontracting(contract)
    assert result["components"] == base["components"]
    assert result["receipts"] == base["receipts"]
    assert [r["reason"] for r in result["exclusions"]] == [
        "duplicate_event",
        "stale_correction_revision",
        "receipt_reversed",
        "finished_stock_on_inspection",
        "cannot_reverse_shipped_receipt",
        "not_approved",
        "after_cutoff",
    ]


def test_units_and_quality_release_are_material():
    contract = fixture()
    contract["events"][0]["components"][0].update(quantity=2, uom="pack10")
    assert reconcile_subcontracting(contract) == reconcile_subcontracting(fixture())
    contract["events"].append(
        {
            "record_id": "REL",
            "event_id": "REL",
            "sequence": 9,
            "status": "approved",
            "kind": "quality",
            "target_type": "finished",
            "target_id": "R2",
            "quality": "released",
        }
    )
    assert reconcile_subcontracting(contract)["available_finished_quantity"] == 14


def test_generated_events_require_multiple_exception_dispositions():
    for seed in range(100):
        result = reconcile_subcontracting(generate_subcontracting(Random(seed)))
        assert 10 <= result["available_finished_quantity"] <= 24
        assert {r["reason"] for r in result["exclusions"]} == {
            "duplicate_event",
            "stale_correction_revision",
            "finished_stock_on_inspection",
            "cannot_reverse_shipped_receipt",
            "receipt_reversed",
            "supplier_owned_component",
            "component_on_inspection",
            "not_approved",
            "after_cutoff",
        }


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_complete_subcontracting_workflow_replays(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
@pytest.mark.parametrize(
    "mistake", ["double_count_payable", "ignore_hold", "ignore_late_recost", "inflate_production"]
)
def test_downstream_mistakes_cannot_publish(task, mistake):
    class WrongAgent:
        name = mistake

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if (
                        name == "create_structured_artifact"
                        and arguments["artifact_type"] == "integrated_recovery_model"
                    ):
                        content = arguments["content"]
                        impact = content["financial_impact"]
                        bridge = impact["subcontract_bridge"]
                        if mistake == "double_count_payable":
                            impact["reserve_amount"] += bridge["service_payable_cents"] / 100
                        elif mistake == "ignore_hold":
                            bridge["available_finished_quantity"] += 1
                        elif mistake == "ignore_late_recost":
                            bridge["cogs_cents"] += 1
                        else:
                            content["production_plan"]["quantity"] += 1
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    episode = BenchmarkRunner().run_task(task, WrongAgent())
    assert not episode.score.strict_success
    assert not next(c for c in episode.score.criteria if c.id == "publication-execution").passed
