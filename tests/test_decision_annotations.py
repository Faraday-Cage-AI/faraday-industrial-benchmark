from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.decision_annotations import (
    cited_record_ids,
    exception_values_match,
)
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner

ROOT = Path(__file__).parents[1]
TASKS = load_tasks(ROOT / "data/decision-challenge-v2/tasks.json")


def test_annotations_preserve_exact_business_checks():
    expected = [{"record_id": "A", "reason_code": "quality_hold"}]
    good = [{**expected[0], "reason": "Explanation", "notes": "Audited", "metadata": {}}]
    assert exception_values_match(good, expected)
    for bad in (
        [{**good[0], "reason_code": "wrong"}],
        good * 2,
        [],
        [{**good[0], "record_id": "invented"}],
        [{**good[0], "unknown": 1}],
    ):
        assert not exception_values_match(bad, expected)


def test_citations_require_complete_existing_tokens():
    known = {"ART-001", "MSG-002"}
    assert cited_record_ids(["ART-001 committed", "[MSG-002] delivered", "ART-001"], known) == known
    assert (
        cited_record_ids(
            ["NOT-ART-001", "ART-001-extra", "ART-0010", "xART-001", "FAKE-001"], known
        )
        == set()
    )


class AnnotatingOracle:
    name = "annotation-control"

    def run(self, task, tools):
        class Proxy:
            def call(self, name, **arguments):
                arguments = deepcopy(arguments)
                if (
                    name == "create_structured_artifact"
                    and arguments["artifact_type"] == "contingent_network_policy"
                ):
                    for row in arguments["content"]["exceptions"]:
                        row["reason"] = "Supporting audit annotation"
                if name == "finish":
                    arguments["evidence"] = [
                        f"{item} (supporting record)" for item in arguments["evidence"]
                    ]
                return tools.call(name, **arguments)

        return OracleAgent().run(task, Proxy())


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_annotated_workflows_and_replay(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, AnnotatingOracle())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]


def test_old_contract_is_not_regraded():
    task = load_tasks(ROOT / "data/decision-challenge/tasks.json")[0]
    assert not BenchmarkRunner().run_task(task, AnnotatingOracle()).score.strict_success
