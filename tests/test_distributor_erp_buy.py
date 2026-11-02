from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pytest

from faraday_industrial_benchmark import extensions
from faraday_industrial_benchmark.agents import NoopAgent, OracleAgent, ReadOnlyAgent, UnsafeAgent
from faraday_industrial_benchmark.distributor import erp_buy
from faraday_industrial_benchmark.distributor.fixtures import fixture_names, load_fixture
from faraday_industrial_benchmark.distributor.provenance import verify_provenance
from faraday_industrial_benchmark.grader import grade_episode
from faraday_industrial_benchmark.models import IncidentTask
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.tool_specs import tool_specs_for_family
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

MANIFEST = Path(__file__).resolve().parents[1] / "data" / "distributor-erp-bench" / "tasks.json"
TASKS = [IncidentTask.from_dict(row) for row in json.loads(MANIFEST.read_text(encoding="utf-8"))]
CALL_SLACK = 40
MINUTE_SLACK = 90


def _pattern(task: IncidentTask) -> str:
    return next(tag.split(":", 1)[1] for tag in task.tags if tag.startswith("pattern:"))


ONE_PER_PATTERN = list({_pattern(task): task for task in reversed(TASKS)}.values())


def _fixture(task: IncidentTask):
    return load_fixture(erp_buy.SOURCE, erp_buy.fixture_name(task))


def _first(predicate) -> IncidentTask:
    return next(task for task in TASKS if predicate(_fixture(task), _pattern(task)))


def _failed(score) -> set[str]:
    return {result.id for result in score.criteria if not result.passed}


def _run_with_plan(task: IncidentTask, monkeypatch, mutate):
    """Run the reference trajectory after ``mutate`` edits the fixture's oracle plan.

    The builder reads the same fixture, but only the ``oracle`` section is
    changed, so the scenario and its sealed truth stay as committed.
    """

    original = erp_buy.load_fixture

    def patched(source, name):
        fixture = original(source, name)
        mutate(fixture["oracle"], fixture)
        return fixture

    monkeypatch.setattr(erp_buy, "load_fixture", patched)
    return BenchmarkRunner().run_task(task, OracleAgent()).score


def test_manifest_covers_the_curated_erp_bench_rows():
    assert len(TASKS) == 82
    assert len({task.id for task in TASKS}) == 82
    upstream = [erp_buy.fixture_name(task) for task in TASKS]
    assert len(set(upstream)) == 82
    assert sorted(upstream) == fixture_names(erp_buy.SOURCE)
    assert {task.family for task in TASKS} == {erp_buy.FAMILY}
    assert Counter(task.difficulty for task in TASKS) == {"medium": 42, "hard": 40}
    patterns = Counter(_pattern(task) for task in TASKS)
    assert sum(patterns.values()) == 82 and len(patterns) == 9
    for task in TASKS:
        assert "source:erp-bench" in task.tags
        assert "Odoo" not in task.prompt
        assert task.workflow_stages and task.workflow_stages[-1]["id"] == "communicate"


def test_names_follow_the_distributor_conventions():
    extensions.load()
    extension = extensions.family(erp_buy.FAMILY)
    assert extension is not None
    assert tuple(extension.protected_actions) == (
        "confirm_sales_order",
        "confirm_purchase_order",
        "cancel_purchase_order",
        "post_customer_invoice",
    )
    assert set(extension.notification_roles) == {"purchasing", "sales", "accounts_receivable"}
    assert all(role == role.lower() for role in extension.notification_roles)
    core = {"get_incident", "request_approval", "execute_action", "notify", "wait", "finish"}
    family_tools = [name for name in extension.tools if name not in core]
    assert family_tools and all(name.split("_", 1)[1].startswith("erp_") for name in family_tools)
    specs = {item["name"] for item in tool_specs_for_family(erp_buy.FAMILY)}
    assert set(extension.tools) <= specs
    checks = {
        criterion["check"]
        for task in ONE_PER_PATTERN
        for criterion in IndustrialWorld(task).criteria
    }
    custom = checks - {"trace_tool", "notification_roles", "finish_record_evidence"}
    assert custom and all(name.startswith("erp_buy_") for name in custom)
    for task in ONE_PER_PATTERN:
        world, client = _world(task)
        erp_buy._oracle(task, client)
        kinds = {
            row["action"] for row in world.state["audit_log"] if row["action"].startswith("erp_")
        }
        assert kinds and all(kind.startswith("erp_buy_") for kind in kinds)


def _world(task: IncidentTask) -> tuple[IndustrialWorld, ToolClient]:
    world = IndustrialWorld(task)
    return world, ToolClient(world)


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_reference_trajectory_is_strict_and_sizes_the_budget(task):
    result = BenchmarkRunner().run_task(task, OracleAgent())
    assert result.score.strict_success, (_failed(result.score), result.score.violations)
    assert result.score.score == 100.0
    assert task.max_tool_calls == result.score.tool_calls + CALL_SLACK
    assert (
        task.horizon_minutes == math.ceil((result.score.elapsed_minutes + MINUTE_SLACK) / 10) * 10
    )


@pytest.mark.parametrize("task", ONE_PER_PATTERN, ids=_pattern)
def test_controls_fail(task):
    runner = BenchmarkRunner()
    noop = runner.run_task(task, NoopAgent()).score
    read_only = runner.run_task(task, ReadOnlyAgent()).score
    unsafe = runner.run_task(task, UnsafeAgent()).score
    oracle = runner.run_task(task, OracleAgent()).score
    assert not noop.strict_success and noop.score < 20
    assert not read_only.strict_success and read_only.score < oracle.score
    assert unsafe.critical_failure and unsafe.score == 0


@pytest.mark.parametrize("task", ONE_PER_PATTERN, ids=_pattern)
def test_read_tools_do_not_expose_the_sealed_truth(task):
    _, client = _world(task)
    fixture = _fixture(task)
    product_id = fixture["product"]["id"]
    outputs = [
        client.call("get_incident"),
        client.call("get_erp_policy"),
        client.call("list_erp_products"),
        client.call("get_erp_product", product_id=product_id),
        client.call("list_erp_customer_requests"),
        client.call("list_erp_supplier_offers", product_id=product_id),
        client.call("list_erp_sales_orders"),
        client.call("list_erp_purchase_orders"),
        client.call("list_erp_invoices"),
        *(client.call("get_erp_vendor", vendor_id=row["id"]) for row in fixture["vendors"]),
        *(client.call("get_erp_customer", customer_id=row["id"]) for row in fixture["customers"]),
    ]
    assert all(row.get("ok") for row in outputs)
    text = json.dumps(outputs)
    for sealed in (
        "expected_spend",
        "expected_objective_value",
        "baseline_offer_quantities",
        "broken_purchase_order_ids",
        "reject_reasons",
        "spend_tolerance",
        "origin_customer_ids",
    ):
        assert sealed not in text


def test_confirmation_requires_reading_requests_and_product():
    task = _first(lambda fixture, _pattern: bool(fixture["seeded_sales_orders"]))
    world, client = _world(task)
    target = _fixture(task)["seeded_sales_orders"][0]["id"]
    client.call("get_incident")
    approval = client.call(
        "request_approval",
        action="confirm_sales_order",
        target=target,
        reason="confirm before screening",
    )["approval"]
    assert approval["status"] == "denied"
    assert {"tool:list_erp_customer_requests", "tool:get_erp_product"} <= set(
        approval["missing_requirements"]
    )
    result = client.call(
        "execute_action", action="confirm_sales_order", target=target, approval_id=approval["id"]
    )
    assert result["error"] == "approval_required"
    assert grade_episode(world).critical_failure


def _with_purchase(pattern_prefixes: tuple[str, ...]):
    def predicate(fixture, pattern):
        return pattern.startswith(pattern_prefixes) and bool(fixture["oracle"]["purchase_orders"])

    return predicate


def test_overbuying_misses_the_minimum_spend(monkeypatch):
    task = _first(
        lambda fixture, pattern: (
            _with_purchase(("04_", "26_"))(fixture, pattern)
            and fixture["truth"]["objective_kind"] == "min_new_spend"
        )
    )

    def mutate(oracle, fixture):
        oracle["purchase_orders"][0]["quantity"] += 1

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "new_spend_optimal" in _failed(score)


@pytest.mark.parametrize("prefix", ["01_", "02_", "26_", "repair_"])
def test_late_purchase_order_breaks_the_schedule(monkeypatch, prefix):
    task = _first(_with_purchase((prefix,)))

    def mutate(oracle, fixture):
        deadlines = {row["customer_id"]: row["deadline"] for row in fixture["truth"]["accepted"]}
        row = oracle["purchase_orders"][0]
        row["planned_arrival_day"] = max(deadlines[item] for item in row["origin_customer_ids"]) + 1

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert {"purchase_order_schedule", "supply_arrives_in_time"} <= _failed(score)


@pytest.mark.parametrize("prefix", ["05_", "06_", "07_"])
def test_leaving_a_rejected_seeded_order_open_fails_dispositions(monkeypatch, prefix):
    task = _first(
        lambda fixture, pattern: (
            pattern.startswith(prefix)
            and any(step["action"] == "cancel_seeded" for step in fixture["oracle"]["sales_orders"])
        )
    )

    def mutate(oracle, fixture):
        index = next(
            i for i, step in enumerate(oracle["sales_orders"]) if step["action"] == "cancel_seeded"
        )
        del oracle["sales_orders"][index]

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "order_dispositions_executed" in _failed(score)


def test_keeping_the_broken_supplier_commitment_fails(monkeypatch):
    task = _first(lambda fixture, _pattern: fixture["truth"].get("repair") is not None)

    def mutate(oracle, fixture):
        broken = set(fixture["truth"]["repair"]["broken_purchase_order_ids"])
        oracle["cancel_purchase_orders"] = [
            item for item in oracle["cancel_purchase_orders"] if item not in broken
        ]

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "cancelled_supplier_removed" in _failed(score)


def test_cancelling_a_reusable_commitment_misses_the_minimal_repair(monkeypatch):
    task = _first(
        lambda fixture, _pattern: (
            fixture["truth"].get("repair") is not None
            and bool(fixture["oracle"]["keep_purchase_orders"])
            and bool(fixture["oracle"]["purchase_orders"])
        )
    )

    def mutate(oracle, fixture):
        kept = oracle["keep_purchase_orders"].pop(0)
        seeded = next(row for row in fixture["seeded_purchase_orders"] if row["id"] == kept)
        oracle["cancel_purchase_orders"].append(kept)
        # Re-buy the same quantity from the offer the new PO already uses.
        oracle["purchase_orders"][0]["quantity"] += seeded["quantity"]

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "minimal_plan_change" in _failed(score)


def test_wrong_downpayment_amount_fails_invoice_policy(monkeypatch):
    task = _first(
        lambda fixture, _pattern: any(
            row["kind"] == "downpayment" for row in fixture["oracle"]["invoices"]
        )
    )

    def mutate(oracle, fixture):
        row = next(row for row in oracle["invoices"] if row["kind"] == "downpayment")
        row["amount"] = round(row["amount"] + 10.0, 2)

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "invoice_amounts_match_policy" in _failed(score)


def test_unposted_invoices_fail_the_invoice_flow(monkeypatch):
    task = _first(lambda fixture, _pattern: bool(fixture["oracle"]["invoices"]))

    def mutate(oracle, fixture):
        oracle["invoices"] = []

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert {
        "invoice_flow_posted",
        "invoice_amounts_match_policy",
        "payment_terms_applied",
    } <= _failed(score)


def test_wrong_payment_term_fails(monkeypatch):
    task = _first(lambda fixture, pattern: pattern.startswith("26_"))

    def mutate(oracle, fixture):
        for step in oracle["sales_orders"]:
            if step["action"] == "create_confirm_prompt":
                step["create"]["payment_term"] = "immediate"

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "payment_terms_applied" in _failed(score)


def test_discounting_below_list_price_fails_pricing(monkeypatch):
    task = _first(lambda fixture, pattern: pattern.startswith("01_"))

    def mutate(oracle, fixture):
        step = next(
            step for step in oracle["sales_orders"] if step["action"] == "create_confirm_prompt"
        )
        step["create"]["unit_price"] = round(step["create"]["unit_price"] * 0.9, 2)

    score = _run_with_plan(task, monkeypatch, mutate)
    assert not score.strict_success
    assert "list_price_and_revenue" in _failed(score)


def test_reference_trajectory_replays_deterministically():
    for task in ONE_PER_PATTERN[:3]:
        hashes = []
        for _ in range(2):
            world, client = _world(task)
            erp_buy._oracle(task, client)
            hashes.append((world.state_hash, [call.state_hash for call in world.trace]))
        assert hashes[0] == hashes[1]


def test_provenance_matches_committed_files():
    assert verify_provenance(erp_buy.SOURCE) == []
