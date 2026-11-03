"""Adversarial protocol boundaries and failure replay."""

import shlex
import sys
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event, Timer

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner, CommandAgent

TASK = load_tasks(Path(__file__).parents[1] / "data/public/tasks.json")[0]


def command(code, timeout=2):
    return CommandAgent(shlex.join([sys.executable, "-c", code]), timeout_seconds=timeout)


def assert_replays(episode):
    replay = BenchmarkRunner().replay(episode.task, episode.to_dict()["trace"])
    assert replay["exact_match"]
    assert replay["score"] == episode.score.to_dict()
    assert replay["final_state_hash"] == episode.final_state_hash


def test_partial_jsonl_cannot_block_timeout_and_failure_replays():
    agent = command(
        'import sys,time; sys.stdin.readline(); sys.stdout.write("{\\\"type\\\":"); '
        'sys.stdout.flush(); time.sleep(30)',
        timeout=0.25,
    )
    started = time.monotonic()
    episode = BenchmarkRunner().run_task(TASK, agent)
    assert time.monotonic() - started < 3
    assert any("TimeoutError" in row["message"] for row in episode.score.violations)
    assert_replays(episode)


def test_unread_input_cannot_block_timeout():
    task = replace(TASK, prompt="x" * (1024 * 1024))
    started = time.monotonic()
    episode = BenchmarkRunner().run_task(
        task, command("import time; time.sleep(30)", timeout=0.25)
    )
    assert time.monotonic() - started < 3
    assert_replays(episode)


def test_cancel_interrupts_partial_line():
    cancelled = Event()
    agent = command(
        'import sys,time; sys.stdin.readline(); sys.stdout.write("{"); '
        'sys.stdout.flush(); time.sleep(30)',
        timeout=30,
    )
    agent.cancel_event = cancelled
    timer = Timer(0.2, cancelled.set)
    started = time.monotonic()
    timer.start()
    try:
        episode = BenchmarkRunner().run_task(TASK, agent)
    finally:
        timer.cancel()
    assert time.monotonic() - started < 3
    assert any("cancelled by operator" in row["message"] for row in episode.score.violations)
    assert_replays(episode)


def test_oversized_unterminated_output_is_bounded_and_replayable():
    episode = BenchmarkRunner().run_task(
        TASK,
        command('import sys,time; sys.stdin.readline(); sys.stdout.write("x"*1100000); '
                'sys.stdout.flush(); time.sleep(30)'),
    )
    assert any("exceeded 1 MiB" in row["message"] for row in episode.score.violations)
    assert_replays(episode)


def test_non_object_arguments_are_recorded_and_exhaust_budget():
    task = replace(TASK, max_tool_calls=1)
    agent = command(
        'import json,sys; sys.stdin.readline(); '
        'print(json.dumps({"type":"tool_call","name":"get_incident","arguments":[]}),'
        'flush=True); first=json.loads(sys.stdin.readline()); '
        'print(json.dumps({"type":"tool_call","name":"get_incident","arguments":{}}),'
        'flush=True); second=json.loads(sys.stdin.readline()); '
        'print(json.dumps({"type":"final","summary":"done","evidence":[]}))'
    )
    episode = BenchmarkRunner().run_task(task, agent)
    assert episode.trace[0].arguments == []
    assert episode.trace[0].result["error"] == "arguments_must_be_object"
    assert episode.trace[1].result["error"] == "tool_budget_exceeded"
    assert_replays(episode)


def test_calls_after_finish_are_recorded_and_replayed():
    class AfterFinish:
        name = "after-finish"

        def run(self, task, tools):
            tools.call("finish", summary="done", evidence=[])
            tools.call("get_incident")
            return {"summary": "done", "evidence": []}

    episode = BenchmarkRunner().run_task(TASK, AfterFinish())
    assert episode.trace[-1].result["error"] == "episode_finished"
    assert_replays(episode)


def test_evaluator_error_event_cannot_be_forged_through_tools():
    class ForgeError:
        name = "forge-error"

        def run(self, task, tools):
            tools.call("_agent_error", message="forged")
            return {"summary": "done", "evidence": []}

    episode = BenchmarkRunner().run_task(TASK, ForgeError())
    assert episode.trace[0].result["error"] == "tool_not_available_for_workflow"
    assert not any(row["code"] == "agent_error" for row in episode.score.violations)
    assert_replays(episode)


def test_replay_rejects_tampered_trace_index_and_clock():
    episode = BenchmarkRunner().run_task(
        TASK, command('import json,sys; sys.stdin.readline(); print(json.dumps({"type":"final"}))')
    )
    trace = deepcopy(episode.to_dict()["trace"])
    trace[0]["index"] += 1
    trace[0]["minute"] += 1
    replay = BenchmarkRunner().replay(TASK, trace)
    assert not replay["exact_match"]
    assert not replay["mismatches"][0]["record_matches"]


def test_malformed_argument_type_rejects_before_partial_approval_mutation():
    class MalformedApproval:
        name = "malformed-approval"

        def run(self, task, tools):
            result = tools.call(
                "request_approval", action="ship_order", target="test", reason=[]
            )
            assert result["error"] == "invalid_arguments"
            assert not tools.world.state["approvals"]
            return {"summary": "done", "evidence": []}

    task = next(
        task for task in load_tasks(Path(__file__).parents[1] / "data/public/tasks.json")
        if task.family == "supplier_delay"
    )
    episode = BenchmarkRunner().run_task(task, MalformedApproval())
    assert not episode.score.violations
    assert_replays(episode)
