"""Generate a separately versioned, stateful close execution suite."""

import json
from pathlib import Path


def main():
    tasks = json.loads(Path("data/close-chain-v2/tasks.json").read_text())
    for task in tasks:
        task["id"] = task["id"].replace("close-chain", "close-execution")
        task["version"] = "0.14.0-close-execution.1"
        task["tags"].append("close-execution-saga-v1")
        task["title"] = (
            "Execute and recover a cross-entity close with partial receipts and ambiguous commits"
        )
        task["prompt"] += (
            " Before publication, execute the cross-entity posting workflow disclosed in delivery_contract.close_execution_rules."
            " Inspect get_incident for the live stage ledger and newly surfaced receiver exceptions."
            " Partial commits survive later failures; recover without double-posting."
        )
    path = Path("data/close-execution/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
