"""Reproducible no-API qualification of coupled contracts versus relaxed planning."""

import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.contingent import solve, validate_policy
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def main():
    rows = []
    for task in load_tasks("data/challenge/tasks.json"):
        case = build_scenario(task).state["network_truth"]["case"]
        optimum = solve(case)
        relaxed = deepcopy(case)
        del relaxed["coupling"]
        shortcut = solve(relaxed)
        assessment = validate_policy(case, shortcut)
        passed = assessment["feasible"] and (
            assessment["worst_case_cost_cents"],
            sum(assessment["branch_costs_cents"].values()),
        ) == (optimum["worst_case_cost_cents"], sum(optimum["branch_costs_cents"].values()))
        rows.append(
            {
                "task": task.id,
                "exact_optimum_cents": optimum["worst_case_cost_cents"],
                "relaxed_control_passed": passed,
                "relaxed_control": assessment,
            }
        )
    report = {
        "suite_version": "0.7.0-hard.1",
        "kind": "algorithmic_control_not_model_result",
        "cases": len(rows),
        "relaxed_control_failures": sum(not r["relaxed_control_passed"] for r in rows),
        "results": rows,
    }
    Path("reports/coupled-hard-qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
