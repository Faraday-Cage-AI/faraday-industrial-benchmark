"""Import the curated ERPBench-100 tasks as native distributor fixtures.

ERPBench-100 (blobfishai/erp-agent-simulation) generates every tenant, record,
document and gold outcome from ``benchmark/erpbench100/spec.py`` and seeds a
task-local SQLite world with ``world.py``. This importer runs that upstream
generator once per curated task, verifies the generated contract against the
released ``tests/task.json``, and converts the seeded world into compact JSON
fixtures: one per tenant (ERP tables and evidence room) and one per task
(contract, sealed truth, native investigation routes and the native oracle plan).
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from faraday_industrial_benchmark.distributor import erpbench100_contract as contract
from faraday_industrial_benchmark.distributor.provenance import write_provenance

FIXTURE_DIR = Path("src/faraday_industrial_benchmark/distributor/fixtures") / contract.SOURCE
MANIFEST = Path("data/distributor-erpbench100/tasks.json")
RAW_DIR = Path("data/distributor-sources") / contract.SOURCE
RAW_COPIES = ("LICENSE", "LICENSE-DATA", "NOTICE")


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _revision(benchmarks_root: Path) -> str:
    manifest = benchmarks_root / "download-manifest.json"
    if manifest.is_file():
        found: list[str] = []

        def visit(value: Any, key: str = "") -> None:
            if isinstance(value, dict):
                if key == contract.SOURCE and isinstance(value.get("revision"), str):
                    found.append(value["revision"])
                for child_key, child in value.items():
                    visit(child, child_key)
            elif isinstance(value, list):
                for child in value:
                    visit(child, key)

        visit(json.loads(manifest.read_text(encoding="utf-8")))
        if found:
            return found[0]
    raise RuntimeError("cannot determine the pinned ERPBench-100 revision from download-manifest.json")


def _load_upstream(root: Path):
    package_root = root / "benchmark"
    sys.path.insert(0, str(package_root))
    try:
        spec = importlib.import_module("erpbench100.spec")
        world = importlib.import_module("erpbench100.world")
    finally:
        sys.path.remove(str(package_root))
    return spec, world


def _snapshot(upstream_world, task: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    with tempfile.TemporaryDirectory(prefix="erpbench100-import-") as temporary:
        world = upstream_world.ErpWorld.create(task, Path(temporary) / "world.sqlite")
        try:
            return world.snapshot()
        finally:
            world.close()


def _strip(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "tenant_code"}


def _order_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "item_number": line["ProductNumber"],
            "quantity": line["OrderedQuantity"],
            "uom": line.get("OrderedUOM", "EA"),
            "unit_price": line["UnitListPrice"],
        }
        for line in lines
    ]


def _erp_tables(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in contract.ERP_TABLES:
        rows = []
        for raw in snapshot[table]:
            row = _strip(raw)
            if table == "customers":
                row["credit_hold"] = bool(row["credit_hold"])
            if table == "sales_orders":
                row["submitted_flag"] = bool(row["submitted_flag"])
                row["lines"] = _order_lines(row["lines"])
            if table == "standard_receipts":
                row["applications"] = [
                    {"invoice_number": ref["ReferenceNumber"], "amount": ref["ApplyAmount"]}
                    for ref in row.pop("remittance_references")
                ]
            rows.append(row)
        tables[table] = rows
    return tables


def _mail_file(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["message_id"],
        "title": row["subject"],
        "system": "mailbox",
        "version": 1,
        "status": "superseded" if row["message_id"].endswith("-OLD-INSTRUCTIONS") else "authoritative",
        "sections": {
            "message": {
                "subject": row["subject"],
                "from": row["sender"],
                "to": row["recipients"],
                "sent_at": row["sent_at"],
                "body": row["body"],
            }
        },
    }


def _chat_message(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "message_id": row["message_id"],
        "thread_id": row["thread_id"],
        "author": row["author"],
        "text": row["text"],
        "posted_at": row["posted_at"],
    }


def _documents(snapshot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    documents = []
    for row in snapshot["drive_files"]:
        documents.append(
            {
                "id": row["file_id"],
                "title": row["name"],
                "system": "shared_drive",
                "version": row["version"],
                "status": "authoritative" if row["is_current"] else "superseded",
                "sections": {
                    "content": {
                        "file_name": row["name"],
                        "mime_type": row["mime_type"],
                        "logical_name": row["logical_name"],
                        "modified_time": row["modified_time"],
                        "text": row["content"],
                    }
                },
            }
        )
    for row in snapshot["mail_messages"]:
        if row["task_id"] is None:
            documents.append(_mail_file(row))
    channels: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot["chat_messages"]:
        if row["task_id"] is None:
            channels[row["channel"]].append(_chat_message(row))
    for channel, messages in sorted(channels.items()):
        documents.append(
            {
                "id": contract.chat_file_id(channel),
                "title": f"{channel} channel history",
                "system": "chat",
                "version": 1,
                "status": "authoritative",
                "sections": {"thread": sorted(messages, key=lambda item: (item["posted_at"], item["message_id"]))},
            }
        )
    for row in snapshot["spreadsheets"]:
        sections = {}
        for cell_range, rows in sorted(row["ranges"].items()):
            sections[cell_range.split("!", 1)[0]] = {"range": cell_range, "rows": rows}
        documents.append(
            {
                "id": row["spreadsheet_id"],
                "title": row["title"],
                "system": "ops_register",
                "version": 1,
                "status": "authoritative",
                "sections": sections,
            }
        )
    return sorted(documents, key=lambda item: item["id"])


def _tenant_payload(world: dict[str, Any], model: dict[str, Any], snapshot) -> dict[str, Any]:
    profile = {
        key: world[key]
        for key in (
            "code", "short", "company", "industry", "profile", "country", "currency", "org", "site",
            "bu", "channel", "domain", "quarter", "people", "customer", "supplier", "expedite_supplier",
        )
    }
    return {
        "schema": "faraday-erpbench100-tenant/1",
        "profile": profile,
        "erp": _erp_tables(snapshot),
        "documents": _documents(snapshot),
        "numbering": {
            "order_import_order": model["order_import"]["new_order_number"],
            "requisition_number": model["inventory_reorder"]["requisition_number"],
            "requisition_id": model["inventory_reorder"]["requisition_id"],
            "receipt_id": model["receivables_collection"]["new_receipt_id"],
            "receiving_header_id": model["receiving_ap_match"]["receipt_header_id"],
            "invoice_id": model["receiving_ap_match"]["invoice_id"],
            "hold_id": model["receiving_ap_match"]["hold_id"],
            "channel_order_base": 52000,
            "channel_order_step": 7,
        },
    }


# ---------------------------------------------------------------------------
# Native investigation routes
# ---------------------------------------------------------------------------


def _routes(task_id: str, key: str, world: dict[str, Any], model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    s = world["short"]
    sheet = contract.sheet_file_id(s)
    customer = world["customer"]["number"]

    def tool(name: str, any_args: bool = False, **args: Any) -> dict[str, Any]:
        route: dict[str, Any] = {"tool": name, "args": args}
        if any_args:
            route["any_args"] = True
        return route

    def read(file_id: str, section: str) -> dict[str, Any]:
        return tool("read_case_file", file_id=file_id, section_id=section)

    def drive(file_id: str) -> dict[str, Any]:
        return read(file_id, "content")

    def mail(message_id: str) -> dict[str, Any]:
        return read(message_id, "message")

    def chat(channel: str) -> dict[str, Any]:
        return read(contract.chat_file_id(f"#{channel}-{s.lower()}"), "thread")

    def tab(name: str) -> dict[str, Any]:
        return read(sheet, name)

    common = {
        "task_contract": [tool("get_incident")],
        "request_mail": [mail(f"MSG-{task_id}-REQUEST")],
        "authority_memo": [mail(f"MSG-{s}-AUTHORITY-0209"), drive(f"FILE-{s}-AUTHORITY-MEMO-0209"), drive(f"FILE-{s}-SOURCE-MAP")],
        "control_thread": [chat("ops")],
        "ops_register": [tab("Register")],
        "item_master": [tool("list_dist_tenant_items"), drive(f"FILE-{s}-PRICE-LIST-CURRENT"), tab("PriceList")],
        "drive_index": [tool("list_case_files"), drive(f"FILE-{s}-OPS-AUDIT-LOG")],
    }
    oi, sv, rc = model["order_import"], model["shipment_verification"], model["receivables_collection"]
    ir, ap, co, pb = model["inventory_reorder"], model["receiving_ap_match"], model["channel_order_sync"], model["price_list_batch"]
    open_supply = f"PO-{s}-OPEN-SUPPLY" if any(sku["open_po_qty"] for sku in ir["skus"]) else ap["po"]
    domain = {
        "order_import": {
            "batch_search": [tool("list_case_files"), drive(f"FILE-{s}-SOURCE-MAP")],
            "batch_file": [drive(oi["batch_file_id"])],
            "prior_partial_import": [drive(oi["stale_batch_file_id"]), tool("get_dist_tenant_sales_order", order_number=oi["prior_order_number"])],
            "existing_orders": [tool("list_dist_tenant_sales_orders", any_args=True, customer_po_number=world["customer"]["po"])],
            "customer_credit": [tool("get_dist_tenant_customer_account", customer_number=customer), drive(f"FILE-{s}-CREDIT-POLICY-R6"), tab("Aging")],
            "superseded_prices": [drive(f"FILE-{s}-PRICE-LIST-2025H2")],
            "audit_trail": [drive(f"FILE-{s}-OPS-AUDIT-LOG")],
            "customer_master": [tab("Customers"), tool("get_dist_tenant_customer_account", customer_number=customer)],
        },
        "shipment_verification": {
            "shipment_header": [tool("get_dist_tenant_shipment", shipment=sv["shipment"])],
            "shipment_lines": [tool("list_dist_tenant_shipment_lines", shipment=sv["shipment"])],
            "pick_search": [tool("list_case_files"), chat("warehouse")],
            "pick_confirmation": [drive(sv["pick_file_id"])],
            "stale_pick": [drive(sv["stale_pick_file_id"])],
            "sales_order": [tool("get_dist_tenant_sales_order", order_number=sv["order"]), tool("list_dist_tenant_sales_orders", any_args=True)],
            "shipping_register": [tab("Shipping")],
            "warehouse_thread": [chat("warehouse")],
        },
        "receivables_collection": {
            "open_invoices": [tool("list_dist_tenant_receivable_invoices", any_args=True, customer_number=customer)],
            "customer_account": [tool("get_dist_tenant_customer_account", customer_number=customer)],
            "existing_receipts": [tool("list_dist_tenant_customer_receipts", any_args=True, customer_number=customer)],
            "remittance_mail": [mail(rc["remittance_message_id"])],
            "remittance_advice": [drive(rc["remittance_file_id"])],
            "credit_policy": [drive(f"FILE-{s}-CREDIT-POLICY-R6")],
            "ar_aging": [tab("Aging"), drive(f"FILE-{s}-AR-AGING-0209")],
            "invoice_detail": [tool("get_dist_tenant_receivable_invoice", any_args=True, transaction_number=rc["invoices"][0]["transaction_number"])],
        },
        "inventory_reorder": {
            "onhand_balances": [tool("list_dist_tenant_onhand")],
            "open_purchase_orders": [tool("list_dist_tenant_purchase_orders", any_args=True)],
            "supply_lines": [tool("list_dist_tenant_purchase_order_lines", any_args=True, po_number=open_supply), tool("get_dist_tenant_purchase_order", any_args=True, po_number=open_supply)],
            "suppliers": [tool("list_dist_tenant_suppliers")],
            "reorder_policy": [drive(ir["policy_file_id"])],
            "stale_policy": [drive(ir["stale_policy_file_id"])],
            "demand_forecast": [drive(f"FILE-{s}-DEMAND-FORECAST-F06"), tab("Reorder")],
            "planning_thread": [chat("planning")],
        },
        "receiving_ap_match": {
            "purchase_order": [tool("get_dist_tenant_purchase_order", po_number=ap["po"]), tool("list_dist_tenant_purchase_orders", any_args=True)],
            "purchase_order_lines": [tool("list_dist_tenant_purchase_order_lines", po_number=ap["po"])],
            "delivery_note": [drive(ap["delivery_note_file_id"])],
            "supplier_invoice": [drive(ap["invoice_file_id"])],
            "invoice_mail": [mail(f"MSG-{s}-SUPPLIER-INVOICE-0207")],
            "ap_policy": [drive(f"FILE-{s}-AP-MATCH-POLICY")],
            "existing_ap_invoices": [tool("list_dist_tenant_ap_invoices", any_args=True)],
            "supplier_master": [tool("list_dist_tenant_suppliers")],
        },
        "channel_order_sync": {
            "export_search": [tool("list_case_files"), mail(f"MSG-{s}-CHANNEL-0209")],
            "channel_export": [drive(co["export_file_id"])],
            "stale_export": [drive(co["stale_export_file_id"])],
            "synced_orders": [tool("list_dist_tenant_sales_orders", any_args=True, source_system=world["channel"])],
            "customer_capture": [chat("customers"), drive(f"FILE-{s}-CUSTOMER-CAPTURE-0209")],
            "customer_master_tab": [tab("Customers"), tool("list_dist_tenant_customers")],
            "customer_account": [tool("list_dist_tenant_customers"), tool("get_dist_tenant_customer_account", any_args=True, customer_number=customer)],
            "sync_mail": [mail(f"MSG-{s}-CHANNEL-0209")],
        },
        "price_list_batch": {
            "batch_search": [tool("list_case_files"), mail(f"MSG-{s}-PRICING-0209")],
            "price_batch": [drive(pb["batch_file_id"])],
            "current_prices": [tool("list_dist_tenant_items"), drive(f"FILE-{s}-PRICE-LIST-CURRENT")],
            "pricing_policy": [tab("PricingPolicy"), mail(f"MSG-{s}-PRICING-0209")],
            "pricing_mail": [mail(f"MSG-{s}-PRICING-0209")],
            "pricing_thread": [chat("pricing")],
            "prior_batch": [drive(pb["stale_batch_file_id"])],
            "superseded_prices": [drive(f"FILE-{s}-PRICE-LIST-2025H2")],
        },
    }
    return {**common, **domain[key]}


# ---------------------------------------------------------------------------
# Sealed truth and the native oracle plan
# ---------------------------------------------------------------------------


def _truth(key: str, world: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    s = world["short"]
    section = model[key]
    if key == "order_import":
        accepted = [line for line in section["lines"] if line["disposition"] == "accepted"]
        return {
            "customer_po": world["customer"]["po"],
            "customer_number": world["customer"]["number"],
            "batch_file_id": section["batch_file_id"],
            "credit_hold": section["credit_hold"],
            "expected_lines": [[line["item_number"], line["quantity"], line["list_price"]] for line in accepted],
            "order_total": section["order_total"],
            "prior_items": [[line["item_number"], line["quantity"]] for line in section["lines"] if line["previously_imported"]],
            "unrelated_orders": [section["prior_order_number"], f"SO-{s}-DECOY"],
        }
    if key == "shipment_verification":
        return {
            "shipment": section["shipment"],
            "corrected": {str(line["shipment_line_id"]): line["picked"] for line in section["lines"] if line["disposition"] == "corrected"},
            "untouched": [str(line["shipment_line_id"]) for line in section["lines"] if line["disposition"] != "corrected"],
            "decoy_line": str(700000 + len(s)),
        }
    if key == "receivables_collection":
        return {
            "receipt_number": section["receipt_number"],
            "receipt_amount": section["receipt_amount"],
            "receipt_date": section["receipt_date"],
            "customer_number": world["customer"]["number"],
            "applications": [[row["transaction_number"], row["amount"]] for row in section["invoices"] if row["covered"]],
            "uncovered": [row["transaction_number"] for row in section["invoices"] if not row["covered"]],
            "decoy_invoice": f"INV-{s}-DECOY",
        }
    if key == "inventory_reorder":
        return {
            "organization_code": world["org"],
            "expected_lines": [[sku["item_number"], sku["reorder_qty"], sku["unit_cost"]] for sku in section["skus"] if sku["below"]],
            "total": section["requisition_amount"],
            "supplier_number": world["supplier"]["number"],
            "expedite_supplier_number": world["expedite_supplier"]["number"],
            "below_items": [sku["item_number"] for sku in section["skus"] if sku["below"]],
        }
    if key == "receiving_ap_match":
        return {
            "po": section["po"],
            "invoice_number": section["invoice_number"],
            "supplier_number": world["supplier"]["number"],
            "expected_received": [[section["po"], line["line"], line["received"]] for line in section["lines"]],
            "invoice_lines": [[line["line"], line["invoiced_qty"], line["invoice_price"]] for line in section["lines"]],
            "invoice_total": section["invoice_total"],
            "held_lines": [line["line"] for line in section["lines"] if not line["matched"]],
            "closed_po": f"PO-{s}-CLOSED",
        }
    if key == "channel_order_sync":
        return {
            "channel": world["channel"],
            "create_rows": {row["channel_order_id"]: row["total"] for row in section["rows"] if row["disposition"] == "create"},
            "already_synced_orders": [row["synced_order_number"] for row in section["rows"] if row["already_synced"]],
            "new_customer": section["new_customer"],
        }
    if key == "price_list_batch":
        return {
            "applied": [[line["item_number"], line["new_price"], line["effective_date"]] for line in section["applied"]],
            "item_numbers": [item["item_number"] for item in model["items"]],
        }
    raise KeyError(key)


def _plan(key: str, task: dict[str, Any], world: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate upstream oracle write steps into native protected-action calls."""

    supplier_numbers = {world["supplier"]["name"]: world["supplier"]["number"], world["expedite_supplier"]["name"]: world["expedite_supplier"]["number"]}
    item_by_id = {item["item_id"]: item["item_number"] for item in model["items"]}
    section = model[key]
    plan: list[dict[str, Any]] = []
    for step in task["oracle_steps"]:
        tool, a = step["tool"], step["arguments"]
        if tool == "oracle_fusion.sales_orders.create" and key == "order_import":
            plan.append({"action": "commit_dist_tenant_order_import", "target": a["CustomerPONumber"], "payload": {
                "customer_number": a["BuyingPartyNumber"], "source_file_id": a["SourceTransactionNumber"], "submit": a["SubmittedFlag"],
                "lines": [{"item_number": line["ProductNumber"], "quantity": line["OrderedQuantity"], "unit_price": line["UnitListPrice"]} for line in a["lines"]],
            }})
        elif tool == "oracle_fusion.shipment_lines.update":
            plan.append({"action": "correct_dist_tenant_shipment_line", "target": str(a["ShipmentLine"]), "payload": {"shipped_quantity": a["ShippedQuantity"], "comment": a["Comments"]}})
        elif tool == "oracle_fusion.standard_receipts.create":
            plan.append({"action": "apply_dist_tenant_customer_receipt", "target": a["ReceiptNumber"], "payload": {
                "customer_number": a["CustomerAccountNumber"], "amount": a["ReceiptAmount"], "receipt_date": a["ReceiptDate"], "method": a["ReceiptMethod"],
                "applications": [{"invoice_number": ref["ReferenceNumber"], "amount": ref["ApplyAmount"]} for ref in a["remittanceReferences"]],
            }})
        elif tool == "oracle_fusion.purchase_requisitions.create":
            suppliers = {supplier_numbers[line["Supplier"]] for line in a["lines"]}
            if len(suppliers) != 1:
                raise ValueError(f"{task['task_id']}: requisition spans suppliers {sorted(suppliers)}")
            plan.append({"action": "create_dist_tenant_requisition", "target": world["org"], "payload": {
                "supplier_number": suppliers.pop(), "description": a["Description"], "justification": a["Justification"],
                "lines": [{"item_number": line["ItemNumber"], "quantity": line["Quantity"], "unit_price": line["UnitPrice"], "need_by_date": line["RequestedDeliveryDate"]} for line in a["lines"]],
            }})
        elif tool == "oracle_fusion.purchase_requisitions.submit":
            plan.append({"action": "submit_dist_tenant_requisition", "target": a["purchaseRequisitionsUniqID"], "payload": {}})
        elif tool == "oracle_fusion.receiving_receipt_requests.create":
            pos = {line["DocumentNumber"] for line in a["lines"]}
            if len(pos) != 1:
                raise ValueError(f"{task['task_id']}: receipt spans purchase orders {sorted(pos)}")
            plan.append({"action": "receive_dist_tenant_po_delivery", "target": pos.pop(), "payload": {"lines": [{"line": line["DocumentLineNumber"], "quantity": line["Quantity"]} for line in a["lines"]]}})
        elif tool == "oracle_fusion.invoices.create":
            plan.append({"action": "enter_dist_tenant_supplier_invoice", "target": a["InvoiceNumber"], "payload": {
                "supplier_number": supplier_numbers[a["Supplier"]], "po_number": a["invoiceLines"][0]["PurchaseOrderNumber"], "invoice_date": a["InvoiceDate"],
                "invoice_amount": a["InvoiceAmount"],
                "lines": [{"line": line["PurchaseOrderLineNumber"], "quantity": line["Quantity"], "unit_price": line["UnitPrice"]} for line in a["invoiceLines"]],
            }})
        elif tool == "oracle_fusion.invoice_holds.create":
            plan.append({"action": "hold_dist_tenant_supplier_invoice", "target": section["invoice_number"], "payload": {
                "hold_name": a["HoldName"], "lines": [line["line"] for line in section["lines"] if not line["matched"]], "reason": a["HoldReason"],
            }})
        elif tool == "oracle_fusion.invoices.validate":
            plan.append({"action": "validate_dist_tenant_supplier_invoice", "target": a["InvoiceNumber"], "payload": {}})
        elif tool == "oracle_fusion.sales_orders.create" and key == "channel_order_sync":
            plan.append({"action": "create_dist_tenant_channel_order", "target": a["SourceTransactionNumber"], "payload": {"buyer": a["BuyingPartyName"], "order_total": a["OrderTotal"]}})
        elif tool == "google_sheets.spreadsheets.values.append" and key == "channel_order_sync":
            name, _number, email, tax_id, channel = a["values"][0]
            plan.append({"action": "capture_dist_tenant_channel_customer", "target": name, "payload": {"email": email, "tax_id": tax_id, "channel": channel}})
        elif tool == "oracle_fusion.items.update":
            plan.append({"action": "update_dist_tenant_item_list_price", "target": item_by_id[a["ItemId"]], "payload": {"list_price": a["ListPrice"], "effective_date": a["EffectiveDate"]}})
    actions = {step["action"] for step in plan}
    if not plan or not actions <= set(contract.FAMILIES[key]["actions"]):
        raise ValueError(f"{task['task_id']}: unexpected native plan {sorted(actions)}")
    return plan


def _trap_files(key: str, short: str) -> list[str]:
    traps = {
        "order_import": [f"FILE-{short}-PRICE-LIST-2025H2"],
        "shipment_verification": [f"FILE-{short}-PICK-CONFIRM-0205"],
        "receivables_collection": [],
        "inventory_reorder": [f"FILE-{short}-REORDER-POLICY-R3"],
        "receiving_ap_match": [],
        "channel_order_sync": [f"FILE-{short}-CHANNEL-EXPORT-0202"],
        "price_list_batch": [f"FILE-{short}-PRICE-BATCH-Q1", f"FILE-{short}-PRICE-LIST-2025H2"],
    }[key]
    return [*traps, f"MSG-{short}-OLD-INSTRUCTIONS"]


def _value_at_risk(key: str, model: dict[str, Any]) -> float:
    section = model[key]
    field = contract.FAMILIES[key]["value_field"]
    if field is not None:
        return float(section[field])
    return round(sum(abs(line["new_price"] - line["current_price"]) for line in section["applied"]) * 10000, 2)


def _prompt(task: dict[str, Any], key: str) -> str:
    spec = contract.FAMILIES[key]
    header, request, tail = task["prompt"].split("\n\n")
    actions = ", ".join(spec["actions"])
    role_primary, role_secondary = spec["roles"]
    native = (
        "Tenant world: the mailbox, chat channels, shared drive and ops register are versioned case files "
        "(list_case_files, read_case_file), and the ERP is read through the dist_tenant tools. get_incident returns "
        "the task contract with the decision options, status options and register fields. Commit ERP changes only "
        f"through request_approval followed by execute_action ({actions}). Record the outcome as one "
        f"{contract.artifact_type(key)} structured artifact whose content holds every register field, cite only the "
        "current-authority case files you relied on, and read the ERP record and the artifact back after writing. "
        f"Notify {role_primary} with the recommended option id, the primary record and the key register figures, and "
        f"notify {role_secondary} with the decision status id. Read the handoffs back with "
        f"{contract.HANDOFF_READ_TOOL}, then finish with the primary record and the operative source file id as evidence."
    )
    return f"{header}\n\n{request}\n\n{native}\n\n{tail}"


def run(benchmarks_root: Path, repo_root: Path) -> None:
    benchmarks_root = Path(benchmarks_root)
    repo_root = Path(repo_root)
    upstream_root = benchmarks_root / contract.SOURCE
    revision = _revision(benchmarks_root)
    spec, upstream_world = _load_upstream(upstream_root)
    built = {task["task_id"]: task for task in spec.build_tasks()}
    selection = json.loads((benchmarks_root / "distributor-index" / "tasks.json").read_text(encoding="utf-8"))
    rows = sorted((row for row in selection if row["benchmark"] == contract.SOURCE), key=lambda row: row["task_id"])

    fixture_dir = repo_root / FIXTURE_DIR
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    fixture_dir.mkdir(parents=True)
    written: list[Path] = []
    tenants: dict[str, dict[str, Any]] = {}
    manifest: list[dict[str, Any]] = []

    for ordinal, row in enumerate(rows, start=1):
        task_id = row["task_id"]
        release_dir = upstream_root / contract.UPSTREAM["path"] / task_id
        task = json.loads((release_dir / "tests" / "task.json").read_text(encoding="utf-8"))
        key = task["metadata"]["category"]
        if key not in contract.FAMILIES:
            raise ValueError(f"{task_id}: family {key} is not ported")
        reference = built[task_id]
        for field in ("expected_answer", "oracle_steps", "required_investigations", "decision_options", "register_contract", "rubric"):
            if task[field] != reference[field]:
                raise ValueError(f"{task_id}: released {field} differs from spec.build_tasks()")
        model = spec.world_model(task["tenant_code"])
        world = model["world"]
        snapshot = _snapshot(upstream_world, task)

        tenant = _tenant_payload(world, model, snapshot)
        code = world["code"].lower()
        if code in tenants:
            if tenants[code] != tenant:
                raise ValueError(f"{task_id}: tenant-level seed differs between tasks of {code}")
        else:
            tenants[code] = tenant

        routes = _routes(task_id, key, world, model)
        investigation_ids = [item["id"] for item in task["required_investigations"]]
        if investigation_ids != list(routes):
            raise ValueError(f"{task_id}: investigation ids {investigation_ids} do not match native routes {list(routes)}")
        request_mail = next(item for item in snapshot["mail_messages"] if item["task_id"] == task_id)
        task_chat = [{"channel": item["channel"], **_chat_message(item)} for item in snapshot["chat_messages"] if item["task_id"] == task_id]
        plan = _plan(key, task, world, model)
        expected = task["expected_answer"]
        fixture = {
            "schema": "faraday-erpbench100-task/1",
            "upstream_task_id": task_id,
            "tier": row["tier"],
            "selection_reason": row["reason"],
            "family_key": key,
            "tenant": code,
            "short": world["short"],
            "title": task["task_name"],
            "upstream_prompt": task["prompt"],
            "upstream_difficulty": task["metadata"]["difficulty"],
            "upstream_reference_tool_calls": task["metadata"]["reference_tool_calls"],
            "expected_answer": expected,
            "decision_options": [{"id": item["id"], "label": item["label"], "selected": item["selected"]} for item in task["decision_options"]],
            "status_options": task["status_options"],
            "answer_fields": {name: {"type": prop["type"], "description": prop["description"]} for name, prop in task["answer_schema"]["properties"].items()},
            "register_columns": task["register_contract"]["columns"],
            "numeric_fields": list(spec.NUMERIC_FIELDS[key]),
            "rubric": [{"id": item["id"], "category": item["category"], "points": item["points"]} for item in task["rubric"]],
            "investigations": [{"id": item["id"], "description": item["description"], "routes": routes[item["id"]]} for item in task["required_investigations"]],
            "documents": [_mail_file(request_mail)],
            "chat_messages": task_chat,
            "truth": _truth(key, world, model),
            "oracle_plan": plan,
            "operative_source": expected["source_reference"],
            "trap_file_ids": _trap_files(key, world["short"]),
            "target_id": plan[0]["target"],
            "value_at_risk": _value_at_risk(key, model),
        }
        path = fixture_dir / f"{task_id}.json"
        _dump(path, fixture)
        written.append(path)

        family = contract.FAMILIES[key]
        manifest.append(
            {
                "id": f"faraday-erpbench100-{ordinal:03d}",
                "version": contract.TASK_VERSION,
                "family": family["family"],
                "title": f"{task['task_name']} \u2014 {world['company']}",
                "prompt": _prompt(task, key),
                "seed": 100000 + int(task_id.split("-")[-1]),
                "difficulty": family["difficulty"],
                "systems": list(contract.SYSTEMS),
                "max_tool_calls": 80,
                "horizon_minutes": 240,
                "tags": [
                    "distributor",
                    f"source:{contract.SOURCE}",
                    f"upstream:{task_id}",
                    f"tenant:{code}",
                    f"tier:{row['tier']}",
                    f"workflow:{key}",
                ],
                "workflow_stages": [
                    {"id": stage["id"], "objective": stage["objective"], "depends_on": list(stage["depends_on"])}
                    for stage in contract.WORKFLOW_STAGES
                ],
            }
        )

    for code, tenant in sorted(tenants.items()):
        path = fixture_dir / f"tenant-{code}.json"
        _dump(path, tenant)
        written.append(path)

    manifest_path = repo_root / MANIFEST
    _dump(manifest_path, manifest)
    written.append(manifest_path)

    raw_dir = repo_root / RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name in RAW_COPIES:
        destination = raw_dir / name
        shutil.copyfile(upstream_root / name, destination)
        written.append(destination)
    selection_path = raw_dir / "selection.json"
    _dump(selection_path, [
        {key: row[key] for key in ("task_id", "tier", "family", "tenant", "company", "industry", "reason")}
        for row in rows
    ])
    written.append(selection_path)

    write_provenance(contract.SOURCE, {**contract.UPSTREAM, "revision": revision}, written)
