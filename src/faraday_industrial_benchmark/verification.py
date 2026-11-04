"""Verify saved results and their aggregates against authoritative replay."""

from . import __version__
from .provenance import input_fingerprints
from .runner import BenchmarkRunner, summarize_results


def verify_run(payload, tasks, selected_ids=None):
    task_map = {task.id: task for task in tasks}
    selected = set(selected_ids or ())
    results = payload["results"]
    ids = [row["task"]["id"] for row in results]
    if selected - set(ids):
        raise ValueError(f"task IDs absent from saved run: {sorted(selected - set(ids))}")
    reports = []
    reconstructed = []
    runner = BenchmarkRunner()
    for result in results:
        task_id = result["task"]["id"]
        if task_id not in task_map:
            raise ValueError(f"saved task {task_id!r} absent from supplied manifest")
        if selected and task_id not in selected:
            reconstructed.append(result)
            continue
        task = task_map[task_id]
        report = runner.replay(task, result["trace"])
        saved_task = dict(result["task"])
        saved_task.pop("workflow_stages", None)
        comparisons = {
            "task_contract_matches": saved_task == task.public_dict(),
            "agent_matches": result.get("agent") == payload.get("agent"),
            **{
                f"{key}_matches": result.get(key) == report[key]
                for key in ("score", "initial_state_hash", "final_state_hash", "final_answer")
            },
            "applied_events_match": result.get("applied_events") == report["applied_events"],
        }
        report.update(comparisons)
        report["exact_match"] = report["exact_match"] and all(comparisons.values())
        reports.append(report)
        reconstructed.append({**result, "task": task.public_dict(), "score": report["score"]})
    authoritative = summarize_results(reconstructed)
    checks = {
        f"{key}_matches": payload.get(key) == value for key, value in authoritative.items()
    }
    checks["nonempty_unique_coverage"] = bool(ids) and len(ids) == len(set(ids))
    checks["engine_version_matches"] = payload.get("benchmark_version") == __version__
    provenance = payload.get("provenance")
    if provenance is not None:
        checks["provenance_inputs_match"] = provenance.get("inputs") == input_fingerprints(
            [task_map[task_id] for task_id in ids]
        )
        checks["provenance_agent_matches"] = provenance.get("agent", {}).get("name") == payload.get("agent")
        checks["provenance_engine_matches"] = provenance.get("engine_version") == __version__
    elif payload.get("benchmark_version") == "0.8.0":
        checks["provenance_present"] = False
    return {
        "exact_match": bool(reports) and all(checks.values()) and all(
            row["exact_match"] for row in reports
        ),
        "verification_scope": "selected episodes" if selected else "all saved episodes",
        "covers_supplied_manifest": len(ids) == len(task_map) and set(ids) == set(task_map),
        "checks": checks,
        "episodes": reports,
    }
