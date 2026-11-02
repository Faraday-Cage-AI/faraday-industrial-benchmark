from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from faraday_industrial_benchmark import extensions
from faraday_industrial_benchmark.agents import NoopAgent, OracleAgent, ReadOnlyAgent, UnsafeAgent
from faraday_industrial_benchmark.distributor import gdpval_work
from faraday_industrial_benchmark.distributor.gdpval_checks import evaluate
from faraday_industrial_benchmark.distributor.provenance import verify_provenance
from faraday_industrial_benchmark.grader import grade_episode
from faraday_industrial_benchmark.models import IncidentTask
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.tool_specs import PROTECTED_ACTIONS, tool_specs_for_family
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

MANIFEST = Path(__file__).resolve().parents[1] / "data" / "distributor-gdpval" / "tasks.json"
TASKS = [IncidentTask.from_dict(row) for row in json.loads(MANIFEST.read_text(encoding="utf-8"))]
BY_ID = {task.id: task for task in TASKS}
UNSCORED_REASONS = {"file_format", "presentation", "workbook_mechanics", "narrative", "upstream_conflict", "not_applicable"}

# One wrong value per family: (task, path into the truth artifact, wrong value, check that must fail).
WRONG_VALUES = {
    "distributor_sales_analytics": ("faraday-gdpval-003", ["june_shipped", "accounts", "Sigma", "percent_shipped"], 99.0,
                                    "account-sigma-pct"),
    "distributor_pricing_quotation": ("faraday-gdpval-017", ["lines", "400301", "unit_price"], 2500, "400301-price"),
    "distributor_inventory_planning": ("faraday-gdpval-021", ["cost", "total"], 80000, "total-cost"),
    "distributor_warehouse_shipping": ("faraday-gdpval-023", ["shipments", 1, "shipping_method"], "FedEx", "b-5005-method"),
    "distributor_policy_documents": ("faraday-gdpval-011", ["missing_items", "receive_into_inventory"], True, "missing-not-received"),
}


def _failed(score) -> set[str]:
    return {result.id for result in score.criteria if not result.passed}


def test_manifest_covers_23_tasks_in_five_families():
    assert [task.id for task in TASKS] == [f"faraday-gdpval-{index:03d}" for index in range(1, 24)]
    assert set(Counter(task.family for task in TASKS)) == set(gdpval_work.FAMILY_SPECS)
    upstream = set()
    for task in TASKS:
        assert task.version == "0.7.0"
        assert "source:gdpval" in task.tags
        assert any(tag.startswith("occupation:") for tag in task.tags)
        upstream |= {tag for tag in task.tags if tag.startswith("upstream:")}
    assert len(upstream) == 23


def test_names_follow_the_distributor_conventions():
    extensions.load()
    for family, spec in gdpval_work.FAMILY_SPECS.items():
        extension = extensions.family(family)
        assert extension is not None
        assert extension.protected_actions == (spec["action"],)
        assert "_gdp_" in spec["action"] and spec["action"] not in PROTECTED_ACTIONS
        assert all(role == role.lower() for role in extension.notification_roles)
        names = {item["name"] for item in tool_specs_for_family(family)}
        assert {"list_gdp_tables", "query_gdp_table", "get_gdp_shape_report"} <= names


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_reference_trajectory_is_strict(task):
    result = BenchmarkRunner().run_task(task, OracleAgent())
    assert result.score.strict_success, _failed(result.score)
    assert result.score.score == 100.0


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_controls_fail(task):
    runner = BenchmarkRunner()
    noop = runner.run_task(task, NoopAgent()).score
    read_only = runner.run_task(task, ReadOnlyAgent()).score
    unsafe = runner.run_task(task, UnsafeAgent()).score
    assert not noop.strict_success and noop.score < 20
    assert not read_only.strict_success and read_only.score < 20
    assert unsafe.critical_failure and unsafe.score == 0 and not unsafe.strict_success


def _set(content, path, value):
    target = content
    for part in path[:-1]:
        target = target[part]
    assert path[-1] in target if isinstance(target, dict) else 0 <= path[-1] < len(target)
    target[path[-1]] = value


@pytest.mark.parametrize("family", sorted(WRONG_VALUES))
def test_wrong_value_fails_its_criterion(family, monkeypatch):
    task_id, path, value, check_id = WRONG_VALUES[family]
    task = BY_ID[task_id]
    assert task.family == family
    world = IndustrialWorld(task)
    grader = copy.deepcopy(gdpval_work.grader_fixture(task_id))
    _set(grader["truth"], path, value)
    monkeypatch.setattr(gdpval_work, "grader_fixture", lambda _task_id: grader)
    gdpval_work.oracle(task, ToolClient(world))
    score = grade_episode(world)
    assert not score.strict_success
    assert not score.critical_failure
    assert f"artifact-{check_id}" in _failed(score)


def test_reference_trajectory_replays_deterministically():
    for task in TASKS[:: 8]:
        hashes = []
        for _ in range(2):
            world = IndustrialWorld(task)
            gdpval_work.oracle(task, ToolClient(world))
            hashes.append((world.state_hash, [call.state_hash for call in world.trace]))
        assert hashes[0] == hashes[1]


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_every_rubric_item_is_classified(task):
    grader = gdpval_work.grader_fixture(task.id)
    check_ids = {row["id"] for row in grader["checks"]}
    assert grader["rubric"]
    scored = 0
    for item in grader["rubric"]:
        if item["status"] == "scored":
            assert item["criteria"] and set(item["criteria"]) <= check_ids
            scored += 1
        else:
            assert item["status"] == "unscored" and item["reason"] in UNSCORED_REASONS
    assert scored >= len(grader["rubric"]) // 2
    for row in grader["checks"]:
        assert row["weight"] > 0
        passed, detail = evaluate(row, grader["truth"])
        assert passed, (row["id"], detail)


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_episode_fixture_is_sealed(task):
    fixture = gdpval_work.task_fixture(task.id)
    text = json.dumps(fixture)
    for sealed in ('"truth"', '"rubric"', '"checks"', '"rubric_item_id"'):
        assert sealed not in text
    brief = fixture["case_files"][0]["sections"]
    assert brief["submission_contract"]["deliverable_id"] == fixture["incident"]["deliverable_id"]


def test_provenance_matches_committed_files():
    assert verify_provenance("gdpval") == []
