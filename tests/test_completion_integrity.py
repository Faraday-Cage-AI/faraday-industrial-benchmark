import json
from copy import deepcopy

import pytest

from faraday_industrial_benchmark.agents import NoopAgent, OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.grader import efficiency_target, grade_episode
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.provenance import input_fingerprints
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.verification import verify_run
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

TASKS = load_tasks(DEFAULT_TASKS)


def test_fabricated_final_citations_never_strictly_pass_public_suite():
    class FabricatedCitations:
        name = "fabricated-citation-control"

        def run(self, task, tools):
            class Client:
                def call(self, name, **arguments):
                    if name == "finish":
                        arguments["evidence"] = [f"fake-record-{i}" for i in range(30)]
                    return tools.call(name, **arguments)

            return OracleAgent().run(task, Client())

    runner = BenchmarkRunner()
    for task in TASKS:
        score = runner.run_task(task, FabricatedCitations()).score
        assert not score.strict_success, task.id
        assert score.score < 100, task.id


@pytest.mark.parametrize("field", ["summary", "family_summaries", "capability_summaries"])
def test_replay_rejects_forged_aggregate(field):
    run = BenchmarkRunner().run_suite(TASKS[:1], NoopAgent())
    run[field] = {}
    assert not verify_run(run, TASKS)["exact_match"]


def test_replay_binds_source_seed_task_coverage_and_agent_identity():
    run = BenchmarkRunner().run_suite(TASKS[:1], NoopAgent())
    verified = verify_run(run, TASKS)
    assert verified["exact_match"] and not verified["covers_supplied_manifest"]
    tampered = deepcopy(run)
    tampered["agent"] = "different-agent"
    assert not verify_run(tampered, TASKS)["exact_match"]
    tampered = deepcopy(run)
    tampered["provenance"]["inputs"]["task_manifest_sha256"] = "0" * 64
    assert not verify_run(tampered, TASKS)["exact_match"]
    tampered = deepcopy(run)
    tampered["results"] *= 2
    assert not verify_run(tampered, TASKS)["exact_match"]


def test_public_scoring_targets_equal_grader_for_every_task_without_answers():
    for task in TASKS:
        world = IndustrialWorld(task)
        visible = ToolClient(world).call("get_incident")["scoring_contract"]
        assert visible["finish_by_minute_for_full_timeliness"] == world.economics["target_minutes"]
        assert visible["tool_calls_for_full_efficiency"] == efficiency_target(task)
        assert visible["minimum_final_record_ids"] >= 1
        assert not ({"truth", "checks", "criteria", "best_known_cost"} & visible.keys())


def test_crash_after_completed_workflow_is_not_strict_success():
    class CrashesAfterWork:
        name = "crashes-after-work"

        def run(self, task, tools):
            OracleAgent().run(task, tools)
            raise RuntimeError("controlled post-completion crash")

    result = BenchmarkRunner().run_task(TASKS[0], CrashesAfterWork())
    assert not result.score.strict_success
    assert BenchmarkRunner().replay(TASKS[0], result.to_dict()["trace"])["score"] == result.score.to_dict()


def test_quality_overcontainment_does_not_earn_perfect_outcome():
    task = next(task for task in TASKS if task.family == "quality_drift")
    world = IndustrialWorld(task)
    client = ToolClient(world)

    class ExtraHold:
        def call(self, name, **arguments):
            if name == "finish":
                required = next(c["values"] for c in world.criteria if c["id"] == "contain-lots")
                unaffected = next(lot for lot in world.state["lots"] if lot not in required)
                assert client.call("place_quality_hold", lot_id=unaffected, reason="unnecessary hold")["ok"]
            return client.call(name, **arguments)

    OracleAgent().run(task, ExtraHold())
    score = grade_episode(world)
    assert not score.strict_success and score.score < 100
    assert "contain-lots" in {c.id for c in score.criteria if not c.passed}


def test_input_fingerprints_are_deterministic_and_include_nested_distributor_code():
    first = input_fingerprints(TASKS[:1])
    assert first == input_fingerprints(TASKS[:1])
    assert "distributor/gdpval_checks.py" in first["source_files"]
    assert any(path.startswith("distributor/fixtures/") for path in first["source_files"])
    json.dumps(first)
