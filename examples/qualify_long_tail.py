"""Measure contract-blind planning controls, not model capability. No API calls."""

import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.contingent import solve, validate_policy
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def main():
    rows = []
    for task in load_tasks("data/long-tail/tasks.json"):
        case = build_scenario(task).state["network_truth"]["case"]
        optimum = solve(case)
        objective = (optimum["worst_case_cost_cents"], sum(optimum["branch_costs_cents"].values()))
        controls = {}
        for omitted in ("customer_overrides", "carrier_overrides", "both"):
            relaxed = deepcopy(case)
            if omitted in ("customer_overrides", "both"):
                for group in relaxed["coupling"]["customers"]:
                    group.pop("scenario_overrides", None)
            if omitted in ("carrier_overrides", "both"):
                relaxed["coupling"].pop("dispatch_overrides", None)
            plan = solve(relaxed)
            assessment = validate_policy(case, plan)
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
        "version": "0.7.0-tail.1",
        "kind": "algorithmic_ablation_not_model_result",
        "cases": len(rows),
        "failures": {
            name: sum(not row["controls"][name]["passed"] for row in rows)
            for name in ("customer_overrides", "carrier_overrides", "both")
        },
        "results": rows,
    }
    Path("reports/long-tail-qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
