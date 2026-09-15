"""Independent optimality, constraint, chronology, and replay checks."""

from copy import deepcopy
from dataclasses import asdict, replace
from itertools import product

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.contingent import (
    MODES,
    apply_action,
    branch_cost,
    solve,
    solve_branch,
    validate_policy,
)
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.world import IndustrialWorld

TEMPLATE = next(t for t in load_tasks(DEFAULT_TASKS) if t.family == "contingent_network_recovery")


@pytest.mark.parametrize("seed", range(16))
def test_seeded_reference_solutions_are_feasible_and_replayable(seed):
    task = replace(TEMPLATE, seed=seed)
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success
    assert runner.replay(task, asdict(episode)["trace"])["exact_match"]


def test_dp_matches_exhaustive_enumeration_on_small_case():
    case = deepcopy(IndustrialWorld(TEMPLATE).state["network_truth"]["case"])
    case["orders"] = case["orders"][:4]
    for tiers in product(range(3), repeat=2):
        reservations = dict(zip(("standard", "express"), tiers))
        for scenario in case["scenarios"]:
            costs = []
            for modes in product(MODES, repeat=len(case["orders"])):
                rows = [
                    {"order_id": order["order_id"], "mode": mode}
                    for order, mode in zip(case["orders"], modes)
                ]
                cost, _ = branch_cost(case, reservations, scenario, rows)
                if cost is not None:
                    costs.append(cost)
            result = solve_branch(case, reservations, scenario)
            assert (result[0] if result else None) == (min(costs) if costs else None)


def test_row_order_does_not_define_correctness():
    case = IndustrialWorld(TEMPLATE).state["network_truth"]["case"]
    policy = solve(case)
    before = validate_policy(case, policy)
    for rows in policy["branches"].values():
        rows.reverse()
    assert validate_policy(case, policy) == before


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "omit",
        "unknown",
        "all_stock",
        "all_defer",
        "bool_tier",
        "overspend",
        "missing_branch",
    ],
)
def test_invalid_policies_rejected(mutation):
    case = IndustrialWorld(TEMPLATE).state["network_truth"]["case"]
    policy = solve(case)
    rows = next(iter(policy["branches"].values()))
    if mutation == "duplicate":
        rows[1] = deepcopy(rows[0])
    elif mutation == "omit":
        rows.pop()
    elif mutation == "unknown":
        rows[0]["mode"] = "magic"
    elif mutation in ("all_stock", "all_defer"):
        for row in rows:
            row["mode"] = mutation.removeprefix("all_")
    elif mutation == "bool_tier":
        policy["reservations"]["standard"] = True
    elif mutation == "overspend":
        policy["reservations"] = {"standard": 2, "express": 2}
    else:
        policy["branches"].pop(next(iter(policy["branches"])))
    assert not validate_policy(case, policy)["feasible"]


def test_cannot_reserve_after_outcome_is_known():
    world = IndustrialWorld(TEMPLATE)
    for _ in range(3):
        world.call_tool("wait", {"minutes": 30})
    assert world.minute > 80
    world.state["structured_artifacts"]["test"] = {"id": "test"}
    ok, error = apply_action(
        world, "reserve_network_capacity", world.state["incident"]["id"], {"artifact_id": "test"}
    )
    assert not ok and error == "reservation_window_closed"


def test_public_validation_does_not_reveal_optimum():
    case = IndustrialWorld(TEMPLATE).state["network_truth"]["case"]
    report = validate_policy(case, solve(case))
    assert not {"optimum", "optimal", "near_optimal", "assignments"} & report.keys()


@pytest.mark.parametrize(
    "mutation", ["double_fee", "wrong_allocation", "false_exception", "wrong_inventory"]
)
def test_artifact_tampering_cannot_strictly_pass(mutation):
    class MutatingAgent:
        name = "negative-artifact-control"

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    if name == "create_structured_artifact":
                        arguments = deepcopy(arguments)
                        content = arguments["content"]
                        if arguments["artifact_type"] == "realized_recovery_ledger":
                            if mutation == "double_fee":
                                content["total_cost_cents"] += content["reservation_fee_cents"]
                            elif mutation == "wrong_allocation":
                                content["allocations"][0]["mode"] = "invalid"
                        elif mutation == "false_exception":
                            content["exceptions"].append(
                                {"record_id": "fabricated", "reason_code": "quality_hold"}
                            )
                        elif mutation == "wrong_inventory":
                            content["inventory_packs"] += 1
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    episode = BenchmarkRunner().run_task(TEMPLATE, MutatingAgent())
    assert not episode.score.strict_success
