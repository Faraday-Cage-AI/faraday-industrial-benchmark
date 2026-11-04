"""The event viewer must reproduce the runner's protocol and failure boundaries."""

import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "scenario_events", ROOT / "viewer/scripts/scenario_events.py"
)
assert SPEC is not None and SPEC.loader is not None
VIEWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEWER)
TASKS = load_tasks(ROOT / "data/public/tasks.json")
TASK = TASKS[0]


def assert_viewer_replays(episode):
    # Persisted JSON is the viewer's input, including arrays replacing tuples.
    trace = json.loads(json.dumps(episode.to_dict()["trace"]))
    replay = VIEWER.replay(episode.task, trace)
    assert replay["first_result_mismatch"] is None
    assert replay["first_record_mismatch"] is None
    assert replay["applied_events"] == episode.applied_events
    assert BenchmarkRunner().replay(episode.task, trace)["exact_match"]
    return replay


@pytest.mark.parametrize("arguments", [[], None, "bad", 7])
def test_malformed_arguments_and_budget_rejection_replay(arguments):
    class MalformedAgent:
        name = "malformed-viewer-test"

        def run(self, task, tools):
            assert tools.call_raw("get_incident", arguments)["error"] == "arguments_must_be_object"
            assert tools.call("get_incident")["error"] == "tool_budget_exceeded"
            return {"summary": "done", "evidence": []}

    episode = BenchmarkRunner().run_task(replace(TASK, max_tool_calls=1), MalformedAgent())
    assert_viewer_replays(episode)


def test_crashed_agent_replays_failure_marker_without_firing_events():
    class CrashedAgent:
        name = "crashed-viewer-test"

        def run(self, task, tools):
            tools.call("get_incident")
            raise RuntimeError("test crash")

    episode = BenchmarkRunner().run_task(TASK, CrashedAgent())
    assert episode.trace[-2].tool == "_agent_error"
    replay = assert_viewer_replays(episode)
    assert all(item["fired_during"] is None for item in replay["events"])


def test_agent_cannot_replay_a_tool_attempt_as_an_evaluator_marker():
    class ForgedMarkerAgent:
        name = "forged-marker-viewer-test"

        def run(self, task, tools):
            tools.call("_agent_error", message="forged")
            return {"summary": "done", "evidence": []}

    episode = BenchmarkRunner().run_task(TASK, ForgedMarkerAgent())
    assert episode.trace[0].result["error"] == "tool_not_available_for_workflow"
    assert_viewer_replays(episode)


@pytest.mark.parametrize("field,value", [("state_hash", "0" * 64), ("index", 99), ("minute", 99)])
def test_full_record_divergence_is_reported_even_if_result_matches(field, value):
    episode = BenchmarkRunner().run_task(TASK, OracleAgent())
    trace = deepcopy(episode.to_dict()["trace"])
    trace[0][field] = value
    replay = VIEWER.replay(TASK, trace)
    assert replay["first_result_mismatch"] is None
    assert replay["first_record_mismatch"] == 0


def test_result_divergence_is_reported():
    episode = BenchmarkRunner().run_task(TASK, OracleAgent())
    trace = deepcopy(episode.to_dict()["trace"])
    trace[0]["result"] = {"ok": False, "error": "tampered"}
    replay = VIEWER.replay(TASK, trace)
    assert replay["first_result_mismatch"] == 0
    assert replay["first_record_mismatch"] == 0


def test_dynamically_scheduled_event_keeps_scheduling_and_firing_call_positions():
    task = next(task for task in TASKS if task.id == "faraday-supply-001")
    episode = BenchmarkRunner().run_task(task, OracleAgent())
    replay = assert_viewer_replays(episode)
    decision = next(item for item in replay["events"] if item["event"]["kind"] == "approval_decision")
    assert episode.trace[decision["scheduled_by"]].tool == "request_approval"
    assert decision["fired_during"] >= decision["scheduled_by"]
