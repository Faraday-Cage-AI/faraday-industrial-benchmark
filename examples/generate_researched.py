"""Source-inspired cost-propagation extension, fixed seeds before model runs."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/professional/tasks.json").read_text())[-1]
    tasks = [
        {
            **template,
            "id": f"faraday-researched-{i + 1:03d}",
            "seed": 61901 + i,
            "version": "0.10.0-researched.3",
            "max_tool_calls": 300,
            "horizon_minutes": 600,
            "tags": template["tags"]
            + [
                "receipt-cost-propagation-v1",
                "explicit-review-contract-v2",
                "revision-safe-review-v3",
            ],
            "prompt": template["prompt"]
            + " Reconcile the separate receipt-cost propagation tree, respecting ownership, approval, logical nodes, cost-method stops, signed price adjustments and quarantine availability. Include cost_bridge and carry only its expense adjustment into the reserve. Do not mix inventory revaluation with expense or AP cash.",
        }
        for i in range(8)
    ]
    path = Path("data/researched-v3/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
