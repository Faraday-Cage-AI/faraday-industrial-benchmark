"""Verify a saved native submission against sealed case expectations, no model API."""

import argparse
import json
from pathlib import Path

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.native_review import verify_native
from faraday_industrial_benchmark.runner import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--episode",
        required=True,
        help="Original episode JSON; tool actions are replayed and regraded",
    )
    parser.add_argument("--tasks", default="data/professional/tasks.json")
    args = parser.parse_args()
    try:
        task = next(t for t in load_tasks(args.tasks) if t.id == args.task)
        result = verify_native(task, args.workbook, args.report)
        episode_path = Path(args.episode)
        if episode_path.stat().st_size > 20_000_000:
            raise ValueError("episode too large")
        episode = json.loads(episode_path.read_text())
        if episode["task"]["id"] != task.id or len(episode["trace"]) > task.max_tool_calls + 2:
            raise ValueError("episode identity or call budget mismatch")
        replay = BenchmarkRunner().replay(task, episode["trace"])
        result["workflow_replay_exact"] = replay["exact_match"]
        result["workflow_strict_success"] = replay["score"]["strict_success"]
        result["strict_success"] = bool(
            result["strict_success"] and replay["exact_match"] and replay["score"]["strict_success"]
        )
    except Exception as exc:  # noqa: BLE001 -- malformed untrusted submissions must fail closed
        result = {"task": args.task, "strict_success": False, "error": type(exc).__name__}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["strict_success"] else 1)


if __name__ == "__main__":
    main()
