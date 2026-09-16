"""Reporting integrity checks; these fixtures make no model/API calls."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("frontier_audit", ROOT / "examples/audit_frontier.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(scope="module")
def reference():
    task = load_tasks(ROOT / "data/researched-v2/tasks.json")[0]
    return BenchmarkRunner().run_suite([task], OracleAgent())


@pytest.fixture
def measurement(tmp_path, reference):
    task_path = tmp_path / "tasks.json"
    task_path.write_text(
        json.dumps([json.loads((ROOT / "data/researched-v2/tasks.json").read_text())[0]])
    )
    digest = hashlib.sha256((ROOT / "examples/openai_responses_agent.py").read_bytes()).hexdigest()
    task_id = reference["results"][0]["task"]["id"]
    frozen = {
        "task_ids": [task_id],
        "models": ["gpt-5.4", "gpt-5.5"],
        "tasks_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
        "adapter_sha256": digest,
        "source_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "src/faraday_industrial_benchmark").glob("*.py")
        },
    }
    (tmp_path / "frozen-manifest.json").write_text(json.dumps(frozen))
    for model in frozen["models"]:
        report = deepcopy(reference)
        report["results"][0]["agent"] = f"{model}/xhigh/tool-only"
        report["measurement"] = {
            "interrupted": False,
            "adapter_sha256": digest,
            "reasoning_effort": "xhigh",
            "per_response_output_limit": 32768,
            "total_output_limit": 100000,
            "timeout_seconds": 1800,
        }
        (tmp_path / f"{model}-{task_id}.json").write_text(json.dumps(report))
    return tmp_path, task_path, tmp_path / f"gpt-5.4-{task_id}.json"


def test_complete_replayed_measurement(measurement):
    directory, tasks, _ = measurement
    assert MODULE.audit(directory, tasks)["episodes_verified"] == 2


def test_collection_requires_complete_unique_coverage(measurement):
    directory, tasks, _ = measurement
    assert MODULE.audit_collection([directory], tasks)["full_suite_coverage_verified"]
    with pytest.raises(AssertionError, match="Duplicate tasks"):
        MODULE.audit_collection([directory, directory], tasks)
    with pytest.raises(AssertionError, match="full supplied suite"):
        MODULE.audit_collection([], tasks)


def test_explicit_subset_cannot_name_unknown_tasks(measurement):
    directory, tasks, _ = measurement
    with pytest.raises(AssertionError, match="Unknown or empty"):
        MODULE.audit(directory, tasks, selected_ids={"unknown"})


@pytest.mark.parametrize("malformed", [False, True])
def test_frozen_budget_must_match_recorded_budget(measurement, malformed):
    directory, tasks, _ = measurement
    path = directory / "frozen-manifest.json"
    frozen = json.loads(path.read_text())
    frozen["measurement_settings"] = (
        {}
        if malformed
        else {
            "reasoning_effort": "xhigh",
            "per_response_output_limit": 65536,
            "total_output_limit": 200000,
            "timeout_seconds": 3600,
        }
    )
    path.write_text(json.dumps(frozen))
    with pytest.raises(AssertionError):
        MODULE.audit(directory, tasks)


@pytest.mark.parametrize("defect", ["missing", "interrupted", "settings", "score", "trace"])
def test_rejects_invalid_measurement(measurement, defect):
    directory, tasks, path = measurement
    report = json.loads(path.read_text())
    if defect == "missing":
        path.unlink()
    else:
        if defect == "interrupted":
            report["measurement"]["interrupted"] = True
        elif defect == "settings":
            report["measurement"]["reasoning_effort"] = "low"
        elif defect == "score":
            report["results"][0]["score"]["score"] = -1
        else:
            report["results"][0]["trace"][0]["state_hash"] = "tampered"
        path.write_text(json.dumps(report))
    with pytest.raises(AssertionError):
        MODULE.audit(directory, tasks)


def test_rejects_incomplete_source_freeze(measurement):
    directory, tasks, _ = measurement
    path = directory / "frozen-manifest.json"
    frozen = json.loads(path.read_text())
    frozen["source_hashes"] = {}
    path.write_text(json.dumps(frozen))
    with pytest.raises(AssertionError, match="Incomplete source freeze"):
        MODULE.audit(directory, tasks)


@pytest.mark.parametrize("used", [99999, 100000])
def test_terminal_budget_reconstruction_requires_usage_evidence(tmp_path, used):
    class ExitAgent:
        name = "synthetic-exit-control"

        def run(self, task, tools):
            tools.call("get_incident")
            raise RuntimeError("agent exited before final response (code=1)")

    task = load_tasks(ROOT / "data/researched-v2/tasks.json")[0]
    episode = BenchmarkRunner().run_task(task, ExitAgent()).to_dict()
    usage = tmp_path / "usage.jsonl"
    usage.write_text(json.dumps({"usage": {"output_tokens": used}}) + "\n")
    if used < 100000:
        with pytest.raises(AssertionError):
            MODULE.replay_budget_exit(task, episode, usage, {"total_output_limit": 100000})
    else:
        result = MODULE.replay_budget_exit(task, episode, usage, {"total_output_limit": 100000})
        assert result["score"] == episode["score"]
        assert result["final_state_hash"] == episode["final_state_hash"]


@pytest.mark.parametrize("elapsed", [1799, 1801])
def test_timeout_reconstruction_requires_elapsed_evidence(elapsed):
    class TimeoutAgent:
        name = "synthetic-timeout-control"

        def run(self, task, tools):
            tools.call("get_incident")
            raise TimeoutError("agent command exceeded 1800s")

    task = load_tasks(ROOT / "data/researched-v2/tasks.json")[0]
    episode = BenchmarkRunner().run_task(task, TimeoutAgent()).to_dict()
    measurement = {"timeout_seconds": 1800, "wall_seconds": elapsed}
    if elapsed < 1800:
        with pytest.raises(AssertionError):
            MODULE.replay_timeout_exit(task, episode, measurement)
    else:
        result = MODULE.replay_timeout_exit(task, episode, measurement)
        assert result["score"] == episode["score"]
        assert result["final_state_hash"] == episode["final_state_hash"]
