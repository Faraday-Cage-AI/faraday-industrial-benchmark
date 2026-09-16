from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.contingent import MODES, branch_cost, solve_branch
from faraday_industrial_benchmark.coupled import group_charge, terminal_charge
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario

TASKS = load_tasks(Path(__file__).parents[1] / "data/long-tail/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_long_tail_end_to_end(task):
    score = BenchmarkRunner().run_task(task, OracleAgent()).score
    assert score.strict_success, [(c.id, c.detail) for c in score.criteria if not c.passed]


def test_override_scope_and_replacement():
    group = {
        "minimum_orders": 1,
        "paired_first_two": True,
        "service_credit_cents": [0, 10, 100, 1000],
        "scenario_overrides": {
            "emergency": {
                "paired_first_two": False,
                "prohibited_modes": ["standard"],
                "service_credit_cents": [0, 90, 900, 9000],
            }
        },
    }
    assert group_charge(group, ["stock", "express", "defer"]) is None
    assert group_charge(group, ["stock", "express", "defer"], {"id": "emergency"}) == 90
    assert group_charge(group, ["stock", "standard", "defer"], {"id": "emergency"}) is None
    assert group_charge(group, ["defer"] * 3, {"id": "emergency"}) is None
    assert group_charge(group, ["stock", "stock", "defer"], {"id": "normal"}) == 10


def test_minimum_dispatch_is_aggregate_and_zero_exempt():
    case = {
        "coupling": {
            "activation_fees_cents": {"stock": 10, "standard": 20, "express": 30},
            "dispatch_overrides": {
                "tail": {
                    "minimum_packs": {"express": 6},
                    "activation_fees_cents": {"express": 100},
                }
            },
        }
    }
    scenario = {"id": "tail"}
    assert terminal_charge(case, (2, 0, 0), scenario) == 10
    assert terminal_charge(case, (2, 0, 5), scenario) is None
    assert terminal_charge(case, (2, 0, 6), scenario) == 110
    assert terminal_charge(case, (2, 0, 7), scenario) == 110
    assert terminal_charge(case, (2, 0, 5), {"id": "normal"}) == 40


def test_multigroup_solver_matches_exhaustive_assignments():
    case = deepcopy(build_scenario(TASKS[0]).state["network_truth"]["case"])
    # Two groups independently consume resources, but the carrier floor is global.
    groups = sorted(
        case["coupling"]["customers"], key=lambda g: not bool(g.get("scenario_overrides"))
    )[:2]
    case["coupling"]["customers"] = groups
    ids = {oid for group in groups for oid in group["orders"]}
    case["orders"] = [o for o in case["orders"] if o["order_id"] in ids]
    for scenario in case["scenarios"][-2:]:
        for tier in (0, 1, 2):
            reservations = {"standard": tier, "express": tier}
            costs = []
            for modes in product(MODES, repeat=6):
                assignments = [
                    {"order_id": o["order_id"], "mode": m} for o, m in zip(case["orders"], modes)
                ]
                cost, _ = branch_cost(case, reservations, scenario, assignments)
                if cost is not None:
                    costs.append(cost)
            actual = solve_branch(case, reservations, scenario)
            assert (actual[0] if actual else None) == (min(costs) if costs else None)
