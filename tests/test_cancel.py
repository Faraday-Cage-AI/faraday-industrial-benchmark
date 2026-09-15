import shlex
import sys
import time
from threading import Event

from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner, CommandAgent


def test_operator_cancel_terminates_command_promptly():
    cancelled = Event()
    cancelled.set()
    agent = CommandAgent(
        shlex.join([sys.executable, "-c", "import time; time.sleep(30)"]), cancel_event=cancelled
    )
    started = time.monotonic()
    episode = BenchmarkRunner().run_task(load_tasks(DEFAULT_TASKS)[0], agent)
    assert time.monotonic() - started < 5
    assert not episode.score.strict_success
    assert any("cancelled by operator" in str(row) for row in episode.score.violations)
