"""Freeze a new scoring version without overwriting previous task manifests."""

import json
from pathlib import Path


def main():
    tasks = json.loads(Path("data/close-execution/tasks.json").read_text())
    for task in tasks:
        task["version"] = "0.14.0-close-execution.2"
        task["tags"].append("semantic-close-v2")
        task["prompt"] += (
            " Exclusion report row order is not graded; the record IDs and reasons must still be correct. Read the revised dimension-balanced evaluation contract."
        )
    target = Path("data/close-execution-v2/tasks.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
