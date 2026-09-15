from dataclasses import asdict
import json

from jsonschema import validate

from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.difficulty import build_difficulty_profile
from faraday_industrial_benchmark.generation import generate_tasks, generation_commitment
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.scenarios import build_scenario
from faraday_industrial_benchmark.world import IndustrialWorld, canonical_hash


def test_public_suite_shape():
    tasks = load_tasks(DEFAULT_TASKS)
    assert len(tasks) == 74
    assert {task.family for task in tasks} == {
        "contingent_network_recovery",
        "capital_project",
        "customer_credit",
        "engineering_change",
        "invoice_exception",
        "inventory_mismatch",
        "machine_failure",
        "payroll_anomaly",
        "period_close",
        "quality_drift",
        "rush_order",
        "supplier_delay",
        "vendor_master_change",
        "transportation_disruption",
        "warehouse_wave",
        "network_allocation",
        "cold_chain_recall",
        "trade_compliance",
        "demand_supply_rebalance",
        "drawing_review",
        "assembly_bom_review",
        "revision_review",
        "standards_specification_review",
        "manufacturing_document_drafting",
        "pid_review",
        "process_capability_review",
        "construction_document_review",
        "supplier_quality_recovery",
        "recall_financial_response",
        "engineering_production_release",
        "order_to_cash_disruption",
        "plant_fulfillment_recovery",
        "integrated_operating_review",
    }
    assert len({task.id for task in tasks}) == len(tasks)


def test_every_scenario_is_seed_deterministic():
    for task in load_tasks(DEFAULT_TASKS):
        left = build_scenario(task)
        right = build_scenario(task)
        assert left.state == right.state
        assert [asdict(event) for event in left.events] == [asdict(event) for event in right.events]
        assert left.criteria == right.criteria
        assert left.economics == right.economics


def test_public_seeds_produce_distinct_states():
    hashes = [canonical_hash(build_scenario(task).state) for task in load_tasks(DEFAULT_TASKS)]
    assert len(set(hashes)) == len(hashes)


def test_evaluator_contract_is_not_exposed_by_tool_client():
    task = load_tasks(DEFAULT_TASKS)[0]
    world = IndustrialWorld(task)
    incident = world.call_tool("get_incident", {})
    serialized = str(incident)
    assert "criteria" not in serialized
    assert "unmitigated_cost" not in serialized
    assert "best_known_cost" not in serialized


def test_heldout_generation_is_reproducible_and_unique():
    templates = load_tasks(DEFAULT_TASKS)
    first = generate_tasks(templates, per_family=5, root_seed=8675309)
    second = generate_tasks(templates, per_family=5, root_seed=8675309)
    assert first == second
    assert len(first) == 165
    assert len({task.id for task in first}) == 165
    assert len({task.seed for task in first}) == 165
    assert generation_commitment(first) == generation_commitment(second)


def test_public_task_manifest_matches_published_json_schema():
    task_path = DEFAULT_TASKS / "tasks.json" if DEFAULT_TASKS.is_dir() else DEFAULT_TASKS
    schema_path = task_path.parents[2] / "schemas" / "task.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    records = json.loads(task_path.read_text(encoding="utf-8"))
    for record in records:
        validate(record, schema)


def test_composite_workflow_stage_graphs_are_public_and_topological():
    composite = [task for task in load_tasks(DEFAULT_TASKS) if task.workflow_stages]
    assert len(composite) == 22
    public_stage_count = 0
    for task in load_tasks(DEFAULT_TASKS):
        public_stages = task.public_dict()["workflow_stages"]
        assert public_stages
        public_stage_count += len(public_stages)
        seen = set()
        for stage in public_stages:
            assert set(stage["depends_on"]) <= seen
            seen.add(stage["id"])
    assert sum(len(task.workflow_stages) for task in composite) == 218
    assert public_stage_count == 478


def test_frontier_operating_reviews_have_professional_work_sample_depth():
    tasks = [
        task
        for task in load_tasks(DEFAULT_TASKS)
        if task.family == "integrated_operating_review"
    ]
    assert len(tasks) == 4
    for task in tasks:
        instance = build_scenario(task)
        assert len(instance.criteria) >= 400
        assert len(instance.state["case_files"]) == 11
        assert len(instance.state["operating_review_truth"][instance.state["incident"]["id"]]["exception_rows"]) == 15
        assert len(instance.events) == 4
        assert len(task.workflow_stages) == 15


def test_difficulty_profile_is_deterministic_and_frontier_gated():
    tasks = load_tasks(DEFAULT_TASKS)
    first = build_difficulty_profile(tasks)
    second = build_difficulty_profile(tasks)
    assert first == second
    assert first["summary"] == {
        "tasks": 74,
        "families": 33,
        "frontier_tasks": 12,
        "total_criteria": 2864,
        "max_criteria_per_task": 419,
        "max_workflow_stages": 15,
        "max_oracle_tool_calls": 93,
        "frontier_gates_passed": True,
    }
    assert all(first["frontier_gates"].values())
