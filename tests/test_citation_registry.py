"""Final evidence identities must come from records, including nested ERP registries."""

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.grader import _check, _known_record_ids, grade_episode
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

TASKS = load_tasks(DEFAULT_TASKS)


def _world(family):
    task = next(task for task in TASKS if task.family == family)
    world = IndustrialWorld(task)
    return world, ToolClient(world)


def _assert_evidence(world, tools, evidence, *, distinct):
    assert tools.call("finish", summary="Citation registry control", evidence=evidence)["ok"]
    for check in ("finish_evidence", "finish_record_evidence"):
        assert _check(world, {"check": check, "minimum": distinct})[0]
        assert not _check(world, {"check": check, "minimum": distinct + 1})[0]


@pytest.mark.parametrize("action", [
    {"id": "fake-record"},
    {"shipment_id": "fake-record"},
    {"extra": {"id": "fake-record"}},
    {"extra": [{"record_id": "fake-record"}]},
    {"actions": [{"id": "fake-record"}]},
    {"distribution_plans": {"fake-record": {"id": "fake-record"}}},
])
def test_public_plan_actions_cannot_mint_citable_records(action):
    world, tools = _world("transportation_disruption")
    result = tools.call(
        "create_distribution_plan", plan_type="transportation",
        actions=[action], rationale="Adversarial citation control",
    )
    assert result["ok"]
    plan_id = result["distribution_plan"]["id"]
    assert "fake-record" not in _known_record_ids(world)
    _assert_evidence(world, tools, ["fake-record", plan_id], distinct=1)


def test_nested_plan_spoof_fails_evidence_after_otherwise_completed_workflow():
    world, tools = _world("transportation_disruption")

    class SpoofingClient:
        def call(self, name, **arguments):
            if name == "finish":
                result = tools.call(
                    "create_distribution_plan", plan_type="transportation",
                    actions=[{"id": f"fake-record-{i}"} for i in range(30)],
                    rationale="Adversarial citation control",
                )
                assert result["ok"]
                arguments["evidence"] = [f"fake-record-{i}" for i in range(30)]
            return tools.call(name, **arguments)

    OracleAgent().run(world.task, SpoofingClient())
    score = grade_episode(world)
    evidence_results = [
        result for result in score.criteria
        if result.id in {
            c["id"] for c in world.criteria
            if c["check"] in {"finish_evidence", "finish_record_evidence"}
        }
    ]
    assert evidence_results and all(not result.passed for result in evidence_results)
    assert all(result.passed for result in score.criteria if result not in evidence_results)
    assert not score.strict_success and score.score < 100


@pytest.mark.parametrize("content", [
    {"id": "fake-record"},
    {"records": [{"record_id": "fake-record"}]},
    {"distribution_plans": {"fake-record": {"id": "fake-record"}}},
])
def test_public_artifact_body_cannot_mint_citable_records(content):
    world, tools = _world("distributor_sales_analytics")
    incident = tools.call("get_incident")["incident"]
    files = tools.call("list_case_files")["files"]
    source = files[0]
    result = tools.call(
        "create_structured_artifact", artifact_type=incident["artifact_type"],
        title="Adversarial citation control", content=content,
        citations=[{
            "file_id": source["id"], "section_id": source["section_ids"][0],
            "version": source["version"],
        }],
    )
    assert result["ok"]
    artifact_id = result["artifact"]["id"]
    assert "fake-record" not in _known_record_ids(world)
    _assert_evidence(world, tools, [artifact_id, "fake-record"], distinct=1)


def test_duplicate_real_ids_count_once():
    world, tools = _world("transportation_disruption")
    incident_id = tools.call("get_incident")["incident"]["id"]
    _assert_evidence(world, tools, [incident_id] * 30, distinct=1)


@pytest.mark.parametrize("family", [
    "period_close", "recall_financial_response", "cold_chain_recall", "drawing_review",
])
def test_core_period_genealogy_and_created_records_remain_citable(family):
    world, tools = _world(family)
    OracleAgent().run(world.task, tools)
    known = _known_record_ids(world)
    incident = world.state["incident"]
    if "period" in incident:
        assert incident["period"] in known
    if "lot_id" in incident:
        assert incident["lot_id"] in known
    assert set(world.final_answer["evidence"]) <= known
    assert grade_episode(world).strict_success


@pytest.mark.parametrize("family", [
    "distributor_buy_to_fulfill", "distributor_shipment_verification",
    "distributor_receivables_collection", "distributor_inventory_reorder",
    "distributor_receiving_ap_match", "distributor_sales_analytics",
])
def test_nested_distributor_reference_identities_remain_citable(family):
    world, tools = _world(family)
    OracleAgent().run(world.task, tools)
    assert set(world.final_answer["evidence"]) <= _known_record_ids(world)
    assert grade_episode(world).strict_success


def test_foreign_keys_and_unknown_containers_are_not_record_registries():
    world, _ = _world("transportation_disruption")
    # Defensive coverage for future tools: a new field or container must not
    # silently become a registry merely because it has an identity-shaped value.
    world.state["distribution_plans"]["DP-001"] = {
        "id": "DP-001", "unverified_id": "fake-reference",
        "extra": {"id": "fake-extra"}, "payload": {"id": "fake-payload"},
    }
    world.state["extra"] = {"fake-registry": {"id": "fake-registry"}}
    assert not ({"fake-reference", "fake-extra", "fake-payload", "fake-registry"}
                & _known_record_ids(world))
