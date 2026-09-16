from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.decision_contract import (
    artifact_schemas,
    ledger_errors,
    shape_errors,
)
from faraday_industrial_benchmark.grader import efficiency_target
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario

ROOT = Path(__file__).parents[1]
TASKS = load_tasks(ROOT / "data/decision-challenge-v3/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_all_scoring_parameters_are_public(task):
    instance = build_scenario(task)
    grc = next(f for f in instance.state["case_files"].values() if f["system"] == "GRC")
    public = grc["sections"]["evaluation_contract"]
    assert public["criteria"] == instance.criteria
    assert public["economic_checks"] == instance.economics["checks"]
    assert (
        public["finish_by_minute_for_full_economic_credit"] == instance.economics["target_minutes"]
    )
    assert public["hard_horizon_minutes"] == task.horizon_minutes
    assert public["maximum_tool_calls"] == task.max_tool_calls
    assert public["efficiency_no_penalty_tool_calls"] == efficiency_target(task)
    assert public["delay_cost_per_minute_dollars"] == instance.economics["delay_cost_per_minute"]
    assert "best_known_cost" not in public
    assert "unmitigated_cost" not in public
    assert grc["sections"]["structural_schemas"] == artifact_schemas()


class ContractOracle:
    name = "public-contract-control"

    def __init__(self, finish_minute=None):
        self.finish_minute = finish_minute

    def run(self, task, tools):
        finish_minute = self.finish_minute
        context = {}

        class Proxy:
            def call(self, name, **arguments):
                arguments = deepcopy(arguments)
                if name == "create_structured_artifact":
                    content = arguments["content"]
                    if arguments["artifact_type"] == "realized_recovery_ledger":
                        content.update(
                            case_id=context["case"],
                            policy_artifact_id=context["policy"],
                            reconciliation={"notes": "Audited"},
                        )
                        content["allocations"].reverse()
                        for row in content["allocations"]:
                            row["notes"] = "Checked against locked policy"
                        # A shape error must not consume an artifact ID or poison a correction.
                        bad = deepcopy(arguments)
                        bad["content"]["total_cost_cents"] = True
                        result = tools.call(name, **bad)
                        assert not result["ok"]
                        assert result["error"] == "artifact_schema_error"
                        assert any("total_cost_cents" in field for field in result["fields"])
                if name == "finish" and finish_minute is not None:
                    while tools.world.minute < finish_minute:
                        result = tools.call(
                            "wait", minutes=min(30, finish_minute - tools.world.minute)
                        )
                        assert result["ok"]
                result = tools.call(name, **arguments)
                if name == "get_incident":
                    context["case"] = result["incident"]["id"]
                if (
                    name == "create_structured_artifact"
                    and arguments["artifact_type"] == "contingent_network_policy"
                ):
                    context["policy"] = result["artifact"]["id"]
                return result

        return OracleAgent().run(task, Proxy())


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_annotated_corrected_workflows_replay(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, ContractOracle())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


@pytest.mark.parametrize("minute,strict", [(260, True), (261, False)])
def test_disclosed_finish_boundary(minute, strict):
    episode = BenchmarkRunner().run_task(TASKS[0], ContractOracle(minute))
    assert episode.score.strict_success is strict
    assert episode.score.elapsed_minutes == minute
    assert episode.score.estimated_cost == episode.score.best_known_cost + max(0, minute - 260) * 10
    assert episode.score.dimensions["economics"]["score"] == round(
        10 * (1 - max(0, minute - 260) / 340), 4
    )


def test_ledger_rejects_wrong_business_values_and_references():
    expected = {
        "scenario_id": "S1",
        "reservation_id": "R1",
        "allocations": [{"order_id": "O1", "mode": "stock"}],
        "reservation_fee_cents": 10,
        "operating_cost_cents": 20,
        "total_cost_cents": 30,
        "debit_account": "D",
        "credit_account": "C",
    }
    assert not ledger_errors(expected, expected, "CASE", "POLICY")
    for field, wrong in {
        "scenario_id": "S2",
        "reservation_id": "R2",
        "total_cost_cents": 31,
        "reservation_fee_cents": 11,
        "operating_cost_cents": 21,
        "debit_account": "X",
        "credit_account": "X",
        "case_id": "X",
        "policy_artifact_id": "X",
        "committed_policy_artifact_id": "X",
        "allocations": [],
    }.items():
        errors = ledger_errors({**expected, field: wrong}, expected, "CASE", "POLICY")
        assert any(f"content.{field}" in error for error in errors)
    assert ledger_errors(
        {**expected, "allocations": expected["allocations"] * 2}, expected, "CASE", "POLICY"
    )
    assert shape_errors(
        {**expected, "extra": 1}, artifact_schemas()["realized_recovery_ledger"]
    ) == ["content.extra: unsupported field"]
