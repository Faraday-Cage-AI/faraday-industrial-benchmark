"""Freeze fixed seeds for linked subcontracting and intercompany close cases."""

import json
from pathlib import Path


def main():
    template = json.loads(Path("data/subcontracting-v2/tasks.json").read_text())[0]
    tasks = [
        {
            **template,
            "id": f"faraday-close-chain-{i + 1:03d}",
            "seed": 91901 + i,
            "version": "0.13.0-close-chain.1",
            "tags": template["tags"] + ["intercompany-close-v1"],
            "title": "Reconcile subcontracting recost, intercompany ownership and consolidated recovery reserve",
            "prompt": template["prompt"]
            + " Then reconcile intercompany transfers against corrected source-receipt COGS. Preserve locked transfer prices, distinguish manual physical receipts from logical receipts, and eliminate internal balances and margin across entities. Partial receipts leave group trade-in-transit inventory. Include the exact balanced intercompany_bridge and its signed reserve reclassification in the final model and executive reserve; do not double-count internal payable, transfer-price expense or profit.",
        }
        for i in range(8)
    ]
    path = Path("data/close-chain/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2) + "\n")
    current = [
        {
            **task,
            "version": "0.13.0-close-chain.2",
            "max_tool_calls": 400,
            "horizon_minutes": 900,
            "tags": task["tags"] + ["public-close-contract-v2"],
            "prompt": task["prompt"]
            + " Read the public evaluation contract in the program-office delivery instructions. Finish by simulated minute 300 for full economic credit; hard horizon 900, maximum 400 tool calls. These limits do not change the historical transaction cutoffs.",
        }
        for task in tasks
    ]
    path = Path("data/close-chain-v2/tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n")


if __name__ == "__main__":
    main()
