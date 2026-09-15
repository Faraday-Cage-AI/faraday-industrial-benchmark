#!/usr/bin/env python3
"""Baseline answer generation CLI (Phase 2A: dummy provider only).

Runs the configured models over the 30-task public development subset and
writes private run artifacts plus a validated public manifest under an
ignored run directory. No network calls are possible in this phase: only
``provider_kind: dummy`` model configs are runnable, and configs marked
``non_runnable: true`` are rejected.

This CLI is independent from the frozen ``eval_v2_*`` pipeline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baseline.runner import (  # noqa: E402
    DEFAULT_EVALUATION_SET,
    DEFAULT_OUTPUT_ROOT,
    run_generation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate baseline answers (Phase 2A: dummy provider only)."
    )
    parser.add_argument("--run-id", required=True, help="Run directory id under --output-root")
    parser.add_argument("--models-config", required=True, help="Path to a runnable models YAML")
    parser.add_argument("--profiles", required=True, help="Path to a decoding profiles YAML")
    parser.add_argument(
        "--evaluation-set",
        default=str(DEFAULT_EVALUATION_SET),
        help="Path to evaluation_set_v2.yaml (public development subset)",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Private run output root (git-ignored; default experiments/baseline_v2_2_0/runs)",
    )
    parser.add_argument("--repeats", type=int, default=1, help="Repeat count per task (default 1)")
    args = parser.parse_args()

    summary, run_dir = run_generation(
        run_id=args.run_id,
        models_config_path=Path(args.models_config),
        profiles_path=Path(args.profiles),
        evaluation_set_path=Path(args.evaluation_set),
        output_root=Path(args.output_root),
        repeats=args.repeats,
    )
    overall = summary.overall
    print(f"Run directory (private, git-ignored): {run_dir}")
    print(f"Public manifest: {run_dir / 'public' / 'manifest.public.json'}")
    print(
        f"Rows: {overall.total} | completed: {overall.completed} | "
        f"missing_retry_exhausted: {overall.missing_retry_exhausted} | "
        f"missing_permanent: {overall.missing_permanent} | "
        f"missing_rate: {overall.missing_rate:.4f}"
    )
    print(f"Prompt leakage terms detected: {summary.prompt_leakage_count}")
    print("NOTE: dummy answers are plumbing artifacts, not benchmark results.")
    if summary.prompt_leakage_count:
        return 1
    return 1 if overall.missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
