"""Static contract shared by the ERPBench-100 importer and the native families.

The importer (``examples/distributor_import/erpbench100.py``) and the runtime
modules both read these tables, so tool names, action names, roles, and write
scopes are defined exactly once.
"""

from __future__ import annotations

from typing import Any

SOURCE = "erpbench-100"
TASK_VERSION = "0.8.0"
AS_OF = "2026-02-09T09:00:00Z"

UPSTREAM = {
    "repository": "https://github.com/blobfishai/erp-agent-simulation",
    "license": "Apache-2.0 (code); CC-BY-4.0 (data)",
    "attribution": "ERPBench-100 by Blobfish AI",
    "path": "benchmark/erpbench100/release/harbor/tasks",
}

SYSTEMS = ("ERP", "shared drive", "mailbox", "chat", "ops register")

# Native read tools. Every family exposes the full tenant read surface, as the
# upstream world exposes every provider to every task.
READ_TOOLS = (
    "list_dist_tenant_items",
    "list_dist_tenant_customers",
    "get_dist_tenant_customer_account",
    "list_dist_tenant_sales_orders",
    "get_dist_tenant_sales_order",
    "get_dist_tenant_shipment",
    "list_dist_tenant_shipment_lines",
    "list_dist_tenant_receivable_invoices",
    "get_dist_tenant_receivable_invoice",
    "list_dist_tenant_customer_receipts",
    "list_dist_tenant_onhand",
    "list_dist_tenant_suppliers",
    "list_dist_tenant_purchase_orders",
    "get_dist_tenant_purchase_order",
    "list_dist_tenant_purchase_order_lines",
    "list_dist_tenant_requisitions",
    "get_dist_tenant_requisition",
    "list_dist_tenant_receiving_receipts",
    "list_dist_tenant_ap_invoices",
    "get_dist_tenant_ap_invoice",
)

# Reads back the review handoffs sent with notify (the native counterpart of the
# upstream mail-draft and channel-history readbacks).
HANDOFF_READ_TOOL = "list_dist_tenant_handoffs"

CORE_TOOLS = (
    "get_incident",
    "list_case_files",
    "read_case_file",
    "create_structured_artifact",
    "get_structured_artifact",
    "request_approval",
    "execute_action",
    "notify",
    "wait",
    "finish",
)

ACTION_CONTRACTS = {
    "commit_dist_tenant_order_import": (
        "target=customer_po_number; payload={customer_number, source_file_id, submit, "
        "lines:[{item_number, quantity, unit_price}]}"
    ),
    "correct_dist_tenant_shipment_line": "target=shipment_line_id; payload={shipped_quantity, comment}",
    "apply_dist_tenant_customer_receipt": (
        "target=receipt_number; payload={customer_number, amount, receipt_date, method, "
        "applications:[{invoice_number, amount}]}"
    ),
    "create_dist_tenant_requisition": (
        "target=organization_code; payload={supplier_number, description, justification, "
        "lines:[{item_number, quantity, unit_price, need_by_date}]}"
    ),
    "submit_dist_tenant_requisition": "target=requisition_number; payload={}",
    "receive_dist_tenant_po_delivery": "target=po_number; payload={lines:[{line, quantity}]}",
    "enter_dist_tenant_supplier_invoice": (
        "target=invoice_number; payload={supplier_number, po_number, invoice_date, invoice_amount, "
        "lines:[{line, quantity, unit_price}]}"
    ),
    "validate_dist_tenant_supplier_invoice": "target=invoice_number; payload={}",
    "hold_dist_tenant_supplier_invoice": "target=invoice_number; payload={hold_name, lines:[line numbers], reason}",
    "create_dist_tenant_channel_order": "target=channel_order_id; payload={buyer, order_total}",
    "capture_dist_tenant_channel_customer": "target=customer_name; payload={email, tax_id, channel}",
    "update_dist_tenant_item_list_price": "target=item_number; payload={list_price, effective_date}",
}

FAMILIES: dict[str, dict[str, Any]] = {
    "order_import": {
        "family": "distributor_order_import",
        "label": "Customer order import",
        "roles": ("customer_service", "sales_operations"),
        "actions": ("commit_dist_tenant_order_import",),
        "primary_action": "commit_dist_tenant_order_import",
        "readback_tools": ("get_dist_tenant_sales_order", "list_dist_tenant_sales_orders"),
        "write_tables": ("sales_orders",),
        "difficulty": "hard",
        "value_field": "order_total",
    },
    "shipment_verification": {
        "family": "distributor_shipment_verification",
        "label": "Shipment verification",
        "roles": ("warehouse_operations", "transportation"),
        "actions": ("correct_dist_tenant_shipment_line",),
        "primary_action": "correct_dist_tenant_shipment_line",
        "readback_tools": ("list_dist_tenant_shipment_lines",),
        "write_tables": ("shipment_lines",),
        "difficulty": "hard",
        "value_field": "confirmed_value",
    },
    "receivables_collection": {
        "family": "distributor_receivables_collection",
        "label": "Receipt application and collections",
        "roles": ("credit_control", "accounts_receivable"),
        "actions": ("apply_dist_tenant_customer_receipt",),
        "primary_action": "apply_dist_tenant_customer_receipt",
        "readback_tools": ("list_dist_tenant_customer_receipts",),
        "write_tables": ("standard_receipts", "receivables_invoices"),
        "difficulty": "hard",
        "value_field": "receipt_amount",
    },
    "inventory_reorder": {
        "family": "distributor_inventory_reorder",
        "label": "Reorder monitoring and requisition",
        "roles": ("supply_planning", "procurement"),
        "actions": ("create_dist_tenant_requisition", "submit_dist_tenant_requisition"),
        "primary_action": "create_dist_tenant_requisition",
        "readback_tools": ("get_dist_tenant_requisition", "list_dist_tenant_requisitions"),
        "write_tables": ("purchase_requisitions",),
        "difficulty": "expert",
        "value_field": "requisition_amount",
    },
    "receiving_ap_match": {
        "family": "distributor_receiving_ap_match",
        "label": "Receiving and three-way match",
        "roles": ("accounts_payable", "procurement"),
        "actions": (
            "receive_dist_tenant_po_delivery",
            "enter_dist_tenant_supplier_invoice",
            "validate_dist_tenant_supplier_invoice",
            "hold_dist_tenant_supplier_invoice",
        ),
        "primary_action": "receive_dist_tenant_po_delivery",
        "readback_tools": ("get_dist_tenant_ap_invoice",),
        "write_tables": (
            "receiving_receipt_requests",
            "purchase_order_lines",
            "ap_invoices",
            "invoice_holds",
        ),
        "difficulty": "expert",
        "value_field": "invoice_total",
    },
    "channel_order_sync": {
        "family": "distributor_channel_order_sync",
        "label": "Channel order sync and customer capture",
        "roles": ("sales_operations", "customer_service"),
        "actions": ("create_dist_tenant_channel_order", "capture_dist_tenant_channel_customer"),
        "primary_action": "create_dist_tenant_channel_order",
        "readback_tools": ("list_dist_tenant_sales_orders", "get_dist_tenant_sales_order"),
        # Upstream captured the buyer in the register sheet; natively the capture
        # lands in the customer master, so that table is in scope here.
        "write_tables": ("sales_orders", "customers"),
        "difficulty": "expert",
        "value_field": "synced_value",
    },
    "price_list_batch": {
        "family": "distributor_price_list_batch",
        "label": "Effective-dated price batch",
        "roles": ("pricing", "sales_operations"),
        "actions": ("update_dist_tenant_item_list_price",),
        "primary_action": "update_dist_tenant_item_list_price",
        "readback_tools": ("list_dist_tenant_items",),
        "write_tables": ("items",),
        "difficulty": "hard",
        "value_field": None,
    },
}

FAMILY_BY_NAME = {spec["family"]: key for key, spec in FAMILIES.items()}

ERP_TABLES = (
    "items",
    "customers",
    "suppliers",
    "sales_orders",
    "shipments",
    "shipment_lines",
    "receivables_invoices",
    "standard_receipts",
    "onhand_balances",
    "purchase_orders",
    "purchase_order_lines",
    "purchase_requisitions",
    "receiving_receipt_requests",
    "ap_invoices",
    "invoice_holds",
)

# Primary key per native ERP table (rows are stored keyed by str(primary key)).
TABLE_KEYS = {
    "items": "item_number",
    "customers": "customer_number",
    "suppliers": "supplier_number",
    "sales_orders": "order_number",
    "shipments": "shipment",
    "shipment_lines": "shipment_line_id",
    "receivables_invoices": "transaction_number",
    "standard_receipts": "receipt_number",
    "onhand_balances": "balance_id",
    "purchase_orders": "po_number",
    "purchase_order_lines": "po_line_id",
    "purchase_requisitions": "requisition_number",
    "receiving_receipt_requests": "header_interface_id",
    "ap_invoices": "invoice_number",
    "invoice_holds": "hold_id",
}

WORKFLOW_STAGES = (
    {"id": "read_contract", "objective": "Read the task contract, request and authority memo", "depends_on": ()},
    {"id": "gather_evidence", "objective": "Read the operative and superseded evidence and the ERP records", "depends_on": ("read_contract",)},
    {"id": "calculate", "objective": "Recompute every register figure from the operative evidence", "depends_on": ("gather_evidence",)},
    {"id": "decide", "objective": "Choose the policy-supported decision option and status", "depends_on": ("calculate",)},
    {"id": "commit", "objective": "Commit the ERP writes through approved protected actions", "depends_on": ("decide",)},
    {"id": "read_back", "objective": "Read the committed ERP records back", "depends_on": ("commit",)},
    {"id": "register", "objective": "Record and read back the register artifact", "depends_on": ("read_back",)},
    {"id": "hand_off", "objective": "Notify the contracted roles and finish with evidence", "depends_on": ("register",)},
)


def artifact_type(family_key: str) -> str:
    return f"dist_{family_key}_register"


def chat_file_id(channel: str) -> str:
    return "CHAT-" + channel.lstrip("#").upper()


def sheet_file_id(short: str) -> str:
    return f"SHEET-{short}-OPS"
