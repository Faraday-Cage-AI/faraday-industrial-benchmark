from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.contingent import (
    MODES,
    apply_action,
    branch_cost,
    reservation_fee,
    solve,
    validate_policy,
)
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario
from faraday_industrial_benchmark.world import IndustrialWorld

TASKS = load_tasks(Path(__file__).parents[1] / "data/decision-challenge/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_complete_firm_workflow(task):
    runner = BenchmarkRunner()
    result = runner.run_task(task, OracleAgent())
    assert result.score.strict_success
    assert runner.replay(task, result.to_dict()["trace"])["exact_match"]


def test_firm_contract_rejects_missing_extra_and_hindsight_modes():
    case = build_scenario(TASKS[0]).state["network_truth"]["case"]
    policy = solve(case)
    assert validate_policy(case, policy)["feasible"]
    for releases in (
        {},
        {**policy["firm_releases"], "unknown": "defer"},
        {key: "invalid" for key in policy["firm_releases"]},
    ):
        changed = deepcopy(policy)
        changed["firm_releases"] = releases
        assert not validate_policy(case, changed)["feasible"]
    changed = deepcopy(policy)
    oid = next(iter(changed["firm_releases"]))
    changed["firm_releases"][oid] = next(
        mode for mode in MODES if mode != changed["firm_releases"][oid]
    )
    assert not validate_policy(case, changed)["feasible"]
    for rows in policy["branches"].values():
        rows.reverse()
    assert validate_policy(case, policy)["feasible"]


@pytest.mark.parametrize("minute,allowed", [(180, True), (181, False), (200, False)])
def test_firm_commitment_deadline_and_no_recommit(minute, allowed):
    world = IndustrialWorld(TASKS[0])
    case = world.state["network_truth"]["case"]
    world.state["structured_artifacts"]["test"] = {
        "id": "test",
        "artifact_type": "contingent_network_policy",
        "content": solve(case),
        "citations": [
            {"file_id": f["id"], "section_id": section, "version": f["version"]}
            for f in world.state["case_files"].values()
            if f["system"] != "LIVE"
            for section in f["sections"]
        ],
    }
    # Exercise the action-level boundary directly, independent of tool-call cost.
    world.state["clock_minute"] = minute
    args = (
        world,
        "reserve_network_capacity",
        world.state["incident"]["id"],
        {"artifact_id": "test"},
    )
    ok, error = apply_action(*args)
    assert ok is allowed
    if allowed:
        assert apply_action(*args) == (False, "reservation_already_committed")
    else:
        assert error == "reservation_window_closed"
        assert not world.state.get("network_commitment")


def test_joint_optimizer_matches_independent_exhaustive_enumeration():
    case = deepcopy(build_scenario(TASKS[0]).state["network_truth"]["case"])
    # A tractable three-order/two-outcome slice; enumerate every reservation,
    # every branch assignment, and every common early decision without the DP.
    group = case["coupling"]["customers"][0]
    case["coupling"]["customers"] = [group]
    case["orders"] = [row for row in case["orders"] if row["order_id"] in group["orders"]]
    oid = group["orders"][0]
    case["coupling"]["firm_releases"]["order_ids"] = [oid]
    case["scenarios"] = case["scenarios"][:2]
    best = None
    for standard, express in product(range(3), repeat=2):
        reservations = {"standard": standard, "express": express}
        if reservation_fee(case, reservations) > case["finance"]["reservation_budget_cents"]:
            continue
        branch_options = []
        for scenario in case["scenarios"]:
            options = []
            for modes in product(MODES, repeat=len(case["orders"])):
                rows = [
                    {"order_id": order["order_id"], "mode": mode}
                    for order, mode in zip(case["orders"], modes)
                ]
                cost, _ = branch_cost(case, reservations, scenario, rows)
                if cost is not None:
                    options.append(
                        (next(row["mode"] for row in rows if row["order_id"] == oid), cost)
                    )
            branch_options.append(options)
        for outcomes in product(*branch_options):
            if len({mode for mode, _ in outcomes}) != 1:
                continue
            costs = [cost for _, cost in outcomes]
            objective = max(costs), sum(costs)
            if best is None or objective < best:
                best = objective
    actual = solve(case)
    assert best is not None
    assert (actual["worst_case_cost_cents"], sum(actual["branch_costs_cents"].values())) == best
