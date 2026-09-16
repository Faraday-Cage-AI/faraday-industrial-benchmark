"""Measure whether disclosed early commitments bind; no model-based filtering."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.contingent import solve, validate_policy
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=Path("data/decision-challenge/tasks.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/decision-qualification.json"))
    args = parser.parse_args()
    tasks = load_tasks(args.tasks)
    versions = {task.version for task in tasks}
    assert len(versions) == 1
    results = []
    for task in tasks:
        case = build_scenario(task).state["network_truth"]["case"]
        joint = solve(case)
        relaxed = deepcopy(case)
        contract = relaxed["coupling"].pop("firm_releases")
        hindsight = solve(relaxed)
        first = next(iter(hindsight["branches"].values()))
        hindsight["firm_releases"] = {
            row["order_id"]: row["mode"]
            for row in first
            if row["order_id"] in contract["order_ids"]
        }
        assessment = validate_policy(case, hindsight)
        results.append(
            {
                "task": task.id,
                "seed": task.seed,
                "joint_objective_cents": [
                    joint["worst_case_cost_cents"],
                    sum(joint["branch_costs_cents"].values()),
                ],
                "hindsight_objective_cents": [
                    hindsight["worst_case_cost_cents"],
                    sum(hindsight["branch_costs_cents"].values()),
                ],
                "hindsight_policy_rejected": not assessment["feasible"],
                "assessment": assessment,
            }
        )
        print(task.id, "hindsight rejected:", not assessment["feasible"], flush=True)
    report = {
        "version": next(iter(versions)),
        "kind": "algorithmic_ablation_not_model_result",
        "cases": len(results),
        "hindsight_failures": sum(row["hindsight_policy_rejected"] for row in results),
        "results": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}))


if __name__ == "__main__":
    main()
