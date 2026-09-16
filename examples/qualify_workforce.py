"""No-API ablations for shared labor and treasury constraints."""

import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.contingent import solve, validate_policy
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def main():
    rows = []
    for task in load_tasks("data/workforce/tasks.json"):
        case = build_scenario(task).state["network_truth"]["case"]
        optimum = solve(case)
        objective = (optimum["worst_case_cost_cents"], sum(optimum["branch_costs_cents"].values()))
        controls = {}
        for omitted in ("certified_release_labor", "treasury_prepayment", "both"):
            relaxed = deepcopy(case)
            relaxed["coupling"]["shared_resources"] = [
                r
                for r in relaxed["coupling"]["shared_resources"]
                if omitted != "both" and r["id"] != omitted
            ]
            assessment = validate_policy(case, solve(relaxed))
            passed = (
                assessment["feasible"]
                and (
                    assessment["worst_case_cost_cents"],
                    sum(assessment["branch_costs_cents"].values()),
                )
                == objective
            )
            controls[omitted] = {"passed": passed, "assessment": assessment}
        rows.append(
            {"task": task.id, "seed": task.seed, "objective": objective, "controls": controls}
        )
    report = {
        "version": "0.8.0-workforce.1",
        "kind": "algorithmic_ablation_not_model_result",
        "cases": len(rows),
        "failures": {
            name: sum(not row["controls"][name]["passed"] for row in rows)
            for name in ("certified_release_labor", "treasury_prepayment", "both")
        },
        "results": rows,
    }
    Path("reports/workforce-qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
