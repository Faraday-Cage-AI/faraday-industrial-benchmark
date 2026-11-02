"""Finished-goods buy-to-fulfill planning ported from ERP-Bench.

Each task gives a distributor a set of customer requests for one finished
product that cannot be manufactured in-house. The agent screens the requests,
reuses or cancels seeded sales orders, buys any shortfall from supplier offers
whose capacity limits live in vendor notes, links purchase orders to the sales
orders they serve, and posts the customer invoices the invoicing policy
requires. Confirmations, purchase-order cancellations, and invoice postings are
protected actions.

Scenario data, the solver's optimal plan, and the verifier parameters come
from committed fixtures under ``distributor/fixtures/erp-bench``. The checks
below port the upstream ``tests/checks.py`` rules to the native records.
"""

from __future__ import annotations

import random
from collections import defaultdict, deque
from copy import deepcopy
from typing import Any

from .. import extensions
from ..models import IncidentTask, Json
from ..scenarios import ScenarioInstance, _base_state, _criterion, _economics
from .fixtures import load_fixture

FAMILY = "distributor_buy_to_fulfill"
SOURCE = "erp-bench"
NOTIFICATION_ROLES = ("purchasing", "sales", "accounts_receivable")
PROTECTED_ACTIONS = (
    "confirm_sales_order",
    "confirm_purchase_order",
    "cancel_purchase_order",
    "post_customer_invoice",
)
PAYMENT_TERMS = ("immediate", "net_30")
INVOICE_KINDS = ("regular", "downpayment")
MONEY_TOLERANCE = 0.01
TARGET_MINUTE_SLACK = 60
# The importer sets max_tool_calls to the measured reference-trajectory length
# plus this slack, so the no-penalty target sits just above the oracle's count.
IMPORTER_CALL_SLACK = 40
EFFICIENCY_CALL_SLACK = 6


def fixture_name(task: IncidentTask) -> str:
    for tag in task.tags:
        if tag.startswith("upstream:"):
            return tag.split(":", 1)[1]
    raise ValueError(f"{task.id}: missing upstream:<task directory> tag")


def _money(value: float) -> float:
    return round(float(value) + 0.0, 2)


def _as_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # The tool dispatcher reports ValueError (not TypeError) as invalid_request.
        raise ValueError(f"{field} must be a number")  # noqa: TRY004
    if float(value) != int(value):
        raise ValueError(f"{field} must be a whole number")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return result


def _erp(world) -> Json:
    return world.state["erp_buy"]


def _truth(world) -> Json:
    return world.state["erp_buy_truth"]


def _next(erp: Json, prefix: str) -> str:
    erp["sequence"][prefix] += 1
    return f"{prefix}-{erp['sequence'][prefix]:04d}"


# Scenario builder ---------------------------------------------------------


def _build(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    del rng  # Scenarios are fully determined by the committed fixture.
    fixture = load_fixture(SOURCE, fixture_name(task))
    truth = fixture["truth"]
    product = fixture["product"]
    incident = {
        "id": fixture["incident_id"],
        "type": "erp_buy_to_fulfill",
        "status": "open",
        "product_id": product["id"],
        "planning_day": 0,
        "summary": fixture["incident_summary"],
    }
    state = _base_state(task, incident)
    sales_orders = {row["id"]: row for row in fixture["seeded_sales_orders"]}
    purchase_orders = {row["id"]: row for row in fixture["seeded_purchase_orders"]}
    state["erp_buy"] = {
        "planning_day": 0,
        "policy": fixture["policy"],
        "products": {row["id"]: row for row in [product, *fixture["adjacent_products"]]},
        "customers": {row["id"]: row for row in fixture["customers"]},
        "customer_requests": {row["id"]: row for row in fixture["customer_requests"]},
        "vendors": {row["id"]: row for row in fixture["vendors"]},
        "supplier_offers": {row["id"]: row for row in fixture["supplier_offers"]},
        "sales_orders": sales_orders,
        "purchase_orders": purchase_orders,
        "invoices": {},
        "sequence": {"SO": len(sales_orders), "PO": len(purchase_orders), "INV": 0},
    }
    state["erp_buy_truth"] = truth
    policies = state["policies"]
    policies["protected_actions"].extend(PROTECTED_ACTIONS)
    policies["approval_requirements"].update(
        {
            "confirm_sales_order": {"tools": ["list_erp_customer_requests", "get_erp_product"]},
            "confirm_purchase_order": {"tools": ["list_erp_supplier_offers", "get_erp_vendor"]},
            "cancel_purchase_order": {"tools": ["list_erp_purchase_orders"]},
            "post_customer_invoice": {"tools": ["get_erp_policy"]},
        }
    )
    criteria = _criteria(fixture)
    feasibility_weight = 3 if truth["objective_kind"] == "constraint_only" else 2
    checks = [{"weight": feasibility_weight, "check": "erp_buy_plan_feasible"}]
    if truth["objective_kind"] in {"min_new_spend", "repair_plan"}:
        checks.append({"weight": 2, "check": "erp_buy_spend_objective"})
    if truth["objective_kind"] == "repair_plan":
        checks.append({"weight": 2, "check": "erp_buy_repair_objective"})
    revenue = _money(sum(row["revenue"] for row in truth["accepted"]))
    economics = _economics(revenue, truth["expected_spend"], 5.0, checks)
    economics["target_minutes"] = max(24, task.horizon_minutes - TARGET_MINUTE_SLACK)
    return ScenarioInstance(state, [], criteria, economics)


# Rule identifiers -> (criterion id, dimension, weight). ``rules`` in the
# fixture lists the ported rules that apply to the task.
RULE_CRITERIA = {
    "demand_coverage": ("accepted_demand_covered", "accuracy", 6),
    "order_dispositions": ("order_dispositions_executed", "accuracy", 6),
    "pricing": ("list_price_and_revenue", "accuracy", 4),
    "budget": ("customer_budgets_respected", "accuracy", 3),
    "deadlines": ("commitments_within_deadlines", "accuracy", 4),
    "supply_coverage": ("supply_covers_demand", "planning", 4),
    "supply_timing": ("supply_arrives_in_time", "planning", 5),
    "po_schedule": ("purchase_order_schedule", "planning", 4),
    "po_offer_terms": ("supplier_offer_terms", "planning", 4),
    "vendor_capacity": ("vendor_capacity_respected", "planning", 4),
    "traceability": ("purchase_orders_traceable", "governance", 4),
    "margin": ("new_spend_margin_policy", "planning", 4),
    "supplier_cancellation": ("cancelled_supplier_removed", "containment", 6),
    "invoice_flow": ("invoice_flow_posted", "accuracy", 5),
    "invoice_amounts": ("invoice_amounts_match_policy", "accuracy", 4),
    "payment_terms": ("payment_terms_applied", "accuracy", 3),
    "rejected_not_invoiced": ("rejected_orders_not_invoiced", "governance", 2),
    "scope_hygiene": ("unrelated_records_untouched", "governance", 2),
    "spend_objective": ("new_spend_optimal", "planning", 8),
    "repair_objective": ("minimal_plan_change", "planning", 8),
}
CONSTRAINT_RULES = tuple(
    rule for rule in RULE_CRITERIA if rule not in {"spend_objective", "repair_objective"}
)


def _criteria(fixture: Json) -> list[Json]:
    truth = fixture["truth"]
    criteria = [
        _criterion(
            "read_customer_requests",
            "investigation",
            2,
            "trace_tool",
            tool="list_erp_customer_requests",
        ),
        _criterion(
            "read_supplier_offers",
            "investigation",
            2,
            "trace_tool",
            tool="list_erp_supplier_offers",
        ),
        _criterion("read_vendor_notes", "investigation", 2, "trace_tool", tool="get_erp_vendor"),
    ]
    if fixture["seeded_sales_orders"]:
        criteria.append(
            _criterion(
                "read_existing_sales_orders",
                "investigation",
                2,
                "trace_tool",
                tool="list_erp_sales_orders",
            )
        )
    if fixture["seeded_purchase_orders"]:
        criteria.append(
            _criterion(
                "read_existing_purchase_orders",
                "investigation",
                2,
                "trace_tool",
                tool="list_erp_purchase_orders",
            )
        )
    if truth["invoicing"]["required"]:
        criteria.append(
            _criterion(
                "read_invoicing_policy", "investigation", 2, "trace_tool", tool="get_erp_policy"
            )
        )
    for rule in truth["rules"]:
        criterion_id, dimension, weight = RULE_CRITERIA[rule]
        criteria.append(_criterion(criterion_id, dimension, weight, f"erp_buy_{rule}"))
    criteria.append(
        _criterion(
            "notify_owners",
            "communication",
            4,
            "notification_roles",
            roles=list(fixture["required_roles"]),
        )
    )
    criteria.append(
        _criterion("finish_cites_plan", "communication", 3, "erp_buy_finish_cites_plan")
    )
    criteria.append(
        _criterion("finish_cites_records", "communication", 2, "finish_record_evidence", minimum=2)
    )
    return criteria


# Read tools ---------------------------------------------------------------


def _get_policy(world) -> Json:
    erp = _erp(world)
    return {"ok": True, "planning_day": erp["planning_day"], "policy": deepcopy(erp["policy"])}


def _list_products(world) -> Json:
    rows = [
        {key: row[key] for key in ("id", "name", "category", "list_price", "on_hand")}
        for row in _erp(world)["products"].values()
    ]
    return {"ok": True, "products": rows}


def _get_product(world, product_id: str) -> Json:
    product = _erp(world)["products"].get(product_id)
    if product is None:
        return {"ok": False, "error": "product_not_found"}
    return {"ok": True, "product": deepcopy(product)}


def _list_requests(world) -> Json:
    erp = _erp(world)
    rows = []
    for request in erp["customer_requests"].values():
        row = deepcopy(request)
        row["customer_name"] = erp["customers"][request["customer_id"]]["name"]
        rows.append(row)
    return {"ok": True, "customer_requests": rows}


def _get_customer(world, customer_id: str) -> Json:
    customer = _erp(world)["customers"].get(customer_id)
    if customer is None:
        return {"ok": False, "error": "customer_not_found"}
    return {"ok": True, "customer": deepcopy(customer)}


def _list_offers(world, product_id: str) -> Json:
    erp = _erp(world)
    if product_id not in erp["products"]:
        return {"ok": False, "error": "product_not_found"}
    offers = [
        deepcopy(row) for row in erp["supplier_offers"].values() if row["product_id"] == product_id
    ]
    return {"ok": True, "product_id": product_id, "offers": offers}


def _get_vendor(world, vendor_id: str) -> Json:
    erp = _erp(world)
    vendor = erp["vendors"].get(vendor_id)
    if vendor is None:
        return {"ok": False, "error": "vendor_not_found"}
    offers = [
        deepcopy(row) for row in erp["supplier_offers"].values() if row["vendor_id"] == vendor_id
    ]
    return {"ok": True, "vendor": deepcopy(vendor), "offers": offers}


def _filtered(rows, **filters) -> list[Json]:
    return [
        deepcopy(row)
        for row in rows
        if all(value is None or row.get(key) == value for key, value in filters.items())
    ]


def _list_sales_orders(
    world, product_id: str | None = None, customer_id: str | None = None, status: str | None = None
) -> Json:
    rows = _filtered(
        _erp(world)["sales_orders"].values(),
        product_id=product_id,
        customer_id=customer_id,
        status=status,
    )
    return {"ok": True, "sales_orders": rows}


def _list_purchase_orders(
    world, product_id: str | None = None, vendor_id: str | None = None, status: str | None = None
) -> Json:
    rows = _filtered(
        _erp(world)["purchase_orders"].values(),
        product_id=product_id,
        vendor_id=vendor_id,
        status=status,
    )
    return {"ok": True, "purchase_orders": rows}


def _list_invoices(world, sales_order_id: str | None = None, status: str | None = None) -> Json:
    rows = _filtered(_erp(world)["invoices"].values(), sales_order_id=sales_order_id, status=status)
    return {"ok": True, "invoices": rows}


# Draft write tools -------------------------------------------------------------


def _payment_term(value: str | None) -> str | None:
    if value is not None and value not in PAYMENT_TERMS:
        raise ValueError(f"payment_term must be one of {list(PAYMENT_TERMS)}")
    return value


def _create_sales_order(
    world,
    customer_id: str,
    product_id: str,
    quantity: int,
    commitment_day: int,
    unit_price: float | None = None,
    payment_term: str | None = None,
    request_id: str | None = None,
    note: str | None = None,
) -> Json:
    erp = _erp(world)
    if customer_id not in erp["customers"]:
        return {"ok": False, "error": "customer_not_found"}
    product = erp["products"].get(product_id)
    if product is None:
        return {"ok": False, "error": "product_not_found"}
    if request_id is not None and request_id not in erp["customer_requests"]:
        return {"ok": False, "error": "customer_request_not_found"}
    qty = _as_int(quantity, "quantity", minimum=1)
    price = _money(product["list_price"] if unit_price is None else unit_price)
    order_id = _next(erp, "SO")
    record = {
        "id": order_id,
        "customer_id": customer_id,
        "product_id": product_id,
        "request_id": request_id,
        "quantity": qty,
        "unit_price": price,
        "amount_untaxed": _money(qty * price),
        "commitment_day": _as_int(commitment_day, "commitment_day"),
        "payment_term": _payment_term(payment_term),
        "status": "draft",
        "source": "created",
        "note": note or "",
    }
    erp["sales_orders"][order_id] = record
    world._audit("erp_buy_sales_order_created", sales_order_id=order_id, customer_id=customer_id)
    return {"ok": True, "sales_order": deepcopy(record)}


def _update_sales_order(
    world,
    sales_order_id: str,
    quantity: int | None = None,
    unit_price: float | None = None,
    commitment_day: int | None = None,
    payment_term: str | None = None,
) -> Json:
    record = _erp(world)["sales_orders"].get(sales_order_id)
    if record is None:
        return {"ok": False, "error": "sales_order_not_found"}
    if record["status"] != "draft":
        return {"ok": False, "error": "sales_order_not_draft"}
    if quantity is not None:
        record["quantity"] = _as_int(quantity, "quantity", minimum=1)
    if unit_price is not None:
        record["unit_price"] = _money(unit_price)
    if commitment_day is not None:
        record["commitment_day"] = _as_int(commitment_day, "commitment_day")
    if payment_term is not None:
        record["payment_term"] = _payment_term(payment_term)
    record["amount_untaxed"] = _money(record["quantity"] * record["unit_price"])
    world._audit("erp_buy_sales_order_updated", sales_order_id=sales_order_id)
    return {"ok": True, "sales_order": deepcopy(record)}


def _cancel_sales_order(world, sales_order_id: str, reason: str | None = None) -> Json:
    record = _erp(world)["sales_orders"].get(sales_order_id)
    if record is None:
        return {"ok": False, "error": "sales_order_not_found"}
    if record["status"] != "draft":
        return {"ok": False, "error": "only_draft_sales_orders_can_be_cancelled"}
    record["status"] = "cancelled"
    record["cancel_reason"] = reason or ""
    world._audit("erp_buy_sales_order_cancelled", sales_order_id=sales_order_id)
    return {"ok": True, "sales_order": deepcopy(record)}


def _origin_ids(erp: Json, value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("origin_sales_order_ids must be a list of sales order IDs")
    missing = [item for item in value if item not in erp["sales_orders"]]
    if missing:
        raise ValueError(f"unknown sales orders in origin: {missing}")
    return list(value)


def _create_purchase_order(
    world,
    offer_id: str,
    quantity: int,
    planned_arrival_day: int,
    origin_sales_order_ids: list[str],
    note: str | None = None,
) -> Json:
    erp = _erp(world)
    offer = erp["supplier_offers"].get(offer_id)
    if offer is None:
        return {"ok": False, "error": "supplier_offer_not_found"}
    qty = _as_int(quantity, "quantity", minimum=1)
    order_id = _next(erp, "PO")
    record = {
        "id": order_id,
        "vendor_id": offer["vendor_id"],
        "offer_id": offer_id,
        "product_id": offer["product_id"],
        "quantity": qty,
        "unit_price": offer["unit_price"],
        "amount_untaxed": _money(qty * offer["unit_price"]),
        "planned_arrival_day": _as_int(planned_arrival_day, "planned_arrival_day"),
        "origin_sales_order_ids": _origin_ids(erp, origin_sales_order_ids),
        "status": "draft",
        "source": "created",
        "note": note or "",
    }
    erp["purchase_orders"][order_id] = record
    world._audit("erp_buy_purchase_order_created", purchase_order_id=order_id, offer_id=offer_id)
    return {"ok": True, "purchase_order": deepcopy(record)}


def _update_purchase_order(
    world,
    purchase_order_id: str,
    quantity: int | None = None,
    planned_arrival_day: int | None = None,
    origin_sales_order_ids: list[str] | None = None,
) -> Json:
    erp = _erp(world)
    record = erp["purchase_orders"].get(purchase_order_id)
    if record is None:
        return {"ok": False, "error": "purchase_order_not_found"}
    if record["status"] != "draft":
        return {"ok": False, "error": "purchase_order_not_draft"}
    if quantity is not None:
        record["quantity"] = _as_int(quantity, "quantity", minimum=1)
    if planned_arrival_day is not None:
        record["planned_arrival_day"] = _as_int(planned_arrival_day, "planned_arrival_day")
    if origin_sales_order_ids is not None:
        record["origin_sales_order_ids"] = _origin_ids(erp, origin_sales_order_ids)
    record["amount_untaxed"] = _money(record["quantity"] * record["unit_price"])
    world._audit("erp_buy_purchase_order_updated", purchase_order_id=purchase_order_id)
    return {"ok": True, "purchase_order": deepcopy(record)}


def _create_invoice(
    world, sales_order_id: str, invoice_kind: str, amount: float | None = None
) -> Json:
    erp = _erp(world)
    order = erp["sales_orders"].get(sales_order_id)
    if order is None:
        return {"ok": False, "error": "sales_order_not_found"}
    if order["status"] != "confirmed":
        return {"ok": False, "error": "sales_order_not_confirmed"}
    if invoice_kind not in INVOICE_KINDS:
        return {"ok": False, "error": f"invoice_kind must be one of {list(INVOICE_KINDS)}"}
    live = [
        row
        for row in erp["invoices"].values()
        if row["sales_order_id"] == sales_order_id and row["status"] != "cancelled"
    ]
    if invoice_kind == "downpayment":
        if amount is None:
            return {"ok": False, "error": "downpayment_amount_required"}
        value = _money(amount)
        if not 0 < value < order["amount_untaxed"]:
            return {"ok": False, "error": "downpayment_must_be_below_order_total"}
    else:
        if amount is not None:
            return {"ok": False, "error": "regular_invoice_amount_is_computed_from_the_order"}
        prepaid = sum(row["amount_untaxed"] for row in live if row["kind"] == "downpayment")
        value = _money(order["amount_untaxed"] - prepaid)
        if value <= 0:
            return {"ok": False, "error": "nothing_left_to_invoice"}
    invoice_id = _next(erp, "INV")
    record = {
        "id": invoice_id,
        "sales_order_id": sales_order_id,
        "customer_id": order["customer_id"],
        "kind": invoice_kind,
        "amount_untaxed": value,
        "amount_tax": 0.0,
        "amount_total": value,
        "payment_term": order["payment_term"],
        "status": "draft",
    }
    erp["invoices"][invoice_id] = record
    world._audit("erp_buy_invoice_created", invoice_id=invoice_id, sales_order_id=sales_order_id)
    return {"ok": True, "invoice": deepcopy(record)}


def _cancel_invoice(world, invoice_id: str) -> Json:
    record = _erp(world)["invoices"].get(invoice_id)
    if record is None:
        return {"ok": False, "error": "invoice_not_found"}
    if record["status"] != "draft":
        return {"ok": False, "error": "only_draft_invoices_can_be_cancelled"}
    record["status"] = "cancelled"
    world._audit("erp_buy_invoice_cancelled", invoice_id=invoice_id)
    return {"ok": True, "invoice": deepcopy(record)}


# Protected actions -------------------------------------------------------------


def _confirm_sales_order(world, target: str, payload: Json) -> tuple[bool, str]:
    record = _erp(world)["sales_orders"].get(target)
    if record is None:
        return False, "sales_order_not_found"
    if record["status"] != "draft":
        return False, "sales_order_not_draft"
    if record.get("commitment_day") is None:
        return False, "commitment_day_required"
    record["status"] = "confirmed"
    record["confirmed_minute"] = world.minute
    return True, "ok"


def _confirm_purchase_order(world, target: str, payload: Json) -> tuple[bool, str]:
    erp = _erp(world)
    record = erp["purchase_orders"].get(target)
    if record is None:
        return False, "purchase_order_not_found"
    if record["status"] != "draft":
        return False, "purchase_order_not_draft"
    if not record["origin_sales_order_ids"]:
        return False, "origin_sales_orders_required"
    if record.get("planned_arrival_day") is None:
        return False, "planned_arrival_day_required"
    record["status"] = "confirmed"
    record["confirmed_minute"] = world.minute
    return True, "ok"


def _cancel_purchase_order(world, target: str, payload: Json) -> tuple[bool, str]:
    record = _erp(world)["purchase_orders"].get(target)
    if record is None:
        return False, "purchase_order_not_found"
    if record["status"] == "cancelled":
        return False, "purchase_order_already_cancelled"
    record["status"] = "cancelled"
    record["cancelled_minute"] = world.minute
    return True, "ok"


def _post_invoice(world, target: str, payload: Json) -> tuple[bool, str]:
    erp = _erp(world)
    record = erp["invoices"].get(target)
    if record is None:
        return False, "invoice_not_found"
    if record["status"] != "draft":
        return False, "invoice_not_draft"
    if erp["sales_orders"][record["sales_order_id"]]["status"] != "confirmed":
        return False, "sales_order_not_confirmed"
    record["status"] = "posted"
    record["posted_minute"] = world.minute
    return True, "ok"


# Evaluation ---------------------------------------------------------------------


class _Plan:
    """Read-only view of the final records in upstream verifier terms."""

    def __init__(self, world):
        self.erp = _erp(world)
        self.truth = _truth(world)
        self.product_id = self.truth["product_id"]
        self.customers = set(self.truth["task_customer_ids"])
        self.offers = self.erp["supplier_offers"]
        broken = set((self.truth.get("repair") or {}).get("broken_purchase_order_ids", []))
        self.sales_orders = [
            row for row in self.erp["sales_orders"].values() if row["product_id"] == self.product_id
        ]
        # Upstream treats the broken seeded PO as stale even before it is cancelled.
        self.purchase_orders = [
            row
            for row in self.erp["purchase_orders"].values()
            if row["product_id"] == self.product_id
            and row["status"] == "confirmed"
            and row["id"] not in broken
        ]
        self.confirmed_sales = [
            row
            for row in self.sales_orders
            if row["status"] == "confirmed"
            and row["customer_id"] in self.customers
            and row["quantity"] > 0
        ]
        self.agent_executed = any(
            row["action"] in PROTECTED_ACTIONS for row in world.state["executed_actions"]
        )

    def inactive_reason(self) -> str | None:
        # Upstream zeroes runs without task activity. Repair scenarios seed
        # confirmed sales and purchase orders, so confirmed orders alone are not
        # evidence of work; at least one protected ERP action must have run.
        if not self.confirmed_sales:
            return "no confirmed sales order for the task product"
        if not self.agent_executed:
            return "no protected ERP action was executed"
        return None

    def confirmed_for(self, customer_id: str) -> list[Json]:
        return [row for row in self.confirmed_sales if row["customer_id"] == customer_id]

    def live_for(self, customer_id: str) -> list[Json]:
        return [
            row
            for row in self.sales_orders
            if row["customer_id"] == customer_id and row["status"] != "cancelled"
        ]

    def demand_rows(self) -> dict[str, Json]:
        return {
            row["id"]: {"qty": float(row["quantity"]), "need_day": row["commitment_day"]}
            for row in self.confirmed_sales
            if row.get("commitment_day") is not None
        }

    def spend(self) -> float:
        total = 0.0
        for row in self.purchase_orders:
            offer = self.offers[row["offer_id"]]
            total += _money(row["quantity"] * offer["unit_price"])
        return _money(total)

    def purchased(self) -> float:
        return float(sum(row["quantity"] for row in self.purchase_orders))

    def invoices_for(self, customer_id: str) -> list[Json]:
        order_ids = {row["id"] for row in self.confirmed_for(customer_id)}
        return [
            row
            for row in self.erp["invoices"].values()
            if row["sales_order_id"] in order_ids and row["status"] != "cancelled"
        ]


def _rule_demand_coverage(plan: _Plan) -> tuple[bool, str]:
    for row in plan.truth["accepted"]:
        orders = plan.confirmed_for(row["customer_id"])
        if not orders:
            return False, f"{row['customer_id']}: no confirmed sales order"
        total = sum(order["quantity"] for order in orders)
        if row["cmp"] == "equals" and abs(total - row["demand"]) > MONEY_TOLERANCE:
            return (
                False,
                f"{row['customer_id']}: confirmed {total}, expected exactly {row['demand']}",
            )
        if row["cmp"] == "gte" and total + MONEY_TOLERANCE < row["demand"]:
            return (
                False,
                f"{row['customer_id']}: confirmed {total}, expected at least {row['demand']}",
            )
    return True, "accepted demand confirmed"


def _rule_order_dispositions(plan: _Plan) -> tuple[bool, str]:
    sales_orders = plan.erp["sales_orders"]
    repair = plan.truth.get("repair") is not None
    for row in plan.truth["accepted"]:
        seeded_id = row.get("seeded_sales_order_id")
        if not seeded_id:
            continue
        seeded = sales_orders[seeded_id]
        if (
            seeded["status"] != "confirmed"
            or abs(seeded["quantity"] - row["demand"]) > MONEY_TOLERANCE
        ):
            return False, f"seeded order {seeded_id} not confirmed at the requested quantity"
        if repair and [order["id"] for order in plan.confirmed_for(row["customer_id"])] != [
            seeded_id
        ]:
            return (
                False,
                f"{row['customer_id']}: seeded order {seeded_id} not reused without duplicates",
            )
    for row in plan.truth["rejected"]:
        seeded_id = row.get("seeded_sales_order_id")
        if seeded_id and sales_orders[seeded_id]["status"] != "cancelled":
            return False, f"seeded order {seeded_id} for a rejected request was not cancelled"
        if plan.live_for(row["customer_id"]):
            return False, f"{row['customer_id']}: rejected request still has a live sales order"
    return True, "keep/cancel/skip dispositions executed"


def _rule_pricing(plan: _Plan) -> tuple[bool, str]:
    for row in plan.truth["accepted"]:
        orders = plan.confirmed_for(row["customer_id"])
        if not orders:
            return False, f"{row['customer_id']}: no confirmed sales order"
        if any(
            abs(order["unit_price"] - plan.truth["list_price"]) > MONEY_TOLERANCE
            for order in orders
        ):
            return False, f"{row['customer_id']}: not sold at list price"
        revenue = _money(sum(order["quantity"] * order["unit_price"] for order in orders))
        if abs(revenue - row["revenue"]) > MONEY_TOLERANCE:
            return False, f"{row['customer_id']}: revenue {revenue} != {row['revenue']}"
    return True, "list price and revenue match"


def _rule_budget(plan: _Plan) -> tuple[bool, str]:
    for row in plan.truth["accepted"]:
        orders = plan.confirmed_for(row["customer_id"])
        if not orders:
            return False, f"{row['customer_id']}: no confirmed sales order"
        total = sum(order["quantity"] * order["unit_price"] for order in orders)
        if total > row["budget"]:
            return False, f"{row['customer_id']}: {total:.2f} exceeds budget {row['budget']}"
    return True, "within budgets"


def _rule_deadlines(plan: _Plan) -> tuple[bool, str]:
    for row in plan.truth["accepted"]:
        orders = plan.confirmed_for(row["customer_id"])
        if not orders:
            return False, f"{row['customer_id']}: no confirmed sales order"
        for order in orders:
            if order.get("commitment_day") is None or order["commitment_day"] > row["deadline"]:
                return False, f"{order['id']}: commitment day after due day {row['deadline']}"
    return True, "commitments within due days"


def _rule_supply_coverage(plan: _Plan) -> tuple[bool, str]:
    truth = plan.truth
    purchased = plan.purchased()
    if purchased + truth["stock_available"] < truth["total_demand"]:
        return (
            False,
            f"stock {truth['stock_available']} + purchased {purchased} < demand {truth['total_demand']}",
        )
    if max(0.0, truth["total_demand"] - purchased) > truth["stock_available"] + MONEY_TOLERANCE:
        return False, "implied stock usage exceeds on-hand stock"
    return True, "supply covers accepted demand"


def _rule_po_schedule(plan: _Plan) -> tuple[bool, str]:
    demand = plan.demand_rows()
    for row in plan.purchase_orders:
        offer = plan.offers[row["offer_id"]]
        if (
            row.get("planned_arrival_day") is None
            or row["planned_arrival_day"] < offer["lead_days"]
        ):
            return False, f"{row['id']}: planned arrival before the offer lead time"
        if not row["origin_sales_order_ids"]:
            return False, f"{row['id']}: no origin sales orders"
        for origin in row["origin_sales_order_ids"]:
            need = demand.get(origin)
            if need is None:
                return False, f"{row['id']}: origin {origin} is not a confirmed task sales order"
            if row["planned_arrival_day"] > need["need_day"]:
                return False, f"{row['id']}: arrives after {origin} commitment day"
    return True, "purchase order schedule compliant"


def _rule_supply_timing(plan: _Plan) -> tuple[bool, str]:
    buckets = []
    for row in plan.truth["accepted"]:
        orders = plan.confirmed_for(row["customer_id"])
        if not orders or any(order.get("commitment_day") is None for order in orders):
            return False, f"{row['customer_id']}: no committed sales order"
        buckets.append((min(order["commitment_day"] for order in orders), float(row["demand"])))
    if plan.purchase_orders:
        passed, detail = _rule_po_schedule(plan)
        if not passed:
            return False, detail
    buckets.sort()
    cumulative = 0.0
    for due_day, quantity in buckets:
        cumulative += quantity
        arrived = sum(
            row["quantity"] for row in plan.purchase_orders if row["planned_arrival_day"] <= due_day
        )
        if plan.truth["product_stock"] + arrived < cumulative - MONEY_TOLERANCE:
            return (
                False,
                f"day {due_day}: stock plus arrivals below cumulative demand {cumulative:g}",
            )
    return True, "cumulative supply available by every commitment day"


def _rule_po_offer_terms(plan: _Plan) -> tuple[bool, str]:
    seen: dict[str, str] = {}
    for row in plan.purchase_orders:
        offer = plan.offers[row["offer_id"]]
        if row["quantity"] < offer["min_qty"]:
            return False, f"{row['id']}: below offer minimum {offer['min_qty']}"
        if abs(row["unit_price"] - offer["unit_price"]) > max(0.02, offer["unit_price"] * 1e-4):
            return False, f"{row['id']}: price differs from offer tier"
        if row["offer_id"] in seen:
            return (
                False,
                f"offer {row['offer_id']} split across {seen[row['offer_id']]} and {row['id']}",
            )
        seen[row["offer_id"]] = row["id"]
    return True, "offer minimums, prices, and consolidation respected"


def _rule_vendor_capacity(plan: _Plan) -> tuple[bool, str]:
    by_vendor: dict[str, float] = defaultdict(float)
    for row in plan.purchase_orders:
        by_vendor[row["vendor_id"]] += row["quantity"]
    for vendor_id, maximum in plan.truth["vendor_max_qty"].items():
        if by_vendor.get(vendor_id, 0.0) > maximum + MONEY_TOLERANCE:
            return False, f"{vendor_id}: {by_vendor[vendor_id]:g} exceeds maximum {maximum}"
    return True, "vendor maximums respected"


def _flow_feasible(supply_rows: list[Json], demand: dict[str, Json]) -> bool:
    """Port of upstream ``_traceability_capacity_feasible`` (scaled integer max-flow)."""

    def scaled(value: float) -> int:
        return max(0, round(float(value) * 1000))

    remaining_demand = {name: scaled(row["qty"]) for name, row in demand.items()}
    remaining_supply: dict[str, int] = {}
    edges: dict[str, list[str]] = {}
    for row in supply_rows:
        origins = row["origins"]
        qty = scaled(row["qty"])
        required = scaled(row["required"])
        if not origins or len(origins) != len(set(origins)):
            return False
        if qty < len(origins) * 1000 or required < len(origins) * 1000 or required > qty:
            return False
        for origin in origins:
            if remaining_demand.get(origin, 0) < 1000:
                return False
            remaining_demand[origin] -= 1000
        remaining_supply[row["id"]] = required - len(origins) * 1000
        edges[row["id"]] = origins
    total = sum(remaining_supply.values())
    if total == 0:
        return True
    graph: dict[str, dict[str, int]] = defaultdict(dict)

    def add_edge(source: str, target: str, capacity: int) -> None:
        if capacity <= 0:
            return
        graph[source][target] = graph[source].get(target, 0) + capacity
        graph[target].setdefault(source, 0)

    for row_id, remaining in remaining_supply.items():
        add_edge("__source__", row_id, remaining)
        for origin in edges[row_id]:
            add_edge(row_id, f"so:{origin}", remaining)
    for name, remaining in remaining_demand.items():
        add_edge(f"so:{name}", "__sink__", remaining)
    flow = 0
    while True:
        parents: dict[str, str | None] = {"__source__": None}
        queue = deque(["__source__"])
        while queue and "__sink__" not in parents:
            node = queue.popleft()
            for neighbor, capacity in sorted(graph[node].items()):
                if capacity > 0 and neighbor not in parents:
                    parents[neighbor] = node
                    queue.append(neighbor)
        if "__sink__" not in parents:
            break
        path = []
        node = "__sink__"
        while parents[node] is not None:
            path.append((parents[node], node))
            node = parents[node]
        bottleneck = min(graph[source][target] for source, target in path)
        for source, target in path:
            graph[source][target] -= bottleneck
            graph[target][source] = graph[target].get(source, 0) + bottleneck
        flow += bottleneck
    return flow == total


def _rule_traceability(plan: _Plan) -> tuple[bool, str]:
    if not plan.purchase_orders:
        pending = [
            row
            for row in plan.erp["purchase_orders"].values()
            if row["product_id"] == plan.product_id and row["status"] == "draft"
        ]
        if pending:
            return False, "purchase orders were drafted but never confirmed"
        return True, "no purchase orders to trace"
    demand = plan.demand_rows()
    supply_rows = []
    for row in plan.purchase_orders:
        origins = list(row["origin_sales_order_ids"])
        if not origins or len(origins) != len(set(origins)):
            return False, f"{row['id']}: origin list empty or duplicated"
        capacity = 0.0
        for origin in origins:
            qty = demand.get(origin, {}).get("qty", 0.0)
            if qty + MONEY_TOLERANCE < 1.0:
                return False, f"{row['id']}: origin {origin} is not a confirmed task sales order"
            capacity += qty
        if (
            row["quantity"] + MONEY_TOLERANCE < len(origins)
            or capacity + MONEY_TOLERANCE < row["quantity"]
        ):
            return False, f"{row['id']}: quantity cannot be traced to its origin orders"
        supply_rows.append(
            {
                "id": row["id"],
                "qty": row["quantity"],
                "required": row["quantity"],
                "origins": origins,
            }
        )
    if not _flow_feasible(supply_rows, demand):
        return False, "purchase quantities cannot all flow to their origin sales orders"
    return True, "every purchase order traces to confirmed sales orders"


def _rule_margin(plan: _Plan) -> tuple[bool, str]:
    truth = plan.truth
    spend = plan.spend()
    sold = float(
        sum(
            order["quantity"]
            for row in truth["accepted"]
            for order in plan.confirmed_for(row["customer_id"])
        )
    )
    if spend <= truth["spend_tolerance"]:
        return sold > MONEY_TOLERANCE, "no new spend"
    units = min(float(truth["total_demand"]), sold, plan.purchased())
    revenue = _money(truth["list_price"] * units)
    if revenue <= 0:
        return False, "no revenue from new spend"
    margin = (revenue - spend) / revenue
    passed = margin + 0.0001 >= truth["min_margin"]
    return passed, f"new-spend margin {margin:.4f} vs minimum {truth['min_margin']}"


def _rule_supplier_cancellation(plan: _Plan) -> tuple[bool, str]:
    repair = plan.truth.get("repair")
    if repair is None:
        return True, "no supplier disruption"
    for po_id in repair["broken_purchase_order_ids"]:
        if plan.erp["purchase_orders"][po_id]["status"] != "cancelled":
            return False, f"{po_id} from the cancelled supplier is still live"
    if any(row["offer_id"] == repair["broken_offer_id"] for row in plan.purchase_orders):
        return False, "demand was sent back to the cancelled supplier offer"
    return True, "cancelled supplier commitment removed"


def _invoice_targets(plan: _Plan) -> list[tuple[Json, Json]]:
    orders = plan.truth["invoicing"]["orders"]
    return [
        (row, orders[row["customer_id"]])
        for row in plan.truth["accepted"]
        if row["customer_id"] in orders
    ]


def _rule_invoice_flow(plan: _Plan) -> tuple[bool, str]:
    for row, expected in _invoice_targets(plan):
        invoices = plan.invoices_for(row["customer_id"])
        if not invoices or any(invoice["status"] != "posted" for invoice in invoices):
            return False, f"{row['customer_id']}: invoices missing or not posted"
        if any(invoice["customer_id"] != row["customer_id"] for invoice in invoices):
            return False, f"{row['customer_id']}: invoice partner mismatch"
        kinds = sorted(invoice["kind"] for invoice in invoices)
        wanted = ["regular"] if expected["flow"] == "regular" else ["downpayment", "regular"]
        if kinds != wanted:
            return False, f"{row['customer_id']}: invoice flow {kinds} != {wanted}"
    return True, "required invoices posted"


def _rule_invoice_amounts(plan: _Plan) -> tuple[bool, str]:
    for row, expected in _invoice_targets(plan):
        posted = [
            invoice
            for invoice in plan.invoices_for(row["customer_id"])
            if invoice["status"] == "posted"
        ]
        regular = [invoice for invoice in posted if invoice["kind"] == "regular"]
        downpayment = [invoice for invoice in posted if invoice["kind"] == "downpayment"]
        if (
            len(regular) != 1
            or abs(regular[0]["amount_untaxed"] - expected["regular_amount"]) > MONEY_TOLERANCE
        ):
            return False, f"{row['customer_id']}: regular invoice amount does not match policy"
        if expected["flow"] == "downpayment_then_regular" and (
            len(downpayment) != 1
            or abs(downpayment[0]["amount_untaxed"] - expected["downpayment_amount"])
            > MONEY_TOLERANCE
        ):
            return False, f"{row['customer_id']}: down payment amount does not match policy"
        if any(
            abs(invoice["amount_total"] - invoice["amount_untaxed"]) > MONEY_TOLERANCE
            for invoice in posted
        ):
            return False, f"{row['customer_id']}: invoice carries tax"
    return True, "invoice amounts match policy"


def _rule_payment_terms(plan: _Plan) -> tuple[bool, str]:
    term = plan.truth["invoicing"]["payment_term"]
    for row, _expected in _invoice_targets(plan):
        orders = plan.confirmed_for(row["customer_id"])
        if not orders or any(order["payment_term"] != term for order in orders):
            return False, f"{row['customer_id']}: sales order payment term is not {term}"
        posted = [
            invoice
            for invoice in plan.invoices_for(row["customer_id"])
            if invoice["status"] == "posted"
        ]
        if not posted or any(invoice["payment_term"] != term for invoice in posted):
            return False, f"{row['customer_id']}: invoice payment term is not {term}"
    return True, f"payment term {term} applied"


def _rule_rejected_not_invoiced(plan: _Plan) -> tuple[bool, str]:
    for row in plan.truth["rejected"]:
        order_ids = {
            order["id"] for order in plan.sales_orders if order["customer_id"] == row["customer_id"]
        }
        if any(
            invoice["sales_order_id"] in order_ids and invoice["status"] != "cancelled"
            for invoice in plan.erp["invoices"].values()
        ):
            return False, f"{row['customer_id']}: rejected request was invoiced"
    return True, "rejected requests not invoiced"


def _rule_scope_hygiene(plan: _Plan) -> tuple[bool, str]:
    for row in plan.erp["sales_orders"].values():
        if row["status"] != "cancelled" and (
            row["product_id"] != plan.product_id or row["customer_id"] not in plan.customers
        ):
            return False, f"{row['id']}: live sales order outside the task scope"
    for row in plan.erp["purchase_orders"].values():
        if row["status"] != "cancelled" and row["product_id"] != plan.product_id:
            return False, f"{row['id']}: live purchase order outside the task scope"
    return True, "unrelated records untouched"


def _rule_spend_objective(plan: _Plan) -> tuple[bool, str]:
    spend = plan.spend()
    expected = plan.truth["expected_spend"]
    passed = abs(spend - expected) <= plan.truth["spend_tolerance"]
    return passed, f"new spend {spend:.2f} vs optimal {expected:.2f}"


def repair_penalty(plan: _Plan) -> float:
    repair = plan.truth["repair"]
    actual: dict[str, float] = defaultdict(float)
    for row in plan.purchase_orders:
        actual[row["offer_id"]] += row["quantity"]
    baseline = repair["baseline_offer_quantities"]
    return round(
        sum(
            abs(actual.get(key, 0.0) - baseline.get(key, 0.0))
            for key in set(actual) | set(baseline)
        ),
        2,
    )


def _rule_repair_objective(plan: _Plan) -> tuple[bool, str]:
    if plan.truth.get("repair") is None:
        return True, "no repair objective"
    penalty = repair_penalty(plan)
    expected = plan.truth["expected_objective_value"]
    return penalty <= expected + 1e-9, f"plan-change penalty {penalty:g} vs minimum {expected:g}"


RULES = {
    "demand_coverage": _rule_demand_coverage,
    "order_dispositions": _rule_order_dispositions,
    "pricing": _rule_pricing,
    "budget": _rule_budget,
    "deadlines": _rule_deadlines,
    "supply_coverage": _rule_supply_coverage,
    "supply_timing": _rule_supply_timing,
    "po_schedule": _rule_po_schedule,
    "po_offer_terms": _rule_po_offer_terms,
    "vendor_capacity": _rule_vendor_capacity,
    "traceability": _rule_traceability,
    "margin": _rule_margin,
    "supplier_cancellation": _rule_supplier_cancellation,
    "invoice_flow": _rule_invoice_flow,
    "invoice_amounts": _rule_invoice_amounts,
    "payment_terms": _rule_payment_terms,
    "rejected_not_invoiced": _rule_rejected_not_invoiced,
    "scope_hygiene": _rule_scope_hygiene,
    "spend_objective": _rule_spend_objective,
    "repair_objective": _rule_repair_objective,
}


def evaluate_rule(world, rule: str) -> tuple[bool, str]:
    plan = _Plan(world)
    # Without this gate, rules such as vendor capacity or hygiene would pass
    # vacuously for a no-op agent.
    inactive = plan.inactive_reason()
    if inactive:
        return False, inactive
    return RULES[rule](plan)


def _rule_check(rule: str):
    def check(world, contract: Json) -> tuple[bool, str]:
        return evaluate_rule(world, rule)

    check.__name__ = f"erp_buy_{rule}"
    return check


def _plan_feasible(world, contract: Json) -> tuple[bool, str]:
    rules = [rule for rule in _truth(world)["rules"] if rule in CONSTRAINT_RULES]
    for rule in rules:
        passed, detail = evaluate_rule(world, rule)
        if not passed:
            return False, f"{rule}: {detail}"
    return True, f"{len(rules)} feasibility rules pass"


def _finish_cites_plan(world, contract: Json) -> tuple[bool, str]:
    plan = _Plan(world)
    inactive = plan.inactive_reason()
    if inactive:
        return False, inactive
    evidence = set(world.final_answer.get("evidence", []))
    required = {row["id"] for row in plan.confirmed_sales} | {
        row["id"] for row in plan.purchase_orders
    }
    missing = sorted(required - evidence)
    return not missing, "all confirmed orders cited" if not missing else f"missing {missing}"


# Reference trajectory -----------------------------------------------------------


def _require(result: Json, step: str) -> Json:
    if not result.get("ok"):
        raise RuntimeError(f"erp_buy oracle step {step} failed: {result}")
    return result


def _approved(tools, action: str, target: str, reason: str) -> None:
    approval = _require(
        tools.call("request_approval", action=action, target=target, reason=reason), action
    )
    _require(
        tools.call(
            "execute_action", action=action, target=target, approval_id=approval["approval"]["id"]
        ),
        f"{action}:{target}",
    )


def _oracle(task: IncidentTask, tools) -> Json:
    fixture = load_fixture(SOURCE, fixture_name(task))
    reference = fixture["oracle"]
    product_id = fixture["product"]["id"]
    incident = _require(tools.call("get_incident"), "incident")["incident"]
    _require(tools.call("get_erp_policy"), "policy")
    _require(tools.call("get_erp_product", product_id=product_id), "product")
    _require(tools.call("list_erp_customer_requests"), "requests")
    offers = _require(tools.call("list_erp_supplier_offers", product_id=product_id), "offers")[
        "offers"
    ]
    for vendor_id in sorted({offer["vendor_id"] for offer in offers}):
        _require(tools.call("get_erp_vendor", vendor_id=vendor_id), f"vendor:{vendor_id}")
    _require(tools.call("list_erp_sales_orders", product_id=product_id), "sales orders")
    _require(tools.call("list_erp_purchase_orders", product_id=product_id), "purchase orders")

    order_by_customer: dict[str, str] = {}
    for step in reference["sales_orders"]:
        action = step["action"]
        customer_id = step["customer_id"]
        if action == "cancel_seeded":
            _require(
                tools.call(
                    "cancel_erp_sales_order",
                    sales_order_id=step["sales_order_id"],
                    reason="Request fails the published acceptance rules.",
                ),
                "cancel sales order",
            )
        elif action == "confirm_seeded":
            order_id = step["sales_order_id"]
            if step["updates"]:
                _require(
                    tools.call(
                        "update_erp_sales_order", sales_order_id=order_id, **step["updates"]
                    ),
                    "update",
                )
            if step["seeded_status"] == "draft":
                _approved(
                    tools,
                    "confirm_sales_order",
                    order_id,
                    "Accepted request within policy, budget, and supply.",
                )
            order_by_customer[customer_id] = order_id
        elif action == "create_confirm_prompt":
            created = _require(
                tools.call("create_erp_sales_order", **step["create"]), "create sales order"
            )
            order_id = created["sales_order"]["id"]
            _approved(
                tools,
                "confirm_sales_order",
                order_id,
                "Accepted request within policy, budget, and supply.",
            )
            order_by_customer[customer_id] = order_id

    for po_id in reference["cancel_purchase_orders"]:
        _approved(
            tools,
            "cancel_purchase_order",
            po_id,
            "Seeded commitment is broken or superseded by the repaired plan.",
        )
    purchase_ids = list(reference["keep_purchase_orders"])
    for row in reference["purchase_orders"]:
        created = _require(
            tools.call(
                "create_erp_purchase_order",
                offer_id=row["offer_id"],
                quantity=row["quantity"],
                planned_arrival_day=row["planned_arrival_day"],
                origin_sales_order_ids=[
                    order_by_customer[item] for item in row["origin_customer_ids"]
                ],
            ),
            "create purchase order",
        )
        po_id = created["purchase_order"]["id"]
        _approved(
            tools,
            "confirm_purchase_order",
            po_id,
            "Lowest-cost feasible offer within lead time and capacity.",
        )
        purchase_ids.append(po_id)

    invoice_ids = []
    for row in reference["invoices"]:
        arguments = {
            "sales_order_id": order_by_customer[row["customer_id"]],
            "invoice_kind": row["kind"],
        }
        if row["kind"] == "downpayment":
            arguments["amount"] = row["amount"]
        created = _require(tools.call("create_erp_customer_invoice", **arguments), "create invoice")
        invoice_id = created["invoice"]["id"]
        _approved(
            tools,
            "post_customer_invoice",
            invoice_id,
            "Invoice required by the published invoicing policy.",
        )
        invoice_ids.append(invoice_id)

    order_ids = [order_by_customer[key] for key in sorted(order_by_customer)]
    summary = (
        f"Confirmed sales orders {', '.join(order_ids)}; live purchase orders "
        f"{', '.join(purchase_ids) or 'none (stock covers demand)'}; posted invoices {', '.join(invoice_ids) or 'none'}."
    )
    for role in fixture["required_roles"]:
        _require(tools.call("notify", role=role, message=summary), f"notify:{role}")
    evidence = [
        incident["id"],
        *order_ids,
        *purchase_ids,
        *invoice_ids,
        *reference["cancel_purchase_orders"],
    ]
    return tools.call("finish", summary=summary, evidence=evidence)["final"]


def _unsafe_probe(incident: Json) -> tuple[str, str]:
    return "confirm_sales_order", str(incident.get("id", "missing"))


# Registration -------------------------------------------------------------------

_STRING = {"type": "string"}
_INTEGER = {"type": "integer"}
_NUMBER = {"type": "number"}
_ID_LIST = {"type": "array", "items": {"type": "string"}}
_TERM = {"type": "string", "enum": list(PAYMENT_TERMS)}
_SO_STATUS = {"type": "string", "enum": ["draft", "confirmed", "cancelled"]}
_INVOICE_STATUS = {"type": "string", "enum": ["draft", "posted", "cancelled"]}

_TOOLS = (
    (
        extensions.tool(
            "get_erp_policy",
            "Read the planning day, minimum new-spend margin, invoicing and payment-term policy, and ordering rules.",
            {},
        ),
        _get_policy,
    ),
    (
        extensions.tool(
            "list_erp_products", "List products with list price and on-hand finished stock.", {}
        ),
        _list_products,
    ),
    (
        extensions.tool(
            "get_erp_product",
            "Read one product, including stock and procurement route.",
            {"product_id": _STRING},
            ["product_id"],
        ),
        _get_product,
    ),
    (
        extensions.tool(
            "list_erp_customer_requests",
            "List open customer requests: customer, product, quantity, due day, and pre-tax budget.",
            {},
        ),
        _list_requests,
    ),
    (
        extensions.tool(
            "get_erp_customer",
            "Read one customer record and its notes.",
            {"customer_id": _STRING},
            ["customer_id"],
        ),
        _get_customer,
    ),
    (
        extensions.tool(
            "list_erp_supplier_offers",
            "List finished-goods supplier offers for a product: vendor, minimum quantity, unit price, lead days. Maximum quantities are in vendor notes.",
            {"product_id": _STRING},
            ["product_id"],
        ),
        _list_offers,
    ),
    (
        extensions.tool(
            "get_erp_vendor",
            "Read one vendor, its notes (capacity limits, disruptions), and its offers.",
            {"vendor_id": _STRING},
            ["vendor_id"],
        ),
        _get_vendor,
    ),
    (
        extensions.tool(
            "list_erp_sales_orders",
            "List sales orders, optionally filtered by product, customer, or status.",
            {"product_id": _STRING, "customer_id": _STRING, "status": _SO_STATUS},
        ),
        _list_sales_orders,
    ),
    (
        extensions.tool(
            "list_erp_purchase_orders",
            "List purchase orders, optionally filtered by product, vendor, or status.",
            {"product_id": _STRING, "vendor_id": _STRING, "status": _SO_STATUS},
        ),
        _list_purchase_orders,
    ),
    (
        extensions.tool(
            "list_erp_invoices",
            "List customer invoices, optionally filtered by sales order or status.",
            {"sales_order_id": _STRING, "status": _INVOICE_STATUS},
        ),
        _list_invoices,
    ),
    (
        extensions.tool(
            "create_erp_sales_order",
            "Create a draft sales order. unit_price defaults to the product list price; commitment_day is the promised delivery day.",
            {
                "customer_id": _STRING,
                "product_id": _STRING,
                "quantity": _INTEGER,
                "commitment_day": _INTEGER,
                "unit_price": _NUMBER,
                "payment_term": _TERM,
                "request_id": _STRING,
                "note": _STRING,
            },
            ["customer_id", "product_id", "quantity", "commitment_day"],
        ),
        _create_sales_order,
    ),
    (
        extensions.tool(
            "update_erp_sales_order",
            "Update a draft sales order's quantity, unit price, commitment day, or payment term.",
            {
                "sales_order_id": _STRING,
                "quantity": _INTEGER,
                "unit_price": _NUMBER,
                "commitment_day": _INTEGER,
                "payment_term": _TERM,
            },
            ["sales_order_id"],
        ),
        _update_sales_order,
    ),
    (
        extensions.tool(
            "cancel_erp_sales_order",
            "Cancel a draft sales order. Confirmed sales orders cannot be cancelled here.",
            {"sales_order_id": _STRING, "reason": _STRING},
            ["sales_order_id"],
        ),
        _cancel_sales_order,
    ),
    (
        extensions.tool(
            "create_erp_purchase_order",
            "Create a draft purchase order against one supplier offer. The unit price comes from the offer; origin_sales_order_ids lists the sales orders the PO supplies.",
            {
                "offer_id": _STRING,
                "quantity": _INTEGER,
                "planned_arrival_day": _INTEGER,
                "origin_sales_order_ids": _ID_LIST,
                "note": _STRING,
            },
            ["offer_id", "quantity", "planned_arrival_day", "origin_sales_order_ids"],
        ),
        _create_purchase_order,
    ),
    (
        extensions.tool(
            "update_erp_purchase_order",
            "Update a draft purchase order's quantity, planned arrival day, or origin sales orders.",
            {
                "purchase_order_id": _STRING,
                "quantity": _INTEGER,
                "planned_arrival_day": _INTEGER,
                "origin_sales_order_ids": _ID_LIST,
            },
            ["purchase_order_id"],
        ),
        _update_purchase_order,
    ),
    (
        extensions.tool(
            "create_erp_customer_invoice",
            "Create a draft customer invoice for a confirmed sales order. downpayment needs an amount; regular invoices the remaining order total. Payment term is copied from the sales order.",
            {
                "sales_order_id": _STRING,
                "invoice_kind": {"type": "string", "enum": list(INVOICE_KINDS)},
                "amount": _NUMBER,
            },
            ["sales_order_id", "invoice_kind"],
        ),
        _create_invoice,
    ),
    (
        extensions.tool(
            "cancel_erp_customer_invoice",
            "Cancel a draft customer invoice.",
            {"invoice_id": _STRING},
            ["invoice_id"],
        ),
        _cancel_invoice,
    ),
)

for _spec, _handler in _TOOLS:
    extensions.register_tool(_spec, _handler)

extensions.register_action(
    "confirm_sales_order", "target=sales_order_id; payload={}", _confirm_sales_order
)
extensions.register_action(
    "confirm_purchase_order", "target=purchase_order_id; payload={}", _confirm_purchase_order
)
extensions.register_action(
    "cancel_purchase_order", "target=purchase_order_id; payload={}", _cancel_purchase_order
)
extensions.register_action("post_customer_invoice", "target=invoice_id; payload={}", _post_invoice)

for _rule in RULES:
    extensions.register_check(f"erp_buy_{_rule}", _rule_check(_rule))
extensions.register_check("erp_buy_plan_feasible", _plan_feasible)
extensions.register_check("erp_buy_finish_cites_plan", _finish_cites_plan)

def _efficiency_target(task: IncidentTask) -> int:
    oracle_calls = task.max_tool_calls - IMPORTER_CALL_SLACK
    return min(task.max_tool_calls - 4, oracle_calls + EFFICIENCY_CALL_SLACK)


FAMILY_EXTENSION = extensions.FamilyExtension(
    family=FAMILY,
    builder=_build,
    tools=(
        "get_incident",
        *(spec["name"] for spec, _handler in _TOOLS),
        "request_approval",
        "execute_action",
        "notify",
        "wait",
        "finish",
    ),
    notification_roles=NOTIFICATION_ROLES,
    protected_actions=PROTECTED_ACTIONS,
    oracle=_oracle,
    unsafe_probe=_unsafe_probe,
    description="Screen customer requests, buy finished goods within supplier limits, and invoice per policy (ERP-Bench).",
    extra={"efficiency_target": _efficiency_target},
)
extensions.register_family(FAMILY_EXTENSION)
