"""Business counterexamples for corrected distributor cash timing and AP holds."""

from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.distributor import erpbench100, gdpval_work
from faraday_industrial_benchmark.distributor.erpbench100_erp import erp
from faraday_industrial_benchmark.distributor.gdpval_checks import evaluate, terms_cash_receipts
from faraday_industrial_benchmark.grader import grade_episode
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

ROOT = Path(__file__).resolve().parents[1]
TASKS = load_tasks(ROOT / "data" / "public" / "tasks.json")
TERMS_TASK = next(task for task in TASKS if task.id == "faraday-gdpval-002")
AP_TASK = next(task for task in TASKS if task.id == "faraday-erpbench100-005")


def _cash_check():
    grader = gdpval_work.grader_fixture(TERMS_TASK.id)
    check = next(row for row in grader["checks"] if row.get("aspect") == "cash")
    return grader, check


def test_cash_contract_publishes_the_same_invoice_dates_the_checker_uses():
    fixture = gdpval_work.task_fixture(TERMS_TASK.id)
    sections = fixture["case_files"][0]["sections"]
    timing = sections["submission_contract"]["cash_timing"]
    _, check = _cash_check()
    assert timing["base_year"] == check["base_year"] == 2026
    assert timing["invoice_dates"] == check["invoice_dates"] == {
        "Q1": "2026-03-31", "Q2": "2026-06-30", "Q3": "2026-09-30", "Q4": "2026-12-31"
    }
    assert "calendar days" in timing["receipt_date_rule"]
    assert "within-quarter" in timing["resolution"]
    for invoice_date in timing["invoice_dates"].values():
        assert invoice_date in sections["request"]["role_request"]


def test_both_quarter_end_payment_terms_land_in_the_following_quarter():
    grader, check = _cash_check()
    for scenario in grader["truth"]["scenarios"]:
        assert scenario["cash_receipts"] == {
            f"Q{quarter + 1}": scenario["wholesale_revenue"][f"Q{quarter}"]
            for quarter in range(1, 5)
        }
    assert evaluate(check, grader["truth"])[0]


def test_old_sixty_day_two_quarter_lag_is_rejected():
    grader, check = _cash_check()
    content = deepcopy(grader["truth"])
    sixty = next(row for row in content["scenarios"] if row["payment_terms_days"] == 60)
    sixty["cash_receipts"] = {
        f"Q{quarter + 2}": sixty["wholesale_revenue"][f"Q{quarter}"]
        for quarter in range(1, 5)
    }
    passed, detail = evaluate(check, content)
    assert not passed
    assert "cash Q2" in detail


@pytest.mark.parametrize(
    ("invoice_date", "days", "year", "expected"),
    [
        ("2026-11-30", 30, 2026, {"Q4": 100.0}),
        ("2026-11-30", 60, 2026, {"Q5": 100.0}),
        ("2024-02-29", 30, 2024, {"Q1": 100.0}),
        ("2024-02-29", 60, 2024, {"Q2": 100.0}),
        ("2026-12-31", 30, 2026, {"Q5": 100.0}),
    ],
)
def test_cash_model_adds_days_across_calendar_and_leap_boundaries(invoice_date, days, year, expected):
    assert terms_cash_receipts({"Q1": 100.0}, {"Q1": invoice_date}, days, year) == expected


def test_cash_receipts_sum_multiple_invoices_in_one_quarter():
    assert terms_cash_receipts(
        {"Q1": 100.0, "Q2": 200.0}, {"Q1": "2026-03-31", "Q2": "2026-04-30"}, 30, 2026
    ) == {"Q2": 300.0}


def _ap_extra_hold(lines):
    truth = erpbench100.task_fixture(AP_TASK)["truth"]
    return {
        "action": "hold_dist_tenant_supplier_invoice",
        "target": truth["invoice_number"],
        "payload": {"hold_name": "Price", "lines": lines, "reason": "additional hold under test"},
    }


@pytest.mark.parametrize("lines", [[1, 2, 3, 4], [2]], ids=["unaffected-lines", "duplicate-active-hold"])
def test_unnecessary_or_duplicate_active_ap_holds_do_not_strictly_pass(lines):
    world = IndustrialWorld(AP_TASK)
    erpbench100.reference_run(AP_TASK, ToolClient(world), extra_steps=(_ap_extra_hold(lines),))
    score = grade_episode(world)
    failed = {row.id for row in score.criteria if not row.passed}
    assert not score.strict_success
    assert not score.critical_failure
    assert {"erp_state:secondary_write", "containment:review_gate"} <= failed


def test_missing_required_ap_hold_does_not_strictly_pass(monkeypatch):
    world = IndustrialWorld(AP_TASK)
    fixture = deepcopy(erpbench100.task_fixture(AP_TASK))
    fixture["oracle_plan"] = [
        step for step in fixture["oracle_plan"] if step["action"] != "hold_dist_tenant_supplier_invoice"
    ]
    monkeypatch.setattr(erpbench100, "task_fixture", lambda _task: fixture)
    erpbench100.reference_run(AP_TASK, ToolClient(world))
    score = grade_episode(world)
    assert not score.strict_success
    assert "erp_state:secondary_write" in {row.id for row in score.criteria if not row.passed}


def test_closed_historical_hold_is_not_effective_containment():
    world = IndustrialWorld(AP_TASK)
    erpbench100.reference_run(AP_TASK, ToolClient(world))
    truth = erpbench100.task_fixture(AP_TASK)["truth"]
    erp(world)["invoice_holds"]["historical-test"] = {
        "invoice_number": truth["invoice_number"], "hold_lines": [1, 2, 3, 4], "hold_status": "Closed"
    }
    assert grade_episode(world).strict_success


@pytest.mark.parametrize("task", [TERMS_TASK, AP_TASK], ids=lambda task: task.id)
def test_corrected_distributor_reference_passes_and_replays(task):
    runner = BenchmarkRunner()
    result = runner.run_task(task, OracleAgent()).to_dict()
    assert result["score"]["strict_success"]
    assert result["score"]["score"] == 100.0
    replay = runner.replay(task, result["trace"])
    assert replay["exact_match"]
    assert replay["score"] == result["score"]
