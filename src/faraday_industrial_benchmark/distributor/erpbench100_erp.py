"""Native ERP surface for the ERPBench-100 families: read tools and protected writes.

The tenant ERP lives in ``world.state["dist_erp"]`` as ``{table: {key: row}}``.
Every write tags the rows it creates or changes with ``last_task_id`` so the
evaluator can tell task writes apart from seeded history, as upstream does.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .. import extensions
from . import erpbench100_contract as contract

Json = dict[str, Any]

ERP_KEY = "dist_erp"
CONTEXT_KEY = "dist_erpbench"


def erp(world) -> Json:
    return world.state[ERP_KEY]


def context(world) -> Json:
    return world.state[CONTEXT_KEY]


def _rows(world, table: str) -> list[Json]:
    return list(erp(world)[table].values())


def _ok(**values: Any) -> Json:
    return {"ok": True, **deepcopy(values)}


def _missing(error: str) -> Json:
    return {"ok": False, "error": error}


def _string(description: str) -> Json:
    return {"type": "string", "description": description}


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


def _list_items(world) -> Json:
    return _ok(items=sorted(_rows(world, "items"), key=lambda row: row["item_number"]))


def _list_customers(world) -> Json:
    return _ok(customers=sorted(_rows(world, "customers"), key=lambda row: row["customer_number"]))


def _get_customer_account(world, customer_number: str) -> Json:
    customer = erp(world)["customers"].get(customer_number)
    if not customer:
        return _missing("customer_not_found")
    invoices = [
        row for row in _rows(world, "receivables_invoices")
        if row.get("bill_to_customer_number") == customer_number and row.get("invoice_status") != "Closed"
    ]
    summary = [
        {key: row.get(key) for key in ("transaction_number", "transaction_date", "due_date", "balance_due", "invoice_status")}
        for row in sorted(invoices, key=lambda row: row["transaction_number"])
    ]
    return _ok(
        customer=customer,
        open_invoices=summary,
        open_balance=round(sum(float(row.get("balance_due") or 0) for row in invoices), 2),
    )


def _list_sales_orders(
    world,
    customer_po_number: str | None = None,
    customer_number: str | None = None,
    source_system: str | None = None,
    source_transaction_number: str | None = None,
) -> Json:
    rows = []
    for row in _rows(world, "sales_orders"):
        if customer_po_number and customer_po_number.lower() not in str(row.get("customer_po_number") or "").lower():
            continue
        if customer_number and row.get("buying_party_number") != customer_number:
            continue
        if source_system and row.get("source_transaction_system") != source_system:
            continue
        if source_transaction_number and row.get("source_transaction_number") != source_transaction_number:
            continue
        rows.append(row)
    return _ok(sales_orders=sorted(rows, key=lambda row: row["order_number"]))


def _get_sales_order(world, order_number: str) -> Json:
    row = erp(world)["sales_orders"].get(order_number)
    return _ok(sales_order=row) if row else _missing("sales_order_not_found")


def _get_shipment(world, shipment: str) -> Json:
    row = erp(world)["shipments"].get(shipment)
    if not row:
        return _missing("shipment_not_found")
    count = sum(1 for line in _rows(world, "shipment_lines") if line.get("shipment") == shipment)
    return _ok(shipment=row, line_count=count)


def _list_shipment_lines(world, shipment: str) -> Json:
    if shipment not in erp(world)["shipments"]:
        return _missing("shipment_not_found")
    rows = [row for row in _rows(world, "shipment_lines") if row.get("shipment") == shipment]
    return _ok(shipment=shipment, lines=sorted(rows, key=lambda row: (row["line_number"], row["shipment_line_id"])))


def _list_receivable_invoices(world, customer_number: str | None = None, status: str | None = None) -> Json:
    rows = [
        row for row in _rows(world, "receivables_invoices")
        if (customer_number is None or row.get("bill_to_customer_number") == customer_number)
        and (status is None or row.get("invoice_status") == status)
    ]
    return _ok(invoices=sorted(rows, key=lambda row: row["transaction_number"]))


def _get_receivable_invoice(world, transaction_number: str) -> Json:
    row = erp(world)["receivables_invoices"].get(transaction_number)
    return _ok(invoice=row) if row else _missing("invoice_not_found")


def _list_customer_receipts(world, customer_number: str | None = None) -> Json:
    rows = [
        row for row in _rows(world, "standard_receipts")
        if customer_number is None or row.get("customer_account_number") == customer_number
    ]
    return _ok(receipts=sorted(rows, key=lambda row: row["receipt_number"]))


def _list_onhand(world, item_number: str | None = None) -> Json:
    rows = [row for row in _rows(world, "onhand_balances") if item_number is None or row.get("item_number") == item_number]
    return _ok(balances=sorted(rows, key=lambda row: row["balance_id"]))


def _list_suppliers(world) -> Json:
    return _ok(suppliers=sorted(_rows(world, "suppliers"), key=lambda row: row["supplier_number"]))


def _list_purchase_orders(world, supplier_number: str | None = None, status: str | None = None) -> Json:
    rows = [
        row for row in _rows(world, "purchase_orders")
        if (supplier_number is None or row.get("supplier_number") == supplier_number)
        and (status is None or row.get("status") == status)
    ]
    return _ok(purchase_orders=sorted(rows, key=lambda row: row["po_number"]))


def _po_lines(world, po_number: str) -> list[Json]:
    rows = [row for row in _rows(world, "purchase_order_lines") if row.get("po_number") == po_number]
    return sorted(rows, key=lambda row: row["line_number"])


def _get_purchase_order(world, po_number: str) -> Json:
    row = erp(world)["purchase_orders"].get(po_number)
    if not row:
        return _missing("purchase_order_not_found")
    return _ok(purchase_order=row, lines=_po_lines(world, po_number))


def _list_purchase_order_lines(world, po_number: str) -> Json:
    if po_number not in erp(world)["purchase_orders"]:
        return _missing("purchase_order_not_found")
    return _ok(po_number=po_number, lines=_po_lines(world, po_number))


def _list_requisitions(world) -> Json:
    return _ok(requisitions=sorted(_rows(world, "purchase_requisitions"), key=lambda row: row["requisition_number"]))


def _get_requisition(world, requisition_number: str) -> Json:
    row = erp(world)["purchase_requisitions"].get(requisition_number)
    return _ok(requisition=row) if row else _missing("requisition_not_found")


def _list_receiving_receipts(world, po_number: str | None = None) -> Json:
    rows = [row for row in _rows(world, "receiving_receipt_requests") if po_number is None or row.get("po_number") == po_number]
    return _ok(receipts=sorted(rows, key=lambda row: row["header_interface_id"]))


def _list_ap_invoices(world, supplier_number: str | None = None, po_number: str | None = None) -> Json:
    rows = [
        row for row in _rows(world, "ap_invoices")
        if (supplier_number is None or row.get("supplier_number") == supplier_number)
        and (po_number is None or row.get("po_number") == po_number)
    ]
    return _ok(invoices=sorted(rows, key=lambda row: row["invoice_number"]))


def _get_ap_invoice(world, invoice_number: str) -> Json:
    row = erp(world)["ap_invoices"].get(invoice_number)
    if not row:
        return _missing("invoice_not_found")
    holds = [hold for hold in _rows(world, "invoice_holds") if hold.get("invoice_number") == invoice_number]
    return _ok(invoice=row, holds=sorted(holds, key=lambda hold: hold["hold_id"]))


def _list_handoffs(world) -> Json:
    return _ok(handoffs=world.state["notifications"])


CUSTOMER = {"customer_number": _string("Customer account number")}
OPTIONAL_CUSTOMER = {"customer_number": _string("Optional customer account number filter")}

READ_TOOL_SPECS: dict[str, tuple[str, Json, list[str], Any]] = {
    "list_dist_tenant_items": ("List the tenant item master with list prices, costs and status.", {}, [], _list_items),
    "list_dist_tenant_customers": ("List the tenant customer master.", {}, [], _list_customers),
    "get_dist_tenant_customer_account": ("Read one customer account with credit standing and open receivables.", CUSTOMER, ["customer_number"], _get_customer_account),
    "list_dist_tenant_sales_orders": (
        "List sales orders, optionally filtered by customer PO (substring), customer, source system or source transaction.",
        {
            "customer_po_number": _string("Customer PO number or fragment"),
            "customer_number": _string("Buying party number"),
            "source_system": _string("Source transaction system, for example OPS or a sales channel"),
            "source_transaction_number": _string("Source transaction number"),
        },
        [],
        _list_sales_orders,
    ),
    "get_dist_tenant_sales_order": ("Read one sales order with its lines.", {"order_number": _string("Sales order number")}, ["order_number"], _get_sales_order),
    "get_dist_tenant_shipment": ("Read one shipment header.", {"shipment": _string("Shipment number")}, ["shipment"], _get_shipment),
    "list_dist_tenant_shipment_lines": ("List the lines of one shipment.", {"shipment": _string("Shipment number")}, ["shipment"], _list_shipment_lines),
    "list_dist_tenant_receivable_invoices": (
        "List receivables invoices, optionally by customer and status.",
        {**OPTIONAL_CUSTOMER, "status": _string("Optional invoice status filter")},
        [],
        _list_receivable_invoices,
    ),
    "get_dist_tenant_receivable_invoice": ("Read one receivables invoice.", {"transaction_number": _string("Invoice transaction number")}, ["transaction_number"], _get_receivable_invoice),
    "list_dist_tenant_customer_receipts": ("List customer receipts and their applications.", OPTIONAL_CUSTOMER, [], _list_customer_receipts),
    "list_dist_tenant_onhand": ("List on-hand and reserved balances.", {"item_number": _string("Optional item filter")}, [], _list_onhand),
    "list_dist_tenant_suppliers": ("List the supplier master with lead times and status.", {}, [], _list_suppliers),
    "list_dist_tenant_purchase_orders": (
        "List purchase orders, optionally by supplier and status.",
        {"supplier_number": _string("Optional supplier filter"), "status": _string("Optional status filter")},
        [],
        _list_purchase_orders,
    ),
    "get_dist_tenant_purchase_order": ("Read one purchase order with its lines.", {"po_number": _string("Purchase order number")}, ["po_number"], _get_purchase_order),
    "list_dist_tenant_purchase_order_lines": ("List the lines of one purchase order.", {"po_number": _string("Purchase order number")}, ["po_number"], _list_purchase_order_lines),
    "list_dist_tenant_requisitions": ("List purchase requisitions.", {}, [], _list_requisitions),
    "get_dist_tenant_requisition": ("Read one purchase requisition.", {"requisition_number": _string("Requisition number")}, ["requisition_number"], _get_requisition),
    "list_dist_tenant_receiving_receipts": ("List receiving receipts, optionally for one purchase order.", {"po_number": _string("Optional purchase order filter")}, [], _list_receiving_receipts),
    "list_dist_tenant_ap_invoices": (
        "List supplier (payables) invoices.",
        {"supplier_number": _string("Optional supplier filter"), "po_number": _string("Optional purchase order filter")},
        [],
        _list_ap_invoices,
    ),
    "get_dist_tenant_ap_invoice": ("Read one supplier invoice with its holds.", {"invoice_number": _string("Supplier invoice number")}, ["invoice_number"], _get_ap_invoice),
    contract.HANDOFF_READ_TOOL: ("Read back the review handoffs sent with notify.", {}, [], _list_handoffs),
}

if set(READ_TOOL_SPECS) != {*contract.READ_TOOLS, contract.HANDOFF_READ_TOOL}:
    raise RuntimeError("ERPBench-100 read tool specs drifted from the contract")


# ---------------------------------------------------------------------------
# Protected actions
# ---------------------------------------------------------------------------


class _Reject(Exception):
    pass


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) != int(value) or value <= 0:
        raise _Reject(f"{name}_must_be_a_positive_integer")
    return int(value)


def _amount(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise _Reject(f"{name}_must_be_positive")
    return float(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _Reject(f"{name}_required")
    return value


def _lines(payload: Json) -> list[Json]:
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines or not all(isinstance(line, dict) for line in lines):
        raise _Reject("lines_required")
    return lines


def _bump(number: str, offset: int) -> str:
    prefix, _, digits = number.rpartition("-")
    return f"{prefix}-{int(digits) + offset}"


def _new_key(world, table: str, base: str) -> str:
    offset = 0
    while _bump(base, offset) in erp(world)[table]:
        offset += 1
    return _bump(base, offset)


def _new_int(world, table: str, field: str, base: int) -> int:
    used = {row.get(field) for row in _rows(world, table)}
    value = base
    while value in used:
        value += 1
    return value


def _task_id(world) -> str:
    return world.state["task_id"]


def _guard(apply):
    def wrapped(world, target, payload):
        try:
            return apply(world, str(target), payload or {})
        except _Reject as exc:
            return False, str(exc)

    wrapped.__name__ = apply.__name__
    return wrapped


@_guard
def _commit_order_import(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    customer = tables["customers"].get(str(payload.get("customer_number")))
    if not customer:
        return False, "customer_not_found"
    source = payload.get("source_file_id")
    if source not in world.state["case_files"]:
        return False, "source_file_not_found"
    submit = payload.get("submit")
    if not isinstance(submit, bool):
        return False, "submit_flag_required"
    lines = []
    for line in _lines(payload):
        item = tables["items"].get(str(line.get("item_number")))
        if not item:
            return False, "item_not_found"
        lines.append({
            "item_number": item["item_number"],
            "quantity": _int(line.get("quantity"), "quantity"),
            "uom": item.get("primary_uom", "EA"),
            "unit_price": _amount(line.get("unit_price"), "unit_price"),
        })
    number = _new_key(world, "sales_orders", context(world)["numbering"]["order_import_order"])
    tables["sales_orders"][number] = {
        "order_number": number,
        "customer_po_number": target,
        "buying_party_number": customer["customer_number"],
        "buying_party_name": customer["name"],
        "source_transaction_number": source,
        "source_transaction_system": "OPS",
        "source_message_id": None,
        "submitted_flag": submit,
        "status": "Awaiting Shipping" if submit else "Draft",
        "transaction_type": "Standard Orders",
        "organization_code": context(world)["org"],
        "lines": lines,
        "order_total": round(sum(line["quantity"] * line["unit_price"] for line in lines), 2),
        "created_by": "agent",
        "created_at": contract.AS_OF,
        "last_task_id": _task_id(world),
    }
    return True, number


@_guard
def _correct_shipment_line(world, target: str, payload: Json) -> tuple[bool, str]:
    row = erp(world)["shipment_lines"].get(target)
    if not row:
        return False, "shipment_line_not_found"
    quantity = payload.get("shipped_quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0 or float(quantity) != int(quantity):
        return False, "shipped_quantity_must_be_a_nonnegative_integer"
    comment = payload.get("comment", "")
    if not isinstance(comment, str):
        return False, "comment_must_be_text"
    row.update(shipped_quantity=int(quantity), comments=comment or row.get("comments"), last_task_id=_task_id(world))
    return True, target


@_guard
def _apply_customer_receipt(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    if target in tables["standard_receipts"]:
        return False, "receipt_number_exists"
    customer = tables["customers"].get(str(payload.get("customer_number")))
    if not customer:
        return False, "customer_not_found"
    amount = _amount(payload.get("amount"), "amount")
    receipt_date = _text(payload.get("receipt_date"), "receipt_date")
    method = _text(payload.get("method"), "method")
    applications = payload.get("applications")
    if not isinstance(applications, list) or not applications or not all(isinstance(row, dict) for row in applications):
        return False, "applications_required"
    planned: list[tuple[Json, float]] = []
    for application in applications:
        invoice = tables["receivables_invoices"].get(str(application.get("invoice_number")))
        if not invoice or invoice.get("bill_to_customer_number") != customer["customer_number"]:
            return False, "invoice_not_found_for_customer"
        if any(invoice is seen for seen, _ in planned):
            return False, "duplicate_application"
        applied = _amount(application.get("amount"), "application_amount")
        if applied > float(invoice.get("balance_due") or 0) + 0.005:
            return False, "application_exceeds_balance"
        planned.append((invoice, applied))
    if sum(applied for _, applied in planned) > amount + 0.005:
        return False, "applications_exceed_receipt"
    for invoice, applied in planned:
        balance = round(float(invoice["balance_due"]) - applied, 2)
        invoice["balance_due"] = 0.0 if abs(balance) <= 0.005 else balance
        if invoice["balance_due"] == 0.0:
            invoice["invoice_status"] = "Closed"
        invoice["last_task_id"] = _task_id(world)
    unapplied = round(amount - sum(applied for _, applied in planned), 2)
    profile = context(world)
    tables["standard_receipts"][target] = {
        "standard_receipt_id": _new_int(world, "standard_receipts", "standard_receipt_id", profile["numbering"]["receipt_id"]),
        "receipt_number": target,
        "customer_account_number": customer["customer_number"],
        "receipt_amount": amount,
        "receipt_date": receipt_date,
        "receipt_method": method,
        "receipt_status": "Applied" if abs(unapplied) <= 0.005 else "Partially applied",
        "unapplied_amount": max(unapplied, 0.0),
        "applications": [{"invoice_number": invoice["transaction_number"], "amount": applied} for invoice, applied in planned],
        "business_unit": profile["business_unit"],
        "currency": profile["currency"],
        "created_by": "agent",
        "last_task_id": _task_id(world),
    }
    return True, target


@_guard
def _create_requisition(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    profile = context(world)
    if target != profile["org"]:
        return False, "organization_not_found"
    supplier = tables["suppliers"].get(str(payload.get("supplier_number")))
    if not supplier:
        return False, "supplier_not_found"
    if supplier.get("supplier_status") != "Active":
        return False, "supplier_not_active"
    description = _text(payload.get("description"), "description")
    justification = _text(payload.get("justification"), "justification")
    lines = []
    for index, line in enumerate(_lines(payload), start=1):
        item = tables["items"].get(str(line.get("item_number")))
        if not item:
            return False, "item_not_found"
        lines.append({
            "line_number": index,
            "item_number": item["item_number"],
            "quantity": _int(line.get("quantity"), "quantity"),
            "unit_price": _amount(line.get("unit_price"), "unit_price"),
            "need_by_date": _text(line.get("need_by_date"), "need_by_date"),
            "supplier_number": supplier["supplier_number"],
            "supplier": supplier["name"],
        })
    number = _new_key(world, "purchase_requisitions", profile["numbering"]["requisition_number"])
    tables["purchase_requisitions"][number] = {
        "requisition_number": number,
        "requisition_id": _new_int(world, "purchase_requisitions", "requisition_id", profile["numbering"]["requisition_id"]),
        "organization_code": target,
        "supplier_number": supplier["supplier_number"],
        "supplier": supplier["name"],
        "description": description,
        "justification": justification,
        "document_status": "Incomplete",
        "lines": lines,
        "total_amount": round(sum(line["quantity"] * line["unit_price"] for line in lines), 2),
        "last_task_id": _task_id(world),
    }
    return True, number


@_guard
def _submit_requisition(world, target: str, payload: Json) -> tuple[bool, str]:
    row = erp(world)["purchase_requisitions"].get(target)
    if not row:
        return False, "requisition_not_found"
    if row["document_status"] != "Incomplete":
        return False, "requisition_not_incomplete"
    row.update(document_status="Pending approval", last_task_id=_task_id(world))
    return True, target


@_guard
def _receive_po_delivery(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    po = tables["purchase_orders"].get(target)
    if not po:
        return False, "purchase_order_not_found"
    if po.get("status") != "Open":
        return False, "purchase_order_not_open"
    by_line = {row["line_number"]: row for row in _po_lines(world, target)}
    received = []
    for line in _lines(payload):
        number = _int(line.get("line"), "line")
        quantity = _int(line.get("quantity"), "quantity")
        row = by_line.get(number)
        if not row:
            return False, "purchase_order_line_not_found"
        if row["received_quantity"] + quantity > row["quantity"]:
            return False, "over_receipt"
        received.append((row, number, quantity))
    if len({number for _, number, _ in received}) != len(received):
        return False, "duplicate_receipt_line"
    for row, _, quantity in received:
        row["received_quantity"] += quantity
        row["last_task_id"] = _task_id(world)
    header = _new_int(world, "receiving_receipt_requests", "header_interface_id", context(world)["numbering"]["receiving_header_id"])
    tables["receiving_receipt_requests"][str(header)] = {
        "header_interface_id": header,
        "po_number": target,
        "supplier_number": po["supplier_number"],
        "lines": [{"line": number, "quantity": quantity} for _, number, quantity in received],
        "receipt_status": "Received",
        "last_task_id": _task_id(world),
    }
    return True, str(header)


@_guard
def _enter_supplier_invoice(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    if target in tables["ap_invoices"]:
        return False, "invoice_number_exists"
    supplier = tables["suppliers"].get(str(payload.get("supplier_number")))
    if not supplier:
        return False, "supplier_not_found"
    po_number = str(payload.get("po_number"))
    po = tables["purchase_orders"].get(po_number)
    if not po:
        return False, "purchase_order_not_found"
    if po.get("supplier_number") != supplier["supplier_number"]:
        return False, "purchase_order_supplier_mismatch"
    by_line = {row["line_number"] for row in _po_lines(world, po_number)}
    lines = []
    for line in _lines(payload):
        number = _int(line.get("line"), "line")
        if number not in by_line:
            return False, "purchase_order_line_not_found"
        quantity = _int(line.get("quantity"), "quantity")
        price = _amount(line.get("unit_price"), "unit_price")
        lines.append({"line": number, "quantity": quantity, "unit_price": price, "amount": round(quantity * price, 2)})
    amount = _amount(payload.get("invoice_amount"), "invoice_amount")
    if abs(sum(line["amount"] for line in lines) - amount) > 0.005:
        return False, "invoice_amount_does_not_match_lines"
    tables["ap_invoices"][target] = {
        "invoice_id": _new_int(world, "ap_invoices", "invoice_id", context(world)["numbering"]["invoice_id"]),
        "invoice_number": target,
        "supplier_number": supplier["supplier_number"],
        "supplier": supplier["name"],
        "po_number": po_number,
        "invoice_date": _text(payload.get("invoice_date"), "invoice_date"),
        "invoice_amount": amount,
        "lines": lines,
        "validation_status": "Not validated",
        "last_task_id": _task_id(world),
    }
    return True, target


def _open_holds(world, invoice_number: str) -> list[Json]:
    return [
        hold for hold in _rows(world, "invoice_holds")
        if hold.get("invoice_number") == invoice_number and hold.get("hold_status") == "Open"
    ]


@_guard
def _validate_supplier_invoice(world, target: str, payload: Json) -> tuple[bool, str]:
    invoice = erp(world)["ap_invoices"].get(target)
    if not invoice:
        return False, "invoice_not_found"
    if _open_holds(world, target):
        return False, "invoice_has_open_holds"
    invoice.update(validation_status="Validated", last_task_id=_task_id(world))
    return True, target


@_guard
def _hold_supplier_invoice(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    invoice = tables["ap_invoices"].get(target)
    if not invoice:
        return False, "invoice_not_found"
    hold_name = _text(payload.get("hold_name"), "hold_name")
    reason = _text(payload.get("reason"), "reason")
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        return False, "held_lines_required"
    invoice_lines = {line["line"] for line in invoice["lines"]}
    held = sorted({_int(line, "line") for line in lines})
    if not set(held) <= invoice_lines:
        return False, "invoice_line_not_found"
    hold_id = _new_int(world, "invoice_holds", "hold_id", context(world)["numbering"]["hold_id"])
    tables["invoice_holds"][str(hold_id)] = {
        "hold_id": hold_id,
        "invoice_id": invoice["invoice_id"],
        "invoice_number": target,
        "hold_name": hold_name,
        "hold_lines": held,
        "hold_reason": reason,
        "hold_status": "Open",
        "last_task_id": _task_id(world),
    }
    invoice.update(validation_status="On hold", last_task_id=_task_id(world))
    return True, str(hold_id)


@_guard
def _create_channel_order(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    profile = context(world)
    buyer = _text(payload.get("buyer"), "buyer")
    total = _amount(payload.get("order_total"), "order_total")
    sequence = 1
    while f"SO-{profile['short']}-{52000 + 7 * sequence}" in tables["sales_orders"]:
        sequence += 1
    number = f"SO-{profile['short']}-{52000 + 7 * sequence}"
    customer = next((row for row in tables["customers"].values() if row.get("name") == buyer), None)
    tables["sales_orders"][number] = {
        "order_number": number,
        "customer_po_number": target,
        "buying_party_number": customer["customer_number"] if customer else None,
        "buying_party_name": buyer,
        "source_transaction_number": target,
        "source_transaction_system": profile["channel"],
        "source_message_id": None,
        "submitted_flag": True,
        "status": "Booked",
        "transaction_type": "Standard Orders",
        "organization_code": profile["org"],
        "lines": [],
        "order_total": total,
        "created_by": "channel_sync",
        "created_at": contract.AS_OF,
        "last_task_id": _task_id(world),
    }
    return True, number


@_guard
def _capture_channel_customer(world, target: str, payload: Json) -> tuple[bool, str]:
    tables = erp(world)
    profile = context(world)
    name = _text(target, "customer_name")
    email = _text(payload.get("email"), "email")
    if "@" not in email:
        return False, "email_invalid"
    tax_id = _text(payload.get("tax_id"), "tax_id")
    channel = _text(payload.get("channel"), "channel")
    sequence = 1
    while f"CUST-{profile['short']}-CH{sequence:02d}" in tables["customers"]:
        sequence += 1
    number = f"CUST-{profile['short']}-CH{sequence:02d}"
    tables["customers"][number] = {
        "customer_number": number,
        "name": name,
        "email": email,
        "tax_id": tax_id,
        "source_channel": channel,
        "credit_hold": False,
        "credit_limit": 0.0,
        "payment_terms": "Net 30",
        "created_by": "channel_sync",
        "source_message_id": None,
        "last_task_id": _task_id(world),
    }
    return True, number


@_guard
def _update_item_list_price(world, target: str, payload: Json) -> tuple[bool, str]:
    item = erp(world)["items"].get(target)
    if not item:
        return False, "item_not_found"
    price = _amount(payload.get("list_price"), "list_price")
    effective = _text(payload.get("effective_date"), "effective_date")
    item.update(list_price=price, price_effective_date=effective, last_task_id=_task_id(world))
    return True, target


ACTION_HANDLERS = {
    "commit_dist_tenant_order_import": _commit_order_import,
    "correct_dist_tenant_shipment_line": _correct_shipment_line,
    "apply_dist_tenant_customer_receipt": _apply_customer_receipt,
    "create_dist_tenant_requisition": _create_requisition,
    "submit_dist_tenant_requisition": _submit_requisition,
    "receive_dist_tenant_po_delivery": _receive_po_delivery,
    "enter_dist_tenant_supplier_invoice": _enter_supplier_invoice,
    "validate_dist_tenant_supplier_invoice": _validate_supplier_invoice,
    "hold_dist_tenant_supplier_invoice": _hold_supplier_invoice,
    "create_dist_tenant_channel_order": _create_channel_order,
    "capture_dist_tenant_channel_customer": _capture_channel_customer,
    "update_dist_tenant_item_list_price": _update_item_list_price,
}

if set(ACTION_HANDLERS) != set(contract.ACTION_CONTRACTS):
    raise RuntimeError("ERPBench-100 action handlers drifted from the contract")


def register() -> None:
    for name, (description, properties, required, handler) in READ_TOOL_SPECS.items():
        extensions.register_tool(extensions.tool(name, description, properties, required), handler)
    for name, handler in ACTION_HANDLERS.items():
        extensions.register_action(name, contract.ACTION_CONTRACTS[name], handler)
