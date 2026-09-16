from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.artifact_contract import canonical_exclusions, matches_contract
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario

TASKS = load_tasks(Path(__file__).parents[1] / "data/close-execution-v2/tasks.json")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_semantic_reference_and_replay(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


def test_exclusion_order_is_ignored_but_records_are_not():
    expected = {
        "exclusions": [
            {"record_id": "B", "reason": "draft"},
            {"record_id": "A", "reason": "duplicate"},
        ]
    }
    reordered = {"exclusions": list(reversed(expected["exclusions"]))}
    assert matches_contract(canonical_exclusions(reordered), canonical_exclusions(expected))
    for bad in (
        {"exclusions": expected["exclusions"][:1]},
        {"exclusions": expected["exclusions"] + expected["exclusions"][:1]},
        {"exclusions": [{"record_id": "B", "reason": "wrong"}, expected["exclusions"][1]]},
    ):
        assert not matches_contract(canonical_exclusions(bad), canonical_exclusions(expected))
    events = {"events": [{"record_id": "B"}, {"record_id": "A"}]}
    assert canonical_exclusions(events) == events


def test_dimension_budgets_do_not_depend_on_leaf_count():
    totals = defaultdict(float)
    for criterion in build_scenario(TASKS[0]).criteria:
        totals[criterion["dimension"]] += criterion["weight"]
    assert sum(totals.values()) == pytest.approx(100)
    assert totals["artifact_accuracy"] == pytest.approx(30)
    assert totals["governance"] == pytest.approx(15)
    assert totals["orchestration"] == pytest.approx(10)


def test_reordered_exclusions_publish_through_real_tools():
    class Reordered:
        name = "reordered-exclusions"

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if name == "create_structured_artifact":

                        def reverse_reports(value):
                            if isinstance(value, dict):
                                for key, item in value.items():
                                    if key == "exclusions" and isinstance(item, list):
                                        item.reverse()
                                    reverse_reports(item)
                            elif isinstance(value, list):
                                for item in value:
                                    reverse_reports(item)

                        reverse_reports(arguments["content"])
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    assert BenchmarkRunner().run_task(TASKS[0], Reordered()).score.strict_success
