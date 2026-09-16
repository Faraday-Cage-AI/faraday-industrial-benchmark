"""Qualify the frozen cost-propagation extension without model calls."""

import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner


class CorruptCostBridge:
    name = "cost-bridge-negative-control"

    def __init__(self, mistake):
        self.mistake = mistake
        self.mutated = False

    def run(self, task, tools):
        owner = self

        class Proxy:
            def call(self, name, **arguments):
                arguments = deepcopy(arguments)
                if (
                    name == "create_structured_artifact"
                    and arguments["artifact_type"] == "integrated_recovery_model"
                ):
                    impact = arguments["content"]["financial_impact"]
                    bridge = impact["cost_bridge"]
                    if owner.mistake == "missing_cost_bridge":
                        del impact["cost_bridge"]
                    elif owner.mistake == "inventory_as_expense":
                        impact["reserve_amount"] += bridge["inventory_adjustment_cents"] / 100
                    elif owner.mistake == "quarantine_available":
                        row = next(r for r in bridge["nodes"] if r["node_id"] == "DC-QUALITY")
                        row["available_quantity"] += 1
                    elif owner.mistake == "liability_not_balanced":
                        bridge["liability_adjustment_cents"] += 1
                    owner.mutated = True
                return tools.call(name, **arguments)

        return OracleAgent().run(task, Proxy())


def main():
    rows = []
    runner = BenchmarkRunner()
    for task in load_tasks("data/researched-v3/tasks.json"):
        positive = runner.run_task(task, OracleAgent())
        assert positive.score.strict_success
        assert runner.replay(task, positive.to_dict()["trace"])["exact_match"]
        for mistake in (
            "missing_cost_bridge",
            "inventory_as_expense",
            "quarantine_available",
            "liability_not_balanced",
        ):
            agent = CorruptCostBridge(mistake)
            score = runner.run_task(task, agent).score
            assert agent.mutated and not score.strict_success
            failed = [c.id for c in score.criteria if not c.passed]
            assert any("artifact" in c or "consistent" in c for c in failed)
            rows.append(
                {"task": task.id, "mistake": mistake, "rejected": True, "failed_criteria": failed}
            )
    report = {
        "kind": "deterministic_negative_controls_not_model_results",
        "positive_cases": 8,
        "corruptions_rejected": len(rows),
        "results": rows,
    }
    report["task_version"] = "0.10.0-researched.3"
    Path("reports/researched-v3-qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
