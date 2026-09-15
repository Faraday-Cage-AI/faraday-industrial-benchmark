"""Summarize saved model attempts without confusing operational and API costs."""

import argparse
import json
from pathlib import Path


def summarize(directories):
    rows = []
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
            usage_path = path.with_name(path.stem + "-usage.jsonl")
            calls = (
                [json.loads(line) for line in usage_path.read_text().splitlines()]
                if usage_path.exists()
                else []
            )
            for result in report["results"]:
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
                rows.append(
                    {
                        "model": model,
                        "task_id": result["task"]["id"],
                        "score": score["score"],
                        "strict_success": score["strict_success"],
                        "failed_criteria": [c["id"] for c in score["criteria"] if not c["passed"]],
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
            "mean_score": round(sum(row["score"] for row in subset) / len(subset), 2)
            if subset
            else None,
            "estimated_api_cost_usd": round(
                sum(row["estimated_api_cost_usd"] for row in subset), 4
            ),
        }
    return {
        "track": "v0.6 public contingent recovery; tool-only development baseline",
        "pricing_sources": [
            "https://developers.openai.com/api/docs/models/gpt-5.4",
            "https://developers.openai.com/api/docs/models/gpt-5.5",
        ],
        "interpretation": "Single attempts on eight public development seeds; not a held-out model ranking. API prices are estimates, not invoices. Infrastructure failures and token truncation must be examined separately.",
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
