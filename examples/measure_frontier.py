"""Run a matched tool-only development comparison, loading an authorized env file."""

import argparse
import hashlib
import json
import os
import shlex
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from dotenv import dotenv_values

from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner, CommandAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--agent-python", default=sys.executable)
    args = parser.parse_args()
    cancelled = Event()
    for event_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event_signal, lambda *_: cancelled.set())
    key = dotenv_values(args.env_file).get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Configured platform file has no OpenAI key")
    os.environ["OPENAI_API_KEY"] = key
    tasks = [t for t in load_tasks(args.tasks) if t.family == "contingent_network_recovery"]
    tasks = tasks[args.start : args.start + args.count]
    args.output.mkdir(parents=True, exist_ok=True)
    adapter = Path(__file__).with_name("openai_responses_agent.py").resolve()

    def evaluate(model):
        for task in tasks:
            if cancelled.is_set():
                return
            stem = args.output / f"{model}-{task.id}"
            report_path = Path(str(stem) + ".json")
            if report_path.exists():
                raise RuntimeError("Refusing to overwrite a previous attempt")
            usage_path = Path(str(stem) + "-usage.jsonl")
            command = shlex.join(
                [
                    args.agent_python,
                    str(adapter),
                    "--model",
                    model,
                    "--reasoning-effort",
                    "xhigh",
                    "--max-output-tokens",
                    "32768",
                    "--max-total-output-tokens",
                    "100000",
                    "--usage-log",
                    str(usage_path),
                ]
            )
            started = time.monotonic()
            report = BenchmarkRunner().run_suite(
                [task],
                CommandAgent(
                    command,
                    timeout_seconds=1800,
                    name=f"{model}/xhigh/tool-only",
                    cancel_event=cancelled,
                ),
            )
            report["measurement"] = {
                "interrupted": cancelled.is_set(),
                "wall_seconds": time.monotonic() - started,
                "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
                "reasoning_effort": "xhigh",
                "per_response_output_limit": 32768,
                "total_output_limit": 100000,
                "timeout_seconds": 1800,
                "track": "public development, tool-only; no code interpreter",
                "attempt": 1,
            }
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                json.dumps({"model": model, "task": task.id, "summary": report["summary"]}),
                flush=True,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(evaluate, ("gpt-5.4", "gpt-5.5")))


if __name__ == "__main__":
    main()
