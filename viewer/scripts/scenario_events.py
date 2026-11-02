"""Print an episode's scheduled events as JSON, either generated or replayed from a run.

Usage:
  scenario_events.py <tasks.json> <task-id> [<task-version>]
  scenario_events.py <tasks.json> <task-id> [<task-version>] --replay <run.json>

The viewer runs this on demand because events only exist in the scenario code;
task files don't record them, and run files record only the IDs of applied events.

Without --replay, prints the task's public fields and the events its scenario
schedules up front. With --replay, replays the run's tool calls for that episode
and prints when each event fired, including events that tool calls scheduled.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

REPO = Path(os.environ.get("FARADAY_REPO") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(REPO / "src"))

from faraday_industrial_benchmark.models import IncidentTask, Json, ScheduledEvent, load_tasks  # noqa: E402
from faraday_industrial_benchmark.runner import BudgetedToolClient  # noqa: E402
from faraday_industrial_benchmark.scenarios import build_scenario  # noqa: E402
from faraday_industrial_benchmark.world import IndustrialWorld  # noqa: E402


class NotFound(Exception):
    pass


def matches(task_id: str, version: str | None, candidate_id: str, candidate_version: str) -> bool:
    return candidate_id == task_id and (version is None or candidate_version == version)


def find_task(manifest: Path, task_id: str, version: str | None) -> IncidentTask:
    for task in load_tasks(manifest):
        if matches(task_id, version, task.id, task.version):
            return task
    raise NotFound(f"task {task_id} (version {version or 'any'}) not found in {manifest}")


def find_trace(run_file: Path, task: IncidentTask) -> list[Json]:
    run = json.loads(run_file.read_text(encoding="utf-8"))
    for result in run.get("results", []):
        if matches(task.id, task.version, result["task"]["id"], result["task"]["version"]):
            return result["trace"]
    raise NotFound(f"{run_file} has no episode {task.id} (version {task.version})")


def scheduled(task: IncidentTask) -> Json:
    events = sorted(build_scenario(task).events, key=lambda event: (event.at_minute, event.id))
    return {
        "task": {**task.public_dict(), "workflow_stages": task.workflow_stage_dicts()},
        "events": [asdict(event) for event in events],
    }


def replay(task: IncidentTask, trace: list[Json]) -> Json:
    """Replays tool calls the way `BenchmarkRunner.replay` does, recording event timing."""

    world = IndustrialWorld(task)
    client = BudgetedToolClient(world)
    events: dict[str, ScheduledEvent] = {event.id: event for event in world.pending_events}
    scheduled_by: dict[str, int | None] = {event.id: None for event in world.pending_events}
    position: int | None = None
    schedule = world.schedule_event

    def track(event: ScheduledEvent) -> None:
        events.setdefault(event.id, event)
        scheduled_by.setdefault(event.id, position)
        schedule(event)

    # Tool handlers call self.schedule_event, which finds this instance attribute first.
    world.schedule_event = track  # type: ignore[method-assign]

    fired: list[tuple[str, int]] = []
    first_result_mismatch = None
    for position, call in enumerate(trace):
        before = len(world.applied_events)
        result = client.call(call["tool"], **call.get("arguments", {}))
        # Run files hold JSON, so compare the JSON form.
        if first_result_mismatch is None and json.loads(json.dumps(result)) != call.get("result"):
            first_result_mismatch = position
        fired.extend((event_id, position) for event_id in world.applied_events[before:])

    def entry(event_id: str, fired_during: int | None) -> Json:
        return {
            "event": asdict(events[event_id]),
            "fired_during": fired_during,
            "scheduled_by": scheduled_by[event_id],
        }

    return {
        "events": [entry(event_id, during) for event_id, during in fired]
        + [entry(event.id, None) for event in world.pending_events],
        "applied_events": list(world.applied_events),
        "first_result_mismatch": first_result_mismatch,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print an episode's scheduled events as JSON.")
    parser.add_argument("tasks", type=Path, help="task file, such as data/public/tasks.json")
    parser.add_argument("task_id")
    parser.add_argument("version", nargs="?", help="task version; any version when omitted")
    parser.add_argument("--replay", type=Path, metavar="RUN", help="run file to replay the episode from")
    args = parser.parse_args(argv)
    try:
        task = find_task(args.tasks, args.task_id, args.version)
        payload = replay(task, find_trace(args.replay, task)) if args.replay else scheduled(task)
    except NotFound as error:
        print(error, file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, separators=(",", ":"), default=list)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
