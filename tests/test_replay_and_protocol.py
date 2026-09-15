from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS, cmd_replay
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.report import render_html
from faraday_industrial_benchmark.runner import BenchmarkRunner, CommandAgent
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK = load_tasks(DEFAULT_TASKS)[0]


def test_trace_replay_is_exact_and_tamper_evident():
    runner = BenchmarkRunner()
    result = runner.run_task(TASK, OracleAgent()).to_dict()
    exact = runner.replay(TASK, result["trace"])
    assert exact["exact_match"] is True
    assert exact["score"] == result["score"]
    assert exact["final_answer"] == result["final_answer"]

    tampered = deepcopy(result["trace"])
    tampered[0]["state_hash"] = "0" * 64
    changed = runner.replay(TASK, tampered)
    assert changed["exact_match"] is False
    assert changed["mismatches"][0]["index"] == 0


def test_tool_budget_rejection_is_traced_and_exactly_replayable():
    class OverBudgetAgent:
        name = "over-budget-test"

        def run(self, task, tools):
            for _ in range(task.max_tool_calls + 1):
                tools.call("get_incident")
            return tools.call(
                "finish",
                summary="Budget boundary exercised.",
                evidence=[],
            )["final"]

    runner = BenchmarkRunner()
    result = runner.run_task(TASK, OverBudgetAgent()).to_dict()
    rejected = result["trace"][-2]
    assert rejected["result"]["error"] == "tool_budget_exceeded"
    assert result["score"]["violations"][-1]["code"] == "tool_budget_exceeded"
    assert runner.replay(TASK, result["trace"])["exact_match"] is True


def test_saved_replay_rejects_score_tampering(tmp_path, capsys):
    run = BenchmarkRunner().run_suite([TASK], OracleAgent())
    run["results"][0]["score"]["score"] = 99.0
    path = tmp_path / "tampered-score.json"
    path.write_text(json.dumps(run), encoding="utf-8")

    exit_code = cmd_replay(
        SimpleNamespace(run=str(path), tasks=str(DEFAULT_TASKS), task=[TASK.id])
    )
    replay = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert replay["exact_match"] is False
    assert replay["episodes"][0]["score_matches"] is False


def test_wait_can_advance_exactly_to_the_next_authoritative_event():
    world = IndustrialWorld(TASK)
    client = ToolClient(world)
    next_event = world.pending_events[0]
    result = client.call("wait", until_next_event=True)
    assert result["ok"] is True
    assert world.minute == next_event.at_minute
    assert result["applied_events"] == [next_event.id]


def test_external_jsonl_protocol_runs_without_provider_sdk():
    command = f"{sys.executable} {PROJECT_ROOT / 'examples' / 'jsonl_read_only_agent.py'}"
    result = BenchmarkRunner().run_task(TASK, CommandAgent(command, timeout_seconds=10))
    assert result.score.critical_failure is False
    assert 0 < result.score.score < 30
    assert [call.tool for call in result.trace] == ["get_incident", "finish"]


def test_html_report_contains_auditable_summary(tmp_path):
    run = BenchmarkRunner().run_suite([TASK], OracleAgent())
    output = render_html(run, tmp_path / "report.html")
    text = output.read_text(encoding="utf-8")
    assert "Faraday Industrial Benchmark" in text
    assert TASK.id in text
    assert "STRICT PASS" in text
    assert 'id="faraday-industrial-run"' in text
    match = re.search(r'<script type="application/json" id="faraday-industrial-run">(.*?)</script>', text)
    assert match is not None
    assert json.loads(match.group(1))["summary"]["mean_score"] == 100.0
