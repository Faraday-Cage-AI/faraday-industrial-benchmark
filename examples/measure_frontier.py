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
    parser.add_argument(
        "--adapter", type=Path, default=Path(__file__).with_name("openai_responses_agent.py")
    )
    parser.add_argument("--response-output-limit", type=int, default=32768)
    parser.add_argument("--total-output-limit", type=int, default=100000)
    parser.add_argument("--episode-timeout", type=int, default=1800)
    parser.add_argument(
        "--stop-on-agent-error",
        action="store_true",
        help="Stop scheduling further cases for a model after an agent execution error; preserve the failed report.",
    )
    parser.add_argument(
        "--family", default=None, help="Optional family filter; explicit manifests run all families"
    )
    args = parser.parse_args()
    if not 1 <= args.response_output_limit <= 128000:
        parser.error("response output limit must be between 1 and 128000")
    if args.total_output_limit <= args.response_output_limit or args.episode_timeout <= 0:
        parser.error("total output must exceed response limit; timeout must be positive")
    cancelled = Event()
    for event_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event_signal, lambda *_: cancelled.set())
    key = dotenv_values(args.env_file).get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Configured platform file has no OpenAI key")
    os.environ["OPENAI_API_KEY"] = key
    family = args.family or ("contingent_network_recovery" if args.tasks == DEFAULT_TASKS else None)
    tasks = [t for t in load_tasks(args.tasks) if family is None or t.family == family]
    tasks = tasks[args.start : args.start + args.count]
    if not tasks:
        raise SystemExit("No tasks selected")
    args.output.mkdir(parents=True, exist_ok=True)
    adapter = args.adapter.resolve()
    source_root = Path(__file__).resolve().parents[1]
    source_hashes = {
        str(path.relative_to(source_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((source_root / "src/faraday_industrial_benchmark").glob("*.py"))
    }
    frozen = {
        "task_ids": [t.id for t in tasks],
        "models": ["gpt-5.4", "gpt-5.5"],
        "tasks_sha256": hashlib.sha256(args.tasks.read_bytes()).hexdigest()
        if args.tasks.is_file()
        else None,
        "source_hashes": source_hashes,
        "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
        "adapter_path": str(adapter.relative_to(source_root)),
        "measurement_settings": {
            "reasoning_effort": "xhigh",
            "per_response_output_limit": args.response_output_limit,
            "total_output_limit": args.total_output_limit,
            "timeout_seconds": args.episode_timeout,
        },
    }
    with (args.output / "frozen-manifest.json").open("x") as handle:
        json.dump(frozen, handle, indent=2)

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
                    str(args.response_output_limit),
                    "--max-total-output-tokens",
                    str(args.total_output_limit),
                    "--usage-log",
                    str(usage_path),
                ]
            )
            started = time.monotonic()
            report = BenchmarkRunner().run_suite(
                [task],
                CommandAgent(
                    command,
                    timeout_seconds=args.episode_timeout,
                    name=f"{model}/xhigh/tool-only",
                    cancel_event=cancelled,
                ),
            )
            report["measurement"] = {
                "interrupted": cancelled.is_set(),
                "wall_seconds": time.monotonic() - started,
                "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
                "reasoning_effort": "xhigh",
                "per_response_output_limit": args.response_output_limit,
                "total_output_limit": args.total_output_limit,
                "timeout_seconds": args.episode_timeout,
                "track": "public development, tool-only; no code interpreter",
                "attempt": 1,
            }
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                json.dumps({"model": model, "task": task.id, "summary": report["summary"]}),
                flush=True,
            )
            if args.stop_on_agent_error and any(
                violation.get("code") == "agent_error"
                for episode in report["results"]
                for violation in episode["score"].get("violations", [])
            ):
                print(
                    json.dumps(
                        {"model": model, "scheduling_stopped": "agent_error", "task": task.id}
                    ),
                    flush=True,
                )
                return

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(evaluate, ("gpt-5.4", "gpt-5.5")))


if __name__ == "__main__":
    main()
