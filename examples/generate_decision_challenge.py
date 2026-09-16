"""Fixed-seed joint-decision challenge; no model-based case selection."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/workforce/tasks.json").read_text())[0]
    tasks = [
        {
            **template,
            "id": f"faraday-decision-{i + 1:03d}",
            "version": "0.11.0-decision.3",
            "seed": 71101 + i,
            "title": "Commit irreversible early releases under compound enterprise disruption",
            "max_tool_calls": 300,
            "horizon_minutes": 600,
            "tags": template["tags"]
            + ["firm-release-v1", "annotated-decision-v2", "public-decision-contract-v3"],
            "prompt": template["prompt"]
            .replace("minute 60", "minute 180")
            .replace("minute 80", "minute 200")
            + " Jointly choose the disclosed firm-release modes before uncertainty resolves. Those orders must use the same mode in every branch; other orders may adapt. Optimizing every branch independently is not a valid policy. Read the complete firming contract and timing rules before commitment.",
        }
        for i in range(8)
    ]
    path = Path("data/decision-challenge-v3/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
