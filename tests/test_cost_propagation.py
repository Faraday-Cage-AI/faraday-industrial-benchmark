from copy import deepcopy
from pathlib import Path
from random import Random

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.cost_propagation import generate_costs, reconcile_costs
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner


@pytest.mark.parametrize("delta", [100, -100])
def test_hand_calculated_stopped_branch_and_logical_override(delta):
    def node(name, hand, consumed, children=(), **overrides):
        return dict(
            id=name,
            quantity=hand + consumed + sum(c["quantity"] for c in children),
            on_hand=hand,
            consumed=consumed,
            children=list(children),
            logical=False,
            method="actual",
            propagate=True,
            quarantine="none",
            **overrides,
        )

    hidden = node("hidden", 2, 1)
    stopped = node("stopped", 4, 2, [hidden])
    stopped["method"] = "standard"
    logical = node("logical", 0, 0, [stopped])
    logical.update(logical=True, propagate=False, method="standard")
    held = node("held", 3, 1)
    held["quarantine"] = "reported_finished"
    root = node("root", 5, 2, [logical, held])
    result = reconcile_costs(
        {
            "receipts": [
                {
                    "id": "r",
                    "owner": "buyer",
                    "status": "approved",
                    "old_unit_cents": 1000,
                    "new_unit_cents": 1000 + delta,
                    "root": root,
                }
            ]
        }
    )
    # Twenty units: eight remain valued, twelve expensed (including stopped subtree).
    assert result["inventory_adjustment_cents"] == 8 * delta
    assert result["expense_adjustment_cents"] == 12 * delta
    assert result["liability_adjustment_cents"] == 20 * delta
    rows = {r["node_id"]: r for r in result["nodes"]}
    assert "hidden" not in rows
    assert rows["logical"]["propagated"]
    assert not rows["stopped"]["propagated"]
    assert rows["held"]["available_quantity"] == 0
    assert rows["held"]["inventory_adjustment_cents"] == 3 * delta


def test_conservation_signed_revaluation_and_ownership():
    for seed in range(100):
        contract = generate_costs(Random(seed))
        result = reconcile_costs(contract)
        assert (
            result["inventory_adjustment_cents"] + result["expense_adjustment_cents"]
            == result["liability_adjustment_cents"]
        )
        assert [r["reason"] for r in result["exclusions"]] == [
            "supplier_owned",
            "unapproved_adjustment",
        ]
        assert (
            next(r for r in result["nodes"] if r["node_id"] == "DC-QUALITY")["available_quantity"]
            == 0
        )
        assert next(r for r in result["nodes"] if r["node_id"] == "LOGICAL-TRANSIT")["propagated"]
        reverse = deepcopy(contract)
        receipt = reverse["receipts"][0]
        receipt["new_unit_cents"], receipt["old_unit_cents"] = (
            receipt["old_unit_cents"],
            receipt["new_unit_cents"],
        )
        reversed_result = reconcile_costs(reverse)
        assert reversed_result["expense_adjustment_cents"] == -result["expense_adjustment_cents"]


@pytest.mark.parametrize(
    "task",
    load_tasks(Path(__file__).parents[1] / "data/researched/tasks.json")
    + load_tasks(Path(__file__).parents[1] / "data/researched-v2/tasks.json")
    + load_tasks(Path(__file__).parents[1] / "data/researched-v3/tasks.json"),
    ids=lambda t: f"{t.version}-{t.id}",
)
def test_researched_reference_and_replay(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]
