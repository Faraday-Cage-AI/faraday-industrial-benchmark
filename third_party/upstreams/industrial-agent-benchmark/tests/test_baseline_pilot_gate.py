"""Pilot gate boundary values (baseline_experiment_plan_v1 Section 5)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from baseline.pilot import PilotInputError, Verdict, evaluate_pilot_gate

ROOT = Path(__file__).resolve().parent.parent


def _summary(
    *,
    total=180,
    retry_exhausted=0,
    permanent=0,
    leakage=0,
    judge=True,
    parse_attempted=180,
    parse_succeeded=180,
    missing_fields=0,
    cost=True,
    estimated=100.0,
    measured=100.0,
):
    completed = total - retry_exhausted - permanent
    data = {
        "overall": {
            "total": total,
            "completed": completed,
            "missing_retry_exhausted": retry_exhausted,
            "missing_permanent": permanent,
        },
        "by_model": {
            "model_a": {
                "total": total,
                "missing_retry_exhausted": retry_exhausted,
                "missing_permanent": permanent,
            }
        },
        "by_provider": {
            "provider_x": {
                "total": total,
                "missing_retry_exhausted": retry_exhausted,
                "missing_permanent": permanent,
            }
        },
        "prompt_leakage_count": leakage,
    }
    if judge:
        data["judge"] = {
            "parse_attempted": parse_attempted,
            "parse_succeeded": parse_succeeded,
            "required_field_missing_count": missing_fields,
        }
    if cost:
        data["cost"] = {"estimated_usd": estimated, "measured_usd": measured}
    return data


def test_all_criteria_pass_is_go():
    result = evaluate_pilot_gate(_summary())
    assert result.verdict is Verdict.GO
    assert result.metrics["missing_rate"] == 0.0


def test_one_missing_of_180_is_pass_candidate():
    result = evaluate_pilot_gate(_summary(retry_exhausted=1))
    assert result.verdict is Verdict.GO
    assert result.metrics["missing"] == 1
    assert result.metrics["missing_rate"] == round(1 / 180, 6)
    # Breakdown is still reported even under the limit.
    assert any("breakdown" in r for r in result.reasons)
    assert result.metrics["by_model"]["model_a"]["missing_retry_exhausted"] == 1
    assert result.metrics["by_provider"]["provider_x"]["missing_retry_exhausted"] == 1


def test_two_missing_of_180_is_no_go():
    result = evaluate_pilot_gate(_summary(retry_exhausted=2))
    assert result.verdict is Verdict.NO_GO
    assert any("missing rate" in r for r in result.reasons)


def test_one_permanent_failure_is_no_go_even_within_rate():
    result = evaluate_pilot_gate(_summary(permanent=1))
    assert result.verdict is Verdict.NO_GO
    assert any("missing_permanent = 1" in r for r in result.reasons)


def test_prompt_leakage_is_no_go():
    result = evaluate_pilot_gate(_summary(leakage=1))
    assert result.verdict is Verdict.NO_GO


def test_judge_parse_rate_below_floor_is_no_go():
    result = evaluate_pilot_gate(_summary(parse_succeeded=172))  # 172/180 = 0.9556
    assert result.verdict is Verdict.NO_GO
    assert any("judge_parse_success_rate" in r for r in result.reasons)


def test_judge_parse_rate_between_floor_and_100_needs_review():
    result = evaluate_pilot_gate(_summary(parse_succeeded=177))  # 0.9833
    assert result.verdict is Verdict.NEEDS_REVIEW
    assert any("re-judge" in r for r in result.reasons)


@pytest.mark.parametrize(
    "succeeded,expected",
    [
        (969, Verdict.NO_GO),        # 96.9% — below the 97% floor
        (970, Verdict.NEEDS_REVIEW),  # exactly 97.0% — floor is inclusive
        (999, Verdict.NEEDS_REVIEW),  # 99.9% — still requires 100% for GO
        (1000, Verdict.GO),           # 100% after the allowed re-judge
    ],
)
def test_judge_parse_success_rate_boundaries(succeeded, expected):
    # parse_succeeded counts successes AFTER the single allowed re-judge.
    result = evaluate_pilot_gate(
        _summary(
            total=1000,
            parse_attempted=1000,
            parse_succeeded=succeeded,
        )
    )
    assert result.verdict is expected
    assert result.metrics["judge"]["judge_parse_success_rate"] == round(
        succeeded / 1000, 6
    )


def test_judge_required_field_omission_is_no_go():
    result = evaluate_pilot_gate(_summary(missing_fields=1))
    assert result.verdict is Verdict.NO_GO
    assert any("required-field omissions" in r for r in result.reasons)


def test_single_required_field_omission_overrides_perfect_parse_rate():
    # 100% parse rate but 1 remaining required-field omission -> NO_GO.
    result = evaluate_pilot_gate(
        _summary(parse_attempted=180, parse_succeeded=180, missing_fields=1)
    )
    assert result.verdict is Verdict.NO_GO


def test_absent_judge_metrics_needs_review():
    result = evaluate_pilot_gate(_summary(judge=False))
    assert result.verdict is Verdict.NEEDS_REVIEW
    assert result.metrics["judge"]["provided"] is False


def test_cost_within_band_passes_and_beyond_2x_aborts():
    assert evaluate_pilot_gate(_summary(measured=149.0)).verdict is Verdict.GO
    review = evaluate_pilot_gate(_summary(measured=160.0))
    assert review.verdict is Verdict.NEEDS_REVIEW
    no_go = evaluate_pilot_gate(_summary(measured=250.0))
    assert no_go.verdict is Verdict.NO_GO
    assert any("abort" in r for r in no_go.reasons)


def test_no_go_takes_precedence_over_review():
    result = evaluate_pilot_gate(_summary(permanent=1, judge=False))
    assert result.verdict is Verdict.NO_GO


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.pop("overall"),
        lambda s: s["overall"].update(total=0),
        lambda s: s["overall"].update(missing_permanent=-1),
        lambda s: s["judge"].update(parse_succeeded=999),
        lambda s: s["cost"].update(estimated_usd=0),
    ],
)
def test_invalid_inputs_raise(mutate):
    data = _summary()
    mutate(data)
    with pytest.raises(PilotInputError):
        evaluate_pilot_gate(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_cli(tmp_path, summary_data, extra_args=()):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary_data), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "baseline_pilot_gate.py"),
            "--summary",
            str(path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_go_exit_0(tmp_path):
    result = _run_cli(tmp_path, _summary())
    assert result.returncode == 0, result.stderr
    assert "Pilot gate verdict: GO" in result.stdout


def test_cli_no_go_exit_1(tmp_path):
    result = _run_cli(tmp_path, _summary(retry_exhausted=2))
    assert result.returncode == 1
    assert "NO_GO" in result.stdout


def test_cli_needs_review_exit_2(tmp_path):
    result = _run_cli(tmp_path, _summary(judge=False))
    assert result.returncode == 2
    assert "NEEDS_REVIEW" in result.stdout


def test_cli_rejects_unsafe_input(tmp_path):
    data = _summary()
    data["system_prompt"] = "smuggled prompt body"
    result = _run_cli(tmp_path, data)
    assert result.returncode == 3
    assert "publication boundary" in result.stderr
    assert "smuggled prompt body" not in result.stdout


def test_cli_cost_flags_merge(tmp_path):
    result = _run_cli(
        tmp_path,
        _summary(cost=False),
        extra_args=["--cost-estimated-usd", "100", "--cost-measured-usd", "250"],
    )
    assert result.returncode == 1  # 2.5x -> abort
