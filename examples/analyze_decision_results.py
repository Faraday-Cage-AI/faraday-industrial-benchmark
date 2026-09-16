"""Report objective gaps from committed policies without changing saved scores."""

import argparse
import json
from pathlib import Path

from faraday_industrial_benchmark.contingent import validate_policy
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario


def analyze(directory, tasks_path):
    rows = []
    for task in load_tasks(tasks_path):
        truth = build_scenario(task).state["network_truth"]
        for model in ("gpt-5.4", "gpt-5.5"):
            report = json.loads((directory / f"{model}-{task.id}.json").read_text())
            assert not report["measurement"]["interrupted"]
            episode = report["results"][0]
            artifacts = {}
            committed = None
            for call in episode["trace"]:
                if not call["result"].get("ok"):
                    continue
                if call["tool"] == "create_structured_artifact":
                    artifact = call["result"]["artifact"]
                    artifacts[artifact["id"]] = artifact["content"]
                if (
                    call["tool"] == "execute_action"
                    and call["arguments"]["action"] == "reserve_network_capacity"
                ):
                    committed = call["result"]["execution"]["payload"]["artifact_id"]
            row = {
                "model": model,
                "task_id": task.id,
                "score": episode["score"]["score"],
                "strict_success": episode["score"]["strict_success"],
                "committed_policy": committed,
            }
            if committed:
                assessment = validate_policy(truth["case"], artifacts[committed])
                assert assessment["feasible"]
                worst = assessment["worst_case_cost_cents"]
                aggregate = sum(assessment["branch_costs_cents"].values())
                gap = worst - truth["optimum"]
                assert gap >= 0
                row.update(
                    worst_case_cost_cents=worst,
                    optimal_worst_case_cost_cents=truth["optimum"],
                    worst_case_gap_cents=gap,
                    worst_case_gap_percent=round(100 * gap / truth["optimum"], 5),
                    aggregate_cost_cents=aggregate,
                    optimal_aggregate_cost_cents=truth["optimal_aggregate_cost"],
                    aggregate_tiebreak_gap_cents=aggregate - truth["optimal_aggregate_cost"]
                    if gap == 0
                    else None,
                )
            rows.append(row)
    return {
        "interpretation": "Diagnostics only, not alternative scores. The objective is lexicographic: minimum worst case, then aggregate cost. Aggregate gap is comparable only when worst-case cost is optimal. Synthetic economic penalties are not actual operational losses.",
        "episodes": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.directory, args.tasks)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for row in result["episodes"]:
        if not row["strict_success"]:
            print(json.dumps(row))
