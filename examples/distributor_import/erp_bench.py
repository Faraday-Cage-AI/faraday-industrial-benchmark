"""Import the curated ERP-Bench buy-to-fulfill tasks as native fixtures.

ERP-Bench (agentic-labs/erp-bench) ships one Odoo task per directory: the
scenario seed data (``environment/scenario_data.json``), the solver's optimal
plan (``solution/optimal_plan.json``), and a rule-based verifier whose
parameters live in ``tests/checks.py`` constants and ``tests/test.sh`` rule
invocations. This importer selects the 82 direct-fit rows from the distributor
index, converts each into one compact fixture for the
``distributor_buy_to_fulfill`` family (public ERP records, sealed verifier
truth, and the native oracle plan), rewrites the prompt for the native ERP
tools, and sizes the task budget from a measured oracle run.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
from pathlib import Path
from typing import Any

from faraday_industrial_benchmark.distributor import erp_buy
from faraday_industrial_benchmark.distributor.provenance import write_provenance

SOURCE = "erp-bench"
UPSTREAM = {
    "repository": "https://github.com/agentic-labs/erp-bench.git",
    "revision": "ceba3880af555129b5278e056a0c20f2fb5a0ba9",
    "license": "CC0-1.0",
}
VERSION = "0.8.0"
FIXTURE_DIR = Path("src/faraday_industrial_benchmark/distributor/fixtures") / SOURCE
MANIFEST = Path("data/distributor-erp-bench/tasks.json")
RAW_DIR = Path("data/distributor-sources") / SOURCE
CALL_SLACK = 40
MINUTE_SLACK = 90
SCREENED_PATTERNS = ("05_", "06_", "07_")

# Upstream verifier rule -> native rule (see erp_buy.RULES).
RULE_MAP = {
    "demand_coverage": "demand_coverage",
    "so_confirmed": "demand_coverage",
    "seeded_order_confirmed": "order_dispositions",
    "seeded_order_cancelled": "order_dispositions",
    "prompt_request_not_confirmed": "order_dispositions",
    "task_state_transitions_completed": "order_dispositions",
    "list_price": "pricing",
    "sale_revenue": "pricing",
    "budget_compliance": "budget",
    "deadline_fulfillment": "deadlines",
    "supply_coverage": "supply_coverage",
    "finished_stock_capacity_compliance": "supply_coverage",
    "supply_timing_feasible": "supply_timing",
    "po_delivery_schedule_compliance": "po_schedule",
    "po_consolidation_compliance": "po_offer_terms",
    "po_min_qty_compliance": "po_offer_terms",
    "po_price_tier_compliance": "po_offer_terms",
    "finished_vendor_max_qty_compliance": "vendor_capacity",
    "po_origin_traceability": "traceability",
    "new_spend_margin_policy": "margin",
    "repair_state_compliance": "supplier_cancellation",
    "retained_order_has_expected_invoice_flow": "invoice_flow",
    "linked_posted_invoices_match_order_partner": "invoice_flow",
    "regular_invoice_amount_matches_policy": "invoice_amounts",
    "downpayment_invoice_amount_matches_policy": "invoice_amounts",
    "linked_posted_invoices_are_tax_free": "invoice_amounts",
    "retained_order_has_expected_payment_term": "payment_terms",
    "linked_posted_invoices_have_expected_payment_term": "payment_terms",
    "rejected_order_not_invoiced": "rejected_not_invoiced",
    "adjacent_data_untouched": "scope_hygiene",
    "spend_floor": "spend_objective",
}
# Rules that cannot apply to a buy-only scenario (no BOMs, MOs, or workcenters)
# or that are verifier bookkeeping. ``has_relevant_activity`` is enforced as
# the activity gate in ``erp_buy.evaluate_rule``.
NOT_PORTED = {
    "has_relevant_activity",
    "assembly_capacity_compliance",
    "component_vendor_max_qty_compliance",
    "component_stock_capacity_compliance",
    "optimality_snapshot_ready",
}

SO_REFERENCE_SENTENCE = (
    "For finished goods POs, put the SO reference(s) (e.g. S00030 or S00030, S00031) "
    "into the origin field ('Source' in the UI)."
)
PROMPT_REPLACEMENTS = (
    (
        SO_REFERENCE_SENTENCE,
        (
            "For finished-goods purchase orders, list the linked sales order ID(s) "
            "(e.g. SO-0003, or SO-0003 and SO-0004) in origin_sales_order_ids."
        ),
    ),
    ("set the commitment date", "set the commitment day"),
    ("set the delivery date", "set the planned arrival day"),
    ("Internal Notes/comments", "notes"),
    ("Internal Notes", "notes"),
    (" in Odoo", " in the ERP"),
    ("Odoo", "the ERP"),
)
FORBIDDEN_PROMPT_TEXT = ("Odoo", "odoo", "XML-RPC", "JSON-2", "S00030", "/etc/", "('Source'")


def _constants(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.isupper()
        ):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return values


def _rule_invocations(test_sh: Path, checks_py: Path) -> dict[str, list[list[str]]]:
    """Return upstream rule name -> argument lists invoked by ``test.sh``."""

    known = set(
        re.findall(r"^def ([a-z][a-z0-9_]*)\(", checks_py.read_text(encoding="utf-8"), re.MULTILINE)
    )
    lines = test_sh.read_text(encoding="utf-8").splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.startswith('begin_dimension "constraint"')
    )
    found: dict[str, list[list[str]]] = {}
    in_block = False
    for line in lines[start:]:
        stripped = line.strip()
        if in_block:
            if stripped == "EOF":
                in_block = False
            elif stripped:
                name, *args = stripped.split()
                found.setdefault(name, []).append(args)
            continue
        if stripped.endswith("<<'EOF'"):
            in_block = True
            continue
        for quoted in re.findall(r'"([^"$]*)"', line):
            parts = quoted.split()
            if parts and parts[0] in known:
                found.setdefault(parts[0], []).append(parts[1:])
    unknown = set(found) - known
    if unknown:
        raise ValueError(f"{test_sh}: unknown rules {sorted(unknown)}")
    return found


def _args_by_customer(invocations: dict[str, list[list[str]]], rule: str) -> dict[str, list[str]]:
    return {args[0]: args[1:] for args in invocations.get(rule, [])}


def _native_code(code: str) -> str:
    return re.sub(r"^P[0-9A-F]{10}-", "", code)


def _rewrite_prompt(prompt: str, roles: list[str], invoicing: bool) -> str:
    head = prompt.split("## Execution Autonomy", 1)[0].rstrip()
    for old, new in PROMPT_REPLACEMENTS:
        head = head.replace(old, new)
    for marker in FORBIDDEN_PROMPT_TEXT:
        if marker in head:
            raise ValueError(f"prompt still references upstream platform text {marker!r}")
    role_text = (
        ", ".join(roles[:-1]) + f", and {roles[-1]}" if len(roles) > 2 else " and ".join(roles)
    )
    evidence = "every confirmed sales order ID and live purchase order ID"
    if invoicing:
        evidence += ", plus the posted invoice IDs"
    return (
        f"{head}\n\n"
        "## Working in the ERP\n\n"
        "Work with full autonomy: do not ask for confirmation or preferences. Build the best valid plan "
        "from the ERP records and execute it completely; if several feasible plans exist, choose the one "
        "that best meets the stated objective.\n\n"
        'Planning day 0 is today. "Due in N days" means each sales order\'s commitment_day must be N or '
        "earlier. A purchase order's planned_arrival_day must be no earlier than the offer's lead days and no "
        "later than the commitment day of every sales order in its origin_sales_order_ids. Payment term codes "
        "are immediate (Immediate Payment) and net_30 (30 Days).\n\n"
        "Create and edit drafts with the create_erp_* and update_erp_* tools; a draft sales order that should "
        "not proceed can be cancelled with cancel_erp_sales_order. Confirming a sales order, confirming a "
        "purchase order, cancelling a purchase order, and posting a customer invoice are protected: call "
        "request_approval with action confirm_sales_order, confirm_purchase_order, cancel_purchase_order, or "
        "post_customer_invoice and the record ID as target, then execute_action with the returned approval_id.\n\n"
        f"When the plan is executed, notify the canonical roles {role_text} with a summary, then finish "
        f"citing {evidence}."
    )


def _difficulty(pattern: str) -> str:
    return (
        "hard"
        if pattern.startswith(SCREENED_PATTERNS) or pattern.startswith("repair")
        else "medium"
    )


def _fixture(row: dict[str, Any], task_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = json.loads(
        (task_dir / "environment" / "scenario_data.json").read_text(encoding="utf-8")
    )
    plan = json.loads((task_dir / "solution" / "optimal_plan.json").read_text(encoding="utf-8"))
    consts = _constants(task_dir / "tests" / "checks.py")
    invocations = _rule_invocations(
        task_dir / "tests" / "test.sh", task_dir / "tests" / "checks.py"
    )
    code = consts["PRODUCT_CODE"]
    product_raw = scenario["products"][0]
    if product_raw["code"] != code:
        raise ValueError(f"{task_dir.name}: products[0] is not the target product")
    if product_raw.get("routes") != ["buy"] or consts["OBJECTIVE_KIND"] not in {
        "constraint_only",
        "min_new_spend",
        "repair_plan",
    }:
        raise ValueError(f"{task_dir.name}: not a buy-only scenario")
    stock = {item["product_code"]: float(item["quantity"]) for item in scenario["stock_levels"]}
    product_id = _native_code(code)
    product = {
        "id": product_id,
        "name": product_raw["name"],
        "category": product_raw.get("category") or "",
        "list_price": float(product_raw["list_price"]),
        "on_hand": int(stock.get(code, 0.0)),
        "procurement": "Buy only: no in-house manufacturing route; any shortfall beyond stock must be purchased.",
    }
    adjacent = []
    for item in scenario["products"][1:]:
        adjacent.append(
            {
                "id": _native_code(item["code"]),
                "name": item["name"],
                "category": item.get("category") or "",
                "list_price": float(item["list_price"]),
                "on_hand": int(stock.get(item["code"], 0.0)),
                "procurement": "Not part of this request queue.",
            }
        )
    product_ids = [product_id, *(item["id"] for item in adjacent)]
    if len(set(product_ids)) != len(product_ids):
        raise ValueError(f"{task_dir.name}: native product IDs collide")
    adjacent.sort(key=lambda item: item["id"])

    customer_refs = list(consts["TASK_CUSTOMER_REFS"])
    customer_id = {ref: f"C-{index:02d}" for index, ref in enumerate(customer_refs, 1)}
    customer_rows = {item["ref"]: item for item in scenario["customers"]}
    allocations = {item["ref"]: item for item in plan["allocations"]}
    if set(allocations) != set(customer_refs):
        raise ValueError(f"{task_dir.name}: plan allocations do not match task customers")
    customers = [
        {
            "id": customer_id[ref],
            "name": customer_rows[ref]["name"],
            "email": customer_rows[ref].get("email") or "",
            "budget": float(customer_rows[ref]["budget_dollars"]),
            "note": customer_rows[ref].get("comment") or "",
        }
        for ref in customer_refs
    ]
    request_id = {ref: f"REQ-{index:02d}" for index, ref in enumerate(customer_refs, 1)}
    requests = [
        {
            "id": request_id[ref],
            "customer_id": customer_id[ref],
            "product_id": product_id,
            "quantity": int(allocations[ref]["demand"]),
            "due_day": int(allocations[ref]["deadline"]),
            "budget": float(customer_rows[ref]["budget_dollars"]),
        }
        for ref in customer_refs
    ]

    offers_raw = list(consts["SCENARIO_SUPPLIER_OFFERS"])
    lanes = {item["partner_ref"]: item for item in product_raw["vendor_info"]}
    vendor_refs = list(dict.fromkeys(item["vendor_ref"] for item in offers_raw))
    vendor_id = {ref: f"V-{index:02d}" for index, ref in enumerate(vendor_refs, 1)}
    vendor_rows = {item["ref"]: item for item in scenario["vendors"]}
    max_qty = {ref: int(value) for ref, value in consts["FINISHED_VENDOR_MAX_QTY"].items()}
    vendors = []
    for ref in vendor_refs:
        notes = [
            vendor_rows[ref].get("comment") or "",
            f"Maximum order quantity for {product_id}: {max_qty[ref]} units.",
        ]
        vendors.append(
            {
                "id": vendor_id[ref],
                "name": vendor_rows[ref]["name"],
                "note": " ".join(item for item in notes if item),
            }
        )
    offer_id = {item["offer_key"]: f"OFR-{index:02d}" for index, item in enumerate(offers_raw, 1)}
    offer_by_vendor: dict[str, str] = {}
    offers = []
    for item in offers_raw:
        if item["vendor_ref"] in offer_by_vendor:
            raise ValueError(f"{task_dir.name}: vendor with multiple offers")
        offer_by_vendor[item["vendor_ref"]] = offer_id[item["offer_key"]]
        lane = lanes[item["vendor_ref"]]
        if abs(float(lane["price"]) - float(item["price"])) > 1e-9 or int(lane["delay"]) != int(
            item["delay"]
        ):
            raise ValueError(f"{task_dir.name}: offer constants disagree with scenario data")
        offers.append(
            {
                "id": offer_id[item["offer_key"]],
                "vendor_id": vendor_id[item["vendor_ref"]],
                "product_id": product_id,
                "min_qty": int(item["min_qty"]),
                "unit_price": float(item["price"]),
                "lead_days": int(item["delay"]),
                "lane": lane.get("name") or "",
            }
        )

    seeded_sales = []
    seeded_by_ref: dict[str, str] = {}
    seeded_by_customer: dict[str, str] = {}
    for item in scenario.get("existing_sales_orders") or []:
        if item["product_code"] != code:
            continue
        if item["customer_ref"] not in customer_id:
            raise ValueError(f"{task_dir.name}: seeded order for a non-task customer")
        so_id = f"SO-{len(seeded_sales) + 1:04d}"
        seeded_by_ref[item["ref"]] = so_id
        seeded_by_customer[item["customer_ref"]] = so_id
        qty = int(item["quantity"])
        price = float(item["price_unit"])
        seeded_sales.append(
            {
                "id": so_id,
                "customer_id": customer_id[item["customer_ref"]],
                "product_id": product_id,
                "request_id": request_id[item["customer_ref"]],
                "quantity": qty,
                "unit_price": price,
                "amount_untaxed": round(qty * price, 2),
                "commitment_day": int(item["commitment_days"]),
                "payment_term": None,
                "status": {"draft": "draft", "sale": "confirmed"}[item["state"]],
                "source": "seeded",
                "note": item.get("note") or "",
            }
        )
    seeded_purchases = []
    seeded_po_by_ref: dict[str, str] = {}
    for item in scenario.get("existing_purchase_orders") or []:
        if item["product_code"] != code or item["state"] != "purchase":
            raise ValueError(f"{task_dir.name}: unexpected seeded purchase order")
        po_id = f"PO-{len(seeded_purchases) + 1:04d}"
        seeded_po_by_ref[item["ref"]] = po_id
        oid = offer_id[item["offer_key"]]
        if offer_by_vendor[item["vendor_ref"]] != oid:
            raise ValueError(f"{task_dir.name}: seeded purchase order offer mismatch")
        qty = int(item["quantity"])
        price = float(item["price_unit"])
        seeded_purchases.append(
            {
                "id": po_id,
                "vendor_id": vendor_id[item["vendor_ref"]],
                "offer_id": oid,
                "product_id": product_id,
                "quantity": qty,
                "unit_price": price,
                "amount_untaxed": round(qty * price, 2),
                "planned_arrival_day": int(item["planned_arrival_days"]),
                "origin_sales_order_ids": [
                    seeded_by_customer[ref] for ref in item["origin_customer_refs"]
                ],
                "status": "confirmed",
                "source": "seeded",
                "note": item.get("note") or "",
            }
        )

    coverage = _args_by_customer(invocations, "demand_coverage")
    deadlines = _args_by_customer(invocations, "deadline_fulfillment")
    revenues = _args_by_customer(invocations, "sale_revenue")
    budgets = _args_by_customer(invocations, "budget_compliance")
    list_prices = _args_by_customer(invocations, "list_price")
    demands = {ref: int(value) for ref, value in consts["CUSTOMER_DEMANDS"].items()}
    accepted = []
    rejected = []
    for item in plan["allocations"]:
        ref = item["ref"]
        seeded_id = (
            seeded_by_ref.get(item.get("task_order_ref") or "")
            if item["task_order_source"] == "seeded"
            else None
        )
        if item["task_order_source"] == "seeded" and seeded_id is None:
            raise ValueError(f"{task_dir.name}: seeded allocation without seeded order")
        if item["accepted"]:
            if demands[ref] != int(item["demand"]) or int(deadlines[ref][1]) != int(
                item["deadline"]
            ):
                raise ValueError(f"{task_dir.name}: plan and verifier disagree for {ref}")
            if abs(float(list_prices[ref][1]) - product["list_price"]) > 1e-9:
                raise ValueError(f"{task_dir.name}: list price disagreement")
            accepted.append(
                {
                    "customer_id": customer_id[ref],
                    "demand": demands[ref],
                    "cmp": coverage[ref][2],
                    "deadline": int(deadlines[ref][1]),
                    "revenue": float(revenues[ref][1]),
                    "budget": float(budgets[ref][1]),
                    "source": item["task_order_source"],
                    "seeded_sales_order_id": seeded_id,
                    "action": item["action"],
                }
            )
        else:
            rejected.append(
                {
                    "customer_id": customer_id[ref],
                    "action": item["action"],
                    "seeded_sales_order_id": seeded_id,
                    "reject_reasons": list(item.get("reject_reasons") or []),
                }
            )
    if not accepted:
        raise ValueError(f"{task_dir.name}: no accepted request")

    policy_raw = scenario["invoicing_policy"]
    invoice_orders = {}
    for item in consts["INVOICE_REQUIREMENTS"]:
        if not item["accepted"] or item["invoice_flow"] == "none":
            continue
        flow = item["invoice_flow"]
        downpayment = round(float(item["expected_downpayment_invoice_amount"]), 2)
        regular = round(float(item["expected_regular_invoice_amount"]), 2)
        if abs(downpayment + regular - float(item["sale_order_amount_untaxed"])) > 0.011:
            raise ValueError(f"{task_dir.name}: invoice amounts do not sum to the order total")
        invoice_orders[customer_id[item["customer_ref"]]] = {
            "flow": flow,
            "downpayment_amount": downpayment,
            "regular_amount": regular,
        }
    invoicing_required = bool(policy_raw["invoice_required"])
    if bool(invoice_orders) != invoicing_required:
        raise ValueError(f"{task_dir.name}: invoicing policy and requirements disagree")

    upstream_rules = set(invocations)
    unmapped = upstream_rules - set(RULE_MAP) - NOT_PORTED
    if unmapped:
        raise ValueError(f"{task_dir.name}: unmapped upstream rules {sorted(unmapped)}")
    rules = {RULE_MAP[name] for name in upstream_rules if name in RULE_MAP}
    objective = consts["OBJECTIVE_KIND"]
    repair = None
    if objective == "repair_plan":
        expectations = consts["REPAIR_EXPECTATIONS"]
        if expectations.get("kind") != "supplier_cancellation":
            raise ValueError(f"{task_dir.name}: unsupported repair kind")
        rules |= {"order_dispositions", "repair_objective", "spend_objective"}
        repair = {
            "broken_purchase_order_ids": [
                seeded_po_by_ref[ref] for ref in expectations["broken_purchase_order_refs"]
            ],
            "broken_offer_id": offer_id[expectations["broken_supplier_offer_key"]],
            "baseline_offer_quantities": {
                offer_id[key]: float(value)
                for key, value in expectations["baseline_offer_quantities"].items()
            },
        }
    elif objective == "min_new_spend":
        rules.add("spend_objective")
    rules_sorted = [rule for rule in erp_buy.RULES if rule in rules]

    supply_args = invocations["supply_coverage"][0]
    margin_args = invocations["new_spend_margin_policy"][0]
    if int(float(supply_args[1])) != int(consts["TOTAL_DEMAND"]) or float(supply_args[2]) != float(
        consts["STOCK_AVAILABLE"]
    ):
        raise ValueError(f"{task_dir.name}: supply coverage arguments disagree with constants")
    truth = {
        "product_id": product_id,
        "list_price": product["list_price"],
        "product_stock": float(consts["PRODUCT_STOCK"][code]),
        "stock_available": float(consts["STOCK_AVAILABLE"]),
        "total_demand": int(consts["TOTAL_DEMAND"]),
        "min_margin": float(margin_args[0]),
        "objective_kind": objective,
        "expected_spend": round(float(consts["EXPECTED_SPEND"]), 2),
        "expected_objective_value": round(float(consts["EXPECTED_OBJECTIVE_VALUE"]), 2),
        "spend_tolerance": float(consts["SPEND_TOLERANCE"]),
        "rules": rules_sorted,
        "upstream_rules": sorted(upstream_rules),
        "task_customer_ids": [customer_id[ref] for ref in customer_refs],
        "accepted": accepted,
        "rejected": rejected,
        "invoicing": {
            "required": invoicing_required,
            "payment_term": policy_raw.get("payment_term"),
            "orders": invoice_orders,
        },
        "vendor_max_qty": {vendor_id[ref]: value for ref, value in max_qty.items()},
        "repair": repair,
    }

    # Native reference plan derived from the upstream optimal plan.
    payment_term = policy_raw.get("payment_term") if invoicing_required else None
    sales_steps = []
    for item in plan["allocations"]:
        ref = item["ref"]
        step: dict[str, Any] = {"customer_id": customer_id[ref], "action": item["action"]}
        if item["action"] in {"confirm_seeded", "cancel_seeded"}:
            step["sales_order_id"] = seeded_by_ref[item["task_order_ref"]]
        if item["action"] == "confirm_seeded":
            seeded = next(row for row in seeded_sales if row["id"] == step["sales_order_id"])
            step["seeded_status"] = seeded["status"]
            updates: dict[str, Any] = {}
            if seeded["status"] == "draft":
                if seeded["commitment_day"] != int(item["deadline"]):
                    updates["commitment_day"] = int(item["deadline"])
                if seeded["quantity"] != int(item["demand"]):
                    updates["quantity"] = int(item["demand"])
                if abs(seeded["unit_price"] - product["list_price"]) > 1e-9:
                    updates["unit_price"] = product["list_price"]
                if payment_term:
                    updates["payment_term"] = payment_term
            elif seeded["commitment_day"] > int(item["deadline"]) or seeded["quantity"] != int(
                item["demand"]
            ):
                raise ValueError(f"{task_dir.name}: confirmed seeded order cannot satisfy the plan")
            step["updates"] = updates
        if item["action"] == "create_confirm_prompt":
            create = {
                "customer_id": customer_id[ref],
                "product_id": product_id,
                "quantity": int(item["demand"]),
                "commitment_day": int(item["deadline"]),
                "unit_price": product["list_price"],
                "request_id": request_id[ref],
            }
            if payment_term:
                create["payment_term"] = payment_term
            step["create"] = create
        sales_steps.append(step)

    plan_pos = [
        {
            "offer_id": offer_id[item["offer_key"]],
            "quantity": int(item["quantity"]),
            "planned_arrival_day": int(item["planned_arrival_days"]),
            "origin_customer_ids": [customer_id[ref] for ref in item["origin_customer_refs"]],
        }
        for item in plan["purchase_orders"]
    ]
    for item in plan["purchase_orders"]:
        if item.get("supply_role") != "finished" or item["product_code"] != code:
            raise ValueError(f"{task_dir.name}: non-finished purchase in plan")
    keep, cancel = [], []
    remaining = list(plan_pos)
    for seeded in seeded_purchases:
        signature = {
            "offer_id": seeded["offer_id"],
            "quantity": seeded["quantity"],
            "planned_arrival_day": seeded["planned_arrival_day"],
            "origin_customer_ids": sorted(
                next(row["customer_id"] for row in seeded_sales if row["id"] == so_id)
                for so_id in seeded["origin_sales_order_ids"]
            ),
        }
        match = next(
            (
                row
                for row in remaining
                if {**row, "origin_customer_ids": sorted(row["origin_customer_ids"])} == signature
            ),
            None,
        )
        if match is not None and seeded["id"] not in (repair or {}).get(
            "broken_purchase_order_ids", []
        ):
            keep.append(seeded["id"])
            remaining.remove(match)
        else:
            cancel.append(seeded["id"])
    invoices = []
    for item in accepted:
        expected = invoice_orders.get(item["customer_id"])
        if expected is None:
            continue
        if expected["flow"] == "downpayment_then_regular":
            invoices.append(
                {
                    "customer_id": item["customer_id"],
                    "kind": "downpayment",
                    "amount": expected["downpayment_amount"],
                }
            )
        invoices.append({"customer_id": item["customer_id"], "kind": "regular"})

    # The harness publishes one notification-role contract per family, so every
    # task notifies all three owners, including receivables when no invoice is due.
    roles = ["purchasing", "sales", "accounts_receivable"]
    background = scenario.get("background_and_policy") or ""
    policy_lines = []
    for line in background.splitlines():
        text = line.strip().lstrip("*-").strip()
        if not text:
            continue
        for old, new in PROMPT_REPLACEMENTS:
            text = text.replace(old, new)
        policy_lines.append(text)
    margin_param = next(
        float(item["value"])
        for item in scenario["system_parameters"]
        if item["key"].endswith("min_margin_percent")
    )
    policy = {
        "min_new_spend_margin_percent": margin_param,
        "manufacturing": "No in-house manufacturing capacity; buy any shortfall beyond on-hand stock.",
        "invoicing": {key: policy_raw.get(key) for key in sorted(policy_raw)},
        "payment_term_codes": {"immediate": "Immediate Payment", "net_30": "30 Days"},
        "rules": policy_lines,
    }
    fixture = {
        "source_task": task_dir.name,
        "scenario_number": int(scenario["scenario_number"]),
        "incident_id": f"ERP-BUY-{int(scenario['scenario_number'])}",
        "incident_summary": (
            f"{len(customer_refs)} open customer requests for {product['name']} ({product_id}); "
            f"{product['on_hand']} finished units on hand; no in-house manufacturing."
        ),
        "product": product,
        "adjacent_products": adjacent,
        "customers": customers,
        "customer_requests": requests,
        "vendors": vendors,
        "supplier_offers": offers,
        "seeded_sales_orders": seeded_sales,
        "seeded_purchase_orders": seeded_purchases,
        "policy": policy,
        "required_roles": roles,
        "truth": truth,
        "oracle": {
            "sales_orders": sales_steps,
            "cancel_purchase_orders": cancel,
            "keep_purchase_orders": keep,
            "purchase_orders": remaining,
            "invoices": invoices,
        },
    }
    pattern = row["family"]
    stages = [
        {
            "id": "investigate",
            "objective": "Read policy, stock, customer requests, supplier offers, vendor notes, and existing orders.",
            "depends_on": [],
        },
        {
            "id": "disposition_orders",
            "objective": "Accept, reuse, cancel, or skip each customer request and confirm retained sales orders.",
            "depends_on": ["investigate"],
        },
        {
            "id": "plan_supply",
            "objective": "Choose offers, quantities, arrival days, and origins that cover accepted demand at minimum new spend.",
            "depends_on": ["investigate"],
        },
        {
            "id": "execute_purchasing",
            "objective": "Cancel broken or superseded commitments and confirm linked purchase orders through approval.",
            "depends_on": ["disposition_orders", "plan_supply"],
        },
    ]
    last = "execute_purchasing"
    if invoicing_required:
        stages.append(
            {
                "id": "invoice",
                "objective": "Create and post the customer invoices the invoicing policy requires.",
                "depends_on": ["disposition_orders"],
            }
        )
        last_deps = ["execute_purchasing", "invoice"]
    else:
        last_deps = [last]
    stages.append(
        {
            "id": "communicate",
            "objective": "Notify the owning roles and finish with the executed record IDs.",
            "depends_on": last_deps,
        }
    )
    task = {
        "family": erp_buy.FAMILY,
        "title": row["title"],
        "prompt": _rewrite_prompt(row["prompt"], roles, invoicing_required),
        "seed": int(scenario["scenario_number"]),
        "difficulty": _difficulty(pattern),
        "systems": ["ERP", "SCM", "billing"],
        "tags": [
            "source:erp-bench",
            f"upstream:{task_dir.name}",
            f"pattern:{pattern}",
            f"objective:{objective}",
            "distributor",
            "buy-to-fulfill",
        ],
        "workflow_stages": stages,
    }
    return fixture, task


def _dump_compact(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _measure(task_dict: dict[str, Any]) -> tuple[int, int]:
    from faraday_industrial_benchmark.agents import OracleAgent
    from faraday_industrial_benchmark.models import IncidentTask
    from faraday_industrial_benchmark.runner import BenchmarkRunner

    provisional = IncidentTask.from_dict(
        {**task_dict, "max_tool_calls": 1000, "horizon_minutes": 5000}
    )
    result = BenchmarkRunner().run_task(provisional, OracleAgent())
    if not result.score.strict_success:
        failed = [item.id for item in result.score.criteria if not item.passed]
        raise RuntimeError(
            f"{task_dict['id']}: oracle is not strict: {failed} {result.score.violations}"
        )
    return result.score.tool_calls, result.score.elapsed_minutes


def run(benchmarks_root: Path, repo_root: Path) -> None:
    index = json.loads(
        (benchmarks_root / "distributor-index" / "tasks.json").read_text(encoding="utf-8")
    )
    rows = sorted(
        (row for row in index if row.get("benchmark") == SOURCE),
        key=lambda row: row["task_id"],
    )
    if len(rows) != 82:
        raise ValueError(f"expected 82 curated ERP-Bench rows, found {len(rows)}")
    fixture_dir = repo_root / FIXTURE_DIR
    if fixture_dir.is_dir():
        for stale in fixture_dir.glob("*.json"):
            stale.unlink()
    written: list[Path] = []
    tasks: list[dict[str, Any]] = []
    for number, row in enumerate(rows, 1):
        task_dir = benchmarks_root / SOURCE / "tasks" / row["task_id"]
        fixture, task = _fixture(row, task_dir)
        path = fixture_dir / f"{task_dir.name}.json"
        _dump_compact(path, fixture)
        written.append(path)
        tasks.append({"id": f"faraday-erpbench-{number:03d}", "version": VERSION, **task})

    manifest = []
    for task in tasks:
        calls, minutes = _measure(task)
        horizon = -(-(minutes + MINUTE_SLACK) // 10) * 10
        manifest.append(
            {
                "id": task["id"],
                "version": task["version"],
                "family": task["family"],
                "title": task["title"],
                "prompt": task["prompt"],
                "seed": task["seed"],
                "difficulty": task["difficulty"],
                "systems": task["systems"],
                "max_tool_calls": calls + CALL_SLACK,
                "horizon_minutes": horizon,
                "tags": task["tags"],
                "workflow_stages": task["workflow_stages"],
            }
        )
    manifest_path = repo_root / MANIFEST
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    written.append(manifest_path)

    raw_dir = repo_root / RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    license_copy = raw_dir / "LICENSE"
    shutil.copyfile(benchmarks_root / SOURCE / "LICENSE", license_copy)
    written.append(license_copy)
    write_provenance(SOURCE, dict(UPSTREAM), written)
