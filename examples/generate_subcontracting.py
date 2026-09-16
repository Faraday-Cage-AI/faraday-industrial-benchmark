"""Fixed-seed event-sourced operating-review extension; no model filtering."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/researched-v3/tasks.json").read_text())[0]
    tasks = [
        {
            **template,
            "id": f"faraday-subcontracting-{i + 1:03d}",
            "seed": 81901 + i,
            "version": "0.12.0-subcontracting.1",
            "tags": template["tags"] + ["subcontracting-close-v1"],
            "title": "Close subcontracting corrections and rebuild the cross-functional recovery plan",
            "prompt": template["prompt"]
            + " Reconcile subcontracting events chronologically through the disclosed cutoff. Handle partial receipts, unit conversion, revised absolute consumption adjustments, inspection holds, supplier ownership, duplicates, reversals and late recosting of shipments. Derive available finished stock before allocating nominal MES capacity. Carry corrected supply into customer commitments, freight, production cost, penalty exposure and every deliverable. Include the subcontract_bridge and add only its COGS to the reserve, never component inventory or service payable again.",
        }
        for i in range(8)
    ]
    path = Path("data/subcontracting/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2) + "\n")
    distributed = [
        {
            **task,
            "version": "0.12.0-subcontracting.2",
            "tags": task["tags"] + ["distributed-subcontracting-v2"],
            "prompt": task["prompt"]
            + " Reconstruct the subcontracting contract from current WMS component balances, QMS opening quality states, authoritative SCM event history and ERP valuation rules. SCM's early extract is incomplete. Respect each case's actual lifecycle; do not assume every reversal is approved or every quality hold remains active.",
        }
        for task in tasks
    ]
    path = Path("data/subcontracting-v2/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(distributed, indent=2) + "\n")


if __name__ == "__main__":
    main()
