from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.contingent import (
    MODES,
    branch_cost,
    solve,
    solve_branch,
    validate_policy,
)
from faraday_industrial_benchmark.coupled import group_charge, surcharge
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario

TASKS = load_tasks(Path(__file__).parents[1] / "data/challenge/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_hard_suite_is_solvable(task):
    score = BenchmarkRunner().run_task(task, OracleAgent()).score
    assert score.strict_success, [(c.id, c.detail) for c in score.criteria if not c.passed]


def test_kit_and_customer_floor_are_not_independent_order_checks():
    group = {
        "minimum_orders": 1,
        "paired_first_two": True,
        "service_credit_cents": [0, 10, 100, 1000],
    }
    assert group_charge(group, ["stock", "express", "stock"]) is None
    assert group_charge(group, ["defer", "defer", "defer"]) is None
    assert group_charge(group, ["stock", "stock", "defer"]) == 10
    assert group_charge(group, ["defer", "defer", "stock"]) == 100


def test_coupled_solver_matches_brute_force():
    case = deepcopy(build_scenario(TASKS[0]).state["network_truth"]["case"])
    group = case["coupling"]["customers"][0]
    case["coupling"]["customers"] = [group]
    case["orders"] = [r for r in case["orders"] if r["order_id"] in group["orders"]]
    for tiers in product(range(3), repeat=2):
        reservation = dict(zip(("standard", "express"), tiers))
        for scenario in case["scenarios"]:
            feasible = []
            for modes in product(MODES, repeat=3):
                assignments = [
                    {"order_id": o["order_id"], "mode": m} for o, m in zip(case["orders"], modes)
                ]
                cost, _ = branch_cost(case, reservation, scenario, assignments)
                if cost is not None:
                    feasible.append(cost)
            actual = solve_branch(case, reservation, scenario)
            assert (actual[0] if actual else None) == (min(feasible) if feasible else None)


def test_fees_once_and_legacy_independent_solution_not_optimal():
    case = build_scenario(TASKS[0]).state["network_truth"]["case"]
    rows = [{"order_id": o["order_id"], "mode": "stock"} for o in case["orders"]]
    assert surcharge(case, rows) == case["coupling"]["activation_fees_cents"]["stock"]
    policy = solve(case)
    assert validate_policy(case, policy)["feasible"]
    relaxed = deepcopy(case)
    del relaxed["coupling"]
    shortcut = solve(relaxed)
    report = validate_policy(case, shortcut)
    assert (
        not report["feasible"] or report["worst_case_cost_cents"] > policy["worst_case_cost_cents"]
    )
