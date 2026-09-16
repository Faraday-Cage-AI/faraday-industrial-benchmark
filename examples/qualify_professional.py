"""Run every applicable deterministic corruption on every professional case."""

import json
from pathlib import Path

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.professional_controls import ProfessionalNegativeControl
from faraday_industrial_benchmark.runner import BenchmarkRunner


def main():
    results = []
    for task in load_tasks("data/professional/tasks.json"):
        runner = BenchmarkRunner()
        positive = runner.run_task(task, OracleAgent()).score
        assert positive.strict_success, task.id
        mistakes = [
            "omit_claims_bridge",
            "double_count_prior_receipt",
            "omit_exclusion_evidence",
            "inconsistent_brief",
        ]
        if "finance-reconciliation-v1" in task.tags:
            mistakes += ["cash_reduces_expense", "ignore_credit_notes", "wrong_cash_cutoff"]
        for mistake in mistakes:
            agent = ProfessionalNegativeControl(mistake)
            score = runner.run_task(task, agent).score
            failed = [c.id for c in score.criteria if not c.passed]
            assert agent.mutations > 0, (task.id, mistake, "control did not execute")
            assert not score.strict_success, (task.id, mistake, "corruption accepted")
            assert any(
                "artifact" in criterion or "consistent" in criterion for criterion in failed
            ), failed
            results.append(
                {
                    "task": task.id,
                    "mistake": mistake,
                    "mutations": agent.mutations,
                    "strict_success": score.strict_success,
                    "failed_criteria": failed,
                }
            )
    report = {
        "kind": "deterministic_deliverable_corruption_not_model_result",
        "cases": 24,
        "checks": len(results),
        "rejected": sum(not r["strict_success"] for r in results),
        "results": results,
    }
    Path("reports/professional-qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
