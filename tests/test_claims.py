from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.claims import reconcile_claims
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner


def test_waterfall_and_exclusion_precedence():
    base = {
        "event_id": "a",
        "row_id": "a",
        "amount_cents": 10001,
        "status": "approved",
        "period": "current",
        "category": "property",
    }
    contract = {
        "period": "current",
        "covered_categories": ["property"],
        "deductible_cents": 1000,
        "participation_basis_points": 5000,
        "remaining_limit_cents": 4000,
        "already_received_cents": 500,
        "rows": [
            base,
            {**base, "row_id": "dup", "status": "reversed"},
            {**base, "event_id": "b", "row_id": "pending", "status": "pending"},
        ],
    }
    assert reconcile_claims(contract) == {
        "eligible_cents": 10001,
        "after_deductible_cents": 9001,
        "participated_cents": 4501,
        "capped_cents": 4000,
        "already_received_cents": 500,
        "receivable_cents": 3500,
        "exclusions": [
            {"row_id": "dup", "reason": "duplicate_event"},
            {"row_id": "pending", "reason": "unapproved"},
        ],
    }
    contract["already_received_cents"] = 5000
    assert reconcile_claims(contract)["receivable_cents"] == 0
    contract["deductible_cents"] = 20000
    assert reconcile_claims(contract)["after_deductible_cents"] == 0


@pytest.mark.parametrize(
    "task",
    load_tasks(Path(__file__).parents[1] / "data/professional/tasks.json"),
    ids=lambda t: t.id,
)
def test_professional_workflow(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    score = episode.score
    assert score.strict_success, [(c.id, c.detail) for c in score.criteria if not c.passed]
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


@pytest.mark.parametrize(
    "mistake", ["omit_bridge", "wrong_receivable", "inconsistent_brief", "wrong_cash"]
)
def test_plausible_deliverable_corruption_fails(mistake):
    class CorruptingAgent:
        name = "claims-negative-control"

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if name == "create_structured_artifact":
                        kind = arguments["artifact_type"]
                        if kind == "integrated_recovery_model":
                            impact = arguments["content"]["financial_impact"]
                            if mistake == "omit_bridge":
                                impact.pop("insurance_bridge")
                            elif mistake == "wrong_receivable":
                                impact["insurance_bridge"]["receivable_cents"] += 1
                            elif mistake == "wrong_cash":
                                impact["finance_bridge"]["settled_cash_cents"] += 1
                        elif kind == "executive_decision_brief" and mistake == "inconsistent_brief":
                            arguments["content"]["reserve_amount"] += 1
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    task = load_tasks(Path(__file__).parents[1] / "data/professional/tasks.json")[-1]
    score = BenchmarkRunner().run_task(task, CorruptingAgent()).score
    assert not score.strict_success
