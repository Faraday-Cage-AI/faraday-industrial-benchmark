"""Measure nominal-only planning against robust optimization (not an LLM baseline)."""

import json
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.contingent import solve, solve_branch
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def main():
    template = next(
        t for t in load_tasks(DEFAULT_TASKS) if t.family == "contingent_network_recovery"
    )
    rows = []
    portfolios = Counter()
    for seed in range(32):
        case = build_scenario(replace(template, seed=seed)).state["network_truth"]["case"]
        robust = solve(case)
        portfolios[json.dumps(robust["reservations"], sort_keys=True)] += 1
        nominal = deepcopy(case)
        nominal["scenarios"] = case["scenarios"][:1]
        naive = solve(nominal)
        # Generous control: allow optimal recourse in every actual scenario,
        # but hold the nominally selected first-stage reservation fixed.
        branches = [solve_branch(case, naive["reservations"], s) for s in case["scenarios"]]
        worst = None if any(b is None for b in branches) else max(b[0] for b in branches)
        optimum = robust["worst_case_cost_cents"]
        rows.append(
            {
                "seed": seed,
                "robust_reservations": robust["reservations"],
                "nominal_reservations": naive["reservations"],
                "optimum_cents": optimum,
                "nominal_worst_cost_cents": worst,
                "regret": None if worst is None else worst / optimum - 1,
                "within_tolerance": worst is not None and worst * 100 <= optimum * 102,
            }
        )
    report = {
        "benchmark_version": "0.6.0",
        "kind": "deterministic_algorithm_ablation",
        "interpretation": "Not GPT-5.4 or GPT-5.5 results. Development seeds, not a private test set.",
        "cases": len(rows),
        "outside_tolerance": sum(not r["within_tolerance"] for r in rows),
        "optimal_portfolio_distribution": dict(portfolios),
        "results": rows,
    }
    destination = Path("reports/contingent-ablation.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
