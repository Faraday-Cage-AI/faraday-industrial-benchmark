from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.grader import efficiency_target
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario

ROOT = Path(__file__).parents[1]
TASKS = load_tasks(ROOT / "data/close-chain-v2/tasks.json")
OLD = load_tasks(ROOT / "data/close-chain/tasks.json")


@pytest.mark.parametrize("index", range(8))
def test_public_metadata_matches_grader_without_solved_values(index):
    task = TASKS[index]
    scenario = build_scenario(task)
    brief = next(
        f for f in scenario.state["case_files"].values() if f["system"] == "program-office"
    )
    public = brief["sections"]["delivery_contract"]["evaluation_contract"]
    assert public["criteria"] == [
        {key: c[key] for key in ("id", "dimension", "weight", "check", "minimum") if key in c}
        for c in scenario.criteria
    ]
    assert public["economic_checks"] == scenario.economics["checks"]
    assert (
        public["finish_by_minute_for_full_economic_credit"]
        == scenario.economics["target_minutes"]
        == 300
    )
    assert public["efficiency_no_penalty_tool_calls"] == efficiency_target(task)
    assert public["maximum_tool_calls"] == task.max_tool_calls == 400
    assert public["hard_horizon_minutes"] == task.horizon_minutes == 900
    assert (
        scenario.state["operating_review_truth"]
        == build_scenario(OLD[index]).state["operating_review_truth"]
    )


@pytest.mark.parametrize("minute,strict", [(300, True), (301, False)])
def test_deadline_and_annotated_evidence_match_public_contract(minute, strict):
    class TimedOracle:
        name = "public-close-boundary-control"

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if name == "finish":
                        while tools.world.minute < minute:
                            result = tools.call(
                                "wait", minutes=min(30, minute - tools.world.minute)
                            )
                            assert result["ok"]
                        arguments["evidence"] = [
                            f"{item} (supporting record)" for item in arguments["evidence"]
                        ]
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    runner = BenchmarkRunner()
    episode = runner.run_task(TASKS[0], TimedOracle())
    assert episode.score.strict_success is strict
    assert episode.score.elapsed_minutes == minute
    assert all(c.passed for c in episode.score.criteria)
    assert runner.replay(TASKS[0], episode.to_dict()["trace"])["exact_match"]
