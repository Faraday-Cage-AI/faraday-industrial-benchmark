"""Summarize saved model attempts without confusing operational and API costs."""

import argparse
import json
from pathlib import Path


def summarize(directories):
    rows = []
    versions = set()
    protocols = set()
    for directory in directories:
        cancellation_path = directory / "cancellation.json"
        cancelled = (
            set(json.loads(cancellation_path.read_text())["excluded_reports"])
            if cancellation_path.exists()
            else set()
        )
        for path in sorted(directory.glob("gpt-*.json")):
            if path.name in cancelled:
                continue
            report = json.loads(path.read_text())
            if "measurement" not in report or report["measurement"].get("interrupted"):
                continue
            protocols.add(
                json.dumps(
                    {
                        key: report["measurement"].get(key)
                        for key in (
                            "adapter_sha256",
                            "reasoning_effort",
                            "per_response_output_limit",
                            "total_output_limit",
                            "timeout_seconds",
                        )
                    },
                    sort_keys=True,
                )
            )
            if len(protocols) > 1:
                raise ValueError(
                    "Cannot pool attempts with different adapters or inference budgets"
                )
            usage_path = path.with_name(path.stem + "-usage.jsonl")
            calls = (
                [json.loads(line) for line in usage_path.read_text().splitlines()]
                if usage_path.exists()
                else []
            )
            for result in report["results"]:
                versions.add(result["task"]["version"])
                if len(versions) > 1:
                    raise ValueError("Cannot pool different benchmark task versions")
                model = result["agent"].split("/")[0]
                rates = {"gpt-5.4": (2.5, 0.25, 15), "gpt-5.5": (5, 0.5, 30)}[model]
                cost = 0
                tokens = {"input": 0, "cached": 0, "output": 0}
                for call in calls:
                    usage = call["usage"]
                    incoming = usage.get("input_tokens", 0)
                    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
                    outgoing = usage.get("output_tokens", 0)
                    large = incoming > 272000
                    cost += (
                        ((incoming - cached) * rates[0] + cached * rates[1])
                        * (2 if large else 1)
                        / 1e6
                    )
                    cost += outgoing * rates[2] * (1.5 if large else 1) / 1e6
                    tokens["input"] += incoming
                    tokens["cached"] += cached
                    tokens["output"] += outgoing
                score = result["score"]
                criteria_by_id = {c["id"]: c["passed"] for c in score["criteria"]}
                artifact_checks = [
                    c for c in score["criteria"] if c["dimension"] == "artifact_accuracy"
                ]
                violation_codes = {v.get("code") for v in score["violations"]}
                output_limit = report["measurement"].get("total_output_limit")
                if output_limit is not None and tokens["output"] >= output_limit:
                    execution_status = "cumulative_output_budget_exhausted"
                elif any("TimeoutError" in v.get("message", "") for v in score["violations"]):
                    execution_status = "episode_timeout"
                elif "agent_error" in violation_codes:
                    execution_status = "agent_execution_error"
                elif "tool_budget_exceeded" in violation_codes:
                    execution_status = "tool_budget_exhausted"
                elif any(c["status"] != "completed" for c in calls):
                    execution_status = "incomplete_api_response_observed"
                else:
                    execution_status = "completed_without_recorded_execution_limit"
                rows.append(
                    {
                        "model": model,
                        "task_id": result["task"]["id"],
                        "score": score["score"],
                        "strict_success": score["strict_success"],
                        "execution_status": execution_status,
                        "diagnostics_not_alternative_scores": {
                            "review_published": criteria_by_id.get("publication-execution"),
                            "all_artifact_value_checks_passed": all(
                                c["passed"] for c in artifact_checks
                            )
                            if artifact_checks
                            else None,
                            "all_functions_notified": criteria_by_id.get("notify-all-functions"),
                            "structured_final_evidence_passed": criteria_by_id.get(
                                "finish-with-record-evidence"
                            ),
                            "network_policy_feasible": criteria_by_id.get("feasible"),
                            "network_policy_objective_passed": criteria_by_id.get("near_optimal"),
                            "network_recovery_executed": criteria_by_id.get("executed"),
                            "reservation_before_reveal": criteria_by_id.get(
                                "reserve-before-reveal"
                            ),
                            "network_reconciliation_passed": criteria_by_id.get("reconciliation"),
                        },
                        "failed_criteria": [c["id"] for c in score["criteria"] if not c["passed"]],
                        "failure_details": [
                            {"id": c["id"], "detail": c.get("detail")}
                            for c in score["criteria"]
                            if not c["passed"]
                        ],
                        "violations": score["violations"],
                        "tool_calls": score["tool_calls"],
                        "wall_seconds": report["measurement"]["wall_seconds"],
                        "tokens": tokens,
                        "estimated_api_cost_usd": round(cost, 6),
                        "api_responses": len(calls),
                        "incomplete_responses": sum(c["status"] != "completed" for c in calls),
                        "report": str(path),
                    }
                )
    summaries = {}
    for model in ("gpt-5.4", "gpt-5.5"):
        subset = [row for row in rows if row["model"] == model]
        summaries[model] = {
            "completed_episodes": len(subset),
            "strict_successes": sum(row["strict_success"] for row in subset),
            "execution_status_counts": {
                status: sum(row["execution_status"] == status for row in subset)
                for status in sorted({row["execution_status"] for row in subset})
            },
            "mean_score": round(sum(row["score"] for row in subset) / len(subset), 2)
            if subset
            else None,
            "estimated_api_cost_usd": round(
                sum(row["estimated_api_cost_usd"] for row in subset), 4
            ),
        }
    return {
        "track": "public development; tool-only baseline",
        "task_versions": sorted(versions),
        "measurement_settings": json.loads(next(iter(protocols))) if protocols else None,
        "pricing_sources": [
            "https://developers.openai.com/api/docs/models/gpt-5.4",
            "https://developers.openai.com/api/docs/models/gpt-5.5",
        ],
        "cost_coverage": "Logged response usage only. Costs of unreturned requests or automatic retries may be missing; estimates are not a complete invoice.",
        "interpretation": "Single attempts on the reported public development cases; not a held-out model ranking. API prices are estimates, not invoices. Infrastructure failures and token truncation must be examined separately.",
        "models": summaries,
        "episodes": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.directories)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["models"], indent=2))
