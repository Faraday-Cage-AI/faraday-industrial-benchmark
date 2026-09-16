"""Generate cross-functional challenge cases without invoking models."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/long-tail/tasks.json").read_text())[0]
    template["workflow_stages"] = [
        {**stage, "objective": stage["objective"].replace("six", "eight")}
        for stage in template["workflow_stages"]
    ]
    tasks = [
        {
            **template,
            "id": f"faraday-workforce-{i + 1:03d}",
            "version": "0.8.0-workforce.1",
            "seed": 40801 + i,
            "title": "Resolve network disruption under certified-labor and treasury constraints",
            "tags": template["tags"] + ["cross-functional-v1"],
            "prompt": template["prompt"].replace("six", "eight")
            + " Also enforce shared certified-worker release capacity and same-day treasury prepayment limits. Payroll and tax reserves are protected. Do not count refundable deposits as costs or pool capacity across mutually exclusive scenarios.",
        }
        for i in range(16)
    ]
    target = Path("data/workforce/tasks.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
