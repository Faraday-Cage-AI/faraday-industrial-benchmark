"""Reproducible structural difficulty diagnostics for the public suite."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from .agents import OracleAgent
from .models import IncidentTask, Json
from .platform_harness import BENCHMARK_VERSION
from .runner import BenchmarkRunner
from .scenarios import build_scenario
from .tool_specs import tool_specs_for_family


def _workflow_depth(task: IncidentTask) -> int:
    depths: dict[str, int] = {}
    for stage in task.public_workflow_stages:
        dependencies = stage["depends_on"]
        depths[stage["id"]] = 1 + max(
            (depths[dependency] for dependency in dependencies), default=0
        )
    return max(depths.values(), default=0)


def build_difficulty_profile(tasks: Iterable[IncidentTask]) -> Json:
    """Measure workload structure without pretending it is a model baseline."""

    task_list = list(tasks)
    runner = BenchmarkRunner()
    rows = []
    for task in task_list:
        instance = build_scenario(task)
        oracle = runner.run_task(task, OracleAgent())
        dimensions = Counter(str(criterion["dimension"]) for criterion in instance.criteria)
        checks = Counter(str(criterion["check"]) for criterion in instance.criteria)
        case_files = instance.state.get("case_files", {})
        source_sections = sum(
            len(case_file.get("sections", {})) for case_file in case_files.values()
        )
        changing_source_files = len(
            {
                event.payload.get("file_id")
                for event in instance.events
                if event.kind == "case_file_update"
            }
        )
        operating_truth = instance.state.get("operating_review_truth", {})
        required_artifacts = max(
            (len(truth.get("required_types", [])) for truth in operating_truth.values()),
            default=0,
        )
        required_exceptions = max(
            (len(truth.get("exception_rows", [])) for truth in operating_truth.values()),
            default=0,
        )
        rows.append(
            {
                "task_id": task.id,
                "family": task.family,
                "difficulty": task.difficulty,
                "systems": len(task.systems),
                "available_tools": len(tool_specs_for_family(task.family)),
                "workflow_stages": len(task.public_workflow_stages),
                "workflow_depth": _workflow_depth(task),
                "max_tool_calls": task.max_tool_calls,
                "horizon_minutes": task.horizon_minutes,
                "scheduled_events": len(instance.events),
                "event_types": sorted({event.kind for event in instance.events}),
                "criteria": len(instance.criteria),
                "criteria_by_dimension": dict(sorted(dimensions.items())),
                "criteria_by_check": dict(sorted(checks.items())),
                "source_files": len(case_files),
                "source_sections": source_sections,
                "changing_source_files": changing_source_files,
                "required_artifacts": required_artifacts,
                "artifact_leaf_checks": checks["artifact_value"],
                "required_exception_resolutions": required_exceptions,
                "oracle": {
                    "score": oracle.score.score,
                    "strict_success": oracle.score.strict_success,
                    "tool_calls": oracle.score.tool_calls,
                    "tool_call_headroom": task.max_tool_calls - oracle.score.tool_calls,
                    "elapsed_minutes": oracle.score.elapsed_minutes,
                },
            }
        )

    all_frontier = [row for row in rows if row["difficulty"] == "frontier"]
    # Document-reconciliation and optimization workloads have different shapes.
    # Never inflate rubric counts just to label a decision problem frontier.
    frontier = [row for row in all_frontier if row["family"] == "integrated_operating_review"]
    contingent = [row for row in all_frontier if row["family"] == "contingent_network_recovery"]
    frontier_gates = {
        "at_least_400_criteria_each": bool(frontier)
        and all(row["criteria"] >= 400 for row in frontier),
        "at_least_10_source_files_each": bool(frontier)
        and all(row["source_files"] >= 10 for row in frontier),
        "at_least_4_dynamic_source_revisions_each": bool(frontier)
        and all(row["changing_source_files"] >= 4 for row in frontier),
        "at_least_4_artifacts_each": bool(frontier)
        and all(row["required_artifacts"] >= 4 for row in frontier),
        "at_least_12_exception_resolutions_each": bool(frontier)
        and all(row["required_exception_resolutions"] >= 12 for row in frontier),
        "at_least_15_workflow_stages_each": bool(frontier)
        and all(row["workflow_stages"] >= 15 for row in frontier),
        "oracle_strict_success_each": bool(frontier)
        and all(row["oracle"]["strict_success"] for row in frontier),
    }
    return {
        "schema_version": "faraday-industrial-difficulty-profile/1",
        "benchmark_version": BENCHMARK_VERSION,
        "interpretation": (
            "Structural workload diagnostics and oracle solvability evidence; "
            "not a substitute for measured model results."
        ),
        "summary": {
            "tasks": len(rows),
            "families": len({row["family"] for row in rows}),
            "frontier_tasks": len(all_frontier),
            "total_criteria": sum(row["criteria"] for row in rows),
            "max_criteria_per_task": max((row["criteria"] for row in rows), default=0),
            "max_workflow_stages": max((row["workflow_stages"] for row in rows), default=0),
            "max_oracle_tool_calls": max((row["oracle"]["tool_calls"] for row in rows), default=0),
            "frontier_gates_passed": all(frontier_gates.values()),
        },
        "frontier_gates": frontier_gates,
        "contingent_optimization": {
            "tasks": len(contingent),
            "oracle_strict_success_each": all(row["oracle"]["strict_success"] for row in contingent),
            "reservation_portfolios": 9,
            "disruption_branches": 4,
            "whole_orders_per_branch": 10,
            "unconstrained_assignments_per_branch": 4 ** 10,
            "strict_cost_regret_tolerance": 0.02,
            "note": "Search-space size is not measured model difficulty; efficient solvers can prune it.",
        },
        "tasks": rows,
    }


def save_difficulty_profile(profile: Json, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
