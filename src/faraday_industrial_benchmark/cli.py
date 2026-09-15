"""Command-line interface for running and auditing Faraday Industrial Benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .agents import BUILTIN_AGENTS
from .difficulty import build_difficulty_profile, save_difficulty_profile
from .generation import generate_tasks, generation_commitment, save_task_manifest
from .models import IncidentTask, load_tasks
from .platform_harness import build_platform_harness_contract, save_platform_harness_contract
from .report import render_html
from .runner import BenchmarkRunner, CommandAgent, save_run
from .scenarios import BUILDERS, build_scenario
from .upstreams import DEFAULT_MANIFEST, load_upstream_manifest, verify_upstream_snapshots
from .world import IndustrialWorld


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_TASKS = PROJECT_ROOT / "data" / "public"
INSTALLED_TASKS = Path(sys.prefix) / "share" / "faraday-industrial-benchmark" / "tasks.json"
DEFAULT_TASKS = SOURCE_TASKS if SOURCE_TASKS.exists() else INSTALLED_TASKS


def _load_selected(path: str | Path, task_ids: list[str] | None = None) -> list[IncidentTask]:
    tasks = load_tasks(path)
    if task_ids:
        wanted = set(task_ids)
        tasks = [task for task in tasks if task.id in wanted]
        missing = wanted - {task.id for task in tasks}
        if missing:
            raise ValueError(f"unknown task IDs: {', '.join(sorted(missing))}")
    return tasks


def _validate(tasks: list[IncidentTask]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            errors.append(f"{task.id}: duplicate task ID")
        seen.add(task.id)
        if task.family not in BUILDERS:
            errors.append(f"{task.id}: unknown family {task.family!r}")
            continue
        if task.max_tool_calls < 10:
            errors.append(f"{task.id}: max_tool_calls must be at least 10")
        if task.horizon_minutes < 30:
            errors.append(f"{task.id}: horizon_minutes must be at least 30")
        if not task.prompt.strip():
            errors.append(f"{task.id}: prompt is empty")
        try:
            first = build_scenario(task)
            second = build_scenario(task)
            if first.state != second.state or first.events != second.events:
                errors.append(f"{task.id}: procedural generation is not deterministic")
            if not first.criteria:
                errors.append(f"{task.id}: evaluator contract has no criteria")
            IndustrialWorld(task)
        except Exception as exc:
            errors.append(f"{task.id}: build failed: {type(exc).__name__}: {exc}")
    return errors


def _agent_from_args(args: argparse.Namespace):
    if args.agent_command:
        return CommandAgent(args.agent_command, timeout_seconds=args.timeout, name=args.agent_name)
    return BUILTIN_AGENTS[args.agent]()


def cmd_list(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks)
    for task in tasks:
        systems = ",".join(task.systems)
        print(f"{task.id}\t{task.family}\t{task.difficulty}\t{systems}\t{task.title}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks)
    errors = _validate(tasks)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(tasks)} tasks across {len({task.family for task in tasks})} families.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks, args.task)
    agent = _agent_from_args(args)
    run = BenchmarkRunner().run_suite(tasks, agent)
    output = save_run(run, args.output)
    html_path = None
    if args.html:
        html_path = render_html(run, args.html)
    summary = run["summary"]
    print(
        f"{run['agent']}: mean={summary['mean_score']:.2f} "
        f"strict={summary['strict_successes']}/{summary['tasks']} "
        f"critical={summary['critical_failures']} calls={summary['tool_calls']}"
    )
    print(f"JSON: {output}")
    if html_path:
        print(f"HTML: {html_path}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.run).read_text(encoding="utf-8"))
    tasks = {task.id: task for task in _load_selected(args.tasks)}
    runner = BenchmarkRunner()
    reports = []
    for result in payload["results"]:
        task_id = result["task"]["id"]
        if args.task and task_id not in set(args.task):
            continue
        if task_id not in tasks:
            raise ValueError(f"task {task_id!r} is not present in {args.tasks}")
        report = runner.replay(tasks[task_id], result["trace"])
        comparisons = {
            "task_contract_matches": result.get("task") == tasks[task_id].public_dict(),
            "score_matches": result.get("score") == report["score"],
            "initial_state_hash_matches": (
                result.get("initial_state_hash") == report["initial_state_hash"]
            ),
            "final_state_hash_matches": (
                result.get("final_state_hash") == report["final_state_hash"]
            ),
            "final_answer_matches": result.get("final_answer") == report["final_answer"],
            "applied_events_match": result.get("applied_events") == report["applied_events"],
        }
        report.update(comparisons)
        report["exact_match"] = report["exact_match"] and all(comparisons.values())
        reports.append(report)
    exact = all(report["exact_match"] for report in reports)
    print(json.dumps({"exact_match": exact, "episodes": reports}, indent=2, sort_keys=True))
    return 0 if exact else 1


def cmd_report(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.run).read_text(encoding="utf-8"))
    output = render_html(payload, args.output)
    print(output)
    return 0


def cmd_qualify(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks)
    errors = _validate(tasks)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    runner = BenchmarkRunner()
    runs: dict[str, dict[str, Any]] = {}
    for name in ("oracle", "noop", "read-only", "unsafe"):
        run = runner.run_suite(tasks, BUILTIN_AGENTS[name]())
        runs[name] = run
        summary = run["summary"]
        print(
            f"{name:10s} mean={summary['mean_score']:6.2f} "
            f"strict={summary['strict_successes']:2d}/{summary['tasks']} "
            f"critical={summary['critical_failures']:2d}"
        )
    qualifications = {
        "oracle_all_strict": runs["oracle"]["summary"]["strict_successes"] == len(tasks),
        "oracle_no_critical": runs["oracle"]["summary"]["critical_failures"] == 0,
        "noop_mean_below_20": runs["noop"]["summary"]["mean_score"] < 20,
        "read_only_below_oracle": runs["read-only"]["summary"]["mean_score"] < runs["oracle"]["summary"]["mean_score"],
        "unsafe_all_zero": all(result["score"]["score"] == 0 for result in runs["unsafe"]["results"]),
        "unsafe_all_critical": runs["unsafe"]["summary"]["critical_failures"] == len(tasks),
    }
    passed = all(qualifications.values())
    report = {
        "schema_version": "faraday-industrial-qualification/1",
        "benchmark_version": "0.5.0",
        "passed": passed,
        "checks": qualifications,
        "controls": {name: run["summary"] for name, run in runs.items()},
    }
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Qualification report: {destination}")
    if not passed:
        failed = [name for name, ok in qualifications.items() if not ok]
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("Qualification passed.")
    return 0


def cmd_stability(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks, args.task)
    agent = _agent_from_args(args)
    report = BenchmarkRunner().run_stability(tasks, agent, attempts=args.attempts)
    output = save_run(report, args.output)
    summary = report["summary"]
    print(
        f"{report['agent']}: runs={summary['runs']} mean={summary['mean_score']:.2f} "
        f"strict-run-rate={summary['strict_run_rate']:.4f} "
        f"all-attempts-strict={summary['all_attempts_strict_rate']:.4f} "
        f"critical-rate={summary['critical_failure_rate']:.4f}"
    )
    print(f"Stability JSON: {output}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    templates = _load_selected(args.tasks)
    generated = generate_tasks(
        templates,
        per_family=args.per_family,
        root_seed=args.root_seed,
        split=args.split,
        version=args.version,
    )
    output = save_task_manifest(generated, args.output)
    print(f"Generated {len(generated)} tasks: {output}")
    print(f"Seed commitment: {generation_commitment(generated)}")
    return 0


def cmd_export_harness(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks, args.task)
    errors = _validate(tasks)
    if errors:
        raise ValueError("; ".join(errors))
    contract = build_platform_harness_contract(tasks)
    output = save_platform_harness_contract(contract, args.output)
    print(
        f"Exported {contract['suite']['task_count']} tasks across "
        f"{contract['suite']['family_count']} families: {output}"
    )
    print(f"Public contract SHA-256: {contract['suite']['public_contract_sha256']}")
    return 0


def cmd_difficulty(args: argparse.Namespace) -> int:
    tasks = _load_selected(args.tasks, args.task)
    errors = _validate(tasks)
    if errors:
        raise ValueError("; ".join(errors))
    profile = build_difficulty_profile(tasks)
    output = save_difficulty_profile(profile, args.output)
    summary = profile["summary"]
    print(
        f"Profiled {summary['tasks']} tasks across {summary['families']} families; "
        f"criteria={summary['total_criteria']} frontier={summary['frontier_tasks']} "
        f"gates={'PASS' if summary['frontier_gates_passed'] else 'FAIL'}"
    )
    print(f"Difficulty JSON: {output}")
    return 0 if summary["frontier_gates_passed"] else 1


def cmd_upstreams(args: argparse.Namespace) -> int:
    manifest = load_upstream_manifest(args.manifest)
    if args.verify:
        results = verify_upstream_snapshots(args.manifest, args.root)
        if args.json:
            print(
                json.dumps(
                    {"schema_version": manifest["schema_version"], "results": results}, indent=2
                )
            )
        else:
            for result in results:
                verified = result["verified"]
                state = "VERIFIED" if verified else "FAILED" if verified is False else "REFERENCE"
                print(f"{state:9s}\t{result['id']}\t{result['status']}")
                if verified is False:
                    print(f"  expected: {result.get('expected', 'snapshot missing')}")
                    print(f"  actual:   {result.get('actual', result.get('path'))}")
        return 0 if all(result["verified"] is not False for result in results) else 1

    sources = manifest["sources"]
    if args.json:
        print(json.dumps(manifest, indent=2))
    else:
        for source in sources:
            license_summary = ", ".join(
                f"{key}={value}" for key, value in source["licenses"].items()
            )
            print(f"{source['status']:14s}\t{source['id']}\t{license_summary}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="faraday-bench",
        description="Run Faraday's dynamic industrial-enterprise agent evaluation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list public tasks")
    list_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    list_parser.set_defaults(func=cmd_list)

    validate_parser = subparsers.add_parser("validate", help="validate task and scenario contracts")
    validate_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser("run", help="run a built-in or external agent")
    run_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    run_parser.add_argument("--task", action="append", help="task ID; repeat to select multiple")
    run_parser.add_argument("--agent", choices=sorted(BUILTIN_AGENTS), default="oracle")
    run_parser.add_argument("--agent-command", help="JSONL protocol subprocess command")
    run_parser.add_argument("--agent-name", help="name for an external agent submission")
    run_parser.add_argument("--timeout", type=float, default=120.0)
    run_parser.add_argument("--output", default="runs/latest.json")
    run_parser.add_argument("--html", help="optional static HTML report path")
    run_parser.set_defaults(func=cmd_run)

    replay_parser = subparsers.add_parser("replay", help="verify a saved run exactly")
    replay_parser.add_argument("run")
    replay_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    replay_parser.add_argument("--task", action="append")
    replay_parser.set_defaults(func=cmd_replay)

    report_parser = subparsers.add_parser("report", help="render an HTML report from a run")
    report_parser.add_argument("run")
    report_parser.add_argument("--output", default="runs/report.html")
    report_parser.set_defaults(func=cmd_report)

    qualify_parser = subparsers.add_parser("qualify", help="run oracle and negative controls")
    qualify_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    qualify_parser.add_argument("--output", default="reports/qualification.json")
    qualify_parser.set_defaults(func=cmd_qualify)

    stability_parser = subparsers.add_parser(
        "stability", help="measure repeatability across multiple attempts per task"
    )
    stability_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    stability_parser.add_argument("--task", action="append", help="task ID; repeat to select multiple")
    stability_parser.add_argument("--attempts", type=int, default=5)
    stability_parser.add_argument("--agent", choices=sorted(BUILTIN_AGENTS), default="oracle")
    stability_parser.add_argument("--agent-command", help="JSONL protocol subprocess command")
    stability_parser.add_argument("--agent-name", help="name for an external agent submission")
    stability_parser.add_argument("--timeout", type=float, default=120.0)
    stability_parser.add_argument("--output", default="runs/stability.json")
    stability_parser.set_defaults(func=cmd_stability)

    generate_parser = subparsers.add_parser(
        "generate", help="generate a reproducible held-out task manifest"
    )
    generate_parser.add_argument("--tasks", default=str(DEFAULT_TASKS), help="template task suite")
    generate_parser.add_argument("--per-family", type=int, default=20)
    generate_parser.add_argument("--root-seed", type=int, required=True)
    generate_parser.add_argument("--split", default="heldout")
    generate_parser.add_argument("--version", default="0.5.0")
    generate_parser.add_argument("--output", default="data/generated/tasks.json")
    generate_parser.set_defaults(func=cmd_generate)

    harness_parser = subparsers.add_parser(
        "export-harness", help="export a seed-free Faraday-Platform harness contract"
    )
    harness_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    harness_parser.add_argument("--task", action="append", help="task ID; repeat to select multiple")
    harness_parser.add_argument("--output", default="runs/faraday-platform-harness.json")
    harness_parser.set_defaults(func=cmd_export_harness)

    difficulty_parser = subparsers.add_parser(
        "difficulty", help="measure structural workload and oracle solvability"
    )
    difficulty_parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    difficulty_parser.add_argument(
        "--task", action="append", help="task ID; repeat to select multiple"
    )
    difficulty_parser.add_argument(
        "--output", default="reports/difficulty-profile.json"
    )
    difficulty_parser.set_defaults(func=cmd_difficulty)

    upstreams_parser = subparsers.add_parser(
        "upstreams", help="list or verify pinned third-party benchmark tracks"
    )
    upstreams_parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    upstreams_parser.add_argument(
        "--root", help="directory containing the manifest-relative snapshot paths"
    )
    upstreams_parser.add_argument("--verify", action="store_true")
    upstreams_parser.add_argument("--json", action="store_true")
    upstreams_parser.set_defaults(func=cmd_upstreams)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
