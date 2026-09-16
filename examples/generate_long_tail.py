"""Generate reproducible synthetic challenge tasks; never invokes a model."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/challenge/tasks.json").read_text())[0]
    tasks = []
    for i in range(24):
        task = {
            **template,
            "id": f"faraday-long-tail-{i + 1:03d}",
            "version": "0.7.0-tail.1",
            "seed": 30701 + i,
            "title": "Resolve compound disruption with customer waivers and emergency carrier contracts",
            "tags": template["tags"] + ["long-tail-contracts-v1"],
            "prompt": template["prompt"]
            + (
                " Apply all scenario-specific contract overrides: customer qualification"
                " exclusions, emergency kit-split waivers, replacement service credits,"
                " minimum carrier dispatch loads and replacement activation fees."
                " Base terms remain binding unless explicitly overridden."
            ),
        }
        tasks.append(task)
    target = Path("data/long-tail/tasks.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
