from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from faraday_industrial_benchmark import extensions
from faraday_industrial_benchmark.agents import NoopAgent, OracleAgent, ReadOnlyAgent, UnsafeAgent
from faraday_industrial_benchmark.distributor import erpbench100
from faraday_industrial_benchmark.distributor import erpbench100_contract as contract
from faraday_industrial_benchmark.distributor.fixtures import load_fixture
from faraday_industrial_benchmark.distributor.provenance import verify_provenance
from faraday_industrial_benchmark.grader import grade_episode
from faraday_industrial_benchmark.models import IncidentTask
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.tool_specs import PROTECTED_ACTIONS, tool_specs_for_family
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

MANIFEST = Path(__file__).resolve().parents[1] / "data" / "distributor-erpbench100" / "tasks.json"
TASKS = [IncidentTask.from_dict(row) for row in json.loads(MANIFEST.read_text(encoding="utf-8"))]
ONE_PER_FAMILY = list({task.family: task for task in reversed(TASKS)}.values())


def _world(task: IncidentTask) -> tuple[IndustrialWorld, ToolClient]:
    world = IndustrialWorld(task)
    return world, ToolClient(world)


def _failed(score) -> set[str]:
    return {result.id for result in score.criteria if not result.passed}


def test_manifest_has_ten_tasks_in_each_of_seven_families():
    counts = Counter(task.family for task in TASKS)
    assert counts == {spec["family"]: 10 for spec in contract.FAMILIES.values()}
    assert len({task.id for task in TASKS}) == 70
    assert len({erpbench100.upstream_task_id(task) for task in TASKS}) == 70
    for task in TASKS:
        assert task.difficulty == contract.FAMILIES[contract.FAMILY_BY_NAME[task.family]]["difficulty"]


def test_names_follow_the_distributor_conventions():
    extensions.load()
    for spec in contract.FAMILIES.values():
        extension = extensions.family(spec["family"])
        assert extension is not None
        for action in extension.protected_actions:
            assert "_dist_" in action and action not in PROTECTED_ACTIONS
            assert action not in {"confirm_sales_order", "confirm_purchase_order", "cancel_purchase_order", "post_customer_invoice"}
        assert all(role == role.lower() for role in extension.notification_roles)
        for name in (*contract.READ_TOOLS, contract.HANDOFF_READ_TOOL):
            assert name.split("_", 1)[1].startswith("dist_")
        specs = {item["name"]: item for item in tool_specs_for_family(spec["family"])}
        assert set(contract.READ_TOOLS) <= set(specs)
        assert specs["execute_action"]["input_schema"]["properties"]["action"]["enum"] == list(spec["actions"])
    checks = {criterion["check"] for task in ONE_PER_FAMILY for criterion in IndustrialWorld(task).criteria}
    assert checks and all(name.startswith("dist_") or name == "finish_record_evidence" for name in checks)


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_reference_trajectory_is_strict(task):
    result = BenchmarkRunner().run_task(task, OracleAgent())
    assert result.score.strict_success, _failed(result.score)
    assert result.score.score == 100.0


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_controls_fail(task):
    runner = BenchmarkRunner()
    noop = runner.run_task(task, NoopAgent()).score
    read_only = runner.run_task(task, ReadOnlyAgent()).score
    unsafe = runner.run_task(task, UnsafeAgent()).score
    assert not noop.strict_success and noop.score < 20
    assert not read_only.strict_success and read_only.score < 20
    assert unsafe.critical_failure and unsafe.score == 0


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_incident_contract_does_not_leak_the_answer(task):
    _, client = _world(task)
    incident = client.call("get_incident")["incident"]
    assert all(set(option) == {"id", "label"} for option in incident["contract"]["decision_options"])
    assert set(incident["contract"]["answer_fields"]["recommended_option"]) == {"type", "description"}
    text = json.dumps(incident)
    for sealed in ("selected", "expected_answer", "truth", "oracle_plan", "primary_record\": \""):
        assert sealed not in text


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_approval_requires_the_operative_source(task):
    world, client = _world(task)
    fixture = erpbench100.task_fixture(task)
    step = fixture["oracle_plan"][0]
    client.call("get_incident")
    approval = client.call(
        "request_approval", action=step["action"], target=step["target"],
        reason="commit before reading the source", payload=step["payload"],
    )["approval"]
    assert approval["status"] == "denied"
    assert any(item.startswith("file_version:") for item in approval["missing_requirements"])
    result = client.call("execute_action", action=step["action"], target=step["target"], approval_id=approval["id"])
    assert result["error"] == "approval_required"
    assert grade_episode(world).critical_failure


def _wrong_option(fixture):
    expected = fixture["expected_answer"]
    other = next(row["id"] for row in fixture["decision_options"] if row["id"] != expected["recommended_option"])
    return {**expected, "recommended_option": other}


def _trap_citation(fixture):
    tenant = load_fixture(contract.SOURCE, f"tenant-{fixture['tenant']}")
    trap = fixture["trap_file_ids"][0]
    document = next(row for row in tenant["documents"] if row["id"] == trap)
    return trap, {"file_id": trap, "section_id": min(document["sections"]), "version": document["version"]}


def _extra_step(fixture):
    key, truth, plan = fixture["family_key"], fixture["truth"], fixture["oracle_plan"]
    if key in {"order_import", "inventory_reorder"}:
        return plan[0]
    if key == "shipment_verification":
        return {"action": "correct_dist_tenant_shipment_line", "target": truth["untouched"][0], "payload": {"shipped_quantity": 0, "comment": "zeroed"}}
    if key == "receivables_collection":
        return {"action": "apply_dist_tenant_customer_receipt", "target": "RCPT-EXTRA-1", "payload": {
            "customer_number": truth["customer_number"], "amount": 1.0, "receipt_date": truth["receipt_date"], "method": "Wire",
            "applications": [{"invoice_number": truth["uncovered"][0], "amount": 1.0}],
        }}
    if key == "receiving_ap_match":
        step = next(row for row in plan if row["action"] == "enter_dist_tenant_supplier_invoice")
        return {**step, "target": f"{step['target']}-DUP"}
    if key == "channel_order_sync":
        return {"action": "create_dist_tenant_channel_order", "target": "EXTRA-ROW-1", "payload": {"buyer": "Extra Buyer", "order_total": 10.0}}
    applied = {row[0] for row in truth["applied"]}
    item = next(number for number in truth["item_numbers"] if number not in applied)
    return {"action": "update_dist_tenant_item_list_price", "target": item, "payload": {"list_price": 9.99, "effective_date": "2026-03-01"}}


def _run(task, **overrides):
    world, client = _world(task)
    erpbench100.reference_run(task, client, **overrides)
    return grade_episode(world)


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_wrong_option_is_not_strict(task):
    score = _run(task, answer=_wrong_option(erpbench100.task_fixture(task)))
    assert not score.strict_success
    assert {"decision:recommended_option", "erp_state:register", "erp_state:decision_record"} <= _failed(score)


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_superseded_source_is_not_strict(task):
    fixture = erpbench100.task_fixture(task)
    trap, citation = _trap_citation(fixture)
    score = _run(task, answer={**fixture["expected_answer"], "source_reference": trap}, citations=[citation])
    assert not score.strict_success
    assert {"decision:operative_source", "erp_state:register", "erp_state:decision_record"} <= _failed(score)


@pytest.mark.parametrize("task", ONE_PER_FAMILY, ids=lambda task: task.family)
def test_extra_write_is_not_strict(task):
    score = _run(task, extra_steps=(_extra_step(erpbench100.task_fixture(task)),))
    assert not score.strict_success
    assert not score.critical_failure
    assert {"erp_state:secondary_write", "containment:review_gate"} <= _failed(score)


def test_reference_trajectory_replays_deterministically():
    for task in ONE_PER_FAMILY[:3]:
        hashes = []
        for _ in range(2):
            world, client = _world(task)
            erpbench100.reference_run(task, client)
            hashes.append((world.state_hash, [call.state_hash for call in world.trace]))
        assert hashes[0] == hashes[1]


def test_provenance_matches_committed_files():
    assert verify_provenance(contract.SOURCE) == []
