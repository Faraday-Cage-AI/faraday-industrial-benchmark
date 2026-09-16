"""Generate long-tail operating-review work samples, no paid model calls."""

import json
from pathlib import Path


def main():
    template = next(
        t
        for t in json.loads(Path("data/public/tasks.json").read_text())
        if t["family"] == "integrated_operating_review"
    )
    tasks = [
        {
            **template,
            "id": f"faraday-professional-{i + 1:03d}",
            "version": "0.9.0-professional.1",
            "seed": 50901 + i,
            "tags": template["tags"] + ["claims-reconciliation-v1"],
            "prompt": template["prompt"]
            + " Reconcile the raw insurance claims contract, including exclusions, deductible, participation, remaining coverage, and prior receipts. Include the full insurance_bridge in the recovery model and carry only the outstanding receivable into every reserve figure. All four deliverables must agree.",
        }
        for i in range(12)
    ]
    tasks.extend(
        [
            {
                **task,
                "id": f"faraday-professional-finance-{i + 1:03d}",
                "version": "0.9.0-professional.2",
                "seed": 51901 + i,
                "tags": task["tags"] + ["finance-reconciliation-v1"],
                "prompt": task["prompt"]
                + " Also reconcile AP revisions, related credit notes, service-period cutoff, per-document FX, and settled-payment timing. Include finance_bridge and propagate incremental expense into reserve without treating cash settlement as an expense reduction.",
            }
            for i, task in enumerate(tasks[:12])
        ]
    )
    target = Path("data/professional/tasks.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, indent=2) + "\n")


if __name__ == "__main__":
    main()
