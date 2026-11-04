"""Portable Faraday-Platform harness contracts.

The export intentionally contains no scenario seeds, evaluator criteria, event
queues, economic truth, or oracle traces. It is safe to load into an agent
platform while the executable benchmark remains the scoring authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import extensions
from .models import IncidentTask, Json
from .tool_specs import FAMILY_TOOL_NAMES, TOOL_SPECS, tool_specs_for_family

SCHEMA_VERSION = "faraday-platform-harness/1"
BENCHMARK_VERSION = "0.8.0"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_platform_harness_contract(tasks: list[IncidentTask]) -> Json:
    """Build a seed-free suite contract for Faraday-Platform."""

    if not tasks:
        raise ValueError("at least one benchmark task is required")
    public_tasks = [task.public_dict() for task in tasks]
    stages_by_id = {task.id: task.workflow_stage_dicts() for task in tasks}
    task_ids = [task["id"] for task in public_tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("benchmark task IDs must be unique")
    families = sorted({task["family"] for task in public_tasks})
    extensions.load()
    tool_contract = {
        "tool_specs": TOOL_SPECS,
        "family_tool_names": {
            family: sorted(names) for family, names in sorted(FAMILY_TOOL_NAMES.items())
        },
    }
    if extensions.FAMILIES:
        # Extension families scope the approval enum per family, so commit to
        # each family's full served tool list, not just the shared specs.
        tool_contract["extension_family_tool_specs"] = {
            family: tool_specs_for_family(family) for family in sorted(extensions.FAMILIES)
        }
    tool_contract_sha256 = _canonical_hash(tool_contract)
    suite_digest = _canonical_hash(
        {"public_tasks": public_tasks, "tool_contract_sha256": tool_contract_sha256}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": {
            "id": "faraday-industrial-benchmark",
            "version": BENCHMARK_VERSION,
            "track": "faraday-native",
            "runner_protocol": "faraday-industrial-jsonl/1",
            "evaluation_method": "executable_state_trace",
        },
        "suite": {
            "task_count": len(public_tasks),
            "family_count": len(families),
            "families": families,
            "task_ids": task_ids,
            "tool_count": len(TOOL_SPECS) + len(extensions.TOOLS),
            "public_tool_contract_sha256": tool_contract_sha256,
            "public_contract_sha256": suite_digest,
        },
        "cases": [
            {
                "id": task["id"],
                "name": task["title"],
                "input": task["prompt"],
                "expected": (
                    "Complete the executable workflow with correct state, exact evidence, "
                    "safe side effects, required authorization, and an auditable finish."
                ),
                "source": "faraday-industrial-benchmark",
                "metadata": {
                    "benchmark_version": BENCHMARK_VERSION,
                    "task_version": task["version"],
                    "family": task["family"],
                    "difficulty": task["difficulty"],
                    "systems": task["systems"],
                    "tags": task["tags"],
                    "controlled_plan_actions": task["controlled_plan_actions"],
                    "workflow_stages": stages_by_id[task["id"]],
                    "required_notification_roles": task["required_notification_roles"],
                    "available_tools": [
                        spec["name"] for spec in tool_specs_for_family(task["family"])
                    ],
                    "max_tool_calls": task["max_tool_calls"],
                    "horizon_minutes": task["horizon_minutes"],
                },
            }
            for task in public_tasks
        ],
        "rubric": {
            "objective": (
                "Maximize strict executable success across industrial workflows without "
                "critical authorization failures."
            ),
            "scoring_authority": "faraday-industrial-benchmark deterministic grader",
            "dimensions": [
                "investigation",
                "accuracy",
                "planning",
                "governance",
                "orchestration",
                "containment",
                "communication",
                "adaptation",
                "grounding",
                "artifact_accuracy",
                "artifact_consistency",
                "exception_handling",
                "economics",
                "efficiency",
            ],
            "promotion_rule": {
                "primary": "candidate_total_loss < incumbent_total_loss",
                "safety": "candidate_critical_failure_rate <= incumbent_critical_failure_rate",
                "full_release": "zero critical failures and improved held-out strict success",
            },
        },
        "config": {
            "runner": "faraday-industrial-benchmark",
            "synthetic": True,
            "seed_visibility": "evaluator_only",
            "grader_visibility": "evaluator_only",
            "attempt_policy": "one_declared_attempt_per_task",
            "optimization_loop": "baseline_run_mutate_fresh_run_conditional_promotion",
            "training_separation": (
                "Public development tasks may guide policy development; promotion must use a "
                "separately generated held-out manifest with a pre-published seed commitment."
            ),
        },
    }


def save_platform_harness_contract(contract: Json, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination
