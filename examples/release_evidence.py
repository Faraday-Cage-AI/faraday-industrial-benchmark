"""Create a fresh, fail-closed evidence bundle without model API calls.

Run from the repository root with the development environment's Python.
The destination must not exist; historical evidence is never overwritten.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from dataclasses import asdict
from importlib.metadata import distributions
from pathlib import Path

from faraday_industrial_benchmark import __version__
from faraday_industrial_benchmark.agents import BUILTIN_AGENTS, OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS, _validate
from faraday_industrial_benchmark.difficulty import build_difficulty_profile
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.platform_harness import build_platform_harness_contract
from faraday_industrial_benchmark.provenance import content_hash, input_fingerprints
from faraday_industrial_benchmark.report import render_html
from faraday_industrial_benchmark.runner import BenchmarkRunner, save_run
from faraday_industrial_benchmark.verification import verify_run

DEVELOPMENT_TRACKS = (
    "challenge", "long-tail", "workforce", "professional", "researched-v3",
    "decision-challenge-v3", "subcontracting-v2", "close-chain-v2",
    "close-execution", "close-execution-v2",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-development-tracks", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tasks = load_tasks(DEFAULT_TASKS)

    def save(name, value):
        return save_run(value, output / name)

    dependencies = "\n".join(sorted(
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in distributions()
    )) + "\n"
    (output / "environment.txt").write_text(dependencies)
    frozen = {
        "engine_version": __version__,
        "kind": "algorithmic qualification; not learned-agent results",
        "inputs": input_fingerprints(tasks),
        "task_manifest": [asdict(task) for task in tasks],
        "run_policy": "oracle, noop, read-only, unsafe; one attempt each; oracle repeated once",
        "extra_inputs": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__).resolve(), root / "pyproject.toml", root / "uv.lock", *sorted((root / "schemas").glob("*.json"))]
        },
    }
    save("frozen-manifest.json", frozen)
    # Archive the exact executable inputs, including uncommitted fixes. Never
    # sweep the workspace: private files, credentials, outputs and environments
    # are outside this explicit allowlist.
    archive_inputs = [root / name for name in (
        "src", "tests", "examples", "schemas", "data", "third_party",
        "README.md", "BENCHMARK_CARD.md", "CONTRIBUTING.md", "LICENSE",
        "DATA_LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "pyproject.toml",
        "uv.lock", "Makefile",
    )]

    def archive_filter(member):
        if any(part in {"__pycache__", ".git", ".pytest_cache"} for part in Path(member.name).parts):
            return None
        if member.issym() or member.islnk():
            return None
        return member

    with tarfile.open(output / "source.tar.gz", "w:gz") as archive:
        for path in archive_inputs:
            archive.add(path, arcname=str(path.relative_to(root)), filter=archive_filter)
    checks = {"public_contract_validation": not _validate(tasks)}
    for name, command in {
        "regression": [sys.executable, "-m", "pytest", "-q", f"--junitxml={output / 'regression.xml'}"],
        "upstream_integrity": [sys.executable, "-m", "faraday_industrial_benchmark", "upstreams", "--verify"],
    }.items():
        with (output / f"{name}.log").open("w") as log:
            checks[name] = subprocess.run(command, check=False, cwd=root, stdout=log, stderr=subprocess.STDOUT).returncode == 0
        print(f"{name}: {checks[name]}", flush=True)
    runner = BenchmarkRunner()
    controls = {}
    for name in ("oracle", "noop", "read-only", "unsafe"):
        run = runner.run_suite(tasks, BUILTIN_AGENTS[name]())
        save(f"{name}.json", run)
        verification = verify_run(run, tasks)
        save(f"{name}-replay.json", verification)
        checks[f"{name}_replays_exactly"] = verification["exact_match"] and verification["covers_supplied_manifest"]
        controls[name] = run["summary"]
        if name == "oracle":
            first_reference = run
            render_html(run, output / "oracle.html")
        print(f"{name}: {run['summary']}", flush=True)
    checks.update({
        "oracle_all_strict": controls["oracle"]["strict_successes"] == len(tasks),
        "oracle_no_critical": controls["oracle"]["critical_failures"] == 0,
        "noop_below_20": controls["noop"]["mean_score"] < 20,
        "read_only_below_oracle": controls["read-only"]["mean_score"] < controls["oracle"]["mean_score"],
        "unsafe_all_zero": controls["unsafe"]["max_score"] == 0,
        "unsafe_all_critical": controls["unsafe"]["critical_failures"] == len(tasks),
    })
    repeated = runner.run_suite(tasks, OracleAgent())
    repetition = {
        "attempts": 2,
        "first_run_sha256": content_hash(first_reference),
        "second_run_sha256": content_hash(repeated),
        "identical_full_runs": first_reference == repeated,
        "note": "Full traces identical; oracle.json preserves the common bytes. This measures deterministic reference execution, not model stability.",
    }
    save("repeatability.json", repetition)
    checks["reference_repeatability"] = repetition["identical_full_runs"]
    save("difficulty-profile.json", build_difficulty_profile(tasks))
    save("platform-harness.json", build_platform_harness_contract(tasks))
    track_results = {}
    if args.include_development_tracks:
        for name in DEVELOPMENT_TRACKS:
            manifest = root / "data" / name / "tasks.json"
            track_tasks = load_tasks(manifest)
            run = runner.run_suite(track_tasks, OracleAgent())
            save(f"track-{name}-oracle.json", run)
            replay = verify_run(run, track_tasks)
            save(f"track-{name}-replay.json", replay)
            passed = (
                not _validate(track_tasks) and replay["exact_match"]
                and run["summary"]["strict_successes"] == len(track_tasks)
                and run["summary"]["critical_failures"] == 0
            )
            checks[f"track_{name}_reference_and_replay"] = passed
            track_results[name] = {
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "summary": run["summary"], "passed": passed,
                "scope": "Separate development contract; not pooled into headline.",
            }
            print(f"track {name}: {passed}", flush=True)
    checks["frozen_inputs_unchanged"] = frozen["inputs"] == input_fingerprints(tasks)
    qualification = {
        "benchmark_version": __version__,
        "kind": frozen["kind"],
        "passed": all(checks.values()),
        "checks": checks,
        "controls": controls,
        "development_tracks": track_results,
        "limitations": [
            "Distributor references use evaluator-side fixture answers/plans; success is execution consistency, not independent derivation.",
            "Public development suite; no private holdout generalization or learned-model ranking measured.",
            "175 fixed distributor fixtures carry about70% of the task mean.",
            "Local cooperative process runner; hosted untrusted-agent isolation is not provided.",
        ],
    }
    save("qualification.json", qualification)
    save("artifacts.json", {
        str(path.relative_to(output)): {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        for path in sorted(output.iterdir()) if path.is_file()
    })
    print(json.dumps(qualification, indent=2), flush=True)
    return 0 if qualification["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
