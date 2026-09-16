from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.artifact_contract import matches_contract, schema_errors
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.world import IndustrialWorld

TASKS = load_tasks(Path(__file__).parents[1] / "data/researched-v3/tasks.json")


def test_annotations_do_not_hide_business_errors():
    expected = {"rows": [{"case_id": "C", "amount": 125, "active": True}]}
    actual = deepcopy(expected)
    actual["rows"][0].update(id="EXR-1", created_minute=60, metadata={"author": "test"})
    assert matches_contract(actual, expected)
    for field, value in [("amount", 126), ("active", 1), ("case_id", "wrong")]:
        corrupt = deepcopy(actual)
        corrupt["rows"][0][field] = value
        assert not matches_contract(corrupt, expected)
    actual["unsupported_override"] = True
    assert not matches_contract(actual, expected)
    del actual["unsupported_override"]
    del actual["rows"][0]["case_id"]
    assert not matches_contract(actual, expected)


def test_unknown_exception_does_not_poison_registry():
    world = IndustrialWorld(TASKS[0])
    case_id = next(iter(world.state["operating_review_truth"]))
    result = world.call_tool(
        "create_exception_resolution",
        {
            "case_id": case_id,
            "exception_id": "TYPO",
            "category": "test",
            "affected_record_ids": ["x"],
            "disposition": "test",
            "evidence_file_ids": ["x"],
        },
    )
    assert result["error"] == "unknown_exception_id"
    assert not world.state["exception_resolutions"]


def test_resolution_changes_invalidate_only_matching_outstanding_approval():
    world = IndustrialWorld(TASKS[0])
    case_id, truth = next(iter(world.state["operating_review_truth"].items()))
    world.state["approvals"] = {
        "APR-TEST": {
            "id": "APR-TEST",
            "action": "publish_operating_review",
            "target": case_id,
            "status": "approved",
        },
        "APR-OTHER": {
            "id": "APR-OTHER",
            "action": "publish_operating_review",
            "target": "other-case",
            "status": "approved",
        },
    }
    row = deepcopy(truth["exception_rows"][0])
    del row["status"]
    assert world.call_tool("create_exception_resolution", row)["ok"]
    assert world.state["approvals"]["APR-TEST"]["status"] == "superseded"
    assert world.state["approvals"]["APR-OTHER"]["status"] == "approved"


def test_failed_publication_does_not_partially_publish_artifacts():
    observed = []

    class InvalidPackageAgent:
        name = "atomic-publication-control"

        def run(self, task, tools):
            class Proxy:
                def __init__(self):
                    self.artifacts = []

                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if (
                        name == "create_structured_artifact"
                        and arguments["artifact_type"] == "customer_commitment_schedule"
                    ):
                        arguments["content"]["totals"]["committed_quantity"] += 1
                    result = tools.call(name, **arguments)
                    if name == "create_structured_artifact" and result["ok"]:
                        self.artifacts.append(result["artifact"]["id"])
                    if name == "execute_action":
                        assert not result["ok"]
                        for artifact_id in self.artifacts:
                            artifact = tools.call(
                                "get_structured_artifact", artifact_id=artifact_id
                            )["artifact"]
                            observed.append(artifact["status"])
                    return result

            return OracleAgent().run(task, Proxy())

    episode = BenchmarkRunner().run_task(TASKS[0], InvalidPackageAgent())
    assert not episode.score.strict_success
    assert len(observed) == 4 and "published" not in observed


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_public_schema_covers_every_expected_field(task):
    world = IndustrialWorld(task)
    truth = next(iter(world.state["operating_review_truth"].values()))
    brief = next(
        f for f in world.state["case_files"].values() if "delivery_contract" in f["sections"]
    )
    schemas = brief["sections"]["delivery_contract"]["structural_schemas"]
    shared = next(
        row
        for row in truth["exception_rows"]
        if row["exception_id"] == "EX-11-SHARED-SOURCE-CAPACITY"
    )
    assert brief["sections"]["decision_policy"]["source_order"] == shared["affected_record_ids"]
    for kind, content in truth["artifact_contents"].items():
        jsonschema.validate(content, schemas[kind])
        assert not schema_errors(content, schemas[kind])
    exception_schema = schemas["control_action_register"]["properties"]["exceptions"]["items"]
    assert "case_id" in exception_schema["required"]
    incomplete = deepcopy(truth["artifact_contents"]["control_action_register"])
    del incomplete["exceptions"][0]["case_id"]
    errors = schema_errors(incomplete, schemas["control_action_register"])
    assert errors == ["content.exceptions[0].case_id: required"]


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
@pytest.mark.parametrize("after_failed_publication", [False, True])
def test_incorrect_resolution_can_be_corrected_and_published(task, after_failed_publication):
    class CorrectingAgent:
        name = "revision-recovery-control"

        def run(self, task, tools):
            class Proxy:
                inserted = False
                correction = None
                approval_arguments = None

                def call(self, name, **arguments):
                    arguments = deepcopy(arguments)
                    if name == "request_approval":
                        self.approval_arguments = deepcopy(arguments)
                    if name == "create_exception_resolution" and not self.inserted:
                        wrong = deepcopy(arguments)
                        wrong["affected_record_ids"] = ["incorrect-record"]
                        wrong_result = tools.call(name, **wrong)
                        assert wrong_result["ok"]
                        self.inserted = True
                        if after_failed_publication:
                            self.correction = deepcopy(arguments)
                            return wrong_result
                    if name == "execute_action" and self.correction is not None:
                        failed = tools.call(name, **arguments)
                        assert failed["error"] == "operating_review_exception_register_mismatch"
                        assert tools.call("create_exception_resolution", **self.correction)["ok"]
                        self.correction = None
                        fresh = tools.call("request_approval", **self.approval_arguments)
                        assert fresh["ok"]
                        arguments["approval_id"] = fresh["approval"]["id"]
                    if name == "create_structured_artifact":
                        arguments["content"]["metadata"] = {"reviewer": "qualification"}
                        if arguments["artifact_type"] == "control_action_register":
                            for row in arguments["content"]["exceptions"]:
                                row["created_minute"] = 99
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Proxy())

    runner = BenchmarkRunner()
    episode = runner.run_task(task, CorrectingAgent())
    assert episode.score.strict_success
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]
    corrections = [t for t in episode.trace if t.tool == "create_exception_resolution"]
    assert any(t.result["exception_resolution"]["supersedes"] for t in corrections)
