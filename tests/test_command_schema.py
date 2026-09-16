import json
import shlex
import sys
from pathlib import Path

import pytest

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BudgetedToolClient, CommandAgent
from faraday_industrial_benchmark.world import IndustrialWorld


def client():
    task = load_tasks(Path(__file__).parents[1] / "data/close-execution/tasks.json")[0]
    return task, BudgetedToolClient(IndustrialWorld(task))


def test_external_agent_receives_exact_live_schema():
    task, tools = client()
    code = (
        "import json,sys; x=json.loads(sys.stdin.readline()); "
        'print(json.dumps({"type":"final","summary":json.dumps(x["tools"]),"evidence":[]}))'
    )
    final = CommandAgent(shlex.join([sys.executable, "-c", code]), timeout_seconds=10).run(
        task, tools
    )
    assert json.loads(final["summary"]) == tools.tools
    for spec in json.loads(final["summary"]):
        if spec["name"] in {"execute_action", "request_approval"}:
            assert {"post_close_stage", "release_close_hold", "reconcile_close_ledger"} <= set(
                spec["input_schema"]["properties"]["action"]["enum"]
            )


def test_early_closed_stdout_is_not_reported_as_timeout():
    task, tools = client()
    code = "import os,sys,time; sys.stdin.readline(); os.close(1); time.sleep(2)"
    with pytest.raises(RuntimeError, match="closed protocol output"):
        CommandAgent(shlex.join([sys.executable, "-c", code]), timeout_seconds=10).run(task, tools)
