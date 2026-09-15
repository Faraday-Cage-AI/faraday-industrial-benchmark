#!/usr/bin/env python3
"""Pilot gate CLI: Go / No-Go / Needs Review from safe aggregates only.

Reads the runner's summary.json (counts and rates — never answers, prompts,
or judge texts) plus optional judge/cost aggregate blocks, evaluates the
pilot gate criteria of baseline_experiment_plan_v1.md Section 5, and prints
the verdict with reasons. The input is scanned against the public
publication boundary before anything is printed.

Exit codes: 0 = GO, 1 = NO_GO, 2 = NEEDS_REVIEW, 3 = invalid input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baseline.pilot import PilotInputError, Verdict, evaluate_pilot_gate  # noqa: E402
from baseline.redaction import RedactionError, assert_public_safe  # noqa: E402

_EXIT_BY_VERDICT = {Verdict.GO: 0, Verdict.NO_GO: 1, Verdict.NEEDS_REVIEW: 2}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the 30-task pilot gate from safe aggregate summaries."
    )
    parser.add_argument(
        "--summary", required=True,
        help="Path to the runner summary.json (safe aggregates only)",
    )
    parser.add_argument(
        "--judge-summary", default=None,
        help="Optional JSON file with judge aggregates "
        "(parse_attempted / parse_succeeded / required_field_missing_count)",
    )
    parser.add_argument("--cost-estimated-usd", type=float, default=None)
    parser.add_argument("--cost-measured-usd", type=float, default=None)
    args = parser.parse_args()

    try:
        summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read summary: {exc}", file=sys.stderr)
        return 3
    if args.judge_summary:
        try:
            summary["judge"] = json.loads(
                Path(args.judge_summary).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read judge summary: {exc}", file=sys.stderr)
            return 3
    if args.cost_estimated_usd is not None or args.cost_measured_usd is not None:
        if args.cost_estimated_usd is None or args.cost_measured_usd is None:
            print(
                "ERROR: provide both --cost-estimated-usd and --cost-measured-usd",
                file=sys.stderr,
            )
            return 3
        summary["cost"] = {
            "estimated_usd": args.cost_estimated_usd,
            "measured_usd": args.cost_measured_usd,
        }

    # Refuse inputs that carry anything beyond safe aggregates.
    try:
        assert_public_safe(summary)
    except RedactionError as exc:
        print(
            f"ERROR: input violates the publication boundary and was rejected: {exc}",
            file=sys.stderr,
        )
        return 3

    try:
        result = evaluate_pilot_gate(summary)
    except PilotInputError as exc:
        print(f"ERROR: invalid gate input: {exc}", file=sys.stderr)
        return 3

    print(f"Pilot gate verdict: {result.verdict.value}")
    print()
    print("Reasons:")
    for reason in result.reasons:
        print(f"  - {reason}")
    print()
    print("Safe aggregate metrics:")
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
    return _EXIT_BY_VERDICT[result.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
