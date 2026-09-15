"""Pilot gate evaluation (baseline_experiment_plan_v1.md Section 5).

Input is the runner's ``summary.json`` shape — safe aggregates only
(counts, rates, model keys). This module never reads answers, prompts, or
judge texts; the CLI additionally refuses inputs that violate the public
publication boundary, so the gate output is always safe to display or share.

Verdicts:
- GO           — all pass criteria hold.
- NO_GO        — a pass criterion failed or an abort criterion triggered.
- NEEDS_REVIEW — no hard failure, but a human must resolve something
                 (absent judge/cost data, parse rate below 100% pending the
                 single re-judge, cost outside the ±50% estimate band).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MISSING_RATE_LIMIT = 0.01          # pass: missing <= 1% of all answers
# judge_parse_success_rate = (judgements parsed successfully AFTER the single
# allowed re-judge) / (all judgements). 100% is a GO condition; [97%, 100%)
# is NEEDS_REVIEW; below 97% is NO_GO.
JUDGE_PARSE_HARD_FLOOR = 0.97
COST_REVIEW_BAND = 0.5             # within ±50% of estimate: pass
COST_ABORT_MULTIPLIER = 2.0        # more than 2x estimate: NO_GO


class Verdict(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PilotInputError(ValueError):
    """The gate input is not a valid safe-aggregate summary."""


@dataclass
class PilotGateResult:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
        }


def _require_int(obj: dict, key: str, where: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PilotInputError(f"{where}.{key} must be a non-negative integer")
    return value


def evaluate_pilot_gate(summary: dict[str, Any]) -> PilotGateResult:
    """Evaluate the pilot gate over a safe-aggregate summary.

    Expected shape (the runner's summary.json, plus optional blocks):

    - overall: {total, completed, missing_retry_exhausted, missing_permanent}
    - by_model / by_provider: {name: {total, missing_retry_exhausted,
      missing_permanent, ...}}
    - prompt_leakage_count: int
    - judge (optional): {parse_attempted, parse_succeeded,
      required_field_missing_count} — ``parse_succeeded`` counts judgements
      parsed successfully AFTER the single allowed re-judge attempt;
      ``required_field_missing_count`` counts omissions still remaining then
    - cost (optional): {estimated_usd, measured_usd}
    """
    if not isinstance(summary, dict) or not isinstance(summary.get("overall"), dict):
        raise PilotInputError("summary must be a mapping with an 'overall' block")
    overall = summary["overall"]
    total = _require_int(overall, "total", "overall")
    if total == 0:
        raise PilotInputError("overall.total must be > 0")
    retry_exhausted = _require_int(overall, "missing_retry_exhausted", "overall")
    permanent = _require_int(overall, "missing_permanent", "overall")
    missing = retry_exhausted + permanent
    missing_rate = missing / total

    no_go: list[str] = []
    review: list[str] = []
    notes: list[str] = []

    # --- answer generation criteria -------------------------------------
    if permanent > 0:
        no_go.append(
            f"missing_permanent = {permanent} (pass requires 0 permanent failures)"
        )
    if missing_rate > MISSING_RATE_LIMIT:
        no_go.append(
            f"missing rate {missing_rate:.4f} exceeds the {MISSING_RATE_LIMIT:.0%} limit "
            f"({missing}/{total})"
        )
    elif missing > 0:
        notes.append(
            f"missing within limit ({missing}/{total} = {missing_rate:.4f}); "
            "per-model/per-provider breakdown reported below"
        )

    leakage = summary.get("prompt_leakage_count", 0)
    if not isinstance(leakage, int) or isinstance(leakage, bool) or leakage < 0:
        raise PilotInputError("prompt_leakage_count must be a non-negative integer")
    if leakage > 0:
        no_go.append(f"prompt leakage violations = {leakage} (pass requires 0)")

    breakdown = {
        "by_model": _breakdown(summary.get("by_model")),
        "by_provider": _breakdown(summary.get("by_provider")),
    }

    # --- judge criteria ---------------------------------------------------
    judge = summary.get("judge")
    judge_metrics: dict[str, Any] = {"provided": judge is not None}
    if judge is None:
        review.append(
            "judge metrics not provided; gate cannot confirm parse-rate and "
            "required-field criteria"
        )
    elif not isinstance(judge, dict):
        raise PilotInputError("judge block must be a mapping")
    else:
        attempted = _require_int(judge, "parse_attempted", "judge")
        succeeded = _require_int(judge, "parse_succeeded", "judge")
        missing_fields = _require_int(judge, "required_field_missing_count", "judge")
        if attempted == 0:
            raise PilotInputError("judge.parse_attempted must be > 0 when provided")
        if succeeded > attempted:
            raise PilotInputError("judge.parse_succeeded cannot exceed parse_attempted")
        # Rate is measured AFTER the single allowed re-judge attempt.
        parse_rate = succeeded / attempted
        judge_metrics.update(
            {"parse_attempted": attempted, "parse_succeeded": succeeded,
             "judge_parse_success_rate": round(parse_rate, 6),
             "required_field_missing_count": missing_fields}
        )
        if parse_rate < JUDGE_PARSE_HARD_FLOOR:
            no_go.append(
                f"judge_parse_success_rate {parse_rate:.4f} (after the allowed "
                f"re-judge) is below the {JUDGE_PARSE_HARD_FLOOR:.0%} floor"
            )
        elif parse_rate < 1.0:
            review.append(
                f"judge_parse_success_rate {parse_rate:.4f} is in [97%, 100%) after "
                "the allowed re-judge; GO requires 100%"
            )
        if missing_fields > 0:
            no_go.append(
                f"judge required-field omissions remaining after re-judge = "
                f"{missing_fields} (GO requires 0)"
            )

    # --- cost criteria ------------------------------------------------------
    cost = summary.get("cost")
    cost_metrics: dict[str, Any] = {"provided": cost is not None}
    if cost is None:
        review.append("cost estimate/measurement not provided; deviation unchecked")
    elif not isinstance(cost, dict):
        raise PilotInputError("cost block must be a mapping")
    else:
        estimated = cost.get("estimated_usd")
        measured = cost.get("measured_usd")
        for name, value in (("estimated_usd", estimated), ("measured_usd", measured)):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise PilotInputError(f"cost.{name} must be a non-negative number")
        if estimated == 0:
            raise PilotInputError("cost.estimated_usd must be > 0")
        ratio = measured / estimated
        cost_metrics.update({"estimated_usd": estimated, "measured_usd": measured,
                             "ratio": round(ratio, 4)})
        if ratio > COST_ABORT_MULTIPLIER:
            no_go.append(
                f"measured cost is {ratio:.2f}x the estimate (> {COST_ABORT_MULTIPLIER}x "
                "triggers the abort criterion)"
            )
        elif abs(ratio - 1.0) > COST_REVIEW_BAND:
            review.append(
                f"measured cost deviates {ratio:.2f}x from the estimate "
                f"(outside the ±{COST_REVIEW_BAND:.0%} band)"
            )

    if no_go:
        verdict = Verdict.NO_GO
        reasons = no_go + review + notes
    elif review:
        verdict = Verdict.NEEDS_REVIEW
        reasons = review + notes
    else:
        verdict = Verdict.GO
        reasons = notes or ["all pilot gate criteria satisfied"]

    return PilotGateResult(
        verdict=verdict,
        reasons=reasons,
        metrics={
            "total_answers": total,
            "completed": _require_int(overall, "completed", "overall"),
            "missing_retry_exhausted": retry_exhausted,
            "missing_permanent": permanent,
            "missing": missing,
            "missing_rate": round(missing_rate, 6),
            "prompt_leakage_count": leakage,
            "judge": judge_metrics,
            "cost": cost_metrics,
            **breakdown,
        },
    )


def _breakdown(block: Any) -> dict[str, dict[str, int]]:
    """Extract the per-model / per-provider missing breakdown (safe counts)."""
    out: dict[str, dict[str, int]] = {}
    if not isinstance(block, dict):
        return out
    for name, stats in sorted(block.items()):
        if not isinstance(stats, dict):
            continue
        out[str(name)] = {
            "total": int(stats.get("total", 0)),
            "missing_retry_exhausted": int(stats.get("missing_retry_exhausted", 0)),
            "missing_permanent": int(stats.get("missing_permanent", 0)),
        }
    return out
