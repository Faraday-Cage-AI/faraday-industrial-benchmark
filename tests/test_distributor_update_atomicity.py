"""Rejected draft-order requests must leave business records and IDs unchanged."""

from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

TASK = load_tasks(
    Path(__file__).resolve().parents[1] / "data" / "distributor-erp-bench" / "tasks.json"
)[0]


@pytest.fixture
def draft_orders():
    world = IndustrialWorld(TASK)
    client = ToolClient(world)
    product = client.call("get_incident")["incident"]["product_id"]
    customer = client.call("list_erp_customer_requests")["customer_requests"][0]["customer_id"]
    offer = client.call("list_erp_supplier_offers", product_id=product)["offers"][0]
    sales = []
    for day in (5, 6):
        result = client.call(
            "create_erp_sales_order", customer_id=customer, product_id=product,
            quantity=5, unit_price=10.0, commitment_day=day,
        )
        assert result["ok"], result
        sales.append(result["sales_order"])
    result = client.call(
        "create_erp_purchase_order", offer_id=offer["id"], quantity=5,
        planned_arrival_day=2, origin_sales_order_ids=[sales[0]["id"]],
    )
    assert result["ok"], result
    return world, client, sales, result["purchase_order"], offer


def _assert_rejected_without_business_changes(world, client, name, arguments):
    before_erp = deepcopy(world.state["erp_buy"])
    before_audit = deepcopy(world.state["audit_log"])
    before_calls = len(world.trace)
    before_minute = world.minute
    result = client.call(name, **arguments)
    assert result["ok"] is False
    assert result["error"] == "invalid_request", result
    assert world.state["erp_buy"] == before_erp
    assert world.state["audit_log"] == before_audit
    # Rejection still consumes the normal tool latency and leaves an audit trace.
    assert world.minute == before_minute + 2
    assert len(world.trace) == before_calls + 1
    assert world.trace[-1].result == result


@pytest.mark.parametrize(
    "invalid",
    [
        {"commitment_day": -1},
        {"payment_term": "invalid-term"},
    ],
    ids=["negative-day", "invalid-payment-term"],
)
def test_rejected_sales_update_is_atomic(draft_orders, invalid):
    world, client, sales, _, _ = draft_orders
    arguments = {
        "sales_order_id": sales[0]["id"], "quantity": 7, "unit_price": 11.0,
        "commitment_day": 9, "payment_term": "net_30", **invalid,
    }
    _assert_rejected_without_business_changes(world, client, "update_erp_sales_order", arguments)


@pytest.mark.parametrize(
    "invalid",
    [
        {"planned_arrival_day": -1},
        {"origin_sales_order_ids": ["nonexistent-sales-order"]},
    ],
    ids=["negative-arrival", "unknown-origin"],
)
def test_rejected_purchase_update_is_atomic(draft_orders, invalid):
    world, client, sales, purchase, _ = draft_orders
    arguments = {
        "purchase_order_id": purchase["id"], "quantity": 7, "planned_arrival_day": 4,
        "origin_sales_order_ids": [sales[1]["id"]], **invalid,
    }
    _assert_rejected_without_business_changes(world, client, "update_erp_purchase_order", arguments)


@pytest.mark.parametrize("invalid", [{"commitment_day": -1}, {"payment_term": "invalid-term"}])
def test_rejected_sales_creation_preserves_records_and_id_sequence(draft_orders, invalid):
    world, client, sales, _, _ = draft_orders
    arguments = {
        "customer_id": sales[0]["customer_id"], "product_id": sales[0]["product_id"],
        "quantity": 7, "unit_price": 11.0, "commitment_day": 9, **invalid,
    }
    _assert_rejected_without_business_changes(world, client, "create_erp_sales_order", arguments)


@pytest.mark.parametrize(
    "invalid", [{"planned_arrival_day": -1}, {"origin_sales_order_ids": ["nonexistent-sales-order"]}]
)
def test_rejected_purchase_creation_preserves_records_and_id_sequence(draft_orders, invalid):
    world, client, sales, _, offer = draft_orders
    arguments = {
        "offer_id": offer["id"], "quantity": 7, "planned_arrival_day": 4,
        "origin_sales_order_ids": [sales[0]["id"]], **invalid,
    }
    _assert_rejected_without_business_changes(world, client, "create_erp_purchase_order", arguments)


def test_valid_sales_update_commits_all_fields_and_matching_total(draft_orders):
    world, client, sales, _, _ = draft_orders
    before_sequence = deepcopy(world.state["erp_buy"]["sequence"])
    before_audit = len(world.state["audit_log"])
    result = client.call(
        "update_erp_sales_order", sales_order_id=sales[0]["id"], quantity=7,
        unit_price=11.239, commitment_day=9, payment_term="net_30",
    )
    assert result["ok"], result
    expected = {
        **sales[0], "quantity": 7, "unit_price": 11.24, "amount_untaxed": 78.68,
        "commitment_day": 9, "payment_term": "net_30",
    }
    assert result["sales_order"] == expected
    assert world.state["erp_buy"]["sales_orders"][sales[0]["id"]] == expected
    assert world.state["erp_buy"]["sequence"] == before_sequence
    assert len(world.state["audit_log"]) == before_audit + 1
    assert world.state["audit_log"][-1]["action"] == "erp_buy_sales_order_updated"


def test_valid_purchase_update_commits_all_fields_and_matching_total(draft_orders):
    world, client, sales, purchase, _ = draft_orders
    before_sequence = deepcopy(world.state["erp_buy"]["sequence"])
    before_audit = len(world.state["audit_log"])
    result = client.call(
        "update_erp_purchase_order", purchase_order_id=purchase["id"], quantity=7,
        planned_arrival_day=4, origin_sales_order_ids=[sales[1]["id"]],
    )
    assert result["ok"], result
    expected = {
        **purchase, "quantity": 7, "planned_arrival_day": 4,
        "origin_sales_order_ids": [sales[1]["id"]],
        "amount_untaxed": round(7 * purchase["unit_price"], 2),
    }
    assert result["purchase_order"] == expected
    assert world.state["erp_buy"]["purchase_orders"][purchase["id"]] == expected
    assert world.state["erp_buy"]["sequence"] == before_sequence
    assert len(world.state["audit_log"]) == before_audit + 1
    assert world.state["audit_log"][-1]["action"] == "erp_buy_purchase_order_updated"
