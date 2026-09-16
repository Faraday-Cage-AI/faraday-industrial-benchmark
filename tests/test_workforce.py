from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.contingent import MODES, branch_cost, solve_branch
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario
from faraday_industrial_benchmark.workforce import resource_limits, resource_usage

TASKS = load_tasks(Path(__file__).parents[1] / "data/workforce/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_workforce_full_workflow(task):
    score = BenchmarkRunner().run_task(task, OracleAgent()).score
    assert score.strict_success, [(c.id, c.detail) for c in score.criteria if not c.passed]


def test_resource_units_scope_and_zero_usage():
    case = {
        "coupling": {
            "shared_resources": [
                {
                    "limit": 3,
                    "scenario_limits": {"absence": 1},
                    "per_order_by_mode": {"stock": 1, "standard": 2, "express": 1, "defer": 0},
                }
            ]
        }
    }
    assert resource_limits(case, {"id": "normal"}) == (3,)
    assert resource_limits(case, {"id": "absence"}) == (1,)
    assert resource_usage(case, [{"mode": "standard"}, {"mode": "defer"}]) == (2,)
    assert resource_usage(case, []) == (0,)
    assert resource_limits({}, {}) == ()


def test_extended_optimizer_against_exhaustive_search():
    case = deepcopy(build_scenario(TASKS[0]).state["network_truth"]["case"])
    groups = case["coupling"]["customers"][:2]
    case["coupling"]["customers"] = groups
    ids = {oid for group in groups for oid in group["orders"]}
    case["orders"] = [o for o in case["orders"] if o["order_id"] in ids]
    # Tighten resources so the reduced slice exercises the new DP dimensions.
    for resource in case["coupling"]["shared_resources"]:
        resource["limit"] = 4
        resource["scenario_limits"] = {}
    for scenario in case["scenarios"][-2:]:
        reservation = {"standard": 2, "express": 2}
        best = None
        for modes in product(MODES, repeat=6):
            rows = [{"order_id": o["order_id"], "mode": m} for o, m in zip(case["orders"], modes)]
            cost, _ = branch_cost(case, reservation, scenario, rows)
            if cost is not None and (best is None or cost < best):
                best = cost
        actual = solve_branch(case, reservation, scenario)
        assert (actual[0] if actual else None) == best


def test_resource_limits_are_enforced_at_boundary():
    case = deepcopy(build_scenario(TASKS[0]).state["network_truth"]["case"])
    scenario = case["scenarios"][0]
    reservation = {"standard": 2, "express": 2}
    _, rows = solve_branch(case, reservation, scenario)
    usage = resource_usage(case, rows)
    for resource, amount in zip(case["coupling"]["shared_resources"], usage):
        resource["limit"] = amount
    assert branch_cost(case, reservation, scenario, rows)[0] is not None
    # Refundable deposits constrain liquidity; they are not an extra expense.
    without_resources = deepcopy(case)
    without_resources["coupling"].pop("shared_resources")
    assert branch_cost(case, reservation, scenario, rows) == branch_cost(
        without_resources, reservation, scenario, list(reversed(rows))
    )
    case["coupling"]["shared_resources"][0]["limit"] = usage[0] - 1
    assert branch_cost(case, reservation, scenario, rows)[0] is None
