"""Benchmark execution, external-agent protocol, aggregation, and replay."""

from __future__ import annotations

import json
import os
import selectors
import shlex
import statistics
import subprocess
import time
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .grader import grade_episode
from .models import Agent, EpisodeResult, IncidentTask, Json, ToolClientProtocol
from .world import IndustrialWorld, ToolClient


def _record_agent_error(world: IndustrialWorld, message: str) -> Json:
    """Persist a runner failure as evaluator evidence, never an exposed tool."""
    world._violation("agent_error", message, critical=False)  # noqa: SLF001
    return world._record(  # noqa: SLF001
        "_agent_error", {"message": message}, {"ok": False, "error": "agent_error"}
    )


class BudgetedToolClient:
    """Enforce the task tool-call budget for in-process agents."""

    def __init__(self, world: IndustrialWorld):
        self.world = world
        self.client = ToolClient(world)

    @property
    def tools(self) -> list[Json]:
        return self.client.tools

    def call(self, name: str, **arguments: Any) -> Json:
        return self.call_raw(name, arguments)

    def call_raw(self, name: str, arguments: Any) -> Json:
        if len(self.world.trace) >= self.world.task.max_tool_calls and name != "finish":
            self.world._violation(  # noqa: SLF001 - benchmark-enforced boundary
                "tool_budget_exceeded",
                f"agent exceeded {self.world.task.max_tool_calls} tool calls",
                critical=False,
            )
            self.world.finished = True
            result = {
                "ok": False,
                "error": "tool_budget_exceeded",
                "clock_minute": self.world.minute,
            }
            return self.world._record(name, arguments, result)  # noqa: SLF001
        return self.client.call_raw(name, arguments)


class CommandAgent:
    """Run any agent through the newline-delimited JSON protocol.

    The subprocess receives a `start` object. It may emit `tool_call` objects
    and receives matching `tool_result` objects until it emits `final`.
    """

    def __init__(self, command: str, *, timeout_seconds: float = 120.0, name: str | None = None, cancel_event=None):
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.name = name or f"command:{command}"
        self.cancel_event = cancel_event

    def run(self, task: IncidentTask, tools: ToolClientProtocol) -> Json:
        process = subprocess.Popen(
            shlex.split(self.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        writer = selectors.DefaultSelector()
        writer.register(process.stdin, selectors.EVENT_WRITE)
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stdin.fileno(), False)
        start = {
            "type": "start",
            "protocol": "faraday-industrial-jsonl/1",
            "task": task.public_dict(),
            "tools": deepcopy(tools.tools),
        }
        deadline = time.monotonic() + self.timeout_seconds
        final: Json = {}
        finished_by_tool = False

        def check_deadline() -> None:
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise InterruptedError("evaluation cancelled by operator")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"agent command exceeded {self.timeout_seconds:g}s")

        def send(message: Json) -> None:
            data = memoryview((json.dumps(message, separators=(",", ":")) + "\n").encode())
            while data:
                check_deadline()
                if not writer.select(timeout=min(0.1, max(0.0, deadline - time.monotonic()))):
                    continue
                try:
                    written = os.write(process.stdin.fileno(), data)
                except BlockingIOError:
                    continue
                data = data[written:]

        pending = bytearray()
        try:
            send(start)
            while time.monotonic() < deadline:
                check_deadline()
                if b"\n" not in pending:
                    ready = selector.select(timeout=min(0.1, max(0.0, deadline - time.monotonic())))
                    if not ready:
                        if process.poll() is not None:
                            break
                        continue
                    try:
                        chunk = os.read(process.stdout.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        break
                    pending.extend(chunk)
                    if len(pending) > 1024 * 1024:
                        raise RuntimeError("agent JSONL message exceeded 1 MiB")
                    if b"\n" not in pending:
                        continue
                line, _, remainder = pending.partition(b"\n")
                pending = bytearray(remainder)
                try:
                    message = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise RuntimeError(f"agent emitted invalid JSONL: {line.rstrip()}") from exc
                if not isinstance(message, dict):
                    raise RuntimeError("agent JSONL message must be an object")
                message_type = message.get("type")
                if message_type == "tool_call":
                    call_id = str(message.get("id", ""))
                    name = str(message.get("name", ""))
                    arguments = message.get("arguments", {})
                    if isinstance(arguments, dict):
                        result = tools.call(name, **arguments)
                    else:
                        result = tools.call_raw(name, arguments)
                    if name == "finish" and result.get("ok") is True:
                        finished_by_tool = True
                    send({"type": "tool_result", "id": call_id, "name": name, "result": result})
                elif message_type == "final":
                    summary = str(message.get("summary", ""))
                    evidence = message.get("evidence", [])
                    if not isinstance(evidence, list):
                        evidence = []
                    final = {"summary": summary, "evidence": [str(item) for item in evidence]}
                    if not finished_by_tool:
                        tools.call("finish", **final)
                    return final
                else:
                    raise RuntimeError(f"unsupported agent message type: {message_type!r}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"agent command exceeded {self.timeout_seconds:g}s")
            if process.poll() is None:
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("agent closed protocol output before final response") from None
            raise RuntimeError(f"agent exited before final response (code={process.returncode})")
        finally:
            selector.close()
            writer.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()


def summarize_results(results: list[Json]) -> Json:
    """Recompute all suite aggregates from authoritative serialized episodes."""
    scores = [result["score"]["score"] for result in results]
    strict = sum(result["score"]["strict_success"] for result in results)
    critical = sum(result["score"]["critical_failure"] for result in results)
    estimated_cost = sum(result["score"]["estimated_cost"] for result in results)
    unmitigated_cost = sum(result["score"]["unmitigated_cost"] for result in results)
    by_family: dict[str, list[Json]] = defaultdict(list)
    for result in results:
        by_family[result["task"]["family"]].append(result)
    family_summaries = {}
    for family, family_results in sorted(by_family.items()):
        family_scores = [result["score"]["score"] for result in family_results]
        family_summaries[family] = {
            "tasks": len(family_results),
            "mean_score": round(sum(family_scores) / len(family_scores), 2),
            "strict_successes": sum(result["score"]["strict_success"] for result in family_results),
            "critical_failures": sum(result["score"]["critical_failure"] for result in family_results),
            "tool_calls": sum(result["score"]["tool_calls"] for result in family_results),
        }
    dimension_rows: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for result in results:
        for dimension, values in result["score"]["dimensions"].items():
            dimension_rows[dimension].append((values["score"], values["max_score"]))
    capability_summaries = {}
    for dimension, values in sorted(dimension_rows.items()):
        total_score = sum(score for score, _ in values)
        total_max = sum(max_score for _, max_score in values)
        capability_summaries[dimension] = {
            "tasks": len(values),
            "mean_score": round(total_score / len(values), 4),
            "mean_max_score": round(total_max / len(values), 4),
            "attainment_rate": round(total_score / total_max, 4) if total_max else 0.0,
        }
    return {
        "summary": {
            "tasks": len(results),
            "families": len(family_summaries),
            "mean_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "min_score": round(min(scores), 2) if scores else 0.0,
            "max_score": round(max(scores), 2) if scores else 0.0,
            "strict_successes": strict,
            "strict_success_rate": round(strict / len(results), 4) if results else 0.0,
            "critical_failures": critical,
            "estimated_cost": round(estimated_cost, 2),
            "unmitigated_cost": round(unmitigated_cost, 2),
            "estimated_cost_avoided": round(unmitigated_cost - estimated_cost, 2),
            "tool_calls": sum(result["score"]["tool_calls"] for result in results),
        },
        "family_summaries": family_summaries,
        "capability_summaries": capability_summaries,
    }


class BenchmarkRunner:
    def run_task(self, task: IncidentTask, agent: Agent) -> EpisodeResult:
        world = IndustrialWorld(task)
        client = BudgetedToolClient(world)
        try:
            returned = agent.run(task, client)
            if not world.finished:
                summary = str(returned.get("summary", "Agent returned without calling finish."))
                evidence = returned.get("evidence", [])
                if not isinstance(evidence, list):
                    evidence = []
                world.call_tool("finish", {"summary": summary, "evidence": evidence})
        except Exception as exc:  # benchmark records crashes as episode failures
            _record_agent_error(world, f"{type(exc).__name__}: {exc}")
            if not world.finished:
                world.call_tool(
                    "finish",
                    {"summary": "Agent execution failed.", "evidence": []},
                )
        score = grade_episode(world)
        return EpisodeResult(
            task=task,
            agent=agent.name,
            score=score,
            final_answer=deepcopy(world.final_answer),
            trace=deepcopy(world.trace),
            initial_state_hash=world.initial_state_hash,
            final_state_hash=world.state_hash,
            applied_events=list(world.applied_events),
        )

    def run_suite(self, tasks: Iterable[IncidentTask], agent: Agent) -> Json:
        from .provenance import build_run_provenance

        task_list = list(tasks)
        results = [self.run_task(task, agent) for task in task_list]
        return {
            "schema_version": "faraday-industrial-run/3",
            "benchmark_version": "0.8.0",
            "agent": agent.name,
            "provenance": build_run_provenance(task_list, agent),
            **summarize_results([result.to_dict() for result in results]),
            "results": [result.to_dict() for result in results],
        }

    def run_stability(
        self, tasks: Iterable[IncidentTask], agent: Agent, *, attempts: int = 5
    ) -> Json:
        """Measure repeatability instead of allowing one lucky successful run."""

        from .provenance import build_run_provenance

        if attempts < 2:
            raise ValueError("stability evaluation requires at least two attempts")
        task_list = list(tasks)
        rows = []
        all_scores: list[float] = []
        total_strict = 0
        total_critical = 0
        for task in task_list:
            task_results = [self.run_task(task, agent) for _ in range(attempts)]
            scores = [result.score.score for result in task_results]
            strict = sum(result.score.strict_success for result in task_results)
            critical = sum(result.score.critical_failure for result in task_results)
            all_scores.extend(scores)
            total_strict += strict
            total_critical += critical
            rows.append(
                {
                    "task_id": task.id,
                    "scores": scores,
                    "mean_score": round(sum(scores) / attempts, 2),
                    "score_stddev": round(statistics.pstdev(scores), 4),
                    "strict_successes": strict,
                    "critical_failures": critical,
                    "any_attempt_strict": strict > 0,
                    "all_attempts_strict": strict == attempts,
                }
            )
        runs = len(all_scores)
        return {
            "schema_version": "faraday-industrial-stability/1",
            "benchmark_version": "0.8.0",
            "agent": agent.name,
            "attempts": attempts,
            "provenance": {
                **build_run_provenance(task_list, agent),
                "attempt_policy": f"{attempts} attempts per task, all included; not best-of selection",
            },
            "summary": {
                "tasks": len(task_list),
                "runs": runs,
                "mean_score": round(sum(all_scores) / runs, 2) if runs else 0.0,
                "score_stddev": round(statistics.pstdev(all_scores), 4) if all_scores else 0.0,
                "strict_run_rate": round(total_strict / runs, 4) if runs else 0.0,
                "any_attempt_strict_rate": round(
                    sum(row["any_attempt_strict"] for row in rows) / len(rows), 4
                ) if rows else 0.0,
                "all_attempts_strict_rate": round(
                    sum(row["all_attempts_strict"] for row in rows) / len(rows), 4
                ) if rows else 0.0,
                "critical_failure_rate": round(total_critical / runs, 4) if runs else 0.0,
            },
            "results": rows,
        }

    def replay(self, task: IncidentTask, trace: list[Json]) -> Json:
        """Replay tool calls and return authoritative state and score evidence."""

        world = IndustrialWorld(task)
        client = BudgetedToolClient(world)
        mismatches: list[Json] = []
        for index, expected in enumerate(trace):
            if (
                expected["tool"] == "_agent_error"
                and expected.get("result") == {"ok": False, "error": "agent_error"}
            ):
                actual_result = _record_agent_error(world, expected["arguments"]["message"])
            else:
                actual_result = client.call_raw(expected["tool"], expected.get("arguments", {}))
            actual_hash = world.trace[-1].state_hash
            actual_record = asdict(world.trace[-1])
            record_matches = actual_record == expected
            if not record_matches:
                mismatches.append(
                    {
                        "index": index,
                        "tool": expected["tool"],
                        "result_matches": actual_result == expected.get("result"),
                        "state_hash_matches": actual_hash == expected.get("state_hash"),
                        "record_matches": record_matches,
                        "expected_state_hash": expected.get("state_hash"),
                        "actual_state_hash": actual_hash,
                    }
                )
        score = grade_episode(world)
        return {
            "task_id": task.id,
            "calls_replayed": len(trace),
            "exact_match": not mismatches,
            "mismatches": mismatches,
            "initial_state_hash": world.initial_state_hash,
            "final_state_hash": world.state_hash,
            "final_answer": deepcopy(world.final_answer),
            "applied_events": list(world.applied_events),
            "score": score.to_dict(),
        }


def save_run(run: Json, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
