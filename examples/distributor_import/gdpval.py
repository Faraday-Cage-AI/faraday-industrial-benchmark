"""Rebuild curated GDPval tasks as native distributor tool-world fixtures.

GDPval rows are file-producing prompts graded by rubric. This importer turns
23 curated wholesale and distribution rows into deterministic scenarios:

* reference workbooks become queryable tables (``query_gdp_table``) and
  reference documents become versioned case files;
* the requested deliverable becomes one structured artifact with a published
  submission contract;
* every rubric item is classified either as scored by a sealed field check or
  as recorded-unscored with a reason (file type, formatting, prose quality);
* web-research inputs are frozen into case files from the upstream expert
  deliverable so episodes never browse.

Expected values are recomputed from the reference data wherever the data allow
it and cross-checked against the rubric; where the upstream prompt, rubric, and
deliverable disagree, the resolution is written to the grader fixture notes.
Re-running the importer is byte-identical.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import re
import zipfile
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import docx
import openpyxl
from pypdf import PdfReader

from faraday_industrial_benchmark.distributor.gdpval_checks import evaluate
from faraday_industrial_benchmark.distributor.provenance import write_provenance

Json = dict[str, Any]

SOURCE = "gdpval"
VERSION = "0.7.0"
UPSTREAM = {
    "repository": "openai/gdpval",
    "revision": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    "license": "none declared",
    "note": "deliverables and rubrics committed as grader-only material by owner decision",
}

FAMILIES: dict[str, Json] = {
    "distributor_sales_analytics": {
        "action": "publish_gdp_analysis",
        "roles": ("sales_operations", "demand_planning"),
        "systems": ("ERP", "BI", "DMS"),
    },
    "distributor_pricing_quotation": {
        "action": "issue_gdp_quotation",
        "roles": ("sales_operations", "controller"),
        "systems": ("ERP", "CPQ", "DMS"),
    },
    "distributor_inventory_planning": {
        "action": "release_gdp_inventory_plan",
        "roles": ("inventory_control", "supply_planning"),
        "systems": ("ERP", "WMS", "DMS"),
    },
    "distributor_warehouse_shipping": {
        "action": "post_gdp_warehouse_record",
        "roles": ("warehouse_operations", "transportation"),
        "systems": ("WMS", "TMS", "DMS"),
    },
    "distributor_policy_documents": {
        "action": "issue_gdp_procedure",
        "roles": ("sales_operations", "warehouse_operations"),
        "systems": ("DMS", "ERP", "CRM"),
    },
}

GENERAL_CONVENTIONS = [
    "Content is a JSON object; field names follow the contract paths (dots separate nested keys).",
    "Numbers are plain JSON numbers without currency symbols or thousands separators.",
    "Percentages are on a 0-100 scale unless a field says it is a fraction.",
    "Dates are ISO strings (YYYY-MM-DD); months are YYYY-MM.",
    "Code fields take values from the code_catalog section of this case file.",
    "Map keys use the identifiers exactly as they appear in the source data.",
]

UNSCORED_REASONS = {
    "file_format": "requires a specific file type or file packaging; the tool world records structured artifacts instead of files",
    "presentation": "visual layout, styling, charting, or titling that a deterministic field check cannot judge",
    "workbook_mechanics": "spreadsheet mechanics (formulas, tables, filters, cell types) with no structured-artifact equivalent",
    "narrative": "free-text quality, tone, or persuasiveness that requires human judgment",
    "upstream_conflict": "rubric value contradicts the upstream reference data; the data-derived value is scored instead",
    "not_applicable": "condition never occurs in the reference data, so the item cannot discriminate",
}

GLOBAL_RULES: list[tuple[str, str]] = [
    (
        (r"^\s*(provides|delivers|delivered|output contains|the deliverable is|a word file|"
        r"an excel workbook|the final output|deliver)\b.*\b(file|workbook|document|deck|"
        r"presentation|pdf|xlsx|docx|pptx|spreadsheet)\b"),
        "u:file_format",
    ),
    (r"^\s*(the )?(final )?(deliverable|submission) is (provided|delivered|a)\b", "u:file_format"),
    (r"overall formatting and style", "u:presentation"),
]


# --- source access -----------------------------------------------------------


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return list(ast.literal_eval(value))


class SourceTask:
    def __init__(self, root: Path, index_row: Json):
        self.root = root
        self.row = json.loads(Path(index_row["exported_row_file"]).read_text(encoding="utf-8"))
        self.task_id = self.row["task_id"]
        self.prompt = self.row["prompt"]
        rubric = self.row["rubric_json"]
        self.rubric = json.loads(rubric) if isinstance(rubric, str) else rubric
        self.references = [root / "gdpval" / item for item in _as_list(self.row["reference_files"])]
        self.deliverables = [root / "gdpval" / item for item in _as_list(self.row["deliverable_files"])]

    def _find(self, paths: list[Path], needle: str) -> Path:
        matches = [path for path in paths if needle.lower() in path.name.lower()]
        if len(matches) != 1:
            raise ValueError(f"{self.task_id}: expected one file matching {needle!r}, got {matches}")
        return matches[0]

    def ref(self, needle: str) -> Path:
        return self._find(self.references, needle)

    def deliv(self, needle: str) -> Path:
        return self._find(self.deliverables, needle)


def _cell(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        rounded = round(value, 6)
        return int(rounded) if rounded.is_integer() else rounded
    if isinstance(value, str):
        return value.strip()
    return value


def xlsx_rows(path: Path, sheet: str | None = None) -> list[tuple[Any, ...]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook[sheet] if sheet else workbook.worksheets[0]
    rows = [tuple(_cell(value) for value in row) for row in worksheet.iter_rows(values_only=True)]
    workbook.close()
    return rows


def docx_paragraphs(path: Path) -> list[str]:
    document = docx.Document(str(path))
    lines = [paragraph.text.strip() for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            lines.append(" | ".join(cells))
    return [line for line in lines if line]


def pdf_text(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                lines.append(line)
    return lines


def pptx_slides(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.findall(r"\d+", name)[0]),
        )
        slides = []
        for name in names:
            xml = archive.read(name).decode("utf-8")
            slides.append(" ".join(re.findall(r"<a:t>([^<]*)</a:t>", xml)))
    return slides


# --- spec helpers --------------------------------------------------------------


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def check(check_id: str, kind: str, path: str | list[Any] | None = None, expected: Any = None, **extra: Any) -> Json:
    row: Json = {"id": check_id, "kind": kind}
    if path is not None:
        row["path"] = path.split(".") if isinstance(path, str) else list(path)
    if expected is not None:
        row["expected"] = expected
    row.update(extra)
    return row


def num(check_id: str, path: str | list[Any], expected: float, tolerance: float = 0.01) -> Json:
    return check(check_id, "number", path, expected, tolerance=tolerance)


def table(suffix: str, title: str, description: str, columns: list[str], rows: list[list[Any]]) -> Json:
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"table {suffix}: row width {len(row)} != {len(columns)}")
    return {"suffix": suffix, "title": title, "description": description, "columns": columns, "rows": rows}


def document(suffix: str, title: str, system: str, sections: Json) -> Json:
    return {"suffix": suffix, "title": title, "system": system, "sections": sections}


def field(path: str, kind: str, description: str) -> Json:
    return {"path": path, "type": kind, "description": description}


def codes(*pairs: tuple[str, str]) -> list[Json]:
    return [{"code": code, "meaning": meaning} for code, meaning in pairs]


def r2(value: float) -> float:
    return round(value + 0.0, 2)


def r4(value: float) -> float:
    return round(value + 0.0, 4)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def classify(rubric: list[Json], rules: list[tuple[str, str]], check_ids: list[str]) -> list[Json]:
    """Assign every rubric item to sealed checks or to an unscored reason."""

    rows: list[Json] = []
    unmatched: list[str] = []
    for item in rubric:
        text = " ".join(str(item["criterion"]).split())
        target = None
        for pattern, template in [*rules, *GLOBAL_RULES]:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                target = template
                for group_index, group in enumerate(match.groups(), start=1):
                    target = target.replace(f"{{{group_index}}}", slug(group or ""))
                break
        base = {
            "rubric_item_id": item["rubric_item_id"],
            "score": item["score"],
            "criterion": item["criterion"],
        }
        if target is None:
            unmatched.append(text)
            continue
        if target.startswith("u:"):
            reason = target[2:]
            require(reason in UNSCORED_REASONS, f"unknown unscored reason {reason}")
            rows.append({**base, "status": "unscored", "reason": reason})
            continue
        resolved: list[str] = []
        for name in target[2:].split(","):
            if name.endswith("*"):
                expanded = [check_id for check_id in check_ids if check_id.startswith(name[:-1])]
                require(bool(expanded), f"wildcard {name} matched no checks")
                resolved.extend(expanded)
            else:
                require(name in check_ids, f"rubric target {name!r} is not a check id ({text[:80]})")
                resolved.append(name)
        rows.append({**base, "status": "scored", "criteria": sorted(set(resolved))})
    require(not unmatched, "unclassified rubric items:\n" + "\n".join(unmatched))
    return rows


TaskBuilder = Callable[[SourceTask], Json]


# --- task 01: Gravon exchange program ------------------------------------------


def t01_exchange_program(src: SourceTask) -> Json:
    phone_prompt = "455-864-3867"
    phone = "560-555-3867"
    require(phone_prompt in src.prompt, "task 01 prompt phone changed upstream")
    request = src.prompt.replace(phone_prompt, phone)
    steps = [
        "submit_ea_form",
        "email_form_to_assigned_rep",
        "rep_returns_form_with_ea_number",
        "place_replacement_order",
        "print_form_into_shipment",
        "write_ea_number_on_box",
        "ship_with_prepaid_freight",
    ]
    header = [
        "customer_name",
        "customer_address",
        "customer_phone",
        "customer_number",
        "ea_number",
        "request_date",
        "replacement_order_po",
        "reason_for_request",
    ]
    truth = {
        "program_type": "exchange",
        "exchange_scope": "underperforming_styles_sizes_for_updated_inventory",
        "administered_by": "sales_representatives",
        "effective_date": "2025-07-01",
        "eligibility": "credit_worthy_customers",
        "frequency": "once_per_season",
        "credit_use": "replacement_merchandise_only",
        "replacement_order_timing": "when_ea_number_granted",
        "form_routing": "email_to_assigned_sales_rep",
        "freight_paid_by": "customer",
        "restocking_fee_per_pair_usd": 5,
        "restocking_fee_billing": "charged_to_customer_account",
        "warehouse": {"address": "555 Waters Avenue, Austin, TX 78726", "phone": phone},
        "process_steps": steps,
        "benefits": ["increase_sales_with_updated_full_size_runs", "remove_dated_merchandise"],
        "form": {
            "header_fields": header,
            "line_columns": ["style_color", "style_name", "pairs_shipped", "pairs_to_return"],
            "totals": ["pairs_shipped"],
            "footer_notes": ["freight_prepaid_by_customer", "restocking_fee_paid_by_customer"],
            "signoffs": ["sales_representative", "sales_manager", "general_manager"],
            "ship_to": {"address": "555 Waters Avenue, Austin, TX 78726", "phone": phone},
        },
    }
    catalog = {
        "program_type": codes(("exchange", "merchandise exchange program"), ("return", "return-for-refund program"), ("consignment", "consignment stock")),
        "exchange_scope": codes(
            ("underperforming_styles_sizes_for_updated_inventory", "swap slow styles/sizes for new, updated inventory"),
            ("damaged_goods_only", "defective or damaged pairs only"),
            ("any_unsold_inventory", "any unsold pairs at any time"),
        ),
        "administered_by": codes(("sales_representatives", "independent sales reps"), ("customer_service", "central customer service desk"), ("warehouse", "warehouse team")),
        "eligibility": codes(("credit_worthy_customers", "customers in good credit standing"), ("all_customers", "every account"), ("prepaid_customers", "cash-in-advance accounts only")),
        "frequency": codes(("once_per_season", "one exchange per season"), ("once_per_year", "one exchange per year"), ("unlimited", "no limit")),
        "credit_use": codes(("replacement_merchandise_only", "credit only applies to replacement merchandise"), ("cash_refund", "credit refunded in cash"), ("open_account_credit", "credit usable against any invoice")),
        "replacement_order_timing": codes(("when_ea_number_granted", "replacement order placed when the EA number is granted"), ("after_return_received", "after the warehouse receives the return"), ("next_season", "with next season's order")),
        "form_routing": codes(("email_to_assigned_sales_rep", "email the form to the account's assigned sales rep"), ("mail_to_warehouse", "mail the form to the warehouse"), ("customer_service_portal", "upload to customer service portal")),
        "freight_paid_by": codes(("customer", "customer pays freight"), ("gravon", "Gravon pays freight"), ("shared", "split freight")),
        "restocking_fee_billing": codes(("charged_to_customer_account", "billed to the customer's account"), ("deducted_from_credit", "netted from the exchange credit"), ("waived", "no restocking fee")),
        "process_steps": codes(
            ("submit_ea_form", "retailer lists inventory on the Gravon Shoes Exchange Authorization form"),
            ("email_form_to_assigned_rep", "form is emailed directly to the assigned sales rep"),
            ("rep_returns_form_with_ea_number", "if approved, rep returns the form with an EA number"),
            ("place_replacement_order", "replacement order is placed when the EA number is granted"),
            ("print_form_into_shipment", "printed copy of the form goes inside the return shipment"),
            ("write_ea_number_on_box", "EA number written on the outside of the box"),
            ("ship_with_prepaid_freight", "customer ships with freight prepaid"),
            ("issue_cash_refund", "accounting issues a cash refund"),
            ("ship_to_store_freight_collect", "warehouse ships replacements freight collect"),
        ),
        "benefits": codes(
            ("increase_sales_with_updated_full_size_runs", "updated styles in full size runs lift sell-through"),
            ("remove_dated_merchandise", "old, dated merchandise is removed from the market"),
            ("reduce_freight_cost", "lower freight cost for Gravon"),
        ),
        "form.header_fields": codes(
            ("customer_name", "customer name"), ("customer_address", "customer address"), ("customer_phone", "customer phone number"),
            ("customer_number", "customer number"), ("ea_number", "Exchange Authorization number"), ("request_date", "date of the return request"),
            ("replacement_order_po", "replacement order PO / replacement pairs"), ("reason_for_request", "reason for request / comments"),
            ("refund_amount", "refund amount requested"), ("credit_card_number", "card for refund"),
        ),
        "form.line_columns": codes(
            ("style_color", "style/color"), ("style_name", "style name"), ("pairs_shipped", "pairs shipped"), ("pairs_to_return", "pairs to be returned"),
            ("refund_value", "refund value per line"),
        ),
        "form.totals": codes(("pairs_shipped", "total of pairs shipped"), ("pairs_to_return", "total of pairs to return")),
        "form.footer_notes": codes(
            ("freight_prepaid_by_customer", "customer must prepay freight"),
            ("restocking_fee_paid_by_customer", "customer pays the restocking fee"),
            ("refund_within_30_days", "refund issued within 30 days"),
        ),
        "form.signoffs": codes(
            ("sales_representative", "sales rep name, signature, date"), ("sales_manager", "sales manager name, signature, date"),
            ("general_manager", "GM name, signature, date"), ("controller", "controller signature"),
        ),
    }
    fields = [
        field("program_type", "code", "Program type."),
        field("exchange_scope", "code", "What retailers may exchange."),
        field("administered_by", "code", "Who administers the program with customers."),
        field("effective_date", "date", "Program effective date."),
        field("eligibility", "code", "Who may participate."),
        field("frequency", "code", "How often an account may exchange."),
        field("credit_use", "code", "How exchange credit may be used."),
        field("replacement_order_timing", "code", "When the replacement order is placed."),
        field("form_routing", "code", "How the authorization form is submitted."),
        field("freight_paid_by", "code", "Who pays return freight."),
        field("restocking_fee_per_pair_usd", "number", "Restocking fee per pair in USD."),
        field("restocking_fee_billing", "code", "How the restocking fee is billed."),
        field("warehouse.address", "string", "Warehouse street address, city, state ZIP as published."),
        field("warehouse.phone", "string", "Warehouse phone number."),
        field("process_steps", "list[code]", "Program steps in the order customers follow them."),
        field("benefits", "list[code]", "Business benefits stated in the overview."),
        field("form.header_fields", "list[code]", "Fields at the top of the Exchange Authorization form."),
        field("form.line_columns", "list[code]", "Line-item columns of the form."),
        field("form.totals", "list[code]", "Columns totalled under the line items."),
        field("form.footer_notes", "list[code]", "Notes printed at the bottom of the form."),
        field("form.signoffs", "list[code]", "Approval blocks (name, signature, date)."),
        field("form.ship_to.address", "string", "Ship-to address printed on the form."),
        field("form.ship_to.phone", "string", "Ship-to phone printed on the form."),
    ]
    checks = [
        check("program-type", "text", "program_type", "exchange"),
        check("exchange-scope", "text", "exchange_scope", truth["exchange_scope"]),
        check("administered-by", "text", "administered_by", "sales_representatives"),
        check("effective-date", "text", "effective_date", "2025-07-01"),
        check("eligibility", "text", "eligibility", "credit_worthy_customers"),
        check("frequency", "text", "frequency", "once_per_season"),
        check("credit-use", "text", "credit_use", "replacement_merchandise_only"),
        check("replacement-order-timing", "text", "replacement_order_timing", "when_ea_number_granted"),
        check("form-routing", "text", "form_routing", "email_to_assigned_sales_rep"),
        check("freight-paid-by", "text", "freight_paid_by", "customer"),
        num("restocking-fee", "restocking_fee_per_pair_usd", 5, 0),
        check("restocking-billing", "text", "restocking_fee_billing", "charged_to_customer_account"),
        check("warehouse-address", "text", "warehouse.address", truth["warehouse"]["address"]),
        check("warehouse-phone", "text", "warehouse.phone", phone),
        check("process-no-refund", "excludes", "process_steps", ["issue_cash_refund", "ship_to_store_freight_collect"]),
        check("benefits", "includes", "benefits", truth["benefits"]),
        check("form-totals", "includes", "form.totals", ["pairs_shipped"]),
        check("form-ship-to-address", "text", "form.ship_to.address", truth["warehouse"]["address"]),
        check("form-ship-to-phone", "text", "form.ship_to.phone", phone),
    ]
    for step in steps[:-1]:
        checks.append(check(f"step-{slug(step)}", "includes", "process_steps", [step]))
    for code_name in header:
        checks.append(check(f"form-header-{slug(code_name)}", "includes", "form.header_fields", [code_name]))
    for code_name in truth["form"]["line_columns"]:
        checks.append(check(f"form-col-{slug(code_name)}", "includes", "form.line_columns", [code_name]))
    for code_name in truth["form"]["footer_notes"]:
        checks.append(check(f"form-note-{slug(code_name)}", "includes", "form.footer_notes", [code_name]))
    for code_name in truth["form"]["signoffs"]:
        checks.append(check(f"form-signoff-{slug(code_name)}", "includes", "form.signoffs", [code_name]))
    checks.append(check("form-no-refund-fields", "excludes", "form.header_fields", ["refund_amount", "credit_card_number"]))
    rules = [
        (r"limited to a single page", "u:presentation"),
        (r"form content is delivered in the Excel file", "u:file_format"),
        (r"explicitly states that this is an exchange program", "c:program-type"),
        (r"explicitly states that it is not a return program", "c:program-type"),
        (r"underperforming styles and sizes", "c:exchange-scope"),
        (r"responsible for administering", "c:administered-by"),
        (r"does not allow credits", "c:credit-use"),
        (r"credits can only be used for replacement", "c:credit-use"),
        (r"orders for replacement merchandise must be placed", "c:replacement-order-timing,step-place-replacement-order"),
        (r"credit.worthy customers may participate", "c:eligibility"),
        (r"one time per season", "c:frequency"),
        (r"submit their inventory on a Gravon", "c:step-submit-ea-form"),
        (r"emailed directly to the customer", "c:form-routing,step-email-form-to-assigned-rep"),
        (r"will return the form with an Exchange Authorization", "c:step-rep-returns-form-with-ea-number"),
        (r"print a copy of the approved form", "c:step-print-form-into-shipment"),
        (r"write the Exchange Authorization number on the outside", "c:step-write-ea-number-on-box"),
        (r"^The Word document states that freight costs", "c:freight-paid-by"),
        (r"\$5 per pair restocking fee applies", "c:restocking-fee"),
        (r"charged to the customer.s account", "c:restocking-billing"),
        (r"^The Word document includes the warehouse address", "c:warehouse-address"),
        (r"^The Word document includes the warehouse phone", "c:warehouse-phone"),
        (r"effective date as July 1, 2025", "c:effective-date"),
        (r"does not authorize returns or refunds", "c:process-no-refund,form-no-refund-fields"),
        (r"does not state a restocking fee amount", "c:restocking-fee"),
        (r"labeled field for the customer.s name", "c:form-header-customer-name"),
        (r"labeled field for the customer.s address", "c:form-header-customer-address"),
        (r"labeled field for the customer.s phone", "c:form-header-customer-phone"),
        (r"labeled field for the customer number", "c:form-header-customer-number"),
        (r"labeled field for the Exchange Authorization number", "c:form-header-ea-number"),
        (r"labeled field for the date of the return request", "c:form-header-request-date"),
        (r"line.item column for Style/Color", "c:form-col-style-color"),
        (r"line.item column for Style Name", "c:form-col-style-name"),
        (r"line.item column for Pairs Shipped", "c:form-col-pairs-shipped"),
        (r"line.item column for Pairs to be Returned", "c:form-col-pairs-to-return"),
        (r"note states that customers must prepay freight", "c:form-note-freight-prepaid-by-customer"),
        (r"note states that customers must pay the restocking fee", "c:form-note-restocking-fee-paid-by-customer"),
        (r"Sales Representative.s name, signature", "c:form-signoff-sales-representative"),
        (r"GM.s name, signature", "c:form-signoff-general-manager"),
        (r"Sales Manager.s name, signature", "c:form-signoff-sales-manager"),
        (r"benefit statement", "c:benefits"),
        (r"discrete bullets or a numbered list", "u:presentation"),
        (r"title or header contains both", "u:presentation"),
        (r"displays the company name", "u:presentation"),
        (r"visible title identifying it", "u:presentation"),
        (r"totals row summing Pairs Shipped", "c:form-totals"),
        (r"Replacement Order PO number", "c:form-header-replacement-order-po"),
        (r"reason for request or comments", "c:form-header-reason-for-request"),
        (r"displays the warehouse shipping address", "c:form-ship-to-address,form-ship-to-phone"),
        (r"visually distinguishes", "u:presentation"),
        (r"separates the top customer", "u:presentation"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Publish the Gravon retailer exchange program and authorization form",
        "difficulty": "hard",
        "goal": "As Gravon Shoes' sales manager, define the retailer exchange program and its Exchange Authorization form.",
        "request": request,
        "artifact_type": "gdp_exchange_program",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["program-type", "restocking-fee", "warehouse-address"],
        "notes": [
            (f"Upstream prompt lists warehouse phone {phone_prompt}; the rubric and expert deliverable use {phone}. "
            "The case-file request was aligned to the graded number."),
        ],
    }


# --- task 02: CosmoGenics terms scenarios ---------------------------------------


def t02_terms_scenarios(src: SourceTask) -> Json:
    rows = xlsx_rows(src.ref("Sales and Shipment"), "Reference")
    lookup = {row[2]: row for row in rows if row and len(row) > 2 and row[2]}
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    retail = dict(zip(quarters, lookup["Retail Sales $"][3:7]))
    shipments = dict(zip(quarters, lookup["Shipments at Retail $"][3:7]))
    require(sum(retail.values()) == 200000, "task 02 retail total")
    ship_total = sum(shipments.values())
    require(ship_total == 255000, "task 02 shipment total")
    request = src.prompt.replace(
        "Projected Shipments at Retail Value of $225,000. Shipments by quarter included in Reference document.",
        "Projected Shipments at Retail Value: shipments by quarter are in the reference table.",
    )
    require(request != src.prompt, "task 02 prompt patch failed")

    def scenario(name: str, margin: float, allowance: float, terms: int) -> Json:
        wholesale = {q: r2(shipments[q] * (1 - margin)) for q in quarters}
        allowance_rows = {q: r2(shipments[q] * allowance) for q in quarters}
        net = {q: r2(wholesale[q] - allowance_rows[q]) for q in quarters}
        lag = 1 if terms == 30 else 2
        receipts = {f"Q{index + 1 + lag}": wholesale[q] for index, q in enumerate(quarters)}
        return {
            "name": name,
            "retailer_margin": margin,
            "marketing_allowance_rate": allowance,
            "payment_terms_days": terms,
            "wholesale_revenue": wholesale,
            "marketing_allowance": allowance_rows,
            "net_wholesale_revenue": net,
            "cash_receipts": receipts,
            "annual_wholesale_revenue": r2(sum(wholesale.values())),
            "annual_marketing_allowance": r2(sum(allowance_rows.values())),
            "annual_net_wholesale_revenue": r2(sum(net.values())),
        }

    scenarios = [scenario("Scenario A", 0.40, 0.04, 60), scenario("Scenario B", 0.45, 0.02, 30), scenario("Scenario C", 0.50, 0.0, 30)]
    require(scenarios[0]["annual_net_wholesale_revenue"] == 142800, "task 02 scenario A net")
    truth = {
        "quarterly_projection": {"retail_sales": retail, "shipments_at_retail": shipments},
        "totals": {"retail_sales": sum(retail.values()), "shipments_at_retail": ship_total},
        "scenarios": scenarios,
        "selected_scenario": "Scenario A",
    }
    fields = [
        field("quarterly_projection.retail_sales", "object<quarter,number>", "Projected retail sales by quarter (keys Q1-Q4)."),
        field("quarterly_projection.shipments_at_retail", "object<quarter,number>", "Projected shipments at retail value by quarter (keys Q1-Q4)."),
        field("totals.retail_sales", "number", "Year-1 retail sales."),
        field("totals.shipments_at_retail", "number", "Year-1 shipments at retail value."),
        field("scenarios", "list[object]", "Exactly three scenarios, each with: name, retailer_margin (fraction of MSRP, e.g. 0.45), "
              "marketing_allowance_rate (fraction of shipments at retail), payment_terms_days (30 or 60), "
              "wholesale_revenue/marketing_allowance/net_wholesale_revenue objects keyed Q1-Q4, cash_receipts object keyed by the "
              "quarter cash arrives (Q1..Q6, where Q5-Q6 are the following year), annual_wholesale_revenue, "
              "annual_marketing_allowance, annual_net_wholesale_revenue."),
        field("selected_scenario", "string", "Name of the recommended scenario (must match one scenario name)."),
    ]
    terms = {"shipments": shipments}
    checks = [
        check(f"retail-{q.lower()}", "number", ["quarterly_projection", "retail_sales", q], retail[q], tolerance=0.5) for q in quarters
    ] + [
        check(f"ship-{q.lower()}", "number", ["quarterly_projection", "shipments_at_retail", q], shipments[q], tolerance=0.5) for q in quarters
    ] + [
        num("retail-total", "totals.retail_sales", 200000, 0.5),
        num("ship-total", "totals.shipments_at_retail", ship_total, 0.5),
    ] + [
        check(f"scenario-{aspect.replace('_', '-')}", "custom", rule="terms_scenarios", aspect=aspect, tolerance=1.0, **terms)
        for aspect in (
            "labels", "margin_range", "margin_varied", "allowance_range", "allowance_varied", "terms_valid",
            "terms_both", "distinct", "selected", "wholesale", "allowance", "net", "cash",
        )
    ]
    rules = [
        (r"exactly three distinct scenarios", "c:scenario-distinct,scenario-labels"),
        (r"clearly labeled with a unique name", "c:scenario-labels"),
        (r"Quarterly retail sales value in the workbook for (Q\d)", "c:retail-{1}"),
        (r"Sum of quarterly retail sales", "c:retail-total"),
        (r"Quarterly shipments at retail value in the workbook for (Q\d)", "c:ship-{1}"),
        (r"Sum of quarterly shipments at retail value equals \$225,000", "u:upstream_conflict"),
        (r"retailer margin that is between", "c:scenario-margin-range"),
        (r"Retailer margin rates are not identical", "c:scenario-margin-varied"),
        (r"marketing allowance rate between", "c:scenario-allowance-range"),
        (r"Marketing allowance rates are not identical", "c:scenario-allowance-varied"),
        (r"payment terms of either Net 30 or Net 60 only", "c:scenario-terms-valid"),
        (r"both Net 30 and Net 60 payment terms are represented", "c:scenario-terms-both"),
        (r"Each pair of scenarios differs", "c:scenario-distinct"),
        (r"Wholesale revenue is calculated from shipments", "c:scenario-wholesale"),
        (r"Implements Wholesale Revenue", "c:scenario-wholesale"),
        (r"Wholesale revenue is shown by quarter", "c:scenario-wholesale"),
        (r"Annual wholesale revenue is shown", "c:scenario-wholesale"),
        (r"No markdown deductions", "c:scenario-wholesale"),
        (r"Marketing allowance is calculated as a percentage", "c:scenario-allowance"),
        (r"Marketing allowance expense is recorded", "c:scenario-allowance"),
        (r"\(NWRAMA\) is calculated", "c:scenario-net"),
        (r"Annual Net Wholesale Revenue after Marketing Allowance \(NWRAMA\) is shown", "c:scenario-net"),
        (r"Shows both quarterly and annual views", "c:scenario-net,scenario-wholesale"),
        (r"cash receipts|Cash receipts", "c:scenario-cash"),
        (r"visual representation", "u:presentation"),
        (r"written summary paragraph of 5", "u:narrative"),
        (r"summary explicitly identifies which scenario", "c:scenario-selected"),
        (r"summary justifies|summary addresses|summary mentions", "u:narrative"),
        (r"labeled input cells", "u:workbook_mechanics"),
        (r"consolidated summary table", "u:presentation"),
        (r"sensitivity note", "u:narrative"),
        (r"Formats currency values", "u:presentation"),
    ]
    return {
        "family": "distributor_pricing_quotation",
        "title": "Model CosmoGenics wholesale terms scenarios",
        "difficulty": "expert",
        "goal": "As senior sales director, model three CosmoGenics terms scenarios (margin, payment terms, marketing allowance) and recommend one.",
        "request": request,
        "artifact_type": "gdp_terms_scenarios",
        "fields": fields,
        "codes": {},
        "tables": [
            table(
                "PROJ",
                "CosmoGenics year-1 sales and shipment projection",
                "Quarterly retail sales and shipments at retail value for the new account.",
                ["measure", "Q1", "Q2", "Q3", "Q4"],
                [["retail_sales", *retail.values()], ["shipments_at_retail", *shipments.values()]],
            )
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["ship-total", "scenario-wholesale", "scenario-cash"],
        "notes": [
            ("Upstream prompt and one rubric item state shipments total $225,000, but the reference quarters sum to $255,000 "
            "(70k+80k+80k+25k); the expert deliverable uses $255,000. The request no longer states the wrong total, the "
            "$225,000 rubric item is unscored (upstream_conflict), and the data total is scored."),
            "Scenario choice is open: scenario checks validate the agent's own inputs against the rubric bounds and formulas.",
        ],
    }


# --- task 03: PO log June shipments -------------------------------------------


def t03_po_log(src: SourceTask) -> Json:
    raw = xlsx_rows(src.ref("PO Log"), "PO Log")
    header_index = next(i for i, row in enumerate(raw) if "PO Number" in row)
    data = [row[1:11] for row in raw[header_index + 1:] if row[1] not in (None, "")]
    columns = [
        "po_number", "account", "ship_start", "cancel_date", "actual_ship_date",
        "order_value_cost", "order_value_retail", "status", "shipped_value_cost", "shipped_value_retail",
    ]
    rows = [[str(row[0]), *row[1:]] for row in data]
    records = [dict(zip(columns, row)) for row in rows]
    june = [r for r in records if "2025-06-01" <= r["actual_ship_date"] <= "2025-06-30"]
    slipped = [
        r for r in records
        if r["ship_start"] >= "2025-06-01" and r["cancel_date"] <= "2025-06-30" and "2025-07-01" <= r["actual_ship_date"] <= "2025-07-31"
    ]
    order_total = sum(r["order_value_cost"] for r in june)
    shipped_total = sum(r["shipped_value_cost"] for r in june)
    short_total = sum(max(r["order_value_cost"] - r["shipped_value_cost"], 0) for r in june)
    require(abs(shipped_total - 140008.204) < 0.01 and abs(order_total - 145218.8) < 0.01, "task 03 June totals")
    slipped_total = sum(r["order_value_cost"] for r in slipped)
    require(slipped_total == 13300, "task 03 slipped total")
    accounts: dict[str, Json] = {}
    for r in june:
        bucket = accounts.setdefault(r["account"], {"order_cost": 0.0, "shipped_cost": 0.0, "short_shipped": 0.0})
        bucket["order_cost"] += r["order_value_cost"]
        bucket["shipped_cost"] += r["shipped_value_cost"]
        bucket["short_shipped"] += max(r["order_value_cost"] - r["shipped_value_cost"], 0)
    for bucket in accounts.values():
        bucket["percent_shipped"] = r2(100 * bucket["shipped_cost"] / bucket["order_cost"])
        for key in ("order_cost", "shipped_cost", "short_shipped"):
            bucket[key] = r2(bucket[key])
    slipped_accounts: dict[str, float] = defaultdict(float)
    for r in slipped:
        slipped_accounts[r["account"]] += r["order_value_cost"]

    def june_row(r: Json) -> Json:
        order, shipped = r["order_value_cost"], r["shipped_value_cost"]
        return {
            "account": r["account"],
            "start_ship_date": r["ship_start"],
            "cancel_date": r["cancel_date"],
            "actual_ship_date": r["actual_ship_date"],
            "order_cost": r2(order),
            "shipped_cost": r2(shipped),
            "percent_shipped": r2(100 * shipped / order) if order else 0,
            "short_shipped": r2(max(order - shipped, 0)),
        }

    def slipped_row(r: Json) -> Json:
        return {
            "account": r["account"],
            "start_ship_date": r["ship_start"],
            "cancel_date": r["cancel_date"],
            "actual_ship_date": r["actual_ship_date"],
            "order_cost": r2(r["order_value_cost"]),
        }

    truth = {
        "june_window": {"start": "2025-06-01", "end": "2025-06-30"},
        "slipped_actual_ship_month": "2025-07",
        "june_shipped": {
            "po_numbers": sorted(r["po_number"] for r in june),
            "rows": {r["po_number"]: june_row(r) for r in sorted(june, key=lambda x: x["po_number"])},
            "total_order_cost": r2(order_total),
            "total_shipped_cost": r2(shipped_total),
            "percent_shipped": r2(100 * shipped_total / order_total),
            "short_shipped": r2(short_total),
            "accounts": dict(sorted(accounts.items())),
        },
        "slipped_to_july": {
            "po_numbers": sorted(r["po_number"] for r in slipped),
            "rows": {r["po_number"]: slipped_row(r) for r in sorted(slipped, key=lambda x: x["po_number"])},
            "total_order_cost": r2(slipped_total),
            "accounts": {key: r2(value) for key, value in sorted(slipped_accounts.items())},
        },
    }
    fields = [
        field("june_window.start", "date", "First day of the June fiscal ship window."),
        field("june_window.end", "date", "Last day of the June fiscal ship window."),
        field("slipped_actual_ship_month", "month", "Month in which the slipped POs actually shipped."),
        field("june_shipped.po_numbers", "list[string]", "Every PO whose actual ship date falls in the June window."),
        field("june_shipped.rows", "object<po_number,object>", "Per June-shipped PO: account, start_ship_date, cancel_date, actual_ship_date, "
              "order_cost, shipped_cost, percent_shipped (0-100), short_shipped (max(order-shipped,0))."),
        field("june_shipped.total_order_cost", "number", "Sum of order value at cost for June-shipped POs."),
        field("june_shipped.total_shipped_cost", "number", "Sum of shipped value at cost for June-shipped POs."),
        field("june_shipped.percent_shipped", "number", "Shipped cost / order cost for June (0-100)."),
        field("june_shipped.short_shipped", "number", "Total short-shipped dollars for June."),
        field("june_shipped.accounts", "object<account,object>", "Per account: order_cost, shipped_cost, percent_shipped (0-100), short_shipped."),
        field("slipped_to_july.po_numbers", "list[string]", "POs with a June ship window (start >= 6/1 and cancel <= 6/30) that shipped in July."),
        field("slipped_to_july.rows", "object<po_number,object>", "Per slipped PO: account, start_ship_date, cancel_date, actual_ship_date, order_cost."),
        field("slipped_to_july.total_order_cost", "number", "Order value at cost of the slipped POs."),
        field("slipped_to_july.accounts", "object<account,number>", "Slipped order value at cost by account."),
    ]
    checks = [
        check("window", "custom", rule="all_of", checks=[
            check("w1", "text", "june_window.start", "2025-06-01"),
            check("w2", "text", "june_window.end", "2025-06-30"),
            check("w3", "text", "slipped_actual_ship_month", "2025-07"),
        ]),
        check("june-pos", "set", "june_shipped.po_numbers", truth["june_shipped"]["po_numbers"]),
        check("june-rows", "custom", "june_shipped.rows", truth["june_shipped"]["rows"], rule="rows_match", tolerance=0.06),
        num("june-total-order", "june_shipped.total_order_cost", order_total, 1.0),
        num("june-total-shipped", "june_shipped.total_shipped_cost", shipped_total, 1.0),
        num("june-pct", "june_shipped.percent_shipped", truth["june_shipped"]["percent_shipped"], 0.5),
        num("june-short", "june_shipped.short_shipped", short_total, 1.0),
        check("accounts", "keys", "june_shipped.accounts", sorted(accounts)),
        check("slipped-pos", "set", "slipped_to_july.po_numbers", truth["slipped_to_july"]["po_numbers"]),
        check("slipped-rows", "custom", "slipped_to_july.rows", truth["slipped_to_july"]["rows"], rule="rows_match", tolerance=0.01),
        num("slipped-total", "slipped_to_july.total_order_cost", slipped_total, 1.0),
        check("slipped-accounts", "custom", "slipped_to_july.accounts", None, rule="map_numbers",
              values=truth["slipped_to_july"]["accounts"], tolerance=1.0),
    ]
    for account, bucket in sorted(accounts.items()):
        checks.append(num(f"account-{slug(account)}-pct", ["june_shipped", "accounts", account, "percent_shipped"], bucket["percent_shipped"], 0.25))
        checks.append(num(f"account-{slug(account)}-short", ["june_shipped", "accounts", account, "short_shipped"], bucket["short_shipped"], 1.0))
    rules = [
        (r"contains two distinct summary tables", "u:presentation"),
        (r"One summary table is for POs that actually shipped in June", "c:june-pos"),
        (r"One summary table is for POs with a June 2025 ship window", "c:slipped-pos"),
        (r"Excel Table with AutoFilter", "u:workbook_mechanics"),
        (r"^The June shipments table contains an? ", "c:june-rows"),
        (r"^The slipped-to-July table contains an? ", "c:slipped-rows"),
        (r"June shipments table includes exactly the POs", "c:june-pos"),
        (r"No row in the June shipments table has a blank", "c:june-rows"),
        (r"slipped-to-July table includes exactly the POs", "c:slipped-pos"),
        (r"POs with missing Start Ship Date", "c:slipped-pos"),
        (r"No PO Number appears in both", "c:june-pos,slipped-pos"),
        (r"^For every row in the June shipments table", "c:june-rows"),
        (r"If PO Value at Cost = 0", "c:june-rows"),
        (r"For rows where PO Actual Shipped Value", "c:june-rows"),
        (r"If PO Actual Shipped Value at Cost >", "c:june-rows"),
        (r"Date columns .* are stored as Excel date", "u:workbook_mechanics"),
        (r"Currency columns", "u:presentation"),
        (r"stored as a numeric percentage", "u:workbook_mechanics"),
        (r"clearly labeled total for June shipped", "c:june-total-shipped"),
        (r"clearly labeled total for the slipped-to-July", "c:slipped-total"),
        (r"narrative text section in the workbook states", "c:june-total-shipped,slipped-total"),
        (r"narrative explicitly references the June window", "c:window"),
        (r"values in the Account columns are members", "c:june-rows,slipped-rows,accounts"),
        (r"Every PO number included in either table exists", "c:june-pos,slipped-pos"),
        (r"zero qualifying slipped POs", "u:not_applicable"),
        (r"visible title or header for the recap", "u:presentation"),
        (r"Status: Shipped", "u:presentation"),
        (r"Ship Date: 6/1", "c:window"),
        (r"Requested Ship Window: June", "c:window"),
        (r"Actual Ship Date: July", "c:window"),
        (r"account-level summary table is provided, it contains columns", "c:accounts"),
        (r"account-level summary is present, it reports (.+?) with percent shipped", "c:account-{1}-pct,account-{1}-short"),
        (r"single-sentence June shipped total", "c:june-total-shipped"),
        (r"overall June completion", "c:june-pct"),
        (r"June shortfall", "c:june-short"),
        (r"slipped cohort timing", "c:window"),
    ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Recap June shipped PO value and orders slipped to July",
        "difficulty": "expert",
        "goal": "As wholesale sales analyst, recap PO value shipped in the June fiscal month by account and quantify June-window orders that slipped to July.",
        "request": src.prompt,
        "artifact_type": "gdp_po_ship_recap",
        "fields": fields,
        "codes": {},
        "tables": [table("POLOG", "Purchase Order Log", "PO-level log with ship window, actual ship date, and order/shipped value at cost and retail.", columns, rows)],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["june-total-shipped", "slipped-total", "june-pos"],
        "notes": ["All expected values are recomputed from the reference PO log and match the rubric and expert deliverable."],
    }


# --- task 04: weeks of supply ----------------------------------------------------


def t04_weeks_of_supply(src: SourceTask) -> Json:
    raw = xlsx_rows(src.ref("Reference Inventory"), "DATA")
    header = raw[0]
    require(header[4] == "Store Number" and header[5] == "UPC", "task 04 header")
    upcs = ["901153373247", "567219040266", "217313054556", "875218534223", "375301052429"]
    columns = ["store_number", "upc", "last_week_inv", "current_week_inv", "daily_inv_sold_last_4_wks"]
    source = [row for row in raw[1:] if row[5] not in (None, "")]
    rows = [[str(row[4]), str(row[5]), row[7], row[8], row[10]] for row in source]
    catalog_rows = sorted({(str(row[5]), row[6]) for row in source})
    rubric_stores = {"875218534223": 1064, "375301052429": 729, "567219040266": 1131, "901153373247": 1232, "217313054556": 1223}
    by_upc: dict[str, Json] = {}
    for upc in upcs:
        subset = [row for row in rows if row[1] == upc]
        stores = {row[0] for row in subset}
        oos = {row[0] for row in subset if row[3] == 0}
        inventory = sum(row[3] for row in subset)
        daily = sum(row[4] for row in subset)
        weekly = daily * 7
        by_upc[upc] = {
            "current_week_inventory": inventory,
            "daily_units_sold_last_4_weeks": r4(daily),
            "weekly_unit_rate_of_sale": r4(weekly),
            "weeks_of_supply": r2(inventory / weekly),
            "active_stores": len(stores),
            "oos_stores": len(oos),
            "pct_stores_oos": r2(100 * len(oos) / len(stores)),
        }
        require(abs(len(stores) - rubric_stores[upc]) <= 1, f"task 04 store count {upc}")
    ranking = sorted(upcs, key=lambda upc: -by_upc[upc]["pct_stores_oos"])
    truth = {"by_upc": by_upc, "oos_ranking": ranking}
    fields = [
        field("by_upc", "object<upc,object>", "Exactly the five requested UPCs (12-digit strings). Each: current_week_inventory, "
              "daily_units_sold_last_4_weeks (sum across active stores), weekly_unit_rate_of_sale (7 x daily), weeks_of_supply "
              "(inventory / weekly rate), active_stores, oos_stores (active stores with zero current-week inventory), "
              "pct_stores_oos (0-100)."),
        field("oos_ranking", "list[string]", "The five UPCs ordered from highest to lowest percent of stores out of stock."),
    ]
    checks = [check("upcs", "keys", "by_upc", upcs), check("oos-ranking", "list", "oos_ranking", ranking)]
    tolerances = {
        "current_week_inventory": ("inv", 0),
        "daily_units_sold_last_4_weeks": ("daily", 0.1),
        "weekly_unit_rate_of_sale": ("weekly", 0.1),
        "weeks_of_supply": ("wos", 0.1),
        "oos_stores": ("oos", 0),
        "pct_stores_oos": ("pct", 0.1),
    }
    for upc in upcs:
        for key, (prefix, tolerance) in tolerances.items():
            checks.append(num(f"{prefix}-{upc}", ["by_upc", upc, key], by_upc[upc][key], tolerance))
        store_tolerance = 1 if by_upc[upc]["active_stores"] != rubric_stores[upc] else 0
        checks.append(num(f"stores-{upc}", ["by_upc", upc, "active_stores"], by_upc[upc]["active_stores"], store_tolerance))
    rules = [
        (r"includes exactly these five UPCs", "c:upcs"),
        (r"displayed in full", "u:presentation"),
        (r"For UPC (\d+), the Weekly Unit Rate", "c:weekly-{1}"),
        (r"For UPC (\d+), WOS", "c:wos-{1}"),
        (r"For UPC (\d+), Number of Stores", "c:stores-{1}"),
        (r"For UPC (\d+), Count of OOS", "c:oos-{1}"),
        (r"For UPC (\d+), Percent OOS", "c:pct-{1}"),
        (r"For UPC (\d+), Current Week Inventory", "c:inv-{1}"),
        (r"For UPC (\d+), Daily Inventory Sold", "c:daily-{1}"),
        (r"Number of Stores per UPC equals", "c:stores-*"),
        (r"Count of Stores Out of Stock per UPC", "c:oos-*"),
        (r"Percent of Stores Out of Stock per UPC equals", "c:pct-*"),
        (r"Weekly Unit Rate of Sale per UPC is calculated", "c:weekly-*"),
        (r"Weeks of Supply \(WOS\) per UPC equals", "c:wos-*"),
        (r"evaluates to 0, the WOS cell", "u:not_applicable"),
        (r"Percent OOS values are between 0% and 100%", "c:pct-*,oos-*"),
        (r"store-level rows", "u:workbook_mechanics"),
        (r"computed via formulas", "u:workbook_mechanics"),
        (r"chart|Chart", "u:presentation"),
        (r"formatted consistently|consistent numeric format", "u:presentation"),
        (r"No visible Excel errors", "u:workbook_mechanics"),
        (r"No UPCs outside the specified five", "c:upcs"),
        (r"clear column headings", "u:presentation"),
    ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Summarize weeks of supply and store out-of-stock rates for top UPCs",
        "difficulty": "expert",
        "goal": "As wholesale sales analyst, compute weeks of supply and store-level out-of-stock rates for the five top-selling UPCs at a national drugstore account.",
        "request": src.prompt,
        "artifact_type": "gdp_wos_summary",
        "fields": fields,
        "codes": {},
        "tables": [
            table("INV", "Week 28 store inventory by UPC", "One row per store and UPC for retail week 28 of 2025 (all 45 UPCs on the account).", columns, rows),
            table("UPCS", "UPC catalog", "UPC descriptions for the account.", ["upc", "description"], [list(row) for row in catalog_rows]),
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["wos-875218534223", "pct-875218534223", "upcs"],
        "notes": [
            ("The data hold 728 rows/stores for UPC 375301052429 and 1222 for 217313054556; the rubric and expert workbook "
            "report 729 and 1223. Store counts for those two UPCs are scored within +/-1 store."),
            "Out of stock means zero current-week inventory; every listed store is active (each row carries a sales rate).",
        ],
    }


# --- task 05: PO entry audit -----------------------------------------------------


def t05_po_entry_audit(src: SourceTask) -> Json:
    raw = xlsx_rows(src.ref("PO Data"), "RawData")
    require(raw[0][0] == "PO Number", "task 05 header")
    lines = [row for row in raw[1:] if row[0]]
    columns = ["line_id", "po_number", "sku", "ordered_units", "entered_unit_price", "expected_unit_price", "uom", "case_pack", "ship_to_location"]
    rows = [[f"L{index:02d}", *row[:8]] for index, row in enumerate(lines, start=1)]
    missing_pack = [row for row in rows if str(row[6]).upper() == "CASE" and (row[7] in (None, "") or row[7] <= 0)]
    line_truth: dict[str, Json] = {}
    by_sku: dict[str, Json] = {}
    for row in rows:
        line_id, _, sku, units, entered, expected, uom, pack, _ = row
        price = int(round(entered, 4) != round(expected, 4))
        case = int(str(uom).upper() == "CASE" and bool(pack) and units % pack != 0)
        types = [name for name, flag in (("price_mismatch", price), ("case_pack", case)) if flag]
        line_truth[line_id] = {"price_mismatch": price, "case_pack_error": case, "total_errors": price + case, "error_types": types}
        if price + case:
            bucket = by_sku.setdefault(sku, {"price_mismatch": 0, "case_pack": 0, "total_errors": 0})
            bucket["price_mismatch"] += price
            bucket["case_pack"] += case
            bucket["total_errors"] += price + case
    totals = {
        "price_mismatch": sum(v["price_mismatch"] for v in line_truth.values()),
        "case_pack": sum(v["case_pack_error"] for v in line_truth.values()),
    }
    totals["total_errors"] = totals["price_mismatch"] + totals["case_pack"]
    require(totals == {"price_mismatch": 15, "case_pack": 10, "total_errors": 25}, f"task 05 totals {totals}")
    flagged_price = sorted(k for k, v in line_truth.items() if v["price_mismatch"])
    flagged_case = sorted(k for k, v in line_truth.items() if v["case_pack_error"])
    pricing_skus = sorted(sku for sku, v in by_sku.items() if v["price_mismatch"] >= 3)
    require(pricing_skus == ["SKU-0103", "SKU-0107", "SKU-0108", "SKU-0112"], f"task 05 pricing skus {pricing_skus}")
    truth = {
        "lines": line_truth,
        "flagged_lines": {"price_mismatch": flagged_price, "case_pack": flagged_case},
        "by_sku": dict(sorted(by_sku.items())),
        "totals": totals,
        "priority_skus": pricing_skus,
        "pricing_review_skus": pricing_skus,
    }
    fields = [
        field("lines", "object<line_id,object>", "Every order line (L01..). Each: price_mismatch (0/1), case_pack_error (0/1, only when UOM is CASE "
              "and ordered units are not a multiple of the case pack), total_errors, error_types (list of codes)."),
        field("flagged_lines.price_mismatch", "list[string]", "Line ids with a price mismatch."),
        field("flagged_lines.case_pack", "list[string]", "Line ids with a case-pack error."),
        field("by_sku", "object<sku,object>", "SKUs with at least one error. Each: price_mismatch, case_pack, total_errors (line counts)."),
        field("totals.price_mismatch", "number", "Total price-mismatch lines."),
        field("totals.case_pack", "number", "Total case-pack error lines."),
        field("totals.total_errors", "number", "Total errors across all lines."),
        field("priority_skus", "list[string]", "SKUs to address first because errors recur."),
        field("pricing_review_skus", "list[string]", "SKUs whose pricing setup/master data should be reviewed."),
    ]
    catalog = {"lines.error_types": codes(("price_mismatch", "entered price differs from expected price"), ("case_pack", "CASE item not ordered in case-pack multiples"))}
    checks = [
        check("line-flags", "custom", "lines", line_truth, rule="rows_match", tolerance=0),
        check("sku-keys", "keys", "by_sku", sorted(by_sku)),
        num("total-price", "totals.price_mismatch", 15, 0),
        num("total-case", "totals.case_pack", 10, 0),
        num("total-errors", "totals.total_errors", 25, 0),
        check("flagged-price", "set", "flagged_lines.price_mismatch", flagged_price),
        check("flagged-case", "set", "flagged_lines.case_pack", flagged_case),
    ]
    for sku in ("SKU-0103", "SKU-0112"):
        checks.append(check(f"priority-{slug(sku)}", "includes", "priority_skus", [sku]))
        checks.append(check(f"review-{slug(sku)}", "includes", "pricing_review_skus", [sku]))
    for sku, bucket in sorted(by_sku.items()):
        checks.append(check(f"sku-{slug(sku)}-total", "custom", rule="all_of", checks=[
            num("p", ["by_sku", sku, "price_mismatch"], bucket["price_mismatch"], 0),
            num("c", ["by_sku", sku, "case_pack"], bucket["case_pack"], 0),
            num("t", ["by_sku", sku, "total_errors"], bucket["total_errors"], 0),
        ]))
    line_lookup = defaultdict(list)
    for row in rows:
        line_lookup[(row[1], row[2], row[3])].append(row[0])
    for kind, flagged in (("price", flagged_price), ("case", flagged_case)):
        for line_id in flagged:
            row = next(r for r in rows if r[0] == line_id)
            path = "flagged_lines.price_mismatch" if kind == "price" else "flagged_lines.case_pack"
            checks.append(check(f"{kind}-{slug(row[1])}-{slug(row[2])}-{row[3]}", "includes", path, [line_id]))
    rules = [
        (r"detailed sheet in the Excel file includes the source columns", "c:line-flags"),
        (r"adds four functional columns", "c:line-flags"),
        (r"Price Mismatch flag logic", "c:line-flags,flagged-price"),
        (r"Case Pack Error flag logic", "c:line-flags,flagged-case"),
        (r"When UOM is not 'CASE'", "c:line-flags"),
        (r"Total Errors per line equals", "c:line-flags"),
        (r"flags are binary", "c:line-flags"),
        (r"contain no spreadsheet error values", "u:workbook_mechanics"),
        (r"Error Summary text accurately reflects", "c:line-flags"),
        (r"separate Summary worksheet that aggregates errors by SKU", "c:sku-keys"),
        (r"Summary worksheet displays three measures", "c:sku-*"),
        (r"drill-down to the PO level", "u:workbook_mechanics"),
        (r"Reconciliation: the sum of Price Mismatch", "c:total-price"),
        (r"Reconciliation: the sum of Case Pack", "c:total-case"),
        (r"Reconciliation: the sum of Total Errors", "c:total-errors"),
        (r"totals are correct: 15 Price", "c:total-price"),
        (r"totals are correct: 10 Case", "c:total-case"),
        (r"totals are correct: 25 Total", "c:total-errors"),
        (r"missing/invalid Case Pack", "u:not_applicable" if not missing_pack else "u:workbook_mechanics"),
        (r"sorted or easily sortable", "u:presentation"),
        (r"briefly defines the two checks", "u:narrative"),
        (r"at least one actionable recommendation", "c:priority-sku-0103,priority-sku-0112"),
        (r"states that 15 Price Mismatch", "c:total-price"),
        (r"states that 10 Case Pack", "c:total-case"),
        (r"identifies (SKU-\d+) as a high-priority", "c:priority-{1}"),
        (r"recommends reviewing the pricing setup or master data for (SKU-\d+)", "c:review-{1}"),
        (r"Per-PO/SKU check: (PO\d+), (SKU-\d+) is flagged as a Price Mismatch when (\d+) unit", "c:price-{1}-{2}-{3}"),
        (r"Per-PO/SKU check: (PO\d+), (SKU-\d+) is flagged as a Case Pack error when (\d+) unit", "c:case-{1}-{2}-{3}"),
        (r"Per-SKU total: (SKU-\d+) has", "c:sku-{1}-total"),
    ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Audit wholesale PO lines for price and case-pack entry errors",
        "difficulty": "expert",
        "goal": "As wholesale sales analyst, audit recent PO lines for price mismatches and case-pack violations and summarize errors by SKU.",
        "request": src.prompt,
        "artifact_type": "gdp_po_entry_audit",
        "fields": fields,
        "codes": catalog,
        "tables": [table("POLINES", "Wholesale PO line export", "Line-level PO export; line_id is assigned in export order.", columns, rows)],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["total-errors", "line-flags", "priority-sku-0103"],
        "notes": [
            ("The rubric names SKU-0103 and SKU-0112 as priorities; the expert summary names SKU-0103/0107/0108/0112. "
            "Priority and pricing-review checks require 0103 and 0112 and allow the other two."),
            f"Lines with UOM CASE and a missing or non-positive case pack in the data: {len(missing_pack)}.",
        ],
    }


# --- task 06: floorstand budget ----------------------------------------------------


def t06_floorstand_budget(src: SourceTask) -> Json:
    original_raw = xlsx_rows(src.ref("Store List Original"), "Store List")
    final_raw = xlsx_rows(src.ref("final count"), "FINAL")
    original = [row for row in original_raw if isinstance(row[0], int)]
    start = next(i for i, row in enumerate(final_raw) if row[0] == "STORE #")
    final = [row for row in final_raw[start + 1:] if row[0] not in (None, "")]
    original_ids = {int(row[0]) for row in original}
    final_ids = {int(row[0]) for row in final}
    added = sorted(final_ids - original_ids)
    removed = sorted(original_ids - final_ids)
    require(len(original_ids) == 1228 and len(final_ids) == 1257, "task 06 store counts")
    require(removed == [3737, 4099], f"task 06 removed {removed}")
    email = docx_paragraphs(src.ref("Email Trail"))
    base, side, strip, strip_new = 5.65, 2.24, 1.89, 1.89 + 0.25
    unit_original = r2(base + 2 * side + 4 * strip)
    unit_revised = r2(base + 2 * side + 4 * strip_new)
    units_original = round(len(original_ids) * 1.05)
    units_revised = round(len(final_ids) * 1.05)
    cost_original = r2(unit_original * units_original)
    cost_revised = r2(unit_revised * units_revised)
    require((unit_original, unit_revised, units_original, units_revised) == (17.69, 18.69, 1289, 1320), "task 06 units")
    require((cost_original, cost_revised) == (22802.41, 24670.8), "task 06 costs")
    change = r2(cost_revised - cost_original)
    truth = {
        "components": {
            "base_unit": {"original_unit_cost": base, "revised_unit_cost": base, "pieces_per_unit": 1},
            "side_panels": {"original_unit_cost": side, "revised_unit_cost": side, "pieces_per_unit": 2},
            "shelf_strips": {"original_unit_cost": strip, "revised_unit_cost": r2(strip_new), "pieces_per_unit": 4},
        },
        "per_unit_cost": {"original": unit_original, "revised": unit_revised, "change": r2(unit_revised - unit_original)},
        "store_count": {"original": len(original_ids), "final": len(final_ids)},
        "overage_pct": 5,
        "units_to_produce": {"original": units_original, "revised": units_revised},
        "program_cost": {"original": cost_original, "revised": cost_revised, "change": change},
        "store_changes": {"added": [str(x) for x in added], "removed": [str(x) for x in removed]},
        "store_status": {"4099": "not_included", "3737": "not_included"},
        "email": {
            "units_to_produce": units_revised,
            "budget_increase": change,
            "new_total_budget": cost_revised,
            "approved_stores": len(final_ids),
            "drivers": ["higher_final_store_count", "shelf_strip_cost_increase"],
        },
    }
    fields = [
        field("components", "object<component,object>", "Keys base_unit, side_panels, shelf_strips; each original_unit_cost, revised_unit_cost (per piece), pieces_per_unit."),
        field("per_unit_cost.original", "number", "Original cost per floorstand."),
        field("per_unit_cost.revised", "number", "Revised cost per floorstand."),
        field("per_unit_cost.change", "number", "Revised minus original per-unit cost."),
        field("store_count.original", "number", "Stores on the original list (before overage)."),
        field("store_count.final", "number", "Stores on the final approved matrix (before overage)."),
        field("overage_pct", "number", "Unit overage percentage applied to both scenarios."),
        field("units_to_produce.original", "number", "Original units including overage (whole units)."),
        field("units_to_produce.revised", "number", "Revised units including overage (whole units)."),
        field("program_cost.original", "number", "Original total program cost."),
        field("program_cost.revised", "number", "Revised total program cost."),
        field("program_cost.change", "number", "Revised minus original program cost."),
        field("store_changes.added", "list[string]", "Store numbers on the final matrix but not the original list."),
        field("store_changes.removed", "list[string]", "Store numbers on the original list but not the final matrix."),
        field("store_status", "object<store,code>", "Status of stores 4099 and 3737 on the final matrix."),
        field("email.units_to_produce", "number", "Updated floorstands to produce stated in the draft email."),
        field("email.budget_increase", "number", "Program budget change stated in the email."),
        field("email.new_total_budget", "number", "New total program budget stated in the email."),
        field("email.approved_stores", "number", "Stores approved for floorstands stated in the email."),
        field("email.drivers", "list[code]", "Drivers of the budget change named in the email."),
    ]
    catalog = {
        "store_status": codes(("included", "store is on the final matrix"), ("not_included", "store is not on the final matrix")),
        "email.drivers": codes(
            ("higher_final_store_count", "final matrix has more stores"),
            ("shelf_strip_cost_increase", "$0.25 increase per shelf strip"),
            ("higher_overage", "larger overage percentage"),
            ("freight_increase", "higher freight cost"),
        ),
    }
    comp = truth["components"]
    checks = [
        num("base-cost", "components.base_unit.original_unit_cost", base),
        num("side-cost", "components.side_panels.original_unit_cost", side),
        num("strip-cost", "components.shelf_strips.original_unit_cost", strip),
        num("base-pieces", "components.base_unit.pieces_per_unit", 1, 0),
        num("side-pieces", "components.side_panels.pieces_per_unit", 2, 0),
        num("strip-pieces", "components.shelf_strips.pieces_per_unit", 4, 0),
        check("revised-components", "custom", rule="all_of", checks=[
            num("b", "components.base_unit.revised_unit_cost", base),
            num("s", "components.side_panels.revised_unit_cost", side),
            num("t", "components.shelf_strips.revised_unit_cost", comp["shelf_strips"]["revised_unit_cost"]),
        ]),
        num("unit-original", "per_unit_cost.original", unit_original),
        num("unit-revised", "per_unit_cost.revised", unit_revised),
        num("unit-change", "per_unit_cost.change", 1.0),
        num("stores-original", "store_count.original", 1228, 0),
        num("stores-final", "store_count.final", 1257, 0),
        num("overage", "overage_pct", 5, 0),
        num("units-original", "units_to_produce.original", units_original, 0),
        num("units-revised", "units_to_produce.revised", units_revised, 0),
        num("cost-original", "program_cost.original", cost_original, 22.8),
        num("cost-revised", "program_cost.revised", cost_revised, 123.0),
        num("cost-change", "program_cost.change", change, 9.3),
        check("stores-added", "set", "store_changes.added", truth["store_changes"]["added"], strip_leading_zeros=True),
        check("stores-removed", "set", "store_changes.removed", truth["store_changes"]["removed"], strip_leading_zeros=True),
        check("status-4099", "text", "store_status.4099", "not_included"),
        check("status-3737", "text", "store_status.3737", "not_included"),
        num("email-units", "email.units_to_produce", units_revised, 0),
        num("email-increase", "email.budget_increase", change, 9.3),
        num("email-total", "email.new_total_budget", cost_revised, 123.0),
        num("email-stores", "email.approved_stores", 1257, 0),
        check("email-drivers", "set", "email.drivers", truth["email"]["drivers"]),
    ]
    rules = [
        (r"draft email mentions both drivers", "c:email-drivers"),
        (r"compares original vs. revised per.unit cost", "c:unit-original,unit-revised"),
        (r"compares original vs. revised total program cost", "c:cost-original,cost-revised"),
        (r"at least two worksheets", "u:presentation"),
        (r"Tab 2 lists the final store list", "c:stores-final,stores-added,stores-removed"),
        (r"Tab 2 highlights new store locations", "c:stores-added"),
        (r"explicit line item for shelf strips", "c:strip-cost"),
        (r"base unit cost matching", "c:base-cost,revised-components"),
        (r"side panel cost matching", "c:side-cost,revised-components"),
        (r"shelf-strip cost matching", "c:strip-cost"),
        (r"base unit = 1", "c:base-pieces"),
        (r"side panels = 2", "c:side-pieces"),
        (r"shelf strips = 4", "c:strip-pieces"),
        (r"increases only the shelf.strip component", "c:revised-components"),
        (r"Per.unit cost change equals", "c:unit-change"),
        (r"Original per.unit cost equals the sum", "c:unit-original"),
        (r"Revised per.unit cost equals original", "c:unit-revised,unit-change"),
        (r"Original per.unit cost shown", "c:unit-original"),
        (r"Revised per.unit cost shown", "c:unit-revised"),
        (r"overage percentage as 5%", "c:overage"),
        (r"Original store count", "c:stores-original"),
        (r"Final store count", "c:stores-final"),
        (r"Original total units", "c:units-original"),
        (r"Revised total units", "c:units-revised"),
        (r"Original total program cost equals", "c:cost-original"),
        (r"Revised total program cost equals", "c:cost-revised"),
        (r"Original total program cost is shown", "c:cost-original"),
        (r"Revised total program cost is shown", "c:cost-revised"),
        (r"displays the budget change", "c:cost-change"),
        (r"Budget change .* is shown", "c:cost-change"),
        (r"Tab 2 contains exactly the set", "c:stores-final,stores-added,stores-removed"),
        (r"set of highlighted", "c:stores-added"),
        (r"removed store IDs", "c:stores-removed"),
        (r"status of Store 4099", "c:status-4099"),
        (r"status of Store 3737", "c:status-3737"),
        (r"draft email states the updated total number", "c:email-units"),
        (r"draft email states the total program cost increase", "c:email-increase"),
        (r"draft email states the new total program budget", "c:email-total"),
        (r"draft email mentions both drivers", "c:email-drivers"),
        (r"draft email mentions the revised total stores", "c:email-stores"),
        (r"Numbers in the draft email", "c:email-units,email-increase,email-total"),
        (r"Currency values in the comparison worksheet", "u:presentation"),
        (r"explicitly displays the original and final store counts", "c:stores-original,stores-final"),
        (r"explicitly displays the total production units", "c:units-original,units-revised"),
        (r"per.unit comparison includes a line", "c:unit-change"),
        (r"total program comparison includes a line", "c:cost-change"),
        (r"legend or note", "u:presentation"),
        (r"internally consistent", "c:overage,cost-original,cost-revised"),
        (r"Creates a draft email that summarizes", "c:email-units,email-increase,email-total"),
        (r"clearly named", "u:file_format"),
    ]
    return {
        "family": "distributor_inventory_planning",
        "title": "Revise the holiday floorstand budget for the final store matrix",
        "difficulty": "expert",
        "goal": "As order analyst, reconcile the original and final holiday floorstand store lists and restate unit and program cost after the shelf-strip increase.",
        "request": src.prompt,
        "artifact_type": "gdp_floorstand_budget",
        "fields": fields,
        "codes": catalog,
        "tables": [
            table("STORES-ORIG", "Holiday floorstand store list (original)", "Sales team's original list: one floorstand per store.",
                  ["store", "units"], [[row[0], row[1]] for row in original]),
            table("STORES-FINAL", "Approved final holiday matrix", "Retailer's approved final store matrix (store numbers as published, with notes).",
                  ["store", "notes"], [[str(row[0]), row[1]] for row in final]),
        ],
        "documents": [document("EMAILS", "Floorstand email trail", "email", {"thread": email})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["cost-revised", "cost-change", "units-revised"],
        "notes": ["Store sets are compared as integers (the final matrix publishes zero-padded store numbers)."],
    }


# --- task 07: brand data gathering questionnaire ----------------------------------

BRAND_TOPICS = [
    ("brand_overview", "company background, ownership, and contacts"),
    ("sku_information", "SKU-level item data: UPCs, dimensions, case packs, item setup"),
    ("pricing", "wholesale cost, MSRP/MAP, and pricing policy"),
    ("inventory_levels", "on-hand inventory, weeks of supply, replenishment"),
    ("door_count", "current retail door counts and account footprint"),
    ("revenue_trends", "historical revenue and growth by channel"),
    ("promotional_activity", "trade promotions, discounts, and promo calendar"),
    ("marketing_plans", "marketing calendar, budget, and launch support"),
    ("sales_team_structure", "sales organization, territories, and brokers"),
    ("operational_capabilities", "order processing, EDI, lead times, fulfillment"),
    ("compliance_requirements", "regulatory, labeling, insurance, and certifications"),
    ("manufacturing_partnerships", "contract manufacturers, capacity, and sourcing"),
    ("logistics", "shipping points, freight terms, routing"),
]


def t07_brand_questionnaire(src: SourceTask) -> Json:
    questions = [
        ("brand_overview", "What is the brand's legal name, headquarters address, and primary operations and sales contacts?"),
        ("sku_information", "Please list every active SKU with UPC, case pack, unit dimensions, and weight."),
        ("sku_information", "Which SKUs are new launches or planned discontinuations in the next 12 months?"),
        ("pricing", "What are the wholesale cost, MSRP, and MAP for each SKU, and when was pricing last changed?"),
        ("inventory_levels", "What are current on-hand inventory levels by SKU and typical weeks of supply?"),
        ("door_count", "How many retail doors carry the brand today, by account and region?"),
        ("revenue_trends", "What were annual net revenues for the last three years and the year-to-date trend by channel?"),
        ("promotional_activity", "What promotions, discounts, or trade programs ran in the past 12 months and which are planned?"),
        ("marketing_plans", "What marketing campaigns, budget, and launch support are planned for the next 12 months?"),
        ("sales_team_structure", "How is the sales team structured (internal reps, brokers, territories) and who manages key accounts?"),
        ("operational_capabilities", "What are standard order lead times, EDI capabilities, and order fill rates?"),
        ("logistics", "Where does product ship from, and what are freight terms and minimum order quantities?"),
        ("compliance_requirements", "Which regulatory, labeling, insurance, and certification requirements does the brand meet?"),
        ("manufacturing_partnerships", "Who manufactures the products, what is available capacity, and are there backup suppliers?"),
    ]
    rows = [{"id": f"Q{index:02d}", "topic": topic, "prompt": prompt} for index, (topic, prompt) in enumerate(questions, start=1)]
    truth = {"title": "Brand Data Gathering", "format": "question_based", "audience": "brand_operations_and_sales", "questions": rows}
    catalog = {
        "format": codes(("question_based", "written questions with answer space"), ("checklist", "tick-box checklist"), ("free_form_memo", "narrative memo")),
        "audience": codes(("brand_operations_and_sales", "brand-side operations or sales teams"), ("internal_buyers", "distributor buyers"), ("consumers", "end consumers")),
        "questions.topic": codes(*BRAND_TOPICS),
    }
    fields = [
        field("title", "string", "Document title."),
        field("format", "code", "How information is collected."),
        field("audience", "code", "Who completes the form."),
        field("questions", "list[object]", "Each question: id, topic (code), prompt (the written question)."),
    ]
    topic_codes = [code for code, _ in BRAND_TOPICS]
    checks = [
        check("title", "text", "title", "Brand Data Gathering"),
        check("format", "text", "format", "question_based"),
        check("questions", "custom", "questions", None, rule="records", min_count=10, nonempty=["prompt", "topic"], unique="id",
              allowed={"topic": topic_codes}),
    ]
    graded = [code for code in topic_codes if code not in ("brand_overview", "logistics")]
    for code_name in graded:
        checks.append(check(f"topic-{slug(code_name)}", "custom", "questions", None, rule="records", require_values={"topic": [code_name]}))
    topic_rules = {
        "SKU-level": "sku-information", "pricing": "pricing", "inventory levels": "inventory-levels", "door-counts": "door-count",
        "revenue trends": "revenue-trends", "promotional activity": "promotional-activity", "marketing plans": "marketing-plans",
        "sales team structure": "sales-team-structure", "operational capabilities": "operational-capabilities",
        "compliance requirements": "compliance-requirements", "manufacturing partnerships": "manufacturing-partnerships",
    }
    rules: list[tuple[str, str]] = [(rf"prompt related to (?:gathering |the )?{re.escape(key)}", f"c:topic-{value}") for key, value in topic_rules.items()]
    rules += [
        (r"multi-page text-based document", "u:file_format"),
        (r"titled \"Brand Data Gathering\"", "c:title"),
        (r"question-based format", "c:format,questions"),
        (r"multiple written prompts", "c:questions"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Draft the brand data-gathering questionnaire for new brand partners",
        "difficulty": "hard",
        "goal": "As distribution sales manager, draft the Brand Data Gathering questionnaire that new brand partners complete during onboarding.",
        "request": src.prompt,
        "artifact_type": "gdp_brand_questionnaire",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["questions", "topic-pricing", "topic-operational-capabilities"],
        "notes": ["Topic coverage is scored per required topic; question wording is free text and unscored beyond being present."],
    }


# --- task 08: territory fit report ---------------------------------------------------

REGIONS = ["South", "Northeast", "Midwest", "West Coast"]


def t08_territory_fit(src: SourceTask) -> Json:
    raw = xlsx_rows(src.ref("Territory Fit"), "Sheet1")
    require(raw[0][:7] == ("Store Name", "Region", "State", "Gender", "Fit", "Units Ordered", "Total Revenue"), "task 08 header")
    data = [row[:7] for row in raw[1:] if row[0] not in (None, "")]
    require({row[1] for row in data} == set(REGIONS), "task 08 regions")
    columns = ["store_name", "region", "state", "gender", "fit", "units", "revenue"]
    by_gender: Json = {}
    summary: Json = {}
    for gender in ("Men", "Women"):
        regions: Json = {}
        for region in REGIONS:
            fits: dict[str, list[float]] = defaultdict(lambda: [0, 0])
            for row in data:
                if row[3] == gender and row[1] == region:
                    fits[row[4]][0] += row[5]
                    fits[row[4]][1] += row[6]
            ordered = sorted(fits, key=lambda name: (-fits[name][0], name))
            top = ordered[0]
            regions[region] = {
                "fits": {name: {"units": fits[name][0], "revenue": r2(fits[name][1])} for name in sorted(fits)},
                "total_units": sum(value[0] for value in fits.values()),
                "total_revenue": r2(sum(value[1] for value in fits.values())),
                "top_fit": {"fit": top, "units": fits[top][0], "revenue": r2(fits[top][1])},
                "ranking_by_units": ordered,
            }
        by_gender[gender] = {"regions": regions}
        summary[gender] = {
            "units": sum(item["total_units"] for item in regions.values()),
            "revenue": r2(sum(item["total_revenue"] for item in regions.values())),
        }
    summary["combined"] = {
        "units": summary["Men"]["units"] + summary["Women"]["units"],
        "revenue": r2(summary["Men"]["revenue"] + summary["Women"]["revenue"]),
    }
    expected_tops = {
        ("Men", "South"): ("Baggy", 915, 78885), ("Men", "Northeast"): ("Relaxed", 937, 77189),
        ("Men", "Midwest"): ("Carpenter", 915, 80685), ("Men", "West Coast"): ("Carpenter", 309, 30693),
        ("Women", "South"): ("Boyfriend", 744, 68904), ("Women", "Northeast"): ("Relaxed", 870, 72337),
        ("Women", "Midwest"): ("Cargo", 652, 52728), ("Women", "West Coast"): ("Flare", 360, 36232),
    }
    for (gender, region), top in expected_tops.items():
        got = by_gender[gender]["regions"][region]["top_fit"]
        require((got["fit"], got["units"], got["revenue"]) == top, f"task 08 top {gender} {region}: {got}")
    truth = {"report_date": "2025-07-09", "regions": REGIONS, "by_gender": by_gender, "executive_summary": summary}
    fields = [
        field("report_date", "date", "Report date shown on the title/summary."),
        field("regions", "list[string]", "Regions covered, named as in the source data."),
        field("by_gender", "object<gender,object>", "Keys Men and Women. Each has regions: object keyed by region with fits "
              "(object keyed by fit name: units, revenue), total_units, total_revenue, top_fit {fit, units, revenue} "
              "(top by units), ranking_by_units (fit names, highest units first)."),
        field("executive_summary", "object", "Men, Women, and combined: each {units, revenue} across all four regions."),
    ]
    checks = [
        check("report-date", "text", "report_date", "2025-07-09"),
        check("regions", "set", "regions", REGIONS),
        check("genders", "keys", "by_gender", ["Men", "Women"]),
    ]
    for key in ("Men", "Women", "combined"):
        checks.append(check(f"summary-{slug(key)}", "custom", rule="all_of", checks=[
            num("u", ["executive_summary", key, "units"], summary[key]["units"], 0),
            num("r", ["executive_summary", key, "revenue"], summary[key]["revenue"], 1.0),
        ]))
    ties = {("Men", "Northeast"): [("Slim", "Bootcut")]}
    optional = {("Women", "West Coast"): ["Wide Leg"]}
    for gender in ("Men", "Women"):
        for region in REGIONS:
            item = by_gender[gender]["regions"][region]
            base = ["by_gender", gender, "regions", region]
            tag = f"{slug(gender)}-{slug(region)}"
            checks.append(check(f"fits-{tag}", "custom", [*base, "fits"], item["fits"], rule="rows_match", tolerance=1.0))
            checks.append(check(f"total-{tag}", "custom", rule="all_of", checks=[
                num("u", [*base, "total_units"], item["total_units"], 0),
                num("r", [*base, "total_revenue"], item["total_revenue"], 1.0),
            ]))
            checks.append(check(f"top-{tag}", "custom", rule="all_of", checks=[
                check("f", "text", [*base, "top_fit", "fit"], item["top_fit"]["fit"]),
                num("u", [*base, "top_fit", "units"], item["top_fit"]["units"], 0),
                num("r", [*base, "top_fit", "revenue"], item["top_fit"]["revenue"], 1.0),
            ]))
            groups: list[list[str]] = []
            tied = {name for pair in ties.get((gender, region), []) for name in pair}
            for name in item["ranking_by_units"]:
                if name in tied:
                    if not groups or set(groups[-1]) != tied:
                        groups.append(sorted(tied))
                    continue
                groups.append([name])
            checks.append(check(f"rank-{tag}", "custom", [*base, "ranking_by_units"], None, rule="ranking", groups=groups,
                                optional=optional.get((gender, region), [])))
    region_alt = r"(Midwest|South|Northeast|West Coast)"
    rules = [
        (r"covers only the four requested", "c:regions"),
        (r"Men's performance content is presented on slide", "c:genders"),
        (r"executive summary section includes Men totals", "c:summary-men"),
        (r"executive summary section includes Women totals", "c:summary-women"),
        (r"Executive summary Men totals", "c:summary-men"),
        (r"Executive summary Women totals", "c:summary-women"),
        (r"combined Men\+Women totals", "c:summary-combined"),
        (rf"fit-level sales breakdown .* for \b(Men|Women) {region_alt}", "c:fits-{1}-{2}"),
        (rf"Slides presenting {region_alt} results", "c:regions"),
        (rf"^\b(Men|Women) {region_alt} .*regional totals", "c:total-{1}-{2}"),
        (r"where parts and totals are both displayed", "c:total-*"),
        (r"No numeric values or rankings", "c:fits-*,total-*,rank-*"),
        (r"pie chart", "u:presentation"),
        (r"top-selling fits for (Men|Women) in each region", "c:top-{1}-*"),
        (rf"For (Men|Women) in the {region_alt}", "c:top-{1}-{2}"),
        (rf"chart or graph for (Men|Women) {region_alt}", "c:rank-{1}-{2}"),
        (r"at least one slide aggregating", "c:summary-men,summary-women"),
        (r"indicate whether displayed values are Units or Revenue", "u:presentation"),
        (r"use a dollar sign", "u:presentation"),
        (r"date July 9, 2025", "c:report-date"),
    ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Recap top-selling denim fits by region and gender",
        "difficulty": "expert",
        "goal": "As U.S. sales manager, rank men's and women's fits by region from wholesale sell-in data and summarize totals for merchandising.",
        "request": src.prompt,
        "artifact_type": "gdp_territory_fit_recap",
        "fields": fields,
        "codes": {},
        "tables": [table("SELLIN", "Territory fit sell-in", "Store-level sell-in by region, state, gender, and fit.", columns, [list(row) for row in data])],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["summary-combined", "top-men-south", "top-women-northeast"],
        "notes": [
            "Rankings are by units. Men Northeast Slim (507) and Bootcut (503) may appear in either order, as the rubric allows.",
            "The rubric's Women West Coast ranking omits Wide Leg (45 units, last); the ranking check accepts it present or absent.",
        ],
    }


# --- task 09: ERP order type proposal --------------------------------------------------

ORDER_CHALLENGES = [
    ("parent_po_placeholder_cancellation", "parent pre-order placeholders must be cancelled manually when allocated orders arrive; often missed, inflating the order book"),
    ("preorder_cancellation_skew", "cancelling parent pre-orders skews pre-order cancellation reporting"),
    ("bulk_hides_committed_preorders", "using Bulks without classification hides that they are committed pre-orders"),
    ("wrong_order_type_via_edi", "accounts send EDI POs with the wrong order type or mapping is incorrect"),
    ("order_type_not_editable", "order type cannot be changed manually in the new ERP"),
    ("special_opportunities_not_visible", "direct shipments and stock clearance orders are not distinguishable"),
    ("inflated_order_book_for_logistics", "logistics cannot trust order book quantities for shipping capacity planning"),
]


def t09_order_types(src: SourceTask) -> Json:
    reference = docx_paragraphs(src.ref("Order Types"))
    require(any("Forecast Bulk" in line for line in reference), "task 09 reference changed")
    challenge_codes = [code for code, _ in ORDER_CHALLENGES]
    proposed = [
        {
            "code": "parent_bulk", "name": "Parent Bulk (Pre-Order Bulk)",
            "rationale": "Harbor & March pre-orders are committed but not ship-ready; a parent bulk reduces automatically as allocated EDI orders arrive.",
            "reporting_improvement": "Committed pre-order value stays visible without manual parent-PO cancellation, so the book is not inflated.",
            "difference_from_base": "Unlike Forecast Bulk it is a committed buy; unlike Pre-Order it is not ship-ready and is drawn down by allocations.",
            "challenges_addressed": ["parent_po_placeholder_cancellation", "preorder_cancellation_skew", "bulk_hides_committed_preorders"],
            "entry_criterion": "Committed PO received before the sell-in deadline that will be allocated to more than one DC/store.",
            "erp_tag": "Sales order header Order Type = PBULK",
        },
        {
            "code": "direct_shipment", "name": "Direct Shipment",
            "rationale": "Orders fulfilled outside US stock need separate visibility for demand planning.",
            "reporting_improvement": "Demand planning sees which demand was not served from US stock.",
            "difference_from_base": "Shipped direct from factory/origin rather than from US DC inventory.",
            "challenges_addressed": ["special_opportunities_not_visible"],
            "entry_criterion": "Order ships direct from origin with no US DC receipt.",
            "erp_tag": "Order Type = DSHIP",
        },
        {
            "code": "stock_clearance", "name": "Stock Clearance",
            "rationale": "Closeout and clearance deals distort re-order (chase) reporting when mixed in.",
            "reporting_improvement": "Chase re-orders stay clean; clearance revenue reported separately.",
            "difference_from_base": "Discounted off-price inventory sale, not committed seasonal or chase demand.",
            "challenges_addressed": ["special_opportunities_not_visible"],
            "entry_criterion": "Line priced below standard wholesale on inventory flagged as closeout.",
            "erp_tag": "Order Type = CLR",
        },
        {
            "code": "draft_order", "name": "Draft (EDI Review)",
            "rationale": "EDI orders arrive with the wrong type and cannot be corrected after confirmation.",
            "reporting_improvement": "Orders are reviewed and typed correctly before entering the order book.",
            "difference_from_base": "Holding state for unconfirmed inbound orders; converts to Pre-Order or Re-Order once reviewed.",
            "challenges_addressed": ["wrong_order_type_via_edi", "order_type_not_editable"],
            "entry_criterion": "Any inbound EDI order whose type or mapping fails validation.",
            "erp_tag": "Order Type = DRAFT until confirmed",
        },
    ]
    truth = {
        "goal": "clear_reporting_without_interpretation",
        "base_order_types": ["pre_order", "re_order", "bulk"],
        "additive_to_base_types": True,
        "proposed_order_types": proposed,
        "challenges_cited": challenge_codes,
        "base_type_changes": [{
            "type": "bulk", "revised_name": "Forecast Bulk",
            "revised_definition": "Bulk used only to reserve forecast chase inventory that re-orders draw down.",
            "reason": "Differentiates chase forecast bulks from committed parent bulks.",
        }],
        "assignment_level": "po_header",
        "mixed_type_po_handling": "Mixed-intent POs are split into separate sales orders, one order type each.",
        "erp_tag_field": "Sales order header Order Type code",
        "growth_considerations": "Types are generic so new key accounts and channels reuse them without new codes.",
        "validation_rules": ["EDI orders with missing or invalid type default to DRAFT", "Parent Bulk requires a parent account and allocation date"],
        "type_change_governance": [{"role": "sales_operations", "permission": "assign_and_change"}, {"role": "key_account_manager", "permission": "request_change"}],
        "training": ["quick_reference_guide", "training_sessions"],
        "rollout_plan": ["pilot with Harbor & March for one season", "review KPIs", "roll out to all key accounts"],
        "risks": [{"risk": "Users pick the wrong new type", "mitigation": "Validation rules and quick reference guide"}],
        "executive_summary": "Add Parent Bulk, Direct Shipment, Stock Clearance, and Draft order types and rename Bulk to Forecast Bulk.",
        "stakeholder_benefits": [
            {"stakeholder": "leadership", "benefit": "Order book reflects committed versus chase business without investigation."},
            {"stakeholder": "key_account_managers", "benefit": "Fewer clarification requests and clear buy-in vs chase history."},
            {"stakeholder": "logistics", "benefit": "Trustworthy monthly volumes for shipping capacity."},
        ],
        "kpis": [{"kpi": "pct_orders_with_valid_type", "target": "99%"}, {"kpi": "misclassified_orders_per_month", "target": "<5"}],
        "audit_trail_required": True,
        "exception_handling": "Misclassified orders are corrected by Sales Ops via change request, logged, and reports re-run.",
    }
    statuses = ["allocated", "shipped", "cancelled", "backordered", "released", "invoiced"]
    catalog = {
        "goal": codes(
            ("clear_reporting_without_interpretation", "order book reporting understood by all functions without interpretation"),
            ("maximize_order_volume", "increase order intake"), ("reduce_erp_licenses", "cut ERP user licences"),
        ),
        "base_order_types": codes(("pre_order", "Pre-Order"), ("re_order", "Re-Order"), ("bulk", "Bulk"), ("forecast", "legacy Salesforce forecast")),
        "challenges": codes(*ORDER_CHALLENGES),
        "assignment_level": codes(("po_header", "one type per PO/sales order header"), ("line_level", "type set per line"), ("both", "header default with line override")),
        "operational_statuses": codes(*[(status, "order status, not an order type") for status in statuses]),
        "type_change_governance.role": codes(
            ("sales_operations", "Sales Operations"), ("customer_service", "Customer Service"), ("key_account_manager", "KAM"),
            ("demand_planning", "Demand Planning"), ("it_erp_admin", "ERP administrators"),
        ),
        "training": codes(("quick_reference_guide", "one-page order type guide"), ("training_sessions", "live training"), ("sop_update", "updated SOP"), ("office_hours", "office hours")),
    }
    fields = [
        field("goal", "code", "Objective of the proposal."),
        field("base_order_types", "list[code]", "Existing base order types the proposal builds on."),
        field("additive_to_base_types", "bool", "True when the proposed types are added alongside the base types."),
        field("proposed_order_types", "list[object]", "Each: code (unique snake_case), name, rationale, reporting_improvement, difference_from_base, "
              "challenges_addressed (list of challenge codes), entry_criterion (measurable), erp_tag."),
        field("challenges_cited", "list[code]", "Reference-file challenges the proposal cites."),
        field("base_type_changes", "list[object]", "Changes to base types, each: type, revised_name, revised_definition, reason (empty list if none)."),
        field("assignment_level", "code", "Where the order type is assigned."),
        field("mixed_type_po_handling", "string", "How POs mixing intents are handled (required when line-level assignment is allowed)."),
        field("erp_tag_field", "string", "ERP field or code that carries the order type."),
        field("growth_considerations", "string", "How the design scales with growth."),
        field("validation_rules", "list[string]", "Validation or automation rules enforcing correct type selection."),
        field("type_change_governance", "list[object]", "Each: role (code), permission."),
        field("training", "list[code]", "Enablement materials."),
        field("rollout_plan", "list[string]", "High-level rollout or pilot steps."),
        field("risks", "list[object]", "Each: risk, mitigation."),
        field("executive_summary", "string", "Summary of recommendations and next steps."),
        field("stakeholder_benefits", "list[object]", "Each: stakeholder (leadership, key_account_managers, key_accounts, logistics, demand_planning, ...), benefit."),
        field("kpis", "list[object]", "Each: kpi, target."),
        field("audit_trail_required", "bool", "Whether order type changes keep an audit trail/change log."),
        field("exception_handling", "string", "How misclassified orders are corrected and reports updated."),
    ]
    types_path = "proposed_order_types"
    checks = [
        check("goal", "text", "goal", truth["goal"]),
        check("base-types", "set", "base_order_types", truth["base_order_types"]),
        check("additive", "bool", "additive_to_base_types", True),
        check("types-new", "custom", types_path, None, rule="records", min_count=1, nonempty=["code", "name"],
              forbid={"code": ["pre_order", "re_order", "bulk", "forecast_bulk", "preorder", "reorder"]}),
        check("types-unique", "custom", types_path, None, rule="records", unique="code"),
        check("types-rationale", "custom", types_path, None, rule="records", nonempty=["rationale"]),
        check("types-reporting", "custom", types_path, None, rule="records", nonempty=["reporting_improvement"]),
        check("types-difference", "custom", types_path, None, rule="records", nonempty=["difference_from_base"]),
        check("types-challenge-map", "custom", types_path, None, rule="records", some_nonempty=["challenges_addressed"],
              allowed={"challenges_addressed": challenge_codes}),
        check("types-entry-criteria", "custom", types_path, None, rule="records", some_nonempty=["entry_criterion"]),
        check("types-no-status", "custom", types_path, None, rule="records", forbid={"code": statuses}),
        check("challenges-cited", "overlaps", "challenges_cited", challenge_codes),
        check("base-changes", "custom", "base_type_changes", None, rule="records", min_count=0,
              nonempty=["type", "revised_definition", "reason"], allowed={"type": ["pre_order", "re_order", "bulk"]}),
        check("assignment-level", "member", "assignment_level", ["po_header", "line_level", "both"]),
        check("mixed-po", "custom", rule="if_then",
              when=check("w", "member", "assignment_level", ["line_level", "both"]),
              then=check("t", "nonempty", "mixed_type_po_handling")),
        check("erp-tag", "nonempty", "erp_tag_field"),
        check("growth", "nonempty", "growth_considerations"),
        check("validation-rules", "nonempty", "validation_rules"),
        check("governance", "custom", "type_change_governance", None, rule="records", nonempty=["role", "permission"]),
        check("training", "nonempty", "training"),
        check("rollout", "nonempty", "rollout_plan"),
        check("risks", "custom", "risks", None, rule="records", nonempty=["risk", "mitigation"]),
        check("executive-summary", "nonempty", "executive_summary"),
        check("benefit-leadership", "custom", "stakeholder_benefits", None, rule="records", nonempty=["benefit"],
              require_values={"stakeholder": ["leadership"]}),
        check("benefit-key-accounts", "custom", "stakeholder_benefits", None, rule="records", nonempty=["benefit"],
              require_any={"stakeholder": ["key_accounts", "key_account_managers"]}),
        check("kpis", "custom", "kpis", None, rule="records", nonempty=["kpi"]),
        check("audit-trail", "bool", "audit_trail_required", True),
        check("exception-handling", "nonempty", "exception_handling"),
    ]
    rules = [
        (r"delivered as a Microsoft Word document", "u:file_format"),
        (r"states the goal is to make reporting clear", "c:goal"),
        (r"new order types are additions", "c:additive"),
        (r"introduces at least one new order type", "c:types-new"),
        (r"unique name", "c:types-unique,types-new"),
        (r"explicit business rationale", "c:types-rationale"),
        (r"For each proposed order type, the proposal states at least one specific way it improves reporting", "c:types-reporting"),
        (r"recognizes the existing base order types", "c:base-types"),
        (r"references at least one specific challenge or use case", "c:challenges-cited"),
        (r"explicitly mapped to a proposed order type", "c:types-challenge-map"),
        (r"Argues how a proposed order type addresses a challenge", "c:types-challenge-map"),
        (r"at least one difference between the proposed order type", "c:types-difference"),
        (r"the revised definition is stated", "c:base-changes"),
        (r"the reason for the change are stated", "c:base-changes"),
        (r"intended assignment level", "c:assignment-level"),
        (r"mixed-type POs are handled", "c:mixed-po"),
        (r"measurable entry criterion", "c:types-entry-criteria"),
        (r"ERP field or code to tag", "c:erp-tag"),
        (r"reduces misreporting or manual interpretation", "c:types-reporting"),
        (r"cites at least one challenge from the reference file", "c:challenges-cited"),
        (r"specific inefficiency or data accuracy issue", "c:challenges-cited,types-challenge-map"),
        (r"growth/scale", "c:growth"),
        (r"validation or automation rule", "c:validation-rules"),
        (r"governance on who can assign", "c:governance"),
        (r"training, guides, or enablement", "c:training"),
        (r"rollout or pilot plan", "c:rollout"),
        (r"risk of adding the new order type", "c:risks"),
        (r"avoids redefining operational statuses", "c:types-no-status"),
        (r"executive summary or closing section", "c:executive-summary"),
        (r"leadership benefits", "c:benefit-leadership"),
        (r"positive impact on key accounts", "c:benefit-key-accounts"),
        (r"measurable KPI", "c:kpis"),
        (r"audit trail or change log", "c:audit-trail"),
        (r"exception-handling step", "c:exception-handling"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Propose new ERP order types for key-account reporting",
        "difficulty": "hard",
        "goal": "As key-account sales manager, propose ERP order types (beyond Pre-Order, Re-Order, Bulk) that make the order book readable without interpretation.",
        "request": src.prompt,
        "artifact_type": "gdp_order_type_proposal",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [document("ORDERTYPES", "Order types, entry and challenges", "DMS", {"reference": reference})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["types-new", "types-challenge-map", "base-types"],
        "notes": [
            ("The proposal is open-ended: checks score structure (each type carries rationale, reporting effect, difference, "
            "challenge mapping from the catalog) and exclude base types and operational statuses as new types."),
        ],
    }


# --- task 10: return authorization process ----------------------------------------------


def t10_return_process(src: SourceTask) -> Json:
    reference = docx_paragraphs(src.ref("Return Issues"))
    require(len(reference) >= 10, "task 10 reference changed")
    sla = {
        "ra_issued": (3, "kam_rtv_approval", "customer_service"),
        "return_received": (60, "ra_issuance", "warehouse_dc"),
        "receiving_report": (14, "dc_receipt", "warehouse_dc"),
        "credit_issued": (45, "dc_receipt", "customer_service"),
        "ra_closed": (90, "ra_creation", "customer_service"),
    }
    actions = {
        "ra_issued": "CS generates the RA#, sends it to the account and DC, and uploads the approved item list into D365.",
        "return_received": "Account ships labeled cartons; DC receives the return within the window.",
        "receiving_report": "DC sends CS a report of items received by RA (style/size/qty).",
        "credit_issued": "CS reconciles the DC report against RA lines and issues the return credit.",
        "ra_closed": "CS closes credited RAs; unreceived RAs are manually closed at 90 days and the account notified.",
    }
    steps = {
        code: {"action": actions[code], "deadline_days": days, "deadline_anchor": anchor, "responsible": role}
        for code, (days, anchor, role) in sla.items()
    }
    steps["ra_issued"]["uploads_item_list_to"] = "D365"
    handoffs = ["kam_to_customer_service", "customer_service_to_account_and_dc", "dc_to_customer_service", "customer_service_credit_to_account", "closure_notice_to_account"]
    truth = {
        "internal_process": {
            "audience": "internal",
            "ra_trigger": "kam_rtv_approval",
            "day_basis": "calendar_days",
            "steps": steps,
            "reconciliation": {"required_before_credit": True, "compares": ["dc_receiving_report", "ra_line_items", "quantities"]},
            "unlabeled_return_policy": "hold_pending_identification",
            "late_return_policy": "refuse_or_require_new_ra",
            "closure": {
                "received_and_credited_status": "closed",
                "unresolved_at_90_days": ["manual_close_in_system", "notify_account"],
                "responsible": "customer_service",
            },
            "handoffs": handoffs,
        },
        "external_guidelines": {
            "audience": "key_accounts",
            "intro_statement": "Following these guidelines ensures your return is processed and credited quickly and accurately.",
            "day_basis": "calendar_days",
            "return_window_days": 60,
            "credit_days_after_receipt": 45,
            "ra_request_info": ["po_number", "line_product_identifier_and_quantity", "return_reason", "ship_from_address", "contact_name_and_email_or_phone"],
            "sized_breakdown_required": True,
            "carton_labeling": ["ra_number_on_all_outer_cartons"],
            "packing_slip_contents": ["product_identifier", "quantity"],
            "expired_window_action": "new_ra_required",
            "noncompliance_consequences": ["delayed_processing", "refused"],
            "missing_documents_delay_credit": True,
            "unlisted_items_delay_credit": True,
            "chargeback_dispute_reserved": True,
            "contact_channel": "returns@company.example (RA requests and questions)",
        },
    }
    catalog = {
        "steps": codes(
            ("ra_issued", "RA# issued to account and DC, item list in D365"), ("return_received", "return received at DC"),
            ("receiving_report", "DC report of items received to CS"), ("credit_issued", "return credit issued"), ("ra_closed", "RA closed"),
        ),
        "deadline_anchor": codes(
            ("kam_rtv_approval", "KAM approves the RTV"), ("ra_issuance", "RA# issued"), ("dc_receipt", "DC receives shipment"),
            ("ra_creation", "RA created"), ("account_request", "account requests the return"),
        ),
        "roles": codes(
            ("key_account_manager", "KAM"), ("key_account_representative", "KAR"), ("customer_service", "CS"),
            ("warehouse_dc", "warehouse / DC"), ("finance", "Finance"), ("account", "key account"),
        ),
        "day_basis": codes(("calendar_days", "calendar days"), ("business_days", "business days")),
        "unlabeled_return_policy": codes(
            ("hold_pending_identification", "hold unlabeled/unidentified returns; no credit until matched to an RA"),
            ("quarantine_and_investigate", "quarantine and investigate with the account before credit"),
            ("credit_on_receipt", "credit whatever arrives"),
        ),
        "late_return_policy": codes(
            ("refuse_or_require_new_ra", "returns after 60 days are refused or need a new RA"),
            ("hold_pending_kam_approval", "late returns held until the KAM approves"),
            ("accept_and_credit", "accept and credit late returns"),
        ),
        "closure.unresolved_at_90_days": codes(("manual_close_in_system", "manually close the RA"), ("notify_account", "notify the account"), ("extend_30_days", "extend by 30 days")),
        "reconciliation.compares": codes(("dc_receiving_report", "DC receiving report"), ("ra_line_items", "RA lines"), ("quantities", "quantities"), ("invoice_prices", "invoice prices")),
        "handoffs": codes(
            ("kam_to_customer_service", "KAM approval to CS"), ("customer_service_to_account_and_dc", "RA# to account and DC"),
            ("dc_to_customer_service", "DC receiving report to CS"), ("customer_service_credit_to_account", "credit notice to account"),
            ("closure_notice_to_account", "90-day closure notice to account"),
        ),
        "external_guidelines.ra_request_info": codes(
            ("po_number", "original order/PO number"), ("line_product_identifier_and_quantity", "per-line SKU/UPC/style and quantity"),
            ("return_reason", "return reason"), ("ship_from_address", "ship-from address"), ("contact_name_and_email_or_phone", "contact name and email/phone"),
            ("store_number", "store number"),
        ),
        "external_guidelines.carton_labeling": codes(("ra_number_on_all_outer_cartons", "RA# clearly on every outer carton"), ("ra_number_on_first_carton", "RA# on one carton")),
        "external_guidelines.packing_slip_contents": codes(("product_identifier", "SKU/UPC/style"), ("quantity", "quantity per item"), ("unit_price", "unit price")),
        "external_guidelines.expired_window_action": codes(("new_ra_required", "request a new RA# before shipping"), ("ship_anyway", "ship with the old RA#")),
        "external_guidelines.noncompliance_consequences": codes(("delayed_processing", "processing/credit delayed"), ("refused", "return refused"), ("no_credit", "no credit issued")),
    }
    fields = [
        field("internal_process.audience", "string", "Audience of the internal process document."),
        field("internal_process.ra_trigger", "code", "Event that starts the RA issuance clock."),
        field("internal_process.day_basis", "code", "Whether SLA days are calendar or business days."),
        field("internal_process.steps", "object<step,object>", "Keyed by step code; each: action, deadline_days, deadline_anchor (code), responsible (role code); "
              "ra_issued also uploads_item_list_to (system)."),
        field("internal_process.reconciliation", "object", "required_before_credit (bool), compares (list[code])."),
        field("internal_process.unlabeled_return_policy", "code", "Handling of unlabeled or unidentified returns before credit."),
        field("internal_process.late_return_policy", "code", "Handling of returns received after the 60-day window."),
        field("internal_process.closure", "object", "received_and_credited_status, unresolved_at_90_days (list[code]), responsible (role code)."),
        field("internal_process.handoffs", "list[code]", "Handoffs enumerated at key milestones."),
        field("external_guidelines.audience", "string", "Audience of the external guidelines."),
        field("external_guidelines.intro_statement", "string", "Opening instruction to accounts."),
        field("external_guidelines.day_basis", "code", "Whether stated days are calendar or business days."),
        field("external_guidelines.return_window_days", "number", "Days after RA issuance by which returns must arrive."),
        field("external_guidelines.credit_days_after_receipt", "number", "Days after DC receipt by which credit is issued."),
        field("external_guidelines.ra_request_info", "list[code]", "Information required when requesting an RA."),
        field("external_guidelines.sized_breakdown_required", "bool", "Whether a sized breakdown is requested."),
        field("external_guidelines.carton_labeling", "list[code]", "Carton labeling requirements."),
        field("external_guidelines.packing_slip_contents", "list[code]", "Required packing slip contents."),
        field("external_guidelines.expired_window_action", "code", "What to do when items are not in transit before the window expires."),
        field("external_guidelines.noncompliance_consequences", "list[code]", "Consequences of noncompliant returns."),
        field("external_guidelines.missing_documents_delay_credit", "bool", "Missing packing slip or RA labeling may delay credit."),
        field("external_guidelines.unlisted_items_delay_credit", "bool", "Items not on the packing slip may delay credit."),
        field("external_guidelines.chargeback_dispute_reserved", "bool", "Right reserved to dispute chargebacks when guidelines are not followed."),
        field("external_guidelines.contact_channel", "string", "Email address or portal for RA requests."),
    ]
    ip = "internal_process"
    eg = "external_guidelines"

    def step_check(code: str, extra: Json | None = None) -> Json:
        days, anchor, role = sla[code]
        expected = {code: {"deadline_days": days, "deadline_anchor": anchor, "responsible": role, **(extra or {})}}
        return check(f"step-{slug(code)}", "custom", [ip, "steps"], expected, rule="rows_match", tolerance=0, exact_ids=False)

    checks = [
        step_check("ra_issued", {"uploads_item_list_to": "D365"}),
        step_check("return_received"),
        step_check("receiving_report"),
        step_check("credit_issued"),
        step_check("ra_closed"),
        check("steps-structure", "custom", [ip, "steps"], None, rule="records", min_count=5, nonempty=["action", "deadline_days", "responsible"]),
        check("steps-keys", "keys", [ip, "steps"], list(sla)),
        check("ra-trigger", "text", [ip, "ra_trigger"], "kam_rtv_approval"),
        check("reconciliation", "custom", rule="all_of", checks=[
            check("r", "bool", [ip, "reconciliation", "required_before_credit"], True),
            check("c", "includes", [ip, "reconciliation", "compares"], ["dc_receiving_report", "ra_line_items", "quantities"]),
        ]),
        check("unlabeled-policy", "member", [ip, "unlabeled_return_policy"], ["hold_pending_identification", "quarantine_and_investigate"]),
        check("late-policy", "member", [ip, "late_return_policy"], ["refuse_or_require_new_ra", "hold_pending_kam_approval"]),
        check("closure-rule", "custom", rule="all_of", checks=[
            check("s", "text", [ip, "closure", "received_and_credited_status"], "closed"),
            check("u", "includes", [ip, "closure", "unresolved_at_90_days"], ["manual_close_in_system", "notify_account"]),
        ]),
        check("closure-role", "text", [ip, "closure", "responsible"], "customer_service"),
        check("handoffs", "includes", [ip, "handoffs"], handoffs),
        check("day-basis", "custom", rule="all_of", checks=[
            check("i", "member", [ip, "day_basis"], ["calendar_days", "business_days"]),
            check("e", "member", [eg, "day_basis"], ["calendar_days", "business_days"]),
        ]),
        check("audiences", "custom", rule="all_of", checks=[
            check("i", "nonempty", [ip, "audience"]), check("e", "nonempty", [eg, "audience"]),
        ]),
        num("ext-window", [eg, "return_window_days"], 60, 0),
        num("ext-credit", [eg, "credit_days_after_receipt"], 45, 0),
        check("ext-carton", "includes", [eg, "carton_labeling"], ["ra_number_on_all_outer_cartons"]),
        check("ext-packing-slip", "includes", [eg, "packing_slip_contents"], ["product_identifier", "quantity"]),
        check("ext-noncompliance", "includes", [eg, "noncompliance_consequences"], ["delayed_processing", "refused"]),
        check("ext-intro", "nonempty", [eg, "intro_statement"]),
        check("ext-sized", "bool", [eg, "sized_breakdown_required"], True),
        check("ext-expired", "text", [eg, "expired_window_action"], "new_ra_required"),
        check("ext-missing-docs", "bool", [eg, "missing_documents_delay_credit"], True),
        check("ext-unlisted", "bool", [eg, "unlisted_items_delay_credit"], True),
        check("ext-chargeback", "bool", [eg, "chargeback_dispute_reserved"], True),
        check("ext-contact", "nonempty", [eg, "contact_channel"]),
    ]
    for code_name in truth[eg]["ra_request_info"]:
        checks.append(check(f"ext-info-{slug(code_name)}", "includes", [eg, "ra_request_info"], [code_name]))
    rules = [
        (r"requires reconciliation of RA line items", "c:reconciliation"),
        (r"defines a reconciliation check", "c:reconciliation"),
        (r"noncompliant returns \(unlabeled, late, missing documents\) may be delayed", "c:ext-noncompliance"),
        (r"consequences for noncompliant returns", "c:ext-noncompliance"),
        (r"Provides two separate Microsoft Word", "u:file_format"),
        (r"clearly indicates its audience", "c:audiences"),
        (r"clearly presents WHAT", "c:steps-structure"),
        (r"specifies the action\(s\) required", "c:steps-structure"),
        (r"expected timeline \(i\.e\., WHEN\)", "c:steps-structure"),
        (r"responsible role or team \(i\.e\., WHO\)", "c:steps-structure"),
        (r"approval of RTV as the trigger", "c:ra-trigger,step-ra-issued"),
        (r"assigns Customer Service as responsible for generating", "c:step-ra-issued"),
        (r"warehouse/DC as responsible for receiving", "c:step-return-received,step-receiving-report"),
        (r"names the role/team responsible for issuing the return credit", "c:step-credit-issued"),
        (r"RA number must be issued within 3 days", "c:step-ra-issued"),
        (r"Internal process states returns must be received", "c:step-return-received"),
        (r"provides a report of items received to Customer Service within 14", "c:step-receiving-report"),
        (r"Internal process states return credit is issued within 45", "c:step-credit-issued"),
        (r"RA is closed internally after 90", "c:step-ra-closed"),
        (r"if the return is received and credited, the RA is marked closed", "c:closure-rule"),
        (r"responsible for the 90.day closure", "c:closure-role"),
        (r"unlabeled or unidentified returns", "c:unlabeled-policy"),
        (r"returns received after the 60-day deadline", "c:late-policy"),
        (r"step representing RA issuance", "c:step-ra-issued"),
        (r"step representing the shipment being received", "c:step-return-received"),
        (r"step representing the warehouse/DC providing a report", "c:step-receiving-report"),
        (r"step representing Customer Service validation", "c:step-credit-issued,reconciliation"),
        (r"three.column table or equivalent", "c:steps-structure"),
        (r"External guidelines state that returns must arrive", "c:ext-window"),
        (r"RA number to be clearly displayed", "c:ext-carton"),
        (r"packing slip with item.level detail", "c:ext-packing-slip"),
        (r"External guidelines state that credit will be issued within 45", "c:ext-credit"),
        (r"brief instruction at the top", "c:ext-intro"),
        (r"including order/PO number", "c:ext-info-po-number"),
        (r"including per.line product identifiers", "c:ext-info-line-product-identifier-and-quantity"),
        (r"including a return reason", "c:ext-info-return-reason"),
        (r"including ship.from address", "c:ext-info-ship-from-address,ext-info-contact-name-and-email-or-phone"),
        (r"sized breakdown", "c:ext-sized"),
        (r"new RA number must be obtained", "c:ext-expired"),
        (r"missing packing slips and/or missing RA labeling", "c:ext-missing-docs"),
        (r"items not listed on the packing slip", "c:ext-unlisted"),
        (r"right to dispute chargebacks", "c:ext-chargeback"),
        (r"clear contact channel", "c:ext-contact"),
        (r"calendar or business days", "c:day-basis"),
        (r"clear headings", "u:presentation"),
        (r"enumerates handoffs", "c:handoffs"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Standardize the key-account return authorization process and guidelines",
        "difficulty": "hard",
        "goal": "As key-account sales manager, define the internal RA process (what, when, who) and the external account return guidelines.",
        "request": src.prompt,
        "artifact_type": "gdp_return_authorization_policy",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [document("RETURNS", "Current return issues", "DMS", {"issues": reference})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["step-credit-issued", "reconciliation", "ext-window"],
        "notes": ["SLA steps are graded on deadline days, anchor event, and responsible role; action text is free-form."],
    }

# --- task 11: dealer parts receiving procedure ---------------------------------------


def t11_receiving_procedure(src: SourceTask) -> Json:
    steps = [
        "delivery_arrival",
        "monitor_unloading",
        "check_box_condition",
        "verify_box_count_against_bol",
        "open_glass_boxes",
        "inspect_sheet_metal",
        "document_discrepancies_at_delivery",
        "obtain_driver_signature_on_discrepancies",
        "sign_bol_pod",
        "open_packing_slip_boxes_first",
        "review_bol_and_packing_list",
        "verify_part_numbers_and_quantities",
        "inspect_items_and_packaging",
        "mark_verified_cartons",
        "move_damaged_or_wrong_parts_to_hold",
        "report_issues_to_pdc",
        "receive_and_bin_parts",
        "confirm_in_dms",
    ]
    step_catalog = codes(
        ("delivery_arrival", "delivery truck arrives; receiving begins"),
        ("monitor_unloading", "watch each box as it comes off the truck"),
        ("check_box_condition", "check the condition of each box as it is unloaded"),
        ("verify_box_count_against_bol", "confirm every box/carton on the BOL was delivered"),
        ("open_glass_boxes", "open boxes marked glass before the driver leaves"),
        ("inspect_sheet_metal", "examine sheet metal parts for dents or damage"),
        ("document_discrepancies_at_delivery", "note damage, shortage, or overage on the BOL at delivery"),
        ("obtain_driver_signature_on_discrepancies", "get the driver's initials/signature on noted discrepancies"),
        ("sign_bol_pod", "sign the BOL/POD"),
        ("sign_bol_on_arrival", "sign the BOL as soon as the truck arrives"),
        ("open_packing_slip_boxes_first", "open boxes with packing slips first"),
        ("review_bol_and_packing_list", "review the BOL and packing list"),
        ("verify_part_numbers_and_quantities", "verify part numbers and quantities against the packing list"),
        ("inspect_items_and_packaging", "visually inspect items and packaging for damage"),
        ("mark_verified_cartons", "mark verified cartons/items to prevent double handling"),
        ("move_damaged_or_wrong_parts_to_hold", "move damaged, wrong, or over parts to the hold area"),
        ("report_issues_to_pdc", "report damage/short/over to the parts distribution center"),
        ("receive_and_bin_parts", "receive parts into inventory and bin them"),
        ("receive_missing_items", "receive the full packing list quantity even if items are missing"),
        ("confirm_in_dms", "confirm the completed order in the dealer DMS"),
    )
    truth = {
        "title": "Receiving Parts Order Procedures",
        "stock_orders": {"handling": "Receive, bin, and make ready to sell within about two hours of delivery.", "ready_within_hours": 2},
        "critical_orders": {
            "handling": "Receive immediately; bin or deliver straight to the requester and notify them.",
            "receiving_expectation": "immediate",
            "differences": ["prioritize_receipt", "immediate_binning_or_delivery", "notify_requester", "expedited_shortage_escalation"],
        },
        "steps": steps,
        "checklist": steps,
        "damage": {
            "documentation": ["photos", "note_on_bol", "damage_report"],
            "marking": "bright_colored_tape",
            "hold_area": True,
            "retain_packaging": True,
            "report_to_pdc_with_photos": True,
        },
        "missing_items": {"log_quantities": True, "receive_into_inventory": False},
        "overage_wrong_parts": {"disposition": "segregate_hold_pending_pdc"},
        "pdc_report": {"required_fields": ["order_or_bol_number", "part_numbers", "quantities", "issue_type", "photos"]},
        "keep_annotated_bol_copy": True,
        "second_person_verification": True,
        "receiving_area": True,
    }
    catalog = {
        "steps": step_catalog,
        "critical_orders.differences": codes(
            ("prioritize_receipt", "critical orders are received first"), ("immediate_binning_or_delivery", "bin or deliver to requester immediately"),
            ("notify_requester", "notify the technician/customer who requested the part"), ("expedited_shortage_escalation", "escalate shortages to the PDC immediately"),
            ("same_as_stock", "handled exactly like stock orders"),
        ),
        "damage.documentation": codes(("photos", "photographs of the damage"), ("note_on_bol", "noted on the BOL/POD"), ("damage_report", "internal damage report"), ("verbal_only", "verbal notice to driver")),
        "damage.marking": codes(("bright_colored_tape", "bright tape around damaged areas in photos"), ("none", "no marking")),
        "overage_wrong_parts.disposition": codes(
            ("segregate_hold_pending_pdc", "keep out of saleable stock in a hold area pending PDC instructions"),
            ("receive_into_stock", "receive into saleable stock"), ("return_to_driver", "hand back to the driver"),
        ),
        "pdc_report.required_fields": codes(
            ("order_or_bol_number", "order / BOL number"), ("part_numbers", "part numbers"), ("quantities", "quantities"),
            ("issue_type", "damage, short, or over"), ("photos", "photos attached"), ("driver_name", "driver name"),
        ),
    }
    fields = [
        field("title", "string", "Procedure title."),
        field("stock_orders.handling", "string", "How stock orders are handled."),
        field("stock_orders.ready_within_hours", "number", "Target hours from delivery to ready-to-sell for stock orders."),
        field("critical_orders.handling", "string", "How critical orders are handled."),
        field("critical_orders.receiving_expectation", "string", "Receiving expectation for critical orders (e.g. immediate)."),
        field("critical_orders.differences", "list[code]", "Procedural differences from stock orders."),
        field("steps", "list[code]", "Check-in steps in order, from delivery arrival through DMS confirmation."),
        field("checklist", "list[code]", "Concise receiving checklist (step codes), arrival through DMS confirmation."),
        field("damage.documentation", "list[code]", "How damage is documented."),
        field("damage.marking", "code", "How damage is marked for visibility in photos."),
        field("damage.hold_area", "bool", "Damaged/suspect items kept in a designated hold area."),
        field("damage.retain_packaging", "bool", "Original packaging kept until claims are resolved."),
        field("damage.report_to_pdc_with_photos", "bool", "Damage reported to the PDC with photo evidence."),
        field("missing_items.log_quantities", "bool", "Missing items and quantities logged on the receiving record."),
        field("missing_items.receive_into_inventory", "bool", "Whether items not physically present are received into inventory."),
        field("overage_wrong_parts.disposition", "code", "Disposition of overages or wrong parts."),
        field("pdc_report.required_fields", "list[code]", "Information included when reporting to the PDC."),
        field("keep_annotated_bol_copy", "bool", "Keep a copy of the annotated BOL/POD."),
        field("second_person_verification", "bool", "Second-person check for high-value items or discrepancies."),
        field("receiving_area", "bool", "Maintain a dedicated receiving area."),
    ]

    def has(check_id: str, *codes_needed: str) -> Json:
        return check(check_id, "custom", "steps", None, rule="sequence", includes=list(codes_needed))

    checks = [
        check("title", "member", "title", ["Receiving Parts Order Procedures", "Receiving Parts Order Procedure",
                                            "Parts Order Receiving Procedures", "Receiving Parts Orders Procedures"]),
        check("stock-guidance", "nonempty", "stock_orders.handling"),
        check("critical-guidance", "nonempty", "critical_orders.handling"),
        num("stock-target", "stock_orders.ready_within_hours", 2, 0.5),
        check("critical-target", "text", "critical_orders.receiving_expectation", "immediate"),
        check("critical-difference", "overlaps", "critical_orders.differences", truth["critical_orders"]["differences"]),
        check("steps-sequence", "custom", "steps", None, rule="sequence", first="delivery_arrival", last="confirm_in_dms",
              excludes=["sign_bol_on_arrival", "receive_missing_items"]),
        check("checklist", "custom", "checklist", None, rule="sequence", first="delivery_arrival", last="confirm_in_dms"),
        has("step-bol-review", "review_bol_and_packing_list"),
        has("step-verify-parts", "verify_part_numbers_and_quantities"),
        has("step-inspect", "inspect_items_and_packaging"),
        has("step-document-discrepancies", "document_discrepancies_at_delivery"),
        has("step-driver-signature", "obtain_driver_signature_on_discrepancies"),
        has("step-monitor-unloading", "monitor_unloading"),
        has("step-box-condition", "check_box_condition"),
        has("step-packing-slips-first", "open_packing_slip_boxes_first"),
        has("step-sheet-metal", "inspect_sheet_metal"),
        has("step-mark-verified", "mark_verified_cartons"),
        check("glass-before-driver-leaves", "custom", "steps", None, rule="sequence", before=[["open_glass_boxes", "sign_bol_pod"]]),
        check("sign-after-confirm", "custom", "steps", None, rule="sequence",
              before=[["verify_box_count_against_bol", "sign_bol_pod"], ["check_box_condition", "sign_bol_pod"]]),
        check("damage-documentation", "includes", "damage.documentation", ["photos"]),
        check("damage-marking", "text", "damage.marking", "bright_colored_tape"),
        check("damage-hold", "bool", "damage.hold_area", True),
        check("damage-packaging", "bool", "damage.retain_packaging", True),
        check("damage-pdc-photos", "bool", "damage.report_to_pdc_with_photos", True),
        check("missing-log", "bool", "missing_items.log_quantities", True),
        check("missing-not-received", "bool", "missing_items.receive_into_inventory", False),
        check("overage-hold", "text", "overage_wrong_parts.disposition", "segregate_hold_pending_pdc"),
        check("pdc-fields", "includes", "pdc_report.required_fields", truth["pdc_report"]["required_fields"]),
        check("bol-copy", "bool", "keep_annotated_bol_copy", True),
        check("second-person", "bool", "second_person_verification", True),
        check("receiving-area", "bool", "receiving_area", True),
    ]
    rules = [
        (r"Final deliverable is provided as a PDF", "u:file_format"),
        (r"PDF length", "u:presentation"),
        (r"distinct guidance for the handling of Stock", "c:stock-guidance"),
        (r"distinct guidance for the handling of Critical", "c:critical-guidance"),
        (r"clearly ordered sequence", "c:steps-sequence"),
        (r"start of the process explicitly references delivery", "c:steps-sequence"),
        (r"review the bill of lading", "c:step-bol-review"),
        (r"Part numbers and quantities are verified", "c:step-verify-parts"),
        (r"visually inspected for damage", "c:step-inspect"),
        (r"documented at delivery time", "c:step-document-discrepancies"),
        (r"driver's initials or signature", "c:step-driver-signature"),
        (r"includes guidance on documenting damage", "c:damage-documentation"),
        (r"Missing items and their quantities are listed", "c:missing-log"),
        (r"items not physically present must not be received", "c:missing-not-received"),
        (r"Overages or wrong parts are not received", "c:overage-hold"),
        (r"providing the manufacturer.s parts distribution center \(PDC\) with photo", "c:damage-pdc-photos"),
        (r"When communicating with the PDC", "c:pdc-fields"),
        (r"critical orders section specifies at least one procedural difference", "c:critical-difference"),
        (r"kept in a designated hold area", "c:damage-hold"),
        (r"retaining original packaging", "c:damage-packaging"),
        (r"keeping a copy .* annotated BOL", "c:bol-copy"),
        (r"signing the BOL/POD only after reconciling", "c:sign-after-confirm"),
        (r"receiving checklist", "c:checklist"),
        (r"marking verified cartons", "c:step-mark-verified"),
        (r"second-person verification", "c:second-person"),
        (r"maintaining a receiving area", "c:receiving-area"),
        (r"document title contains", "c:title"),
        (r"monitoring unloading", "c:step-monitor-unloading"),
        (r"checking the condition of each box", "c:step-box-condition"),
        (r"opening boxes with packing slips first", "c:step-packing-slips-first"),
        (r"boxes marked 'glass'", "c:glass-before-driver-leaves"),
        (r"sheet metal parts", "c:step-sheet-metal"),
        (r"bright-colored tape", "c:damage-marking"),
        (r"how to mark damage for visibility", "c:damage-marking"),
        (r"only be signed after confirming that all boxes", "c:sign-after-confirm"),
        (r"confirmed within the dealer's data management system", "c:steps-sequence"),
        (r"within approximately two hours", "c:stock-target"),
        (r"immediate receiving and binning", "c:critical-target"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Standardize dealer parts receiving for stock and critical orders",
        "difficulty": "hard",
        "goal": "As district parts manager, publish a dealer check-in procedure for stock and critical parts orders from truck arrival to DMS confirmation.",
        "request": src.prompt,
        "artifact_type": "gdp_receiving_procedure",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["steps-sequence", "missing-not-received", "overage-hold"],
        "notes": ["Visual guidance (annotated photos) is represented by the damage marking and documentation codes; imagery is not graded."],
    }


# --- task 12: Beutist set selling recap --------------------------------------------------

BEUTIST_METRICS = ["ytd_2023", "ytd_2022", "ytd_pct_change", "expected_sales", "available_inventory", "inventory_minus_expected", "inventory_pct_of_expected"]


def t12_set_selling(src: SourceTask) -> Json:
    path = src.ref("Beutist")

    def padded(sheet: str) -> list[tuple[Any, ...]]:
        return [tuple(row) + (None,) * (12 - len(row)) for row in xlsx_rows(path, sheet)]

    tab1 = padded("TAB 1")
    header = next(i for i, row in enumerate(tab1) if row[0] == "Axe")
    sales: list[list[Any]] = []
    axis = None
    for row in tab1[header + 1:]:
        if row[1] in (None, "") or "Total" in str(row[1]) or "Total" in str(row[0] or ""):
            continue
        axis = row[0] or axis
        values = [row[i] if row[i] not in (None, "") else 0 for i in (2, 3, 5, 6, 7)]
        sales.append([axis, row[1], *values])
    tab2 = padded("Tab 2")
    inventory: list[list[Any]] = []
    axis = None
    for row in tab2[3:]:
        if row[1] in (None, "") or "Total" in str(row[0] or ""):
            continue
        axis = row[0] or axis
        inventory.append([axis, row[1], row[2]])
    tab3 = padded("Tab 3")
    october = [[str(row[0]), row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[9], row[10]]
               for row in tab3 if isinstance(row[0], int)]
    tab4 = padded("Tab 4")
    q1 = [[row[5], row[6]] for row in tab4 if isinstance(row[6], (int, float)) and row[5]]
    brands = {row[1]: row[0] for row in sales}
    require({row[1] for row in inventory} == set(brands), "task 12 inventory brands")
    lookup = {norm: name for name in brands for norm in [name.lower()]}
    ship_oct: dict[str, float] = defaultdict(float)
    for row in october:
        ship_oct[lookup[row[8].lower()]] += row[9]
    ship_q1: dict[str, float] = defaultdict(float)
    for brand, value in q1:
        ship_q1[lookup[brand.lower()]] += value
    oh = {row[1]: row[2] for row in inventory}

    def metrics(names: list[str]) -> Json:
        ytd23 = sum(next(r for r in sales if r[1] == n)[2] for n in names)
        ytd22 = sum(next(r for r in sales if r[1] == n)[3] for n in names)
        expected = sum(sum(next(r for r in sales if r[1] == n)[4:7]) for n in names)
        available = sum(oh[n] + ship_oct[n] + ship_q1[n] for n in names)
        row: Json = {"ytd_2023": r2(ytd23), "ytd_2022": r2(ytd22), "expected_sales": r2(expected),
                     "available_inventory": r2(available), "inventory_minus_expected": r2(available - expected)}
        row["ytd_pct_change"] = r2(100 * (ytd23 - ytd22) / ytd22) if ytd22 > 0 else None
        row["inventory_pct_of_expected"] = r2(100 * available / expected) if expected > 0 else None
        return row

    axes = list(dict.fromkeys(brands.values()))
    brand_rows = {name: {"axis": brands[name], **metrics([name]), "comment": ""} for name in brands}
    axis_rows = {axis_name: {**metrics([n for n in brands if brands[n] == axis_name]), "comment": ""} for axis_name in axes}
    grand = {**metrics(list(brands)), "comment": ""}
    rubric_axes = {
        "SKIN CARE": (8625.8, 6237.6, 38, 8625.8, 768.9, 109), "MAKEUP": (1850.7, 1308.1, 41, 1850.6, -334.0, 82),
        "FRAGRANCE": (258.2, 215.0, 20, 258.1, 1295.8, 602),
    }
    for axis_name, expected_values in rubric_axes.items():
        row = axis_rows[axis_name]
        got = (row["ytd_2023"], row["ytd_2022"], row["ytd_pct_change"], row["expected_sales"], row["inventory_minus_expected"], row["inventory_pct_of_expected"])
        require(all(abs(a - b) <= max(abs(b) * 0.01, 0.6) for a, b in zip(got, expected_values)), f"task 12 axis {axis_name}: {got}")
    require(abs(grand["inventory_minus_expected"] - 1730.7) < 0.2 and abs(grand["expected_sales"] - 10734.5) < 0.2, f"task 12 grand {grand}")
    truth = {"as_of": "2023-09-25", "brands": brand_rows, "axis_totals": axis_rows, "grand_total": grand}
    metric_desc = ("ytd_2023, ytd_2022, ytd_pct_change (0-100; null when prior year <= 0), expected_sales (Q3 2022 + Q4 2022 + Q1 2023 set sales), "
                   "available_inventory (OH+OO + October 2023 + Q1 2024 shipments), inventory_minus_expected, inventory_pct_of_expected "
                   "(0-100; null when expected <= 0), comment (left blank).")
    fields = [
        field("as_of", "date", "Analysis date."),
        field("brands", "object<brand,object>", "Every brand in the sales data, keyed by brand name; each: axis plus " + metric_desc),
        field("axis_totals", "object<axis,object>", "Keyed by axis as named in the data; same measures."),
        field("grand_total", "object", "Same measures across all brands."),
    ]
    checks = [
        check("axes", "keys", "axis_totals", axes),
        check("brands", "keys", "brands", list(brands)),
        check("brand-axis", "custom", "brands", {n: {"axis": a} for n, a in brands.items()}, rule="rows_match", exact_ids=False),
        check("comments-blank", "custom", rule="all_of", checks=[
            check("b", "custom", "brands", {n: {"comment": ""} for n in brands}, rule="rows_match", exact_ids=False),
            check("a", "custom", "axis_totals", {a: {"comment": ""} for a in axes}, rule="rows_match", exact_ids=False),
        ]),
    ]
    tags = {"ytd_2023": "ytd23", "ytd_2022": "ytd22", "ytd_pct_change": "pct", "expected_sales": "expected",
            "inventory_minus_expected": "diff", "inventory_pct_of_expected": "cover", "available_inventory": "available"}
    for metric, tag in tags.items():
        is_pct = metric in ("ytd_pct_change", "inventory_pct_of_expected")
        expected_rows = {n: {metric: row[metric]} for n, row in brand_rows.items() if row[metric] is not None}
        checks.append(check(f"brand-{tag}", "custom", "brands", expected_rows, rule="rows_match", exact_ids=False,
                            tolerance=0.5 if is_pct else 0.15))
        for axis_name, row in [*axis_rows.items(), ("grand", grand)]:
            value = row[metric]
            tolerance = 0.5 if is_pct else max(round(abs(value) * 0.01, 2), 0.15)
            target = ["grand_total", metric] if axis_name == "grand" else ["axis_totals", axis_name, metric]
            checks.append(num(f"{tag}-{slug(axis_name.replace(' ', ''))}", target, value, tolerance))
    axis_alt = r"(Skincare|Makeup|Fragrance)"
    measures = [
        (r"dollar difference between total available inventory", "diff"), (r"total available inventory as a percentage", "cover"),
        (r"YTD 2023 set sales dollars", "ytd23"), (r"YTD 2022 set sales dollars", "ytd22"),
        (r"percent change in YTD set sales dollars", "pct"), (r"total expected sales from now", "expected"),
    ]
    rules: list[tuple[str, str]] = [
        (r"Includes each and every Axis", "c:axes"),
        (r"Includes an Axis that is not present", "c:axes"),
        (r"Includes each and every Brand", "c:brands"),
        (r"Includes a Brand that is not present", "c:brands"),
        (r"associated with its respective Axis", "c:brand-axis"),
        (r"placeholder area for comments is left blank", "c:comments-blank"),
        (r"placeholder area for comments", "c:comments-blank"),
        (r"is represented (in dollars|as a percentage)", "u:presentation"),
    ]
    for text_pattern, tag in measures:
        rules += [
            (rf"{text_pattern}.* for (?:the )?{axis_alt} (?:\(or Skin care\) )?Axis total", f"c:{tag}-{{1}}"),
            (rf"{text_pattern}.* for (?:the )?grand total", f"c:{tag}-grand"),
            (rf"{text_pattern}.*(?:for each Brand|broken out by Axis and Brand by taking)", f"c:brand-{tag}"),
            (rf"Includes Axis totals for (?:the )?{text_pattern}", f"c:{tag}-skincare,{tag}-makeup,{tag}-fragrance"),
            (rf"Includes the grand total .* for (?:the )?{text_pattern}", f"c:{tag}-grand"),
            (rf"{text_pattern}.* broken out by Axis and Brand", f"c:brand-{tag}"),
        ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Assess Beutist set inventory coverage against expected sales",
        "difficulty": "expert",
        "goal": "As national-accounts planning manager, recap Beutist set sales by axis and brand and test whether OH+OO and expected shipments cover expected sales.",
        "request": src.prompt,
        "artifact_type": "gdp_set_coverage_recap",
        "fields": fields,
        "codes": {},
        "tables": [
            table("SALES", "Set sales by axis and brand", "Tab 1: YTD and quarterly set sales ($K) by axis and brand.",
                  ["axis", "brand", "ytd_2023_thru_0922", "ytd_2022_thru_0921", "q1_2023", "q4_2022", "q3_2022"], sales),
            table("OHOO", "On-hand plus on-order by brand", "Tab 2: OH+OO inventory ($K) as of 9/22/23.", ["axis", "brand", "oh_plus_oo"], inventory),
            table("OCTSHIP", "October 2023 expected set shipments", "Tab 3: SKU-level October shipments; brand names as keyed by the account.",
                  ["upc", "material_code", "description", "quota_allocated_qty", "open_order_qty", "delivered_qty", "available_qty",
                   "unlabeled_value", "brand", "shipments_usd_10_23_23"], october),
            table("Q1SHIP", "Q1 2024 set shipments", "Tab 4: Q1 2024 set shipment $ by brand.", ["brand", "q1_2024_shipments"], q1),
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["diff-grand", "cover-makeup", "brand-diff"],
        "notes": [
            "Axis totals and the grand total match the rubric within its stated tolerances.",
            ("Brand-level percent measures are not graded where the denominator is zero or negative (Lash BOOSTER prior year, "
            "Luxe ROUGE expected sales)."),
            "Rubric items with negative scores (extra axis or brand) are bound to the exact axis/brand key checks.",
        ],
    }

# --- task 13: XR retailer makeup recap -------------------------------------------------

XR_FIELDS = ["sales_2023", "sales_2022", "dollar_change", "pct_change", "pct_to_total_2023", "pct_to_total_2022", "disco_2023", "pct_disco"]


def t13_xr_makeup(src: SourceTask) -> Json:
    raw = xlsx_rows(src.deliv("XR Retailer 2023"), "DATA-XR MU 2023")
    columns = ["brand", "sub_brand", "function", "material", "material_status", "sales_2023_k", "sales_2022_k", "pct_chg", "dollar_chg_k"]
    data = [list(row[:9]) for row in raw[1:] if row[0] not in (None, "", "Total") and row[4] != "Material Status"]
    data = [[*row[:4], str(row[4]).zfill(2), *row[5:]] for row in data]
    ty = sum(row[5] for row in data)
    ly = sum(row[6] for row in data)
    require(abs(ty - 20295.49627) < 1e-4 and abs(ly - 20918.40311) < 1e-4, "task 13 totals")
    ongoing = sum(row[5] for row in data if row[4] in ("05", "06"))
    disco = sum(row[5] for row in data if row[4] in ("07", "08"))
    other = ty - ongoing - disco
    functions: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for row in data:
        functions[row[2]][0] += row[5]
        functions[row[2]][1] += row[6]
        if row[4] in ("07", "08"):
            functions[row[2]][2] += row[5]

    def metrics(names: list[str]) -> Json:
        t = sum(functions[n][0] for n in names)
        last = sum(functions[n][1] for n in names)
        d = sum(functions[n][2] for n in names)
        return {
            "sales_2023": r4(t), "sales_2022": r4(last), "dollar_change": r4(t - last),
            "pct_change": r4(100 * (t - last) / last), "pct_to_total_2023": r4(100 * t / ty),
            "pct_to_total_2022": r4(100 * last / ly), "disco_2023": r4(d), "pct_disco": r4(100 * d / t),
        }

    order = {
        "top_volume_drivers": sorted(functions, key=lambda n: -functions[n][0])[:3],
        "largest_increases": sorted(functions, key=lambda n: -(functions[n][0] - functions[n][1]))[:3],
        "largest_detractors": sorted(functions, key=lambda n: functions[n][0] - functions[n][1])[:3],
    }
    require(set(order["top_volume_drivers"]) == {"MASCARAS WASHABLE", "LIQUID FOUNDATIONS", "OTHER EYELINERS"}, "task 13 top")
    require(set(order["largest_increases"]) == {"STICK LIPSTICKS", "CONCEALERS", "LIQUID EYELINERS"}, "task 13 increases")
    require(set(order["largest_detractors"]) == {"MASCARAS WASHABLE", "LIQUID FOUNDATIONS", "LIP LINERS"}, "task 13 detractors")
    sections = {key: {"functions": {n: metrics([n]) for n in names}, "total": metrics(names)} for key, names in order.items()}
    truth = {
        "title": "XR Retailer 2023 Sales Performance Analysis - Makeup Category Final",
        "scope": {"account": "XR Retailer", "category": "Makeup"},
        "currency_unit": "thousands",
        "overall_business": {"sales_2023": r4(ty), "sales_2022": r4(ly), "pct_change": r4(100 * (ty - ly) / ly), "dollar_change": r4(ty - ly)},
        "discontinued_risk": {
            "ongoing_sales_2023": r4(ongoing), "discontinued_sales_2023": r4(disco),
            "other_status_sales_2023": r4(other), "pct_sales_discontinued": r4(100 * disco / ty),
        },
        **sections,
    }
    section_desc = ("object with functions (object keyed by function name, exactly three) and total; each row: " + ", ".join(XR_FIELDS)
                    + " (dollars in thousands, percentages 0-100; pct_to_total uses the overall 2023 / 2022 totals; disco = status 07/08).")
    fields = [
        field("title", "string", "Recap title."),
        field("scope.account", "string", "Account analysed."),
        field("scope.category", "string", "Category analysed."),
        field("currency_unit", "string", "Unit of all dollar figures (as in the data pull)."),
        field("overall_business", "object", "sales_2023, sales_2022, pct_change (0-100), dollar_change."),
        field("discontinued_risk", "object", "ongoing_sales_2023 (status 05/06), discontinued_sales_2023 (07/08), other_status_sales_2023 "
              "(any other status), pct_sales_discontinued (discontinued / overall 2023, 0-100)."),
        field("top_volume_drivers", "object", "Three functions with the highest 2023 sales: " + section_desc),
        field("largest_increases", "object", "Three functions with the largest $ increase vs 2022: " + section_desc),
        field("largest_detractors", "object", "Three functions with the largest $ decrease vs 2022: " + section_desc),
    ]
    tolerances = {"sales_2023": 0.005, "sales_2022": 0.005, "dollar_change": 0.005, "disco_2023": 0.005}
    checks = [
        check("title", "text", "title", truth["title"]),
        check("scope", "custom", rule="all_of", checks=[
            check("a", "text", "scope.account", "XR Retailer"), check("c", "text", "scope.category", "Makeup"),
        ]),
        check("currency-unit", "text", "currency_unit", "thousands"),
        num("overall-ty", "overall_business.sales_2023", ty, 0.005),
        num("overall-ly", "overall_business.sales_2022", ly, 0.005),
        num("overall-pct", "overall_business.pct_change", truth["overall_business"]["pct_change"], 0.02),
        num("overall-change", "overall_business.dollar_change", ty - ly, 0.005),
        num("ongoing", "discontinued_risk.ongoing_sales_2023", ongoing, 0.005),
        num("disco", "discontinued_risk.discontinued_sales_2023", disco, 0.005),
        num("disco-other", "discontinued_risk.other_status_sales_2023", other, 0.005),
        num("disco-pct", "discontinued_risk.pct_sales_discontinued", truth["discontinued_risk"]["pct_sales_discontinued"], 0.02),
        check("sections", "custom", rule="all_of", checks=[
            check(key, "nonempty", key) for key in ("overall_business", "discontinued_risk", *order)
        ]),
    ]
    tags = {"top_volume_drivers": "top", "largest_increases": "inc", "largest_detractors": "det"}
    for key, tag in tags.items():
        section = sections[key]
        checks.append(check(f"{tag}-functions", "keys", [key, "functions"], order[key]))
        checks.append(check(f"{tag}-columns", "custom", [key, "functions"], section["functions"], rule="rows_match", tolerance=0.02))
        for name, row in section["functions"].items():
            checks.append(check(f"{tag}-{slug(name)}", "custom", rule="all_of", checks=[
                num(metric, [key, "functions", name, metric], value, tolerances.get(metric, 0.02)) for metric, value in row.items()
            ]))
        checks.append(check(f"{tag}-total", "custom", rule="all_of", checks=[
            num(metric, [key, "total", metric], value, tolerances.get(metric, 0.02)) for metric, value in section["total"].items()
        ]))
    section_alt = {"Top Volume Drivers": "top", "Largest Volume Increases": "inc", "Largest Volume Detractors": "det"}
    rules: list[tuple[str, str]] = [
        (r"contains a recap sheet", "u:workbook_mechanics"),
        (r"All five sections are present", "c:sections"),
        (r"reports total XR Retailer Makeup sales dollars TY", "c:overall-ty"),
        (r"reports total XR Retailer Makeup sales dollars LY", "c:overall-ly"),
        (r"Overall Business section reports the percent change", "c:overall-pct"),
        (r"Overall Business section reports the dollar change", "c:overall-change"),
        (r"total sales \$\$ of ongoing SKUs", "u:upstream_conflict"),
        (r"total sales \$\$ of discontinued SKUs", "u:upstream_conflict"),
        (r"reports % of Sales \(discos\)", "u:upstream_conflict"),
        (r"ongoing \(05/06\) 2023 sales plus discontinued", "u:upstream_conflict"),
        (r"scoped strictly to Account", "c:scope"),
        (r"handle any zero 2022 values", "u:not_applicable"),
        (r"Currency figures use a consistent", "u:presentation"),
        (r"print layout", "u:presentation"),
        (r"filename, the recap sheet name, or a title cell", "c:title"),
        (r"clearly indicates whether figures are in full dollars or in thousands", "c:currency-unit"),
    ]
    for label, tag in section_alt.items():
        rules += [
            (rf"{label} section contains a table with column covering", f"c:{tag}-columns"),
            (rf"{label} lists exactly the following three functions", f"c:{tag}-functions"),
            (rf"For {label}: row (.+?) reports", f"c:{tag}-{{1}}"),
            (rf"{label} section includes a TOTAL row", f"c:{tag}-total"),
            (rf"{label} TOTAL row numeric fields", f"c:{tag}-total"),
        ]
    return {
        "family": "distributor_sales_analytics",
        "title": "Recap XR retailer 2023 makeup sales, discontinued risk, and function drivers",
        "difficulty": "expert",
        "goal": "As national account director, recap XR retailer 2023 makeup sales, discontinued-SKU exposure, and the top, rising, and declining functions.",
        "request": src.prompt,
        "artifact_type": "gdp_category_recap",
        "fields": fields,
        "codes": {},
        "tables": [table("XRMU", "XR retailer makeup data pull FY2023", "SKU-level makeup sales for XR retailer, dollars in thousands; "
                         "material_status 05/06 ongoing, 07/08 discontinued.", columns, data)],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["overall-ty", "disco", "top-total"],
        "notes": [
            ("The rubric's totals (TY 20,295.496k) come from the corrected data pull inside the expert workbook; the attached "
            "reference pull totals 20,427.756k. The corrected pull is served as the table."),
            ("In that pull, status 05/06 sum to 16,678.595k and 07/08 to 3,572.501k, plus one status-09 SKU (44.4k). The rubric's "
            "16,742.996k / 3,552.5k / 17.50% cannot be reproduced from the rows; those items are unscored (upstream_conflict) and "
            "the data-derived values are scored. Function-level DISCO values match the rubric."),
        ],
    }


# --- task 14: July stockout prevention -----------------------------------------------------


def t14_stockout_plan(src: SourceTask) -> Json:
    path = src.ref("Inventory_and_Shipments")
    current = xlsx_rows(path, "Current Inventory")
    require(current[0][:4] == ("Today's Date", "2025-07-04", "Month End", "2025-07-31"), "task 14 header")
    stock = [[row[0], row[1], row[2]] for row in current if str(row[0]).startswith("PRD-")]
    inbound = [[row[0], row[1], row[2], row[3]] for row in xlsx_rows(path, "Incoming Shipments") if str(row[0]).startswith("PRD-")]
    ratio = xlsx_rows(path, "Ratio")
    cases_per_pallet = ratio[1][0]
    require(cases_per_pallet == 80, "task 14 ratio")
    as_of = dt.date(2025, 7, 4)
    month_end = dt.date(2025, 7, 31)
    remaining = (month_end - as_of).days
    skus: Json = {}
    additional: Json = {}
    for sku, cases, rate in stock:
        rows = [row for row in inbound if row[0] == sku and row[1] <= month_end.isoformat()]
        inbound_cases = sum(row[2] * cases_per_pallet for row in rows)
        doh = cases / rate
        oos = as_of + dt.timedelta(days=int(doh))
        delivered = (cases + inbound_cases) / rate
        demand = rate * remaining
        gap = demand - cases - inbound_cases
        needed = max(0.0, gap)
        pallets = -(-needed // cases_per_pallet) if needed else 0
        earliest = min(row[1] for row in rows) if rows else None
        late = earliest is None or earliest > oos.isoformat()
        required = oos if late else as_of + dt.timedelta(days=int(delivered))
        skus[sku] = {
            "current_cases": cases, "daily_rate": rate, "current_doh": r4(doh), "oos_date": oos.isoformat(),
            "inbound_cases_by_jul31": inbound_cases, "delivered_doh": r4(delivered), "july_demand_cases": r2(demand),
            "gap_cases": r2(gap), "additional_cases_needed": r2(needed), "pallets_required": int(pallets),
            "rounded_up": bool(needed) and needed % cases_per_pallet != 0, "required_delivery_date": required.isoformat(),
            "earlier_delivery_needed": bool(pallets) and late,
        }
        if pallets:
            additional[sku] = {"pallets": int(pallets), "cases": int(pallets * cases_per_pallet), "delivery_date": required.isoformat()}
    expected = {
        "PRD-001": (2.8, "2025-07-06", 15, "2025-07-10"), "PRD-004": (0.4, "2025-07-04", 20, "2025-07-04"),
        "PRD-007": (0.1, "2025-07-04", 6, "2025-07-23"), "PRD-010": (2.6, "2025-07-06", 21, "2025-07-07"),
    }
    for sku, (doh, oos, pallets, date) in expected.items():
        row = skus[sku]
        require(abs(row["current_doh"] - doh) <= 0.05 and row["oos_date"] == oos and row["pallets_required"] == pallets
                and row["required_delivery_date"] == date, f"task 14 {sku}: {row}")
    flagged = sorted(sku for sku, row in skus.items() if row["earlier_delivery_needed"])
    require(flagged == ["PRD-004", "PRD-006"], f"task 14 flags {flagged}")
    truth = {
        "as_of_date": as_of.isoformat(),
        "horizon_end": month_end.isoformat(),
        "remaining_july_days": remaining,
        "cases_per_pallet": cases_per_pallet,
        "skus": skus,
        "inbound_schedule": [{"sku": r[0], "delivery_date": r[1], "pallets": r[2], "cases": r[2] * cases_per_pallet} for r in inbound],
        "additional_shipments": additional,
    }
    fields = [
        field("as_of_date", "date", "Date anchoring all calculations."),
        field("horizon_end", "date", "Planning horizon end."),
        field("remaining_july_days", "number", "Days of demand remaining in July, computed as horizon_end minus as_of_date."),
        field("cases_per_pallet", "number", "Pallet-to-case conversion."),
        field("skus", "object<sku,object>", "Every SKU: current_cases, daily_rate, current_doh (cases / rate), oos_date (as_of + whole days "
              "of current DOH), inbound_cases_by_jul31, delivered_doh ((current + inbound by Jul 31) / rate), july_demand_cases "
              "(rate x remaining days), gap_cases (demand - current - inbound), additional_cases_needed (max(0, gap)), "
              "pallets_required (ceiling of needed / cases_per_pallet), rounded_up (bool), required_delivery_date (oos_date when "
              "the earliest scheduled inbound arrives after oos_date; otherwise as_of + whole days of delivered_doh), "
              "earlier_delivery_needed (bool: pallets required and earliest inbound later than oos_date)."),
        field("inbound_schedule", "list[object]", "Each scheduled delivery: sku, delivery_date, pallets, cases."),
        field("additional_shipments", "object<sku,object>", "Only SKUs needing pallets: pallets, cases (pallets x cases_per_pallet), delivery_date."),
    ]
    per_field = {
        "current_doh": ("doh", 0.05), "oos_date": ("oos", None), "delivered_doh": ("delivered", 0.05),
        "additional_cases_needed": ("needed", 1.0), "gap_cases": ("gap", 1.0), "pallets_required": ("pallets", 0),
        "required_delivery_date": ("date", None), "rounded_up": ("rounded", None), "earlier_delivery_needed": ("earlier", None),
        "july_demand_cases": ("demand", 1.0), "inbound_cases_by_jul31": ("inbound", 0),
    }
    checks = [
        check("as-of", "text", "as_of_date", "2025-07-04"),
        check("horizon", "text", "horizon_end", "2025-07-31"),
        num("remaining-days", "remaining_july_days", remaining, 0),
        check("skus", "keys", "skus", list(skus)),
        check("inputs", "custom", "skus", {s: {"current_cases": r["current_cases"], "daily_rate": r["daily_rate"]} for s, r in skus.items()},
              rule="rows_match", exact_ids=False, tolerance=0.01),
        check("inbound-schedule", "custom", "inbound_schedule", None, rule="records", min_count=len(inbound),
              nonempty=["sku", "delivery_date", "pallets", "cases"]),
        check("additional", "custom", "additional_shipments", additional, rule="rows_match", tolerance=0),
    ]
    for key, (tag, tolerance) in per_field.items():
        checks.append(check(f"{tag}-all", "custom", "skus", {s: {key: r[key]} for s, r in skus.items()}, rule="rows_match",
                            exact_ids=False, tolerance=tolerance or 0))
    for sku in expected:
        row = skus[sku]
        checks += [
            num(f"doh-{slug(sku)}", ["skus", sku, "current_doh"], row["current_doh"], 0.05),
            check(f"oos-{slug(sku)}", "text", ["skus", sku, "oos_date"], row["oos_date"]),
            num(f"pallets-{slug(sku)}", ["skus", sku, "pallets_required"], row["pallets_required"], 0),
            check(f"date-{slug(sku)}", "text", ["skus", sku, "required_delivery_date"], row["required_delivery_date"]),
        ]
    for sku in flagged:
        checks.append(check(f"earlier-{slug(sku)}", "bool", ["skus", sku, "earlier_delivery_needed"], True))
    rules = [
        (r"clearly labeled date field", "c:as-of"),
        (r"planning horizon is July 31", "c:horizon"),
        (r"reports current days of inventory on hand", "c:doh-all"),
        (r"projected out.of.stock date that accounts for scheduled inbound", "u:upstream_conflict"),
        (r"reports delivered days of inventory factoring", "c:delivered-all"),
        (r"lists additional shipments needed by SKU and includes", "c:additional"),
        (r"Each SKU appears at most once", "c:additional"),
        (r"calculated per SKU as Current_Cases .* divided by Daily_Rate", "c:doh-all"),
        (r"left blank or N/A when Daily_Rate", "u:not_applicable"),
        (r"If rate of sale is not already per day", "u:not_applicable"),
        (r"Inbound shipments dated on or before July 31", "c:inbound-all,delivered-all"),
        (r"Inbound shipments dated after July 31 are excluded", "u:not_applicable"),
        (r"provides pallets instead of cases", "c:inbound-all"),
        (r"Demand for the remainder of July", "c:demand-all,remaining-days"),
        (r"Additional cases needed per SKU equals", "c:needed-all"),
        (r"Pallets required per SKU equals the ceiling", "c:pallets-all"),
        (r"Rows where rounding up occurred", "c:rounded-all"),
        (r"Rows that require delivery earlier than the current schedule", "c:earlier-all"),
        (r"on or before the projected out.of.stock date computed without", "u:upstream_conflict"),
        (r"on or before July 31 of AsOfDate", "c:date-all"),
        (r"For any SKU with Daily_Rate .* = 0", "u:not_applicable"),
        (r"Immediate.stockout handling", "u:not_applicable"),
        (r"Every SKU in the results and additional.shipments tables matches", "c:skus,additional"),
        (r"Delivered days of inventory to July per SKU equals", "c:delivered-all"),
        (r"Delivered days of inventory to July per SKU is blank", "u:not_applicable"),
        (r"visible field for the current date", "c:as-of"),
        (r"number of days remaining in July", "c:remaining-days"),
        (r"includes the input columns Current_Cases", "c:inputs"),
        (r"Inbound schedule details are shown per delivery", "c:inbound-schedule"),
        (r"lists only SKUs with Pallets_Required", "c:additional"),
        (r"lists any additional delivery dates added", "c:additional"),
        (r"Dates in the workbook are stored", "u:workbook_mechanics"),
        (r"number of cases implied by the rounded.up pallets", "c:additional"),
        (r"gap between projected July demand and total supply", "c:gap-all"),
        (r"total days of inventory combining current and inbound", "c:delivered-all"),
        (r"For SKU (PRD-\d+), the current days of inventory", "c:doh-{1}"),
        (r"For SKU (PRD-\d+), the projected out.of.stock date", "c:oos-{1}"),
        (r"For SKU (PRD-\d+), the additional shipment quantity", "c:pallets-{1}"),
        (r"For SKU (PRD-\d+), the required delivery date", "c:date-{1}"),
        (r"SKU (PRD-\d+) is clearly indicated", "c:earlier-{1}"),
    ]
    return {
        "family": "distributor_inventory_planning",
        "title": "Plan additional July shipments to prevent distributor stockouts",
        "difficulty": "expert",
        "goal": "As beverage sales representative, compute days on hand, stockout dates, and the additional pallets and delivery dates the distributor needs through July 31.",
        "request": src.prompt,
        "artifact_type": "gdp_stockout_plan",
        "fields": fields,
        "codes": {},
        "tables": [
            table("STOCK", "Current distributor inventory", "Current inventory and daily rate of sale by SKU. As of 2025-07-04; month end 2025-07-31.",
                  ["sku", "in_stock_cases", "rate_of_sale_cases_per_day"], stock),
            table("INBOUND", "Incoming shipments", "Scheduled deliveries by SKU.", ["sku", "delivery_date", "pallets", "cases_left"], inbound),
            table("RATIO", "Pallet conversion", "Cases per pallet.", ["cases", "pallets"], [[ratio[1][0], ratio[1][1]]]),
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["pallets-all", "date-all", "earlier-all"],
        "notes": [
            ("Conventions follow the expert workbook and rubric values: remaining days = 31 - 4 = 27; OOS date = as-of plus whole "
            "days of current DOH; required date = OOS date when the first inbound lands after it, else as-of plus whole days of "
            "delivered DOH."),
            ("The rubric item requiring the required date on/before the no-shipment OOS date contradicts its own per-SKU values "
            "(PRD-001 7/10 vs OOS 7/6) and is unscored; so is the item asking OOS to account for inbound shipments."),
            "No SKU has a zero rate, zero stock, non-daily rate, or inbound after July 31; those rubric items are not applicable.",
        ],
    }

# --- task 15: men's fragrance MSRP model -------------------------------------------------

FRAGRANCE_BUCKETS = [("travel", 0.30, 1.4), ("small", 1.5, 2.9), ("large", 3.0, 4.2), ("jumbo", 4.3, 6.8)]


def _bucket(size: float) -> str:
    for name, low, high in FRAGRANCE_BUCKETS:
        if low <= size <= high:
            return name
    raise ValueError(f"size {size} outside buckets")


def t15_fragrance_pricing(src: SourceTask) -> Json:
    price_rows = xlsx_rows(src.ref("Current Product Price List"))
    header = next(i for i, row in enumerate(price_rows) if row[2] == "Fragrance Name")
    skus = [row[1:6] for row in price_rows[header + 1:] if row[2]]
    competitor_raw = xlsx_rows(src.deliv("Competitive Pricing Strategy"), "Men's Competitor Set")
    start = next(i for i, row in enumerate(competitor_raw) if "Brand" in row)
    col = competitor_raw[start].index("Brand")
    bucket_names = {"Travel": "travel", "Small": "small", "Large": "large", "Jumbo": "jumbo"}
    competitors = [
        [row[col], row[col + 1], row[col + 2], row[col + 3], bucket_names[row[col + 4]], row[col + 5]]
        for row in competitor_raw[start + 1:]
        if len(row) > col + 5 and row[col] and row[col + 5]
    ]
    averages: Json = {}
    for bucket, _, _ in FRAGRANCE_BUCKETS:
        rows = [row for row in competitors if row[4] == bucket]
        averages[bucket] = {"all": r4(sum(row[5] / row[3] for row in rows) / len(rows))}
        for conc in ("EDT", "EDP", "Elixir"):
            subset = [row for row in rows if row[2] == conc]
            if subset:
                averages[bucket][conc] = r4(sum(row[5] / row[3] for row in subset) / len(subset))
    expected_averages = {("travel", "EDT"): 97.8186, ("small", "EDP"): 67.8149, ("large", "Elixir"): 52.2192, ("jumbo", "Elixir"): 42.5376}
    for (bucket, conc), value in expected_averages.items():
        require(abs(averages[bucket][conc] - value) < 0.001, f"task 15 average {bucket} {conc}: {averages[bucket][conc]}")
    sku_truth: Json = {}
    for _, name, size, cogs, msrp in skus:
        conc = next(c for c in ("EDT", "EDP", "Elixir") if c in name)
        bucket = _bucket(size)
        avg = averages[bucket][conc]
        new = float(round(avg * size * 0.98))
        sku_truth[name] = {
            "concentration": conc, "size_oz": size, "size_bucket": bucket, "current_msrp": msrp, "cogs": cogs,
            "recommended_msrp": new, "new_price_per_oz": r4(new / size), "pct_msrp_increase": r4(100 * (new - msrp) / msrp),
            "cogs_pct_of_new_msrp": r4(100 * cogs / new), "competitor_avg_per_oz": avg,
            "new_vs_competitor_pct": r4(100 * (new / size - avg) / avg),
        }
    require(len(sku_truth) == 10, "task 15 sku count")
    truth = {
        "skus": sku_truth,
        "competitors": [
            {"brand": r[0], "product": r[1], "concentration": r[2], "size_oz": r[3], "size_bucket": r[4], "msrp": r[5],
             "price_per_oz": r4(r[5] / r[3])}
            for r in competitors
        ],
        "competitor_averages": averages,
        "rationale": {
            "cogs": "New MSRPs keep COGS at roughly 11-17% of MSRP across sizes.",
            "concentrations": "EDP carries a premium over EDT and Elixir over EDP, mirroring COGS and the competitive set.",
            "competitors": "Each new MSRP per ounce sits within 6% of the competitor average for its size and concentration.",
        },
    }
    bucket_catalog = codes(*[(name, f"{low}-{high} oz") for name, low, high in FRAGRANCE_BUCKETS])
    catalog = {"size_bucket": bucket_catalog, "concentration": codes(("EDT", "Eau de Toilette"), ("EDP", "Eau de Parfum"), ("Elixir", "Elixir"))}
    fields = [
        field("skus", "object<sku,object>", "Every SKU from the price list keyed by its fragrance name: concentration, size_oz, size_bucket, "
              "current_msrp, cogs, recommended_msrp, new_price_per_oz, pct_msrp_increase (0-100), cogs_pct_of_new_msrp (0-100), "
              "competitor_avg_per_oz (same bucket and concentration), new_vs_competitor_pct (0-100 scale, new per-oz vs competitor avg)."),
        field("competitors", "list[object]", "Competitor rows used: brand, product, concentration, size_oz, size_bucket, msrp, price_per_oz."),
        field("competitor_averages", "object<bucket,object>", "Per size bucket: average price per ounce for each concentration present "
              "(keys EDT, EDP, Elixir) and 'all' for the whole bucket."),
        field("rationale.cogs", "string", "How recommended MSRPs relate to COGS."),
        field("rationale.concentrations", "string", "Price relationship across EDT, EDP, and Elixir."),
        field("rationale.competitors", "string", "How new MSRPs compare to competitor averages."),
    ]
    band = {name: {"ounces": row["size_oz"], "benchmark": row["competitor_avg_per_oz"]} for name, row in sku_truth.items()}
    floors = {name: {"floor": row["cogs"]} for name, row in sku_truth.items()}

    def sku_field(check_id: str, key: str, tolerance: float = 0) -> Json:
        return check(check_id, "custom", "skus", {n: {key: r[key]} for n, r in sku_truth.items()}, rule="rows_match",
                     exact_ids=False, tolerance=tolerance)

    checks = [
        check("skus", "keys", "skus", list(sku_truth)),
        sku_field("sku-msrp", "current_msrp"),
        sku_field("sku-cogs", "cogs"),
        sku_field("sku-size", "size_oz"),
        sku_field("sku-concentration", "concentration"),
        sku_field("sku-bucket", "size_bucket"),
        sku_field("sku-competitor-avg", "competitor_avg_per_oz", 0.05),
        check("recommended", "custom", "skus", None, rule="records", min_count=10, nonempty=["recommended_msrp"]),
        check("price-band", "custom", rule="price_band", path=["skus"], skus=band, band=0.06, price_field="recommended_msrp"),
        check("above-cogs", "custom", rule="price_band", path=["skus"], skus=floors, band=0.06, price_field="recommended_msrp"),
        check("new-ppo", "custom", "skus", None, rule="record_formula", target="new_price_per_oz", formula="ratio",
              a="recommended_msrp", b="size_oz", tolerance=0.01),
        check("pct-increase", "custom", "skus", None, rule="record_formula", target="pct_msrp_increase", formula="pct_change",
              a="recommended_msrp", b="current_msrp", tolerance=0.05),
        check("cogs-pct", "custom", "skus", None, rule="record_formula", target="cogs_pct_of_new_msrp", formula="pct_of",
              a="cogs", b="recommended_msrp", tolerance=0.05),
        check("vs-competitor", "custom", "skus", None, rule="record_formula", target="new_vs_competitor_pct", formula="pct_change",
              a="new_price_per_oz", b="competitor_avg_per_oz", tolerance=0.1),
        check("competitor-rows", "custom", "competitors", None, rule="records", min_count=len(competitors),
              nonempty=["product", "concentration", "size_oz", "msrp", "price_per_oz"]),
        check("competitor-ppo", "custom", "competitors", None, rule="record_formula", target="price_per_oz", formula="ratio",
              a="msrp", b="size_oz", tolerance=0.01),
        check("buckets", "keys", "competitor_averages", [name for name, _, _ in FRAGRANCE_BUCKETS]),
        check("rationale-cogs", "nonempty", "rationale.cogs"),
        check("rationale-concentrations", "nonempty", "rationale.concentrations"),
        check("rationale-competitors", "nonempty", "rationale.competitors"),
    ]
    for bucket, row in averages.items():
        for conc, value in row.items():
            checks.append(num(f"avg-{bucket}-{slug(conc)}", ["competitor_averages", bucket, conc], value, 0.05))
    ranges = {"0.3-1.4": "travel", "1.5-2.9": "small", "3.0-4.2": "large", "4.3-6.8": "jumbo"}
    rules: list[tuple[str, str]] = [
        (r"appears exactly once in the model", "c:skus"),
        (r"Current MSRP in the model matches", "c:sku-msrp"),
        (r"the COGS in the model matches", "c:sku-cogs"),
        (r"Bottle size \(oz\) recorded", "c:sku-size"),
        (r"Concentration recorded in the model", "c:sku-concentration"),
        (r"dedicated competitor dataset", "c:competitor-rows"),
        (r"assigned to exactly one of the defined size buckets", "c:sku-bucket"),
        (r"Source URL and a Source domain", "u:not_applicable"),
        (r"competitor dataset includes the (product name|bottle size|Concentration|MSRP)", "c:competitor-rows"),
        (r"formula.driven MSRP.per.ounce", "c:competitor-ppo"),
        (r"(0\.3-1\.4|1\.5-2\.9) oz.* size for Elixir Concentration", "u:not_applicable"),
        (r"Includes a recommended MSRP for every SKU", "c:recommended"),
        (r"within 6% of the competitor average", "c:price-band"),
        (r"strictly greater than COGS", "c:above-cogs"),
        (r"new price per ounce field", "c:new-ppo"),
        (r"% MSRP Increase field", "c:pct-increase"),
        (r"COGS % MSRP field", "c:cogs-pct"),
        (r"New Price vs Competitor field", "c:vs-competitor,sku-competitor-avg"),
        (r"rationale explaining how the Recommended MSRPs relate to COGS", "c:rationale-cogs"),
        (r"rationale describing pricing relationships across concentrations", "c:rationale-concentrations"),
        (r"rationale about the relationship between the Recommended new MSRP", "c:rationale-competitors"),
        (r"labeled and formatted in USD", "u:presentation"),
    ]
    for text_range, bucket in ranges.items():
        escaped = re.escape(text_range)
        rules += [
            (rf"Includes the size range {escaped}", "c:buckets"),
            (rf"average cost-per-ounce for {escaped} oz.* size for (EDT|EDP|Elixir) Concentration", f"c:avg-{bucket}-{{1}}"),
            (rf"average cost-per-ounce for {escaped} oz.* size as a whole", f"c:avg-{bucket}-all"),
        ]
    return {
        "family": "distributor_pricing_quotation",
        "title": "Reprice the men's fragrance line against the competitive set",
        "difficulty": "expert",
        "goal": "As director of sales, benchmark men's fragrance MSRPs per ounce against the frozen competitive set and recommend new MSRPs.",
        "request": src.prompt.replace(
            "Conduct online research to collect current competitor U.S. MSRPs.",
            "Competitor U.S. MSRPs were researched in September 2025 and are provided in the competitor table (do not browse).",
        ),
        "artifact_type": "gdp_msrp_model",
        "fields": fields,
        "codes": catalog,
        "tables": [
            table("SKUS", "Current product price list", "Current men's fragrance SKUs with size (oz), COGS, and MSRP.",
                  ["gender", "fragrance_name", "size_oz", "cogs", "msrp"], [list(row) for row in skus]),
            table("COMPSET", "Men's fragrance competitive set (September 2025)", "Competitor regular MSRPs from brand sites, Sephora, "
                  "Ulta, and Macy's, filtered to EDP/EDT/Elixir and the four size buckets; size_bucket as assigned by the research.",
                  ["brand", "product", "concentration", "size_oz", "size_bucket", "msrp"], competitors),
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["price-band", "above-cogs", "skus"],
        "research_frozen": f"{len(competitors)}-row men's competitor set (brand, product, concentration, size, bucket, MSRP) from the expert deliverable's "
                           "'Men's Competitor Set' sheet; source URLs were not recorded upstream.",
        "notes": [
            "Current MSRP and COGS come from the reference price list (the expert workbook altered several values; the rubric requires the reference).",
            ("Recommended prices are open: the band check requires each new price per ounce within +/-6% of the competitor average "
            "for the same bucket and concentration, computed from the frozen set."),
            ("No Elixir competitor exists in the travel or small buckets, so those rubric items are not applicable; the source URL "
            "item is not applicable because the frozen research carries no URLs."),
        ],
    }


# --- task 16: marketplace pro forma ---------------------------------------------------------


def t16_marketplace_pro_forma(src: SourceTask) -> Json:
    email = docx_paragraphs(src.ref("Pricing email"))
    require(any("15% discount" in line for line in email), "task 16 email changed")
    sheet = xlsx_rows(src.deliv("Pro Forma"), "Sheet1")
    priced = [row for row in sheet if isinstance(row[1], int) and isinstance(row[2], (int, float))]
    require(len(priced) == 8, "task 16 deliverable rows")
    names = [("duct", "device"), ("duct", "consumables"), ("ceiling", "device"), ("ceiling", "consumables")]
    tier1 = {key: (row[2], row[3]) for key, row in zip(names, priced[:4])}
    discount = 0.15
    lines: Json = {}
    for tier in (1, 2):
        for product, kind in names:
            retail, cost = tier1[(product, kind)]
            cost = cost if tier == 1 else r2(cost * (1 - discount))
            quantity = 1000
            margin = r2(retail - cost)
            lines[f"{product}_{kind}_tier{tier}"] = {
                "product": f"BrightzoneUV {product.title()}", "line_type": "device" if kind == "device" else "consumable",
                "tier": tier, "quantity": quantity, "retail_price": retail, "cost": cost, "unit_margin": margin,
                "markup_pct": round(100 * margin / cost, 1), "gross_margin": r2(margin * quantity), "revenue": r2(retail * quantity),
            }
    tier_totals = {f"tier{t}": r2(sum(v["gross_margin"] for v in lines.values() if v["tier"] == t)) for t in (1, 2)}
    require(tier_totals == {"tier1": 765000, "tier2": 1124250}, f"task 16 tier totals {tier_totals}")
    require(lines["duct_device_tier2"]["cost"] == 586.5 and lines["ceiling_device_tier2"]["cost"] == 1016.6, "task 16 tier 2 cost")
    truth = {
        "lines": lines,
        "tier_rules": {"tier1_max_units": 999, "tier2_min_units": 1000, "tier2_cost_discount_pct": 15},
        "year1_quantity": {"duct_device": 2000, "ceiling_device": 2000, "duct_consumables": 2000, "ceiling_consumables": 2000},
        "totals": {**{f"{key}_gross_margin": value for key, value in tier_totals.items()},
                   "year1_gross_margin": r2(sum(tier_totals.values())),
                   "year1_revenue": r2(sum(v["revenue"] for v in lines.values()))},
        "assumptions": ["Prices and tier-1 costs from the September 15, 2025 pricing email; tier 2 cost = tier 1 cost less 15%.",
                        "Year-1 volume of 2,000 per product split 1,000 at tier 1 and 1,000 at tier 2; one consumable set per installed unit."],
    }
    price_rows = [[product, kind, tier1[(product, kind)][0], tier1[(product, kind)][1]] for product, kind in names]
    fields = [
        field("lines", "object<line_id,object>", "Exactly eight lines with ids <duct|ceiling>_<device|consumables>_tier<1|2>; each: product, "
              "line_type (device/consumable), tier, quantity, retail_price, cost, unit_margin, markup_pct (unit_margin / cost x 100, one "
              "decimal), gross_margin (unit_margin x quantity), revenue (retail_price x quantity)."),
        field("tier_rules.tier1_max_units", "number", "Highest unit count priced at tier 1."),
        field("tier_rules.tier2_min_units", "number", "Unit count from which tier 2 applies."),
        field("tier_rules.tier2_cost_discount_pct", "number", "Tier 2 cost discount (0-100)."),
        field("year1_quantity", "object", "Year-1 units for duct_device, ceiling_device, duct_consumables, ceiling_consumables."),
        field("totals", "object", "tier1_gross_margin, tier2_gross_margin, year1_gross_margin, year1_revenue."),
        field("assumptions", "list[string]", "Sources and calculation assumptions."),
    ]
    metric_slugs = {"retail_price": "marketplace-retail-price", "cost": "glongrorealestate-cost", "unit_margin": "unit-margin", "markup_pct": "margin"}
    checks = [
        check("line-ids", "keys", "lines", list(lines)),
        check("line-fields", "custom", "lines", None, rule="records", min_count=8,
              nonempty=["product", "quantity", "retail_price", "cost", "unit_margin", "markup_pct", "gross_margin"]),
        check("line-types", "custom", "lines", {k: {"line_type": v["line_type"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False),
        check("tiers", "custom", "lines", {k: {"tier": v["tier"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False, tolerance=0),
        check("tier1-lines", "custom", "lines", {k: {"retail_price": v["retail_price"], "cost": v["cost"]} for k, v in lines.items() if v["tier"] == 1},
              rule="rows_match", exact_ids=False),
        check("tier-rules", "custom", rule="all_of", checks=[
            num("a", "tier_rules.tier1_max_units", 999, 0), num("b", "tier_rules.tier2_min_units", 1000, 0),
            num("c", "tier_rules.tier2_cost_discount_pct", 15, 0),
        ]),
        check("hardware-qty", "custom", rule="all_of", checks=[
            num("d", "year1_quantity.duct_device", 2000, 0), num("c", "year1_quantity.ceiling_device", 2000, 0),
        ]),
        check("consumable-qty", "custom", rule="all_of", checks=[
            num("d", "year1_quantity.duct_consumables", 2000, 0), num("c", "year1_quantity.ceiling_consumables", 2000, 0),
        ]),
        check("quantities", "custom", "lines", {k: {"quantity": v["quantity"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False, tolerance=0),
        check("unit-margin-calc", "custom", "lines", None, rule="record_formula", target="unit_margin", formula="difference", a="retail_price", b="cost"),
        check("markup-calc", "custom", "lines", None, rule="record_formula", target="markup_pct", formula="pct_of", a="unit_margin", b="cost", tolerance=0.06),
        check("gm-calc", "custom", "lines", None, rule="record_formula", target="gross_margin", formula="product", a="unit_margin", b="quantity", tolerance=0.5),
        check("revenue", "custom", rule="all_of", checks=[
            check("r", "custom", "lines", None, rule="record_formula", target="revenue", formula="product", a="retail_price", b="quantity", tolerance=0.5),
            num("t", "totals.year1_revenue", truth["totals"]["year1_revenue"], 0.5),
        ]),
        num("total-gm", "totals.year1_gross_margin", truth["totals"]["year1_gross_margin"], 0.5),
        check("tier-totals", "custom", rule="all_of", checks=[
            num("1", "totals.tier1_gross_margin", tier_totals["tier1"], 0.5), num("2", "totals.tier2_gross_margin", tier_totals["tier2"], 0.5),
        ]),
        check("products", "custom", "lines", None, rule="records", nonempty=["product"], min_distinct={"product": 2}),
        check("assumptions", "nonempty", "assumptions"),
    ]
    for line_id, row in lines.items():
        for key, metric in metric_slugs.items():
            tolerance = 0.1 if key == "markup_pct" else 0.005
            checks.append(num(f"{line_id.replace('_tier', '-t').replace('_', '-')}-{metric}", ["lines", line_id, key], row[key], tolerance))
    rules = [
        (r"Year 1 entries for an HVAC duct", "c:line-ids,products"),
        (r"Year 1 entries for a ceiling", "c:line-ids,products"),
        (r"consumables as separate line items", "c:line-types"),
        (r"for every line item, fields functionally equivalent", "c:line-fields"),
        (r"hardware quantity is 2,000 units for the HVAC", "c:hardware-qty,quantities"),
        (r"hardware quantity is 2,000 units for the ceiling", "c:hardware-qty,quantities"),
        (r"presents pricing for orders of less than 1,000", "c:tier1-lines"),
        (r"Tier 1 for quantities less than 1,000", "c:tier-rules,tiers"),
        (r"Tier 2 for quantities of 1,000 units or more", "c:tier-rules,tiers"),
        (r"Unit Margin \(\$\) is calculated", "c:unit-margin-calc"),
        (r"Markup \(%\) is calculated", "c:markup-calc"),
        (r"Total Gross Margin \(\$\) for each line equals", "c:gm-calc"),
        (r"sum of all line.item Total Gross Margin", "c:total-gm,tier-totals"),
        (r"For Tier (\d) .*BritezoneUV (Duct|Ceiling) (device|consumables) (Marketplace retail price|GloNGroRealEstate cost|Unit Margin|Margin \(%\))",
         "c:{2}-{3}-t{1}-{4}"),
        (r"two products are named", "c:products"),
        (r"visibly distinguishes Tier 1 and Tier 2", "c:tiers"),
        (r"Tier labels use a clear convention", "c:tiers"),
        (r"Currency figures use a currency symbol", "u:presentation"),
        (r"percent metric \(margin/markup\) is formatted", "u:presentation"),
        (r"assumptions/notes section", "c:assumptions"),
        (r"Hardware and consumables are visually grouped", "c:line-types"),
        (r"Consumables quantities reflect one year", "c:consumable-qty"),
        (r"total revenue by line item", "c:revenue"),
    ]
    return {
        "family": "distributor_pricing_quotation",
        "title": "Project year-one marketplace revenue and margin with tiered cost",
        "difficulty": "expert",
        "goal": "As enterprise sales director, project year-one marketplace margin for the duct and ceiling UV devices and consumables under tiered cost.",
        "request": src.prompt,
        "artifact_type": "gdp_pro_forma",
        "fields": fields,
        "codes": {},
        "tables": [table("PRICES", "Proposed marketplace pricing (from the pricing email)", "Tier-1 marketplace retail price and "
                         "GloNGroRealEstate cost per unit; tier 2 receives the discount stated in the email.",
                         ["product", "item", "marketplace_retail_price", "glongro_cost_tier1"], price_rows)],
        "documents": [document("EMAIL", "Pricing email to GloNGroRealEstate", "email", {"email": email})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["total-gm", "tier-totals", "markup-calc"],
        "research_frozen": "The pricing table embedded in the upstream email (not machine-readable in the reference .docx) was "
                           "recovered from the expert pro forma's tier-1 rows.",
        "notes": [
            "Rubric 'Margin (%)' values equal unit margin / cost (markup), e.g. 197/690 = 28.6%; markup_pct follows that definition.",
            "Year-1 volume is split 1,000 units at tier 1 and 1,000 at tier 2, as in the expert pro forma (total GM $1,889,250).",
        ],
    }

# --- task 17: IEHK module quotation -----------------------------------------------------------


def t17_iehk_quotation(src: SourceTask) -> Json:
    sheet = xlsx_rows(src.ref("Internal_Pricing"))
    require(sheet[0] == ("Article Number", "Module Name", "Unit Price (USD)", "Lead Time", "Shelf Life"), "task 17 internal header")
    modules = [row[:5] for row in sheet[1:] if row and isinstance(row[0], int)]
    require(len(modules) == 8, "task 17 module count")
    request = pdf_text(src.ref("Request for Indicative Pricing"))
    require(any("BO-757820" in line for line in request), "task 17 request reference")
    original_quantity = "10 units of the Basic Module (to meet WHO kit standards) and 1 unit each of every other module included in the IEHK 2017"
    require(original_quantity in src.prompt, "task 17 prompt quantity sentence changed")
    prompt = src.prompt.replace(
        original_quantity,
        "12 units of each Basic module (Basic Medicines, Basic Renewable and Equipment, Basic Malaria) and 3 units of each "
        "Supplementary module included in the IEHK 2017",
    )
    lines: Json = {}
    for article, name, price, lead, shelf in modules:
        quantity = 12 if "Basic" in name else 3
        lines[str(article)] = {
            "description": name, "quantity": quantity, "unit_price": price, "line_total": r2(price * quantity),
            "lead_time": lead, "shelf_life": shelf,
        }
    grand_total = r2(sum(row["line_total"] for row in lines.values()))
    require(grand_total == 85950, f"task 17 grand total {grand_total}")
    links = ["https://www.who.int/publications/i/item/978924115221",
             "https://iris.who.int/bitstream/handle/10665/279428/9789241515221-eng.pdf"]
    truth = {
        "quotation_number": "Q6533211",
        "project_reference": "BO-757820",
        "quotation_date": "2025-01-15",
        "client": "Inter-Aid",
        "supplier": "MedWholeGroup",
        "currency": "USD",
        "incoterm": "EXW",
        "unit_price_basis": "EXW",
        "freight_included": False,
        "payment_condition": "prepayment_100",
        "offer_validity_days": 30,
        "offer_validity_basis": "quotation_date",
        "who_reference_link": links[0],
        "lines": lines,
        "grand_total": grand_total,
    }
    catalog = {
        "incoterm": codes(("EXW", "Ex-Works / ex warehouse"), ("FCA", "Free carrier"), ("CIP", "Carriage and insurance paid"), ("DAP", "Delivered at place")),
        "unit_price_basis": codes(("EXW", "unit prices are ex-works"), ("CIP", "unit prices include carriage and insurance")),
        "payment_condition": codes(("prepayment_100", "100% prepayment before dispatch"), ("net_30", "30 days after invoice"),
                                   ("split_50_50", "50% advance, 50% before dispatch")),
        "offer_validity_basis": codes(("quotation_date", "validity counted from the date of quotation"), ("receipt", "from receipt by client")),
    }
    fields = [
        field("quotation_number", "string", "Quotation number."),
        field("project_reference", "string", "Client project reference number."),
        field("quotation_date", "date", "Date of the quotation."),
        field("client", "string", "Client name."),
        field("supplier", "string", "Supplier name."),
        field("currency", "string", "ISO currency code of all amounts."),
        field("incoterm", "code", "Incoterm of the quotation."),
        field("unit_price_basis", "code", "Basis the unit prices are quoted on (the price column label)."),
        field("freight_included", "bool", "Whether transport/freight charges are included."),
        field("payment_condition", "code", "Payment condition."),
        field("offer_validity_days", "number", "Offer validity in days."),
        field("offer_validity_basis", "code", "Event the validity period is counted from."),
        field("who_reference_link", "string", "URL of official WHO documentation on the IEHK 2017 structure."),
        field("lines", "object<article_number,object>", "One line per quoted module keyed by article number; each: description, quantity, "
              "unit_price, line_total, lead_time, shelf_life. Copy lead_time and shelf_life text exactly as written in the internal sheet."),
        field("grand_total", "number", "Grand total of all lines (EXW, no transport)."),
    ]
    checks = [
        check("quote-number", "text", "quotation_number", "Q6533211"),
        check("project-ref", "text", "project_reference", "BO-757820"),
        check("quote-date", "nonempty", "quotation_date"),
        check("client", "text", "client", "Inter-Aid"),
        check("supplier", "text", "supplier", "MedWholeGroup"),
        check("currency", "text", "currency", "USD"),
        check("incoterm", "text", "incoterm", "EXW"),
        check("price-basis", "text", "unit_price_basis", "EXW"),
        check("freight-excluded", "bool", "freight_included", False),
        check("payment", "text", "payment_condition", "prepayment_100"),
        check("validity", "custom", rule="all_of", checks=[
            num("d", "offer_validity_days", 30, 0), check("b", "text", "offer_validity_basis", "quotation_date"),
        ]),
        check("who-link", "member", "who_reference_link", links),
        check("line-ids", "keys", "lines", list(lines)),
        check("descriptions", "custom", "lines", {k: {"description": v["description"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False),
        check("shelf-life", "custom", "lines", {k: {"shelf_life": v["shelf_life"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False),
        check("lead-time", "custom", "lines", {k: {"lead_time": v["lead_time"]} for k, v in lines.items()}, rule="rows_match", exact_ids=False),
        num("grand-total", "grand_total", grand_total, 0.005),
        check("total-sum", "custom", rule="all_of", checks=[
            check("f", "custom", "lines", None, rule="record_formula", target="line_total", formula="product", a="unit_price", b="quantity", tolerance=0.005),
            num("t", "grand_total", grand_total, 0.005), check("x", "bool", "freight_included", False),
        ]),
    ]
    for column in ("description", "quantity", "unit_price", "shelf_life", "lead_time", "line_total"):
        checks.append(check(f"col-{column.replace('_', '-')}", "custom", "lines", None, rule="records", min_count=1, nonempty=[column]))
    for article, row in lines.items():
        checks.append(num(f"{article}-qty", ["lines", article, "quantity"], row["quantity"], 0))
        checks.append(num(f"{article}-price", ["lines", article, "unit_price"], row["unit_price"], 0.005))
        checks.append(num(f"{article}-total", ["lines", article, "line_total"], row["line_total"], 0.005))
    rules = [
        (r"file name exactly equals", "u:file_format"),
        (r"project reference number 'BO-757820'", "c:project-ref"),
        (r"quotation number 'Q6533211'", "c:quote-number"),
        (r"clickable hyperlink to official WHO", "c:who-link"),
        (r"Incoterm ExW", "c:incoterm"),
        (r"transport/freight charges are excluded", "c:freight-excluded"),
        (r"100% prepayment", "c:payment"),
        (r"Offer validity is stated as 30 days", "c:validity"),
        (r"quotation date is present", "c:quote-date"),
        (r"column for item descriptions", "c:col-description"),
        (r"column for article numbers", "c:line-ids"),
        (r"column for quantity", "c:col-quantity"),
        (r"column for unit price", "c:col-unit-price"),
        (r"column for shelf life", "c:col-shelf-life"),
        (r"column for lead time", "c:col-lead-time"),
        (r"column for line total", "c:col-line-total"),
        (r"All monetary amounts .* are in USD", "c:currency"),
        (r"Only whole IEHK 2017 modules are quoted", "c:line-ids,descriptions"),
        (r"Every quoted line corresponds to an IEHK 2017 module", "c:line-ids"),
        (r"Article Number (\d+) is quoted with quantity", "c:{1}-qty"),
        (r"Article Number (\d+) has a unit price", "c:{1}-price"),
        (r"Article Number (\d+) has a line total", "c:{1}-total"),
        (r"shelf life value matches", "c:shelf-life"),
        (r"lead time/availability value matches", "c:lead-time"),
        (r"grand total price is exactly", "c:grand-total"),
        (r"grand total equals the sum of all line totals", "c:total-sum"),
        (r"client name 'Inter-Aid'", "c:client"),
        (r"supplier name 'MedWholeGroup'", "c:supplier"),
        (r"currency code 'USD' appears", "c:currency"),
        (r"labels the unit price column", "c:price-basis"),
    ]
    internal_rows = [list(row) for row in modules]
    return {
        "family": "distributor_pricing_quotation",
        "title": "Quote IEHK 2017 modules EXW to a new NGO client",
        "difficulty": "hard",
        "goal": "As account manager, issue an EXW indicative quotation for IEHK 2017 modules to new NGO client Inter-Aid from the internal price, lead-time, and shelf-life sheet.",
        "request": prompt,
        "artifact_type": "gdp_quotation",
        "fields": fields,
        "codes": catalog,
        "tables": [table("PRICING", "Internal pricing, lead time and shelf life - IEHK 2017 modules",
                         "Small-volume unit prices (USD), current lead time, and guaranteed shelf life per module.",
                         ["article_number", "module_name", "unit_price_usd", "lead_time", "shelf_life"], internal_rows)],
        "documents": [document("RFQ", "Inter-Aid request for indicative pricing BO-757820", "email", {"request": request})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["grand-total", "total-sum", "freight-excluded"],
        "notes": [
            ("Upstream prompt asks for 10 Basic modules and 1 of each other module, but every rubric item and the expert quotation use "
            "12 per Basic module and 3 per Supplementary module (total $85,950); the request was restated with the rubric quantities."),
            "The quotation date is free (scored as present); the oracle uses 2025-01-15.",
            "The WHO reference link is checked against the two official URLs given in the request; browsing is not available.",
        ],
    }


# --- task 18: revised quotation with transport options -----------------------------------------

TRANSPORT_MODES = [
    ("air", "Airfreight Quote", "Euro Air Cargo", ["Euro Air Cargo"]),
    ("sea", "Seafreight Quote", "Red Water Shipping", ["Red Water Shipping", "Red Ocean Shipping"]),
    ("road", "Road Freight Quote", "Euro Road Logistics Co.", ["Euro Road Logistics Co.", "Euro Road Logistics"]),
]


def _usd(lines: list[str], label: str) -> float:
    for line in lines:
        match = re.search(label + r"[^:]*:\s*USD\s*([\d,]+)", line, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    raise ValueError(f"no {label} amount")


def t18_revised_transport_quote(src: SourceTask) -> Json:
    tiers = [row[:3] for row in xlsx_rows(src.ref("Internal Price & Lead Time")) if any(value is not None for value in row)]
    require(tiers[0] == ("Quantity Range", "Price per kit (USD)", "Estimated Delivery Time"), "task 18 tier header")
    quantity = 400
    tier = None
    for label, price, delivery in tiers[1:]:
        bounds = [int(value) for value in re.findall(r"\d+", label)]
        upper = bounds[1] if len(bounds) == 2 else 10**9
        if bounds[0] <= quantity <= upper:
            tier = (label, price, delivery)
    require(tier is not None and tier[1] == 450 and tier[2] == "3 weeks", f"task 18 tier {tier}")
    lead_weeks = int(tier[2].split()[0])
    original = [row[:7] for row in xlsx_rows(src.ref("Q9749821 Danish Wholesale")) if any(value is not None for value in row)]
    product = next(row for row in original if row[0] == "1")
    terms = {row[0]: row[1] for row in original if row[0] in ("Currency", "Incoterm", "Payment condition", "Offer validity")}
    require(terms["Incoterm"] == "CIP" and terms["Payment condition"] == "30 days after invoice", "task 18 original terms")
    documents = []
    options: Json = {}
    exw = r2(quantity * tier[1])
    for mode, needle, forwarder, accepted in TRANSPORT_MODES:
        text_lines = pdf_text(src.ref(needle))
        freight = _usd(text_lines, "Total freight cost")
        transit = next(re.findall(r"(\d+)\s*-\s*(\d+)\s*days", line) for line in text_lines if "transit time" in line.lower())[0]
        reference = next(line.split(":", 1)[1].strip() for line in text_lines if line.lower().startswith(("reference", "quotation reference")))
        options[mode] = {
            "forwarder": forwarder,
            "forwarder_quote_ref": reference,
            "freight_usd": freight,
            "transit_days_min": int(transit[0]),
            "transit_days_max": int(transit[1]),
            "grand_total": r2(exw + freight),
            "delivery_days_max": lead_weeks * 7 + int(transit[1]),
            "within_target": lead_weeks * 7 + int(transit[1]) <= 60,
            "risk_flags": ["border_zone_delays"] if mode == "road" else [],
            "rationale": {"air": "Fastest option but the most expensive.",
                          "sea": "Lowest cost and still well within the two-month delivery target.",
                          "road": "Mid-priced, but the route crosses active border zones with possible delays or disruption."}[mode],
        }
        documents.append(document(mode.upper(), f"{forwarder} freight quote {reference}", "email", {"quote": text_lines}))
    require([options[m]["freight_usd"] for m in ("air", "sea", "road")] == [18975, 3150, 5400], "task 18 freight")
    require([options[m]["grand_total"] for m in ("air", "sea", "road")] == [198975, 183150, 185400], "task 18 grand totals")
    truth = {
        "quotation_number": "Q9749821",
        "supplier": "Danish Wholesale & Co.",
        "client": "Health NGO",
        "destination_country": "Lebanon",
        "line": {"quantity": quantity, "description": product[2], "unit_price": tier[1], "total": exw, "lead_time_weeks": lead_weeks},
        "total_exw": exw,
        "currency": "USD",
        "incoterm": terms["Incoterm"],
        "payment_condition": "net_30",
        "offer_validity_days": 30,
        "transport_options": options,
        "general_remark": {
            "freight_subject_to_change": True, "rate_validity_days_min": 14, "rate_validity_days_max": 30,
            "reconfirm_at_final_order": True, "cold_chain_required": False,
        },
    }
    catalog = {
        "payment_condition": codes(("net_30", "30 days after invoice"), ("prepayment_100", "100% prepayment")),
        "transport_options.*.risk_flags": codes(("border_zone_delays", "route crosses active border zones; delays or disruption possible"),
                                                ("cold_chain", "temperature-controlled handling required"),
                                                ("capacity", "limited carrier capacity")),
    }
    fields = [
        field("quotation_number", "string", "Quotation number (unchanged from the original)."),
        field("supplier", "string", "Supplier name."),
        field("client", "string", "Client name."),
        field("destination_country", "string", "Destination country."),
        field("line", "object", "Product line: quantity, description (as in the original quotation), unit_price, total, lead_time_weeks."),
        field("total_exw", "number", "Total EXW product value."),
        field("currency", "string", "ISO currency code."),
        field("incoterm", "string", "Incoterm as stated on the quotation."),
        field("payment_condition", "code", "Payment condition."),
        field("offer_validity_days", "number", "Offer validity in days from date of offer."),
        field("transport_options", "object<mode,object>", "Exactly the transport options offered, keyed air, sea, road; each: forwarder, "
              "forwarder_quote_ref, freight_usd, transit_days_min, transit_days_max, grand_total (EXW + freight), delivery_days_max "
              "(product lead time in days + maximum transit days), within_target (bool, delivery within the ~two-month / 60-day target), "
              "risk_flags (list[code]), rationale (string)."),
        field("general_remark", "object", "freight_subject_to_change (bool), rate_validity_days_min, rate_validity_days_max, "
              "reconfirm_at_final_order (bool), cold_chain_required (bool)."),
    ]
    checks = [
        num("quantity", "line.quantity", quantity, 0),
        num("unit-price", "line.unit_price", tier[1], 0.005),
        num("lead-time", "line.lead_time_weeks", lead_weeks, 0),
        check("total-exw", "custom", rule="all_of", checks=[num("t", "total_exw", exw, 0.005), num("l", "line.total", exw, 0.005)]),
        check("option-ids", "keys", "transport_options", ["air", "sea", "road"]),
        check("freight-amounts", "custom", "transport_options",
              {m: {"freight_usd": o["freight_usd"], "forwarder_quote_ref": o["forwarder_quote_ref"]} for m, o in options.items()},
              rule="rows_match", tolerance=0.005),
        check("general-remark", "custom", rule="all_of", checks=[
            check("c", "bool", "general_remark.freight_subject_to_change", True),
            num("a", "general_remark.rate_validity_days_min", 14, 0), num("b", "general_remark.rate_validity_days_max", 30, 0),
            check("r", "bool", "general_remark.reconfirm_at_final_order", True),
        ]),
        check("cold-chain", "bool", "general_remark.cold_chain_required", False),
        check("timeline", "custom", "transport_options",
              {m: {"delivery_days_max": o["delivery_days_max"], "within_target": o["within_target"]} for m, o in options.items()},
              rule="rows_match", exact_ids=False, tolerance=0),
        check("description", "member", "line.description", [product[2], "Sterilization kit C"]),
        check("preserved", "custom", rule="all_of", checks=[
            check("q", "text", "quotation_number", "Q9749821"), check("s", "text", "supplier", "Danish Wholesale & Co."),
            check("c", "text", "client", "Health NGO"), check("d", "text", "destination_country", "Lebanon"),
            check("i", "text", "incoterm", "CIP"), check("p", "text", "payment_condition", "net_30"),
            num("v", "offer_validity_days", 30, 0), check("u", "text", "currency", "USD"),
        ]),
        check("road-border-flag", "includes", "transport_options.road.risk_flags", ["border_zone_delays"]),
    ]
    for mode, _needle, _forwarder, accepted in TRANSPORT_MODES:
        option = options[mode]
        checks += [
            num(f"{mode}-freight", ["transport_options", mode, "freight_usd"], option["freight_usd"], 0.005),
            check(f"{mode}-transit", "custom", rule="all_of", checks=[
                num("a", ["transport_options", mode, "transit_days_min"], option["transit_days_min"], 0),
                num("b", ["transport_options", mode, "transit_days_max"], option["transit_days_max"], 0),
            ]),
            check(f"{mode}-rationale", "nonempty", ["transport_options", mode, "rationale"]),
            num(f"{mode}-grand-total", ["transport_options", mode, "grand_total"], option["grand_total"], 0.005),
            check(f"{mode}-forwarder", "member", ["transport_options", mode, "forwarder"], accepted),
        ]
    rules = [
        (r"delivered as a single Excel workbook", "u:file_format"),
        (r"quantity of exactly 400 kits", "c:quantity"),
        (r"unit price per kit is \$450", "c:unit-price"),
        (r"delivery lead time for 400 units", "c:lead-time"),
        (r"Total EXW equals exactly", "c:total-exw"),
        (r"present as distinct option lines", "c:option-ids"),
        (r"listed directly below the Total EXW", "u:presentation"),
        (r"(Air|Sea) .*freight charge equals", "c:{1}-freight"),
        (r"(Road) freight charge equals", "c:{1}-freight"),
        (r"(Air|Sea|Road) .*transport Item remarks include the transit time", "c:{1}-transit"),
        (r"Road transport Item remarks state that the route crosses active border", "c:road-border-flag"),
        (r"(Air|Sea|Road) .*transport Item remarks include a brief rationale", "c:{1}-rationale"),
        (r"(Air|Sea|Road) .*option Grand Total", "c:{1}-grand-total"),
        (r"General remark appears in red font", "c:general-remark"),
        (r"freight amount cited is taken directly", "c:freight-amounts"),
        (r"(Air|Sea|Road) .*transport option identifies the forwarder", "c:{1}-forwarder"),
        (r"preserves the overall structure", "c:preserved"),
        (r"product description references Sterilization kit C", "c:description"),
        (r"Numeric currency formatting is consistent", "u:presentation"),
        (r"Only the three required transport modes", "c:option-ids"),
        (r"combined timeline", "c:timeline"),
        (r"no cold chain packaging is required", "c:cold-chain"),
    ]
    tier_rows = [list(row) for row in tiers[1:]]
    original_sections = {
        "header": [" | ".join(str(value) for value in row if value not in (None, "")) for row in original[:4]],
        "product_line": dict(zip(original[4], product)),
        "terms": terms,
    }
    return {
        "family": "distributor_pricing_quotation",
        "title": "Revise a sterilization kit quotation with volume price and freight options",
        "difficulty": "hard",
        "goal": "As account manager, revise quotation Q9749821 for 400 sterilization kits with the volume price tier and three freight options with grand totals.",
        "request": src.prompt,
        "artifact_type": "gdp_revised_quotation",
        "fields": fields,
        "codes": catalog,
        "tables": [table("TIERS", "Internal price and lead time - Sterilization kit C", "Price per kit (USD) and estimated delivery "
                         "time by order quantity range.", ["quantity_range", "price_per_kit_usd", "estimated_delivery_time"], tier_rows)],
        "documents": [document("ORIGINAL", "Original quotation Q9749821", "CPQ", original_sections), *documents],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["total-exw", "air-grand-total", "sea-grand-total", "road-grand-total"],
        "notes": [
            ("Rubric items on red font and on placing options directly below Total EXW are layout and are recorded unscored; the remark "
            "content itself is scored."),
            "The sea forwarder is named Red Water Shipping in the request and Red Ocean Shipping in the file name; both are accepted.",
            "Original Incoterm (CIP), payment (30 days after invoice), and validity are preserved as in the expert revision.",
        ],
    }

# --- task 19: carrier flat-rate selection -----------------------------------------------------

CARRIERS = ["USPS", "FedEx", "UPS"]
PACKAGE_SIZES = [("pak", "Pak"), ("small_box", "Small Box"), ("medium_box", "Medium Box"), ("large_box", "Large Box"),
                 ("extra_large_box", "Extra Large Box")]


def t19_carrier_flat_rates(src: SourceTask) -> Json:
    sheet = [row[1:5] for row in xlsx_rows(src.deliv("Flat Rate Shipping Analysis")) if len(row) > 4 and row[1] is not None]
    require(sheet[1] == (None, "USPS", "FedEx", "UPS") or sheet[0][0] == "Annual Gross Rate Increase", "task 19 layout")
    history = {carrier: {} for carrier in CARRIERS}
    for row in sheet:
        if isinstance(row[0], int) and 2020 <= row[0] <= 2025:
            for carrier, value in zip(CARRIERS, row[1:]):
                history[carrier][str(row[0])] = r2(value * 100)
    start = next(i for i, row in enumerate(sheet) if str(row[0]).startswith("Flat Rate Shipping Costs (2025)"))
    rates_2025: Json = {carrier: {} for carrier in CARRIERS}
    for (size, _label), row in zip(PACKAGE_SIZES, sheet[start + 1:start + 6]):
        for carrier, value in zip(CARRIERS, row[1:]):
            rates_2025[carrier][size] = value if isinstance(value, (int, float)) else None
    volumes = {"pak": 1000, "small_box": 2300, "medium_box": 2100, "large_box": 540, "extra_large_box": 120}
    for size, label in PACKAGE_SIZES:
        require(f"{label.split()[0]}" in src.prompt, "task 19 prompt sizes")
    averages = {carrier: r4(sum(history[carrier].values()) / 6) for carrier in CARRIERS}
    rates_2026: Json = {carrier: {} for carrier in CARRIERS}
    totals: Json = {carrier: {} for carrier in CARRIERS}
    for carrier in CARRIERS:
        factor = 1 + sum(history[carrier].values()) / 600
        for size, _label in PACKAGE_SIZES:
            rate = rates_2025[carrier][size]
            rates_2026[carrier][size] = None if rate is None else r4(rate * factor)
            totals[carrier][size] = None if rate is None else r2(rate * factor * volumes[size])
    recommendations = {}
    for size, _label in PACKAGE_SIZES:
        offered = [(totals[carrier][size], carrier) for carrier in CARRIERS if totals[carrier][size] is not None]
        recommendations[size] = min(offered)[1]
    require(recommendations == {"pak": "USPS", "small_box": "USPS", "medium_box": "UPS", "large_box": "UPS", "extra_large_box": "UPS"},
            f"task 19 recommendations {recommendations}")
    require(abs(totals["USPS"]["small_box"] - 25307.42) < 0.01 and abs(totals["FedEx"]["extra_large_box"] - 4789.72) < 0.01,
            "task 19 totals")
    truth = {
        "rate_increases": history,
        "average_increase_pct": averages,
        "rates_2025": rates_2025,
        "volumes_2026": volumes,
        "rates_2026": rates_2026,
        "total_cost_2026": totals,
        "recommendations": recommendations,
    }
    size_keys = [size for size, _label in PACKAGE_SIZES]
    fields = [
        field("rate_increases", "object<carrier,object<year,number>>", "Annual general rate increase (0-100) per carrier (USPS, FedEx, "
              "UPS) for each year 2020-2025."),
        field("average_increase_pct", "object<carrier,number>", "Average annual increase 2020-2025 per carrier (0-100); used as the 2026 estimate."),
        field("rates_2025", "object<carrier,object<size,number|null>>", "Current flat-rate price per package size (pak, small_box, "
              "medium_box, large_box, extra_large_box); null where the carrier does not offer that size."),
        field("volumes_2026", "object<size,number>", "Projected 2026 shipment volume per package size."),
        field("rates_2026", "object<carrier,object<size,number|null>>", "Estimated 2026 flat rate (2025 rate x (1 + carrier average increase)); null where not offered."),
        field("total_cost_2026", "object<carrier,object<size,number|null>>", "Estimated 2026 total cost (2026 rate x volume); null where not offered."),
        field("recommendations", "object<size,carrier>", "Recommended carrier for each package size."),
    ]
    checks: list[Json] = []
    year_checks: list[Json] = []
    money_checks: list[Json] = []
    for carrier in CARRIERS:
        key = carrier.lower()
        checks.append(check(f"{key}-history", "custom", ["rate_increases", carrier], None, rule="map_numbers",
                            values=history[carrier], tolerance=0.1))
        for year, value in history[carrier].items():
            row = num(f"{key}-{year}", ["rate_increases", carrier, year], value, 0.1)
            checks.append(row)
            year_checks.append(row)
        checks.append(num(f"{key}-avg", ["average_increase_pct", carrier], averages[carrier], 0.04))
        checks.append(check(f"{key}-2026-table", "keys", ["rates_2026", carrier], size_keys))
        for size in size_keys:
            for table_key, suffix, values in (("rates_2025", "2025", rates_2025), ("rates_2026", "2026", rates_2026),
                                              ("total_cost_2026", "total", totals)):
                value = values[carrier][size]
                check_id = f"{key}-{size.replace('_', '-')}-{suffix}"
                if value is None:
                    checks.append(check(check_id, "custom", table_key, {carrier: {size: None}}, rule="rows_match", exact_ids=False))
                else:
                    row = num(check_id, [table_key, carrier, size], value, r4(abs(value) * 0.01))
                    checks.append(row)
                    money_checks.append(row)
    checks += [
        check("avg-computed", "custom", rule="all_of", checks=[c for c in checks if c["id"].endswith("-avg")]),
        check("rates-2025-table", "custom", rule="all_of", checks=[
            check(c.lower(), "keys", ["rates_2025", c], size_keys) for c in CARRIERS]),
        check("rates-2025-carriers", "keys", "rates_2025", CARRIERS),
        check("volumes", "custom", "volumes_2026", None, rule="map_numbers", values=volumes, tolerance=0),
        check("totals-table", "custom", rule="all_of", checks=[check("c", "keys", "total_cost_2026", CARRIERS)] + [
            check(c.lower(), "keys", ["total_cost_2026", c], size_keys) for c in CARRIERS]),
        check("recs-table", "keys", "recommendations", size_keys),
        check("monetary-numeric", "custom", rule="all_of", checks=money_checks),
        check("pct-numeric", "custom", rule="all_of", checks=year_checks),
    ]
    for size in size_keys:
        checks.append(num(f"vol-{size.replace('_', '-')}", ["volumes_2026", size], volumes[size], 0))
        checks.append(check(f"rec-{size.replace('_', '-')}", "text", ["recommendations", size], recommendations[size]))
    size_pattern = r"(Pak|Small Box|Medium Box|Large Box|Extra Large Box)"
    rules = [
        (r"historical annual rate increases for the following years: .* carrier (USPS|FedEx|UPS)", "c:{1}-history"),
        (r"States the (\d{4}) annual rate increase for (USPS|UPS|FedEx)", "c:{2}-{1}"),
        (r"average annual rate increase for (USPS|UPS|FedEx)", "c:{1}-avg"),
        (r"computes an average annual rate increase", "c:avg-computed"),
        (r"table for flat rate shipping costs for 2025", "c:rates-2025-table"),
        (rf"States the (USPS|FedEx|UPS) flat rate shipping costs for {size_pattern} in 2025", "c:{1}-{2}-2025"),
        (r"current \(2025\) flat-rate costs table includes all three", "c:rates-2025-carriers"),
        (r"current flat-rate cell contains a numeric", "c:monetary-numeric"),
        (r"table listing the projected 2026 shipment volumes", "c:volumes"),
        (rf"projected 2026 volume for {size_pattern}", "c:vol-{1}"),
        (r"table for 2026 projected flat rate shipping costs per package size .* carrier (USPS|FedEx|UPS)", "c:{1}-2026-table"),
        (rf"2026 projected flat rate shipping cost of {size_pattern} for (USPS|FedEx|UPS)", "c:{2}-{1}-2026"),
        (r"table of estimated total cost per carrier", "c:totals-table"),
        (rf"expected total cost of {size_pattern} for (USPS|FedEx|UPS)", "c:{2}-{1}-total"),
        (r"recommendations table identifying one recommended carrier", "c:recs-table"),
        (rf"carrier recommendation for {size_pattern} as", "c:rec-{1}"),
        (r"All monetary cells", "c:monetary-numeric"),
        (r"rate increases contain numeric percentage", "c:pct-numeric"),
    ]
    history_rows = [[carrier, int(year), value] for carrier in CARRIERS for year, value in history[carrier].items()]
    rate_rows = [[carrier, label, rates_2025[carrier][size], rates_2025[carrier][size] is not None]
                 for carrier in CARRIERS for size, label in PACKAGE_SIZES]
    request = src.prompt
    for old, new in (
        ("First, using search engines, research the historical annual rate increases for USPS, UPS, and FedEx from 2020-2025",
         ("First, using the carrier research tables (researched in 2025; do not browse), record the historical annual rate increases "
         "for USPS, UPS, and FedEx from 2020-2025")),
        ("Next, research and record each carriers current published flat rate shipping costs per package size.",
         "Next, record each carrier's current published flat rate shipping costs per package size from the research tables."),
    ):
        require(old in request, f"task 19 prompt sentence changed: {old[:40]}")
        request = request.replace(old, new)
    return {
        "family": "distributor_warehouse_shipping",
        "title": "Select the lowest-cost flat-rate carrier per package size for 2026",
        "difficulty": "hard",
        "goal": "As outbound shipping manager, project 2026 flat-rate shipping cost by carrier and package size and recommend a carrier per size.",
        "request": request,
        "artifact_type": "gdp_carrier_selection",
        "fields": fields,
        "codes": {},
        "tables": [
            table("GRI", "Carrier general rate increases 2020-2025", "Published annual general rate increase per carrier and year "
                  "(percent, 0-100).", ["carrier", "year", "increase_pct"], history_rows),
            table("FLATRATE", "Carrier flat-rate prices (2025, standard service, business rates)", "Current flat-rate price per "
                  "package size; offered=false and a null price where the carrier has no flat-rate option for that size.",
                  ["carrier", "package_size", "rate_usd", "offered"], rate_rows),
        ],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["monetary-numeric", "recs-table", "usps-avg", "ups-avg", "fedex-avg"],
        "research_frozen": "Annual general rate increases 2020-2025 and 2025 flat-rate prices for USPS, FedEx, and UPS were frozen "
                           "from the expert workbook '2026 Flat Rate Shipping Analysis.xlsx'; source URLs were not recorded upstream.",
        "notes": [
            "2026 rates use the carrier's unrounded six-year average increase; per-cell checks allow the rubric's +/-1%.",
            "USPS has no extra large flat-rate box, so its 2025, 2026, and total cells must be null and USPS is excluded for that size.",
        ],
    }


# --- task 20: ESD handling and storage SOP ----------------------------------------------------


def t20_esd_sop(src: SourceTask) -> Json:
    truth = {
        "document_type": "standard_operating_procedure",
        "subject": "esd_handling_and_storage",
        "title": "Electrostatic Discharge (ESD) Handling & Storage Procedure",
        "sections": ["purpose", "scope", "definitions", "warning_symbols", "workspace_setup", "handling_procedures", "storage_requirements",
                     "packaging_transport", "training", "equipment_maintenance", "audit_compliance", "references", "approval"],
        "purpose": "Define the standardized method for handling and storing ESD-sensitive items to prevent damage and ensure product integrity.",
        "purpose_objectives": ["standardize_handling_storage", "prevent_damage", "ensure_product_integrity"],
        "scope": ["warehouse_personnel", "all_esds_handlers"],
        "scope_items": ["components", "assemblies", "circuit_boards"],
        "definitions": {
            "ESD": "Electrostatic discharge: the sudden flow of electricity between two electrically charged objects.",
            "EPA": "ESD protected area: a designated zone where ESD-sensitive items are handled safely under ESD controls.",
            "ESDS": "ESD-sensitive device: any electronic component that can be damaged by static electricity.",
        },
        "symbols": {"esd_sensitive": "hand_with_slash_in_triangle", "protective_packaging": "hand_in_triangle_with_arc"},
        "signage_locations": ["epa_entry_points", "storage_cabinets", "handling_workstations"],
        "workspace": ["personnel_grounding", "equipment_grounding", "grounded_mats", "common_point_ground", "ionizers_low_humidity",
                      "esd_safe_furniture_tools"],
        "handling": ["handle_in_epa_only", "ground_before_touching", "keep_in_shielding_outside_epa", "handle_by_edges",
                     "no_static_apparel", "esd_gloves_when_required", "receiving_verify_protection", "protected_handoff"],
        "storage": ["static_shielding_bags", "esd_safe_bins", "conductive_foam_trays", "label_storage_locations", "grounded_shelving"],
        "packaging_transport": ["esd_packaging_all_movement", "secure_in_shielding_or_conductive_container", "seal_with_esd_tape",
                                "no_non_esd_materials"],
        "training": {
            "initial_required": True,
            "refresher": "annual_or_on_change",
            "topics": ["static_basics", "esd_symbols_identification", "protective_equipment_use", "hands_on_demonstration"],
        },
        "maintenance": {
            "wrist_strap_test_frequency": "daily",
            "mat_ground_verification_frequency": "weekly",
            "calibration_records": True,
            "damaged_gear": "report_and_replace_immediately",
        },
        "audit": ["periodic_checklist_audits", "monitor_epa_entries_signage", "report_correct_noncompliance", "maintain_records"],
        "humidity": {"low_humidity_increases_risk": True, "mitigation": ["ionizers", "humidification"]},
        "references": ["IPC-A-610G", "ANSI/ESD S20.20", "company_esd_policy"],
        "approval": {"approver_title": "Warehouse Manager", "signature_required": True},
    }
    catalog = {
        "document_type": codes(("standard_operating_procedure", "standard operating procedure (SOP)"), ("work_instruction", "single-task work instruction"),
                               ("policy", "policy statement")),
        "subject": codes(("esd_handling_and_storage", "handling and storage of ESD-sensitive items"), ("esd_assembly_inspection", "inspection of electronic assemblies")),
        "sections": codes(*[(name, name.replace("_", " ")) for name in truth["sections"]]),
        "purpose_objectives": codes(("standardize_handling_storage", "standardize how ESDS items are handled and stored"),
                                    ("prevent_damage", "prevent ESD damage"), ("ensure_product_integrity", "ensure product integrity"),
                                    ("reduce_headcount", "reduce warehouse headcount")),
        "scope": codes(("warehouse_personnel", "warehouse team members"), ("all_esds_handlers", "anyone handling, storing, or working with ESDS items"),
                       ("visitors_only", "visitors only")),
        "scope_items": codes(("components", "electronic components"), ("assemblies", "assemblies"), ("circuit_boards", "circuit boards")),
        "symbols.*": codes(("hand_with_slash_in_triangle", "yellow triangle with black hand and slash: ESD-sensitive item"),
                           ("hand_in_triangle_with_arc", "triangle with hand and arc: ESD protective packaging"),
                           ("lightning_bolt", "electrical hazard bolt")),
        "signage_locations": codes(("epa_entry_points", "EPA entry points"), ("storage_cabinets", "storage cabinets with ESDS items"),
                                   ("handling_workstations", "ESD handling workstations"), ("break_room", "break room")),
        "workspace": codes(("personnel_grounding", "wrist straps or heel grounders to a verified ground point"),
                           ("equipment_grounding", "grounding of equipment and work surfaces"), ("grounded_mats", "grounded ESD-safe mats on benches/floors"),
                           ("common_point_ground", "common-point ground connection for personnel and work surfaces"),
                           ("ionizers_low_humidity", "ionizers in low humidity or where grounding is not possible"),
                           ("esd_safe_furniture_tools", "only ESD-safe chairs, hand tools, and containers"),
                           ("carpeted_floor", "standard carpeted floor")),
        "handling": codes(("handle_in_epa_only", "handle ESDS items only in an EPA"), ("ground_before_touching", "ground yourself before touching ESDS"),
                          ("keep_in_shielding_outside_epa", "keep ESDS in static-shielding packaging outside an EPA"),
                          ("handle_by_edges", "handle by edges/body; never touch pins, leads, contacts, conductive paths"),
                          ("no_static_apparel", "no static-generating apparel (wool, polyester) in the EPA"),
                          ("esd_gloves_when_required", "ESD-approved gloves when the task requires"),
                          ("receiving_verify_protection", "at receiving, identify ESDS items and keep them protected until opened in an EPA"),
                          ("protected_handoff", "maintain ESD protection through hand-off to production or the next step"),
                          ("open_packaging_anywhere", "open ESD packaging at any bench for inspection")),
        "storage": codes(("static_shielding_bags", "static-shielding bags"), ("esd_safe_bins", "ESD-safe bins or containers"),
                         ("conductive_foam_trays", "conductive foam inserts or trays"), ("label_storage_locations", "storage locations labeled with ESD symbols"),
                         ("grounded_shelving", "grounded shelving and racks"), ("standard_plastic_bins", "standard plastic bins")),
        "packaging_transport": codes(("esd_packaging_all_movement", "ESD-safe packaging for any internal or external movement"),
                                     ("secure_in_shielding_or_conductive_container", "items secured in shielding bags or rigid conductive containers in transit"),
                                     ("seal_with_esd_tape", "seal with ESD-safe tape or closures"),
                                     ("no_non_esd_materials", "no bubble wrap, Styrofoam, or other non-ESD packing"),
                                     ("bubble_wrap_cushioning", "cushion with standard bubble wrap")),
        "training.refresher": codes(("annual_or_on_change", "annually or when procedures/equipment change"), ("none", "no refresher")),
        "training.topics": codes(("static_basics", "basics of static electricity"), ("esd_symbols_identification", "ESD symbols and identifying ESDS items and EPAs"),
                                 ("protective_equipment_use", "use of wrist straps, heel grounders, mats"),
                                 ("hands_on_demonstration", "hands-on demonstration and practice")),
        "maintenance.*_frequency": codes(("before_each_use", "before each use"), ("daily", "daily"), ("weekly", "weekly"), ("monthly", "monthly"),
                                         ("annually", "annually")),
        "maintenance.damaged_gear": codes(("report_and_replace_immediately", "report to supervisor and replace immediately"),
                                          ("next_audit", "address at the next audit")),
        "audit": codes(("periodic_checklist_audits", "periodic ESD audits using checklists"), ("monitor_epa_entries_signage", "monitor EPA entries; signage visible"),
                       ("report_correct_noncompliance", "report and correct non-compliance immediately"),
                       ("maintain_records", "records of training, inspections, corrective actions")),
        "humidity.mitigation": codes(("ionizers", "ionizers"), ("humidification", "humidification"), ("none", "no mitigation")),
    }
    fields = [
        field("document_type", "code", "Type of document."),
        field("subject", "code", "Subject of the document."),
        field("title", "string", "Document title."),
        field("sections", "list[code]", "Sections of the document, in order."),
        field("purpose", "string", "Purpose statement."),
        field("purpose_objectives", "list[code]", "Objectives stated in the purpose."),
        field("scope", "list[code]", "Who the procedure applies to."),
        field("scope_items", "list[code]", "Item types covered."),
        field("definitions", "object", "Plain-language definitions keyed ESD, EPA, ESDS."),
        field("symbols.esd_sensitive", "code", "Symbol marking ESD-sensitive items."),
        field("symbols.protective_packaging", "code", "Symbol marking ESD protective packaging."),
        field("signage_locations", "list[code]", "Where ESD warning signs are posted."),
        field("workspace", "list[code]", "EPA workspace setup requirements."),
        field("handling", "list[code]", "Handling controls."),
        field("storage", "list[code]", "Storage requirements."),
        field("packaging_transport", "list[code]", "Packaging and transport controls."),
        field("training.initial_required", "bool", "Initial ESD training required before handling ESDS items."),
        field("training.refresher", "code", "Refresher training interval."),
        field("training.topics", "list[code]", "Training topics."),
        field("maintenance.wrist_strap_test_frequency", "code", "Testing interval for wrist straps and heel grounders."),
        field("maintenance.mat_ground_verification_frequency", "code", "Verification interval for mats and grounding points."),
        field("maintenance.calibration_records", "bool", "Calibration/performance records kept for ionizers and test equipment."),
        field("maintenance.damaged_gear", "code", "Handling of damaged or non-functional ESD gear."),
        field("audit", "list[code]", "Audit and compliance controls."),
        field("humidity.low_humidity_increases_risk", "bool", "Whether the SOP states low humidity increases ESD risk."),
        field("humidity.mitigation", "list[code]", "Low-humidity mitigations."),
        field("references", "list[string]", "Referenced standards and documents (standard designations as published)."),
        field("approval", "object", "Approval block: approver_title, signature_required (bool)."),
    ]

    def has(check_id: str, path: str, *needed: str) -> Json:
        return check(check_id, "includes", path, list(needed))

    checks = [
        check("identity", "custom", rule="all_of", checks=[
            check("t", "text", "document_type", "standard_operating_procedure"), check("s", "text", "subject", "esd_handling_and_storage"),
        ]),
        check("references", "overlaps", "references", ["IPC-A-610G", "IPC-A-610", "IPC A 610G", "IPC-A-610 Rev G"]),
        check("purpose", "custom", rule="all_of", checks=[
            check("p", "nonempty", "purpose"),
            has("o", "purpose_objectives", "standardize_handling_storage", "prevent_damage", "ensure_product_integrity"),
        ]),
        check("scope", "custom", rule="all_of", checks=[has("s", "scope", "warehouse_personnel", "all_esds_handlers"),
                                                         has("i", "scope_items", "components", "assemblies", "circuit_boards")]),
        check("handling-section", "custom", rule="all_of", checks=[has("s", "sections", "handling_procedures"),
                                                                    check("h", "custom", "handling", None, rule="sequence", excludes=["open_packaging_anywhere"])]),
        check("storage-section", "custom", rule="all_of", checks=[has("s", "sections", "storage_requirements"),
                                                                   check("x", "excludes", "storage", ["standard_plastic_bins"]),
                                                                   check("n", "nonempty", "storage")]),
        check("packaging-section", "custom", rule="all_of", checks=[has("s", "sections", "packaging_transport"),
                                                                     has("m", "packaging_transport", "esd_packaging_all_movement")]),
        has("epa-required", "handling", "handle_in_epa_only"),
        check("def-esd", "nonempty", "definitions.ESD"),
        check("def-epa", "nonempty", "definitions.EPA"),
        check("def-esds", "nonempty", "definitions.ESDS"),
        has("shielding-outside-epa", "handling", "keep_in_shielding_outside_epa"),
        check("grounding-tests", "member", "maintenance.wrist_strap_test_frequency", ["daily", "before_each_use"]),
        has("mats", "workspace", "grounded_mats"),
        has("handle-by-edges", "handling", "handle_by_edges"),
        has("transport-shielding", "packaging_transport", "secure_in_shielding_or_conductive_container"),
        check("labeling", "custom", rule="all_of", checks=[check("s", "overlaps", "signage_locations", truth["signage_locations"]),
                                                            has("l", "storage", "label_storage_locations")]),
        has("receiving", "handling", "receiving_verify_protection"),
        has("handoff", "handling", "protected_handoff"),
        check("refresher", "text", "training.refresher", "annual_or_on_change"),
        check("initial-training", "bool", "training.initial_required", True),
        has("topic-static", "training.topics", "static_basics"),
        has("topic-symbols", "training.topics", "esd_symbols_identification"),
        has("topic-equipment", "training.topics", "protective_equipment_use"),
        has("topic-hands-on", "training.topics", "hands_on_demonstration"),
        check("daily-strap-test", "text", "maintenance.wrist_strap_test_frequency", "daily"),
        check("weekly-mats", "text", "maintenance.mat_ground_verification_frequency", "weekly"),
        check("calibration-records", "bool", "maintenance.calibration_records", True),
        check("damaged-gear", "text", "maintenance.damaged_gear", "report_and_replace_immediately"),
        has("audits", "audit", "periodic_checklist_audits"),
        has("epa-monitoring", "audit", "monitor_epa_entries_signage"),
        has("noncompliance", "audit", "report_correct_noncompliance"),
        has("records", "audit", "maintain_records"),
        has("workspace-grounding", "workspace", "personnel_grounding", "equipment_grounding"),
        has("ionizers", "workspace", "ionizers_low_humidity"),
        has("esd-furniture", "workspace", "esd_safe_furniture_tools"),
        has("apparel", "handling", "no_static_apparel"),
        has("gloves", "handling", "esd_gloves_when_required"),
        has("storage-labels", "storage", "label_storage_locations"),
        has("storage-bags", "storage", "static_shielding_bags"),
        has("storage-bins-foam", "storage", "esd_safe_bins", "conductive_foam_trays"),
        has("grounded-shelving", "storage", "grounded_shelving"),
        has("packaging-all-movement", "packaging_transport", "esd_packaging_all_movement"),
        has("secure-items", "packaging_transport", "secure_in_shielding_or_conductive_container"),
        has("esd-tape", "packaging_transport", "seal_with_esd_tape"),
        check("no-bubble-wrap", "custom", rule="all_of", checks=[has("n", "packaging_transport", "no_non_esd_materials"),
                                                                  check("x", "excludes", "packaging_transport", ["bubble_wrap_cushioning"])]),
        check("packaging-symbol", "text", "symbols.protective_packaging", "hand_in_triangle_with_arc"),
        has("sign-entry", "signage_locations", "epa_entry_points"),
        has("sign-storage", "signage_locations", "storage_cabinets"),
        has("sign-workstations", "signage_locations", "handling_workstations"),
        has("common-point-ground", "workspace", "common_point_ground"),
        check("approval", "custom", rule="all_of", checks=[check("t", "nonempty", "approval.approver_title"),
                                                            check("s", "bool", "approval.signature_required", True)]),
        check("humidity", "custom", rule="all_of", checks=[check("r", "bool", "humidity.low_humidity_increases_risk", True),
                                                            check("m", "overlaps", "humidity.mitigation", ["ionizers", "humidification"])]),
    ]
    rules = [
        (r"length is no more than 5 pages", "u:presentation"),
        (r"identifies itself as a standard operating procedure", "c:identity"),
        (r"References section .* IPC-A-610G", "c:references"),
        (r"Purpose section", "c:purpose"),
        (r"Scope section", "c:scope"),
        (r"distinct Handling procedures section", "c:handling-section"),
        (r"distinct Storage requirements section", "c:storage-section"),
        (r"includes Packaging and Transport controls", "c:packaging-section"),
        (r"warehouse environment as including or requiring ESD Protected Areas", "c:epa-required"),
        (r"defines ESD \(Electrostatic", "c:def-esd"),
        (r"defines EPA", "c:def-epa"),
        (r"defines ESDS", "c:def-esds"),
        (r"remain in static.shielding/protective packaging when outside an EPA", "c:shielding-outside-epa"),
        (r"regular verification/testing of personnel grounding", "c:grounding-tests"),
        (r"grounded ESD.safe work surface mats", "c:mats"),
        (r"minimize contact with conductive areas", "c:handle-by-edges"),
        (r"ESD.safe shielding during transport", "c:transport-shielding"),
        (r"ESD caution labeling or signage", "c:labeling"),
        (r"receiving controls", "c:receiving"),
        (r"hand.off to production", "c:handoff"),
        (r"refresher interval", "c:refresher"),
        (r"Initial Training requirements", "c:initial-training"),
        (r"Training topics include basics of static", "c:topic-static"),
        (r"Training topics include ESD symbols", "c:topic-symbols"),
        (r"Training topics include proper use of ESD protective equipment", "c:topic-equipment"),
        (r"Training includes hands.on demonstrations", "c:topic-hands-on"),
        (r"daily testing of wrist straps", "c:daily-strap-test"),
        (r"periodic verification \(e\.g\., weekly\) of ESD mats", "c:weekly-mats"),
        (r"calibration or performance records", "c:calibration-records"),
        (r"immediate reporting/replacement of damaged", "c:damaged-gear"),
        (r"periodic ESD audits using checklists", "c:audits"),
        (r"monitoring EPA entries", "c:epa-monitoring"),
        (r"reporting and immediate correction of ESD non.compliance", "c:noncompliance"),
        (r"records of training, inspections, and corrective actions", "c:records"),
        (r"EPA workspace setup including grounding", "c:workspace-grounding"),
        (r"use of ionizers in low.humidity", "c:ionizers"),
        (r"limits EPA furniture/tools", "c:esd-furniture"),
        (r"avoid static.generating apparel", "c:apparel"),
        (r"ESD.approved gloves", "c:gloves"),
        (r"storage locations for ESDS items be labeled", "c:storage-labels"),
        (r"storage of ESDS items in static.shielding bags", "c:storage-bags"),
        (r"ESD.safe bins/containers and conductive foam", "c:storage-bins-foam"),
        (r"shelving/racks .* grounded", "c:grounded-shelving"),
        (r"mandates ESD.safe packaging for any internal or external movement", "c:packaging-all-movement"),
        (r"securing items inside static.shielding bags or rigid conductive", "c:secure-items"),
        (r"sealing ESD packaging with ESD.safe tape", "c:esd-tape"),
        (r"avoid non.ESD safe packing materials", "c:no-bubble-wrap"),
        (r"symbol used for ESD.compliant protective packaging", "c:packaging-symbol"),
        (r"ESD warning signs at EPA entry points", "c:sign-entry"),
        (r"ESD warning signs at storage cabinets", "c:sign-storage"),
        (r"ESD warning signs at ESD handling workstations", "c:sign-workstations"),
        (r"common.point ground connection", "c:common-point-ground"),
        (r"approval or sign.off block", "c:approval"),
        (r"low humidity increases ESD risk", "c:humidity"),
    ]
    return {
        "family": "distributor_policy_documents",
        "title": "Issue an ESD-sensitive component handling and storage SOP",
        "difficulty": "hard",
        "goal": "As warehouse manager, issue a standard operating procedure for handling and storing ESD-sensitive components that training can adopt.",
        "request": src.prompt,
        "artifact_type": "gdp_esd_sop",
        "fields": fields,
        "codes": catalog,
        "tables": [],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["shielding-outside-epa", "no-bubble-wrap", "grounding-tests"],
        "notes": [
            "The task has no reference files; controls are scored as catalog codes. Each code list carries a non-compliant distractor.",
            ("The expert SOP omits receiving controls, hand-off protection, and the humidity statement that the rubric requires; the "
            "oracle includes them."),
        ],
    }

# --- task 21: incident analysis deck ---------------------------------------------------------

INCIDENT_THEMES = [
    ("mil_std_noncompliance", "items not compliant with MIL-STD requirements", ("MIL-STD",)),
    ("wrong_part_or_quantity", "wrong part number, wrong item, wrong quantity, or missing hardware",
     ("correct Part Number", "Incorrect item", "Incorrect QTY", "required screws")),
    ("warehouse_handling_damage", "damage, packaging, or labeling errors caused in the warehouse",
     ("dropped", "forklift", "waterstained", "ESD", "labeled by the warehouse")),
    ("firmware_software", "incorrect firmware or software loads", ("firmware",)),
    ("product_quality_defects", "manufacturing or quality defects (welds, coatings, wear, tolerance, failed inspection)",
     ("weld", "paint", "scuffing", "wear", "tolerance", "quality inspection")),
]


def _theme(description: str) -> str:
    for code, _meaning, needles in INCIDENT_THEMES:
        if any(needle.lower() in description.lower() for needle in needles):
            return code
    raise ValueError(f"task 21 unthemed incident: {description}")


def t21_incident_analysis(src: SourceTask) -> Json:
    sheet = [row[:13] for row in xlsx_rows(src.ref("Inventory Incident Report"), "Sheet4")]
    header = list(sheet[0])
    require(header[2] == "Manufacturer" and header[6] == "Incident Type" and header[12] == "Resolution Cost", "task 21 header")
    incidents = [row for row in sheet[1:] if row[2]]
    require(len(incidents) == 50, f"task 21 incident count {len(incidents)}")
    counts: dict[str, int] = defaultdict(int)
    cost = {"rma": 0.0, "work_order": 0.0}
    days: dict[str, list[int]] = {"rma": [], "work_order": []}
    themes: dict[str, int] = defaultdict(int)
    for row in incidents:
        kind = "rma" if row[6] == "RMA" else "work_order"
        require(row[6] in ("RMA", "Work Order"), f"task 21 type {row[6]}")
        duration = (dt.date.fromisoformat(row[9]) - dt.date.fromisoformat(row[7])).days
        require(duration == row[10], f"task 21 duration {row}")
        counts[row[2]] += 1
        cost[kind] += row[12] or 0
        days[kind].append(duration)
        themes[_theme(row[11])] += 1
    total = len(incidents)
    order = sorted(counts, key=lambda name: (-counts[name], name))
    pct = {name: r2(100 * counts[name] / total) for name in order}
    total_cost = r2(cost["rma"] + cost["work_order"])
    avg = {
        "all": r2(sum(days["rma"] + days["work_order"]) / total),
        "work_order": r2(sum(days["work_order"]) / len(days["work_order"])),
        "rma": r2(sum(days["rma"]) / len(days["rma"])),
    }
    require(total_cost == 82567 and cost["rma"] == 4250 and avg == {"all": 23.02, "work_order": 19.72, "rma": 26.32}, f"task 21 {avg}")
    require([counts[name] for name in order[:3]] == [10, 9, 6], "task 21 top suppliers")
    theme_rank = sorted(themes, key=lambda code: (-themes[code], code))
    truth = {
        "analysis_year": 2025,
        "incident_type_basis": "incident_type_field",
        "incidents_by_supplier": {name: counts[name] for name in order},
        "total_incidents": total,
        "pct_by_supplier": pct,
        "cost": {
            "total": total_cost, "rma": r2(cost["rma"]), "work_order": r2(cost["work_order"]),
            "rma_share_pct": r2(100 * cost["rma"] / total_cost), "work_order_share_pct": r2(100 * cost["work_order"] / total_cost),
        },
        "avg_resolution_days": avg,
        "methods": {"duration": "close_minus_open_calendar_days", "average": "arithmetic_mean", "percentage": "supplier_over_total"},
        "outliers": {"policy": "included", "note": "Four junction-box RMAs (65 days) and the beam assembly work order (61 days) are "
                     "long-duration outliers; they are included in all averages."},
        "summary": {
            "total_cost": total_cost,
            "top_suppliers": order[:3],
            "avg_days_rma": avg["rma"],
            "avg_days_work_order": avg["work_order"],
            "longer_resolution_type": "rma" if avg["rma"] > avg["work_order"] else "work_order",
            "themes": [{"theme": code, "incident_count": themes[code]} for code in theme_rank],
            "recommendations": [
                {"recommendation": "Require MIL-STD certificates of conformance and add receiving inspection for Velcronix and Orionist Systems.",
                 "audience": "supplier_management", "metric_cited": "Orionist 18% and Velcronix 12% of incidents"},
                {"recommendation": "Open a corrective action with Aperion Defense on weld quality and part-number labeling.",
                 "audience": "supplier_management", "metric_cited": "Aperion Defense 10 incidents (20%)"},
                {"recommendation": "Retrain staff on ESD packaging, forklift use, and high-shelf storage for heavy items.",
                 "audience": "warehouse_management", "metric_cited": "work orders cost $78,317 of $82,567"},
            ],
        },
    }
    suppliers = list(order)
    fields = [
        field("analysis_year", "number", "Calendar year covered by the analysis."),
        field("incident_type_basis", "code", "How incidents are classified as RMA or work order."),
        field("incidents_by_supplier", "object<supplier,number>", "Incident count per supplier (manufacturer name as in the data)."),
        field("total_incidents", "number", "Total incidents."),
        field("pct_by_supplier", "object<supplier,number>", "Share of total incidents per supplier (0-100)."),
        field("cost", "object", "total, rma, work_order resolution cost, and rma_share_pct, work_order_share_pct (0-100); blank cost = 0."),
        field("avg_resolution_days", "object", "Average resolution days: all, work_order, rma."),
        field("methods", "object", "duration, average, percentage method codes."),
        field("outliers", "object", "policy (code) for long-duration incidents and a note."),
        field("summary.total_cost", "number", "Total incident cost restated on the summary."),
        field("summary.top_suppliers", "list[string]", "The three suppliers with the most incidents, highest first."),
        field("summary.avg_days_rma", "number", "Average RMA resolution days restated."),
        field("summary.avg_days_work_order", "number", "Average work-order resolution days restated."),
        field("summary.longer_resolution_type", "code", "Incident type with the longer average resolution time (rma or work_order)."),
        field("summary.themes", "list[object]", "Recurring issue themes from incident descriptions: theme (code), incident_count."),
        field("summary.recommendations", "list[object]", "Recommendations: recommendation, audience (code), metric_cited (analysis metric it relies on)."),
    ]
    catalog = {
        "incident_type_basis": codes(("incident_type_field", "the dataset's Incident Type field"), ("description_keywords", "keywords in descriptions")),
        "methods.duration": codes(("close_minus_open_calendar_days", "close date minus open date, calendar days"),
                                  ("business_days", "business days between open and close")),
        "methods.average": codes(("arithmetic_mean", "arithmetic mean"), ("median", "median")),
        "methods.percentage": codes(("supplier_over_total", "supplier incidents / total incidents"), ("supplier_over_type", "supplier incidents / incidents of its type")),
        "outliers.policy": codes(("included", "long-duration incidents included in averages and flagged"), ("excluded", "excluded from averages")),
        "summary.longer_resolution_type": codes(("rma", "RMA"), ("work_order", "work order")),
        "summary.themes[].theme": codes(*[(code, meaning) for code, meaning, _needles in INCIDENT_THEMES]),
        "summary.recommendations[].audience": codes(("supplier_management", "supplier management"), ("warehouse_management", "warehouse management")),
    }
    checks = [
        num("year", "analysis_year", 2025, 0),
        check("counts", "custom", "incidents_by_supplier", None, rule="map_numbers", values=truth["incidents_by_supplier"], tolerance=0),
        num("total-incidents", "total_incidents", total, 0),
        check("pcts", "custom", "pct_by_supplier", None, rule="map_numbers", values=pct, tolerance=0.5),
        check("supplier-set", "custom", rule="all_of", checks=[check("c", "keys", "incidents_by_supplier", suppliers),
                                                                check("p", "keys", "pct_by_supplier", suppliers)]),
        num("total-cost", "cost.total", total_cost, 0.5),
        num("cost-rma", "cost.rma", truth["cost"]["rma"], 0.5),
        num("cost-wo", "cost.work_order", truth["cost"]["work_order"], 0.5),
        check("cost-split", "custom", rule="all_of", checks=[
            num("r", "cost.rma", truth["cost"]["rma"], 0.5), num("w", "cost.work_order", truth["cost"]["work_order"], 0.5),
            num("rs", "cost.rma_share_pct", truth["cost"]["rma_share_pct"], 0.1),
            num("ws", "cost.work_order_share_pct", truth["cost"]["work_order_share_pct"], 0.1),
        ]),
        num("avg-all", "avg_resolution_days.all", avg["all"], 1),
        num("avg-wo", "avg_resolution_days.work_order", avg["work_order"], 1),
        num("avg-rma", "avg_resolution_days.rma", avg["rma"], 1),
        check("methods", "custom", rule="all_of", checks=[
            check("d", "text", "methods.duration", "close_minus_open_calendar_days"), check("a", "text", "methods.average", "arithmetic_mean"),
            check("p", "text", "methods.percentage", "supplier_over_total"),
        ]),
        check("type-basis", "text", "incident_type_basis", "incident_type_field"),
        check("reconcile", "custom", rule="all_of", checks=[
            num("t", "total_incidents", total, 0),
            check("c", "custom", "incidents_by_supplier", None, rule="map_numbers", values=truth["incidents_by_supplier"], tolerance=0),
            check("p", "custom", "pct_by_supplier", None, rule="map_numbers", values=pct, tolerance=0.5),
        ]),
        check("outliers", "text", "outliers.policy", "included"),
        num("summary-cost", "summary.total_cost", total_cost, 0.5),
        check("top-suppliers", "list", "summary.top_suppliers", order[:3]),
        check("summary-days", "custom", rule="all_of", checks=[
            num("r", "summary.avg_days_rma", avg["rma"], 1), num("w", "summary.avg_days_work_order", avg["work_order"], 1),
        ]),
        check("longer-type", "text", "summary.longer_resolution_type", "rma"),
        check("themes", "custom", "summary.themes", None, rule="records", min_count=2, nonempty=["theme"],
              allowed={"theme": [code for code, _m, _n in INCIDENT_THEMES]}, require_any={"theme": theme_rank[:2]},
              min_distinct={"theme": 2}),
        check("recommendations", "custom", "summary.recommendations", None, rule="records", min_count=3,
              nonempty=["recommendation", "audience"], require_values={"audience": ["supplier_management", "warehouse_management"]}),
        check("rec-metrics", "custom", "summary.recommendations", None, rule="records", some_nonempty=["metric_cited"]),
        check("summary-structure", "custom", rule="all_of", checks=[
            check("t", "nonempty", "summary.themes"), check("r", "nonempty", "summary.recommendations"),
        ]),
    ]
    for name in suppliers:
        checks.append(num(f"count-{slug(name)}", ["incidents_by_supplier", name], counts[name], 0))
        checks.append(num(f"pct-{slug(name)}", ["pct_by_supplier", name], pct[name], 0.5))
    rules = [
        (r"calendar year covered by the analysis as 2025", "c:year"),
        (r"slide that reports the number of incidents per supplier", "c:counts"),
        (r"incident count for (.+?) as exactly", "c:count-{1}"),
        (r"sum of supplier incident counts equals 50", "c:total-incidents"),
        (r"visual chart", "u:presentation"),
        (r"slide reporting the percentage of incidents per supplier", "c:pcts"),
        (r"percent of incidents for (.+?) as", "c:pct-{1}"),
        (r"supplier percentages sum to 100%", "c:pcts"),
        (r"total cost to resolve all incidents", "c:total-cost"),
        (r"total cost to resolve all RMAs", "c:cost-rma"),
        (r"total cost to resolve all Work Orders", "c:cost-wo"),
        (r"average resolution time for all incidents", "c:avg-all"),
        (r"average resolution time for Work Orders", "c:avg-wo"),
        (r"average resolution time for RMAs", "c:avg-rma"),
        (r"Computes duration in calendar days", "c:methods"),
        (r"final summary slide that synthesizes", "c:summary-structure"),
        (r"at least three actionable recommendations", "c:recommendations"),
        (r"recommendation explicitly references analysis metrics", "c:rec-metrics"),
        (r"set of suppliers reported matches exactly", "c:supplier-set"),
        (r"All figures .* are derived from the provided", "c:counts,pcts,total-cost,avg-all"),
        (r"slide title or heading on every slide", "u:presentation"),
        (r"Slide 1.s title", "u:presentation"),
        (r"appear on the same slide", "u:presentation"),
        (r"legible supplier labels", "u:presentation"),
        (r"Currency figures display", "u:presentation"),
        (r"presented together on a single slide", "u:presentation"),
        (r"summary slide restates the total incident cost", "c:summary-cost"),
        (r"summary slide identifies the three suppliers", "c:top-suppliers"),
        (r"summary slide restates the average days", "c:summary-days"),
        (r"compares average resolution times for RMAs vs Work Orders", "c:longer-type"),
        (r"top recurring issue themes", "c:themes"),
        (r"how incident types are classified", "c:type-basis"),
        (r"brief methods note", "c:methods"),
        (r"Supplier-level counts and percentages reconcile", "c:reconcile"),
        (r"total cost split by incident type", "c:cost-split"),
        (r"95th percentile", "c:outliers"),
    ]
    columns = ["part_number", "cage_code", "manufacturer", "description", "serial_number", "qty", "incident_type", "incident_date",
               "incident_status", "incident_closed_date", "duration_days", "incident_description", "resolution_cost"]
    return {
        "family": "distributor_inventory_planning",
        "title": "Analyze 2025 RMA and work-order incidents by supplier",
        "difficulty": "hard",
        "goal": "As inventory analyst, summarize 2025 inventory incidents by supplier, cost, and resolution time and recommend actions to supplier and warehouse management.",
        "request": src.prompt,
        "artifact_type": "gdp_incident_analysis",
        "fields": fields,
        "codes": catalog,
        "tables": [table("INCIDENTS", "Inventory incident report 2025 (RMAs and work orders)", "One row per incident; blank "
                         "resolution cost means no cost was recorded.", columns, [list(row) for row in incidents])],
        "documents": [],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["total-cost", "cost-split", "avg-all"],
        "notes": [
            "Blank resolution costs count as zero; durations recomputed from open/close dates match the dataset column.",
            ("Theme counts in the oracle come from keyword grouping of descriptions; the check requires catalog codes, at least two "
            f"distinct themes, and one of the two most frequent ({', '.join(theme_rank[:2])})."),
            "Chart, slide-title, and same-slide layout items are recorded unscored.",
        ],
    }


# --- task 22: receiving location report --------------------------------------------------------


def t22_location_report(src: SourceTask) -> Json:
    on_line = [row[:6] for row in xlsx_rows(src.ref("Inv on line")) if row and row[0]]
    require(on_line[0] == ("Item Number", "Description", "Line OH", "Line Location", "Min", "Max"), "task 22 inv header")
    log = [row[:8] for row in xlsx_rows(src.ref("Daily Receiving Log"))]
    require(str(log[0][0]).startswith("Date __6/24/25"), "task 22 log date")
    receipts = [row for row in log[2:] if row[2]]
    require([row[2] for row in receipts] == ["P21-L44S38-30", "P04-J63M12-40", "P07-P98K45-20"], "task 22 receipts")
    template = [row[:7] for row in xlsx_rows(src.ref("Blank Location Report"))]
    columns = list(template[1])
    require(columns == ["Item Rec'd", "Item Description", "Qty Rec'd", "Moved From", "Moved To", "Qty Moved", "Balance"], "task 22 template")
    half_item = "P07-P98K45-20"
    half = next(row for row in receipts if row[2] == half_item)
    require(half[5] * 2 == half[4], "task 22 half quantity")
    line_location = "A-300-K11"
    inventory = [list(row) for row in on_line[1:]]
    require(all(row[0] != half_item and row[3] != line_location for row in inventory), "task 22 line location collision")
    inventory.append([half_item, "INTERIOR RAIL, LEFT SIDE", 0, line_location, 50, 75])
    locations = {row[0]: row[3] for row in inventory}
    rows = []
    for row in receipts:
        rows.append({
            "item_received": row[2], "item_description": row[3], "qty_received": row[5], "moved_from": "Receiving Dock",
            "moved_to": locations.get(row[2]), "qty_moved": row[5], "balance": 0,
        })
    truth = {"report_date": "2025-06-24", "rows": rows}
    original = "To this point, only half the quantity of item P11-P09457-01 was received and was moved to its line location."
    require(original in src.prompt, "task 22 prompt sentence changed")
    request = src.prompt.replace(
        original,
        "To this point, only half the ordered quantity of item P07-P98K45-20 was received, and it was moved to its line location. "
        "The shipping department moved every unit received today out of its staging location; an item with no assigned line "
        "location in Inv on line has no Moved To location.",
    )
    fields = [
        field("report_date", "date", "Date of the location report (the receiving date)."),
        field("rows", "list[object]", "One row per item received today with the template columns: item_received, item_description, "
              "qty_received, moved_from (staging location), moved_to (assigned line location, or null when none is assigned), "
              "qty_moved, balance (qty_received - qty_moved)."),
    ]
    expected = {row["item_received"]: {k: v for k, v in row.items() if k not in ("item_received", "moved_from")} for row in rows}
    checks = [
        check("report-structure", "custom", rule="all_of", checks=[
            check("d", "text", "report_date", "2025-06-24"),
            check("r", "custom", "rows", None, rule="records", min_count=3,
                  nonempty=["item_received", "item_description", "qty_received", "moved_from", "qty_moved", "balance"]),
        ]),
        check("unique-items", "custom", "rows", None, rule="records", unique="item_received"),
        check("no-extra-items", "custom", "rows", None, rule="records",
              allowed={"item_received": [row["item_received"] for row in rows]}),
    ]
    for row in rows:
        item = row["item_received"]
        key = item.lower()
        expect = expected[item]

        def match(suffix: str, item: str = item, prefix: str = key, **values: Any) -> Json:
            return check(f"{prefix}-{suffix}", "custom", "rows", {item: values}, rule="rows_match", key="item_received",
                         exact_ids=False, tolerance=0)

        checks += [
            match("present"),
            match("description", item_description=expect["item_description"]),
            match("qty-received", qty_received=expect["qty_received"]),
            check(f"{key}-moved-from", "custom", rule="all_of", checks=[
                match("x"), check("f", "custom", "rows", None, rule="records", nonempty=["moved_from"]),
            ]),
            match("moved-to", moved_to=expect["moved_to"]),
            match("qty-moved", qty_moved=expect["qty_moved"]),
            match("balance", balance=expect["balance"]),
        ]
    rules = [
        (r"Output contains a single Excel", "u:file_format"),
        (r"includes the provided template sheet", "c:report-structure"),
        (r"includes ([A-Z0-9-]+) as one of the items", "c:{1}-present"),
        (r"includes ([A-Z0-9-]+) more than once", "c:unique-items"),
        (r"For item ([A-Z0-9-]+), includes .* in the Item Description", "c:{1}-description"),
        (r"For item ([A-Z0-9-]+), includes \d+ in the Qty Rec'd", "c:{1}-qty-received"),
        (r"For item ([A-Z0-9-]+), includes a non-empty value in the Moved From", "c:{1}-moved-from"),
        (r"For item ([A-Z0-9-]+), the Moved To column is left blank", "c:{1}-moved-to"),
        (r"For item ([A-Z0-9-]+), includes a line-location in the Moved To", "c:{1}-moved-to"),
        (r"For item ([A-Z0-9-]+), includes \d+ in the Qty Moved", "c:{1}-qty-moved"),
        (r"For item ([A-Z0-9-]+), includes 0 in the Balance", "c:{1}-balance"),
        (r"row where the Item Rec'd is not one of", "c:no-extra-items"),
    ]
    log_rows = [list(row) for row in receipts]
    return {
        "family": "distributor_warehouse_shipping",
        "title": "Post the daily receiving location report",
        "difficulty": "medium",
        "goal": "As inventory clerk, post the location report for today's receipts by cross-referencing the receiving log against assigned line locations.",
        "request": request,
        "artifact_type": "gdp_location_report",
        "fields": fields,
        "codes": {},
        "tables": [
            table("INVLINE", "Inv on line - assigned line locations", "Item number, description, line on-hand, assigned line location, min, max.",
                  ["item_number", "description", "line_oh", "line_location", "min", "max"], inventory),
            table("RECLOG", "Daily receiving log 6/24/25", "Items received today by PO.",
                  ["po", "supplier", "item", "item_description", "qty_ordered", "qty_received", "qty_backordered", "on_time"], log_rows),
        ],
        "documents": [document("TEMPLATE", "Blank location report template", "WMS", {"columns": columns, "header": "Date / Location Report"})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["unique-items", "no-extra-items", "p07-p98k45-20-moved-to"],
        "notes": [
            ("Upstream prompt names P11-P09457-01 as the half-received item, but it is not in the receiving log; P07-P98K45-20 "
            "(500 of 1,000 received) is the half-received item in the log and rubric, so the request was restated."),
            ("Upstream Inv on line has no row for P07-P98K45-20; the expert report moves it to A-300-K11, so that assignment was added "
            "to the line-location table. The two other items have no line location and their Moved To must be blank."),
            "Per the rubric, every received unit is moved (balance 0) and the expert's split row for P07-P98K45-20 is not required.",
        ],
    }


# --- task 23: daily shipment manifest ---------------------------------------------------------


def t23_shipment_manifest(src: SourceTask) -> Json:
    tickets = []
    workbook = openpyxl.load_workbook(src.ref("Pick Tickets"), read_only=True, data_only=True)
    sheet_names = [name for name in workbook.sheetnames if name.startswith("PT")]
    workbook.close()
    pick_rows = []
    for name in sheet_names:
        rows = [row[1:9] for row in xlsx_rows(src.ref("Pick Tickets"), name) if any(value is not None for value in row)]
        ticket, customer = rows[0][1], rows[1][1]
        lines = [row for row in rows[3:] if row[0]]
        weight = r2(sum(row[7] for row in lines))
        tickets.append((ticket, customer, weight))
        pick_rows += [[ticket, customer, *row] for row in lines]
    params = [row[2:6] for row in xlsx_rows(src.ref("Shipping parameters")) if any(value is not None for value in row)]
    require(params[0][1:] == ("< 25 lbs", "25.1 - 100 lbs", "> 100.1") and params[1][1:] == ("UPS", "Fed Ex", "Freight"), "task 23 params")
    actual = {"UPS": 5.95, "FedEx": 75.0, "Freight": 150.0}
    require(params[2][1:] == ("2.5 lbs = $5.95", "50 lbs = $75.00", "flat rate $150"), "task 23 TMS actual costs")
    industry = dict(zip(("UPS", "FedEx", "Freight"), params[3][1:]))

    def method(weight: float) -> str:
        if weight < 25:
            return "UPS"
        if weight <= 100:
            return "FedEx"
        return "Freight"

    shipments = []
    for ticket, customer, weight in tickets:
        carrier = method(weight)
        shipments.append({
            "pick_ticket": ticket, "customer": customer, "total_weight_lbs": weight, "shipping_method": carrier, "tracking_number": None,
            "shipment_details": {"UPS": "UPS, 1 box @ 2.5 lb", "FedEx": "FedEx, 2 boxes @ 25 lb each",
                                 "Freight": "LTL freight (XPO Trucking), 1 pallet @ 250 lb"}[carrier],
            "shipment_cost": actual[carrier], "industry_avg_cost": industry[carrier],
            "savings": r2(industry[carrier] - actual[carrier]),
        })
    require([s["pick_ticket"] for s in shipments] == ["A-1001", "B-5005", "C-2001"], "task 23 tickets")
    require([s["savings"] for s in shipments] == [2.0, 75.0, 4.99], "task 23 savings")
    totals = {key: r2(sum(s[field_name] for s in shipments)) for key, field_name in
              (("actual", "shipment_cost"), ("industry_avg", "industry_avg_cost"), ("savings", "savings"))}
    require(totals == {"actual": 230.95, "industry_avg": 312.94, "savings": 81.99}, f"task 23 totals {totals}")
    truth = {"manifest_date": "2025-06-25", "shipments": shipments, "totals": totals}
    fields = [
        field("manifest_date", "date", "Manifest date."),
        field("shipments", "list[object]", "One row per pick ticket with the template columns: pick_ticket, customer, total_weight_lbs, "
              "shipping_method (code), tracking_number (string or null if not yet assigned), shipment_details (carrier, packages, "
              "weight), shipment_cost (actual, from the TMS capture), industry_avg_cost, savings (industry_avg_cost - shipment_cost)."),
        field("totals", "object", "actual, industry_avg, savings totals over all rows."),
    ]
    catalog = {"shipments[].shipping_method": codes(("UPS", "UPS parcel"), ("FedEx", "FedEx parcel"), ("Freight", "LTL freight"))}
    expected = {s["pick_ticket"]: s for s in shipments}

    def rows(check_id: str, *names: str, tolerance: float = 0.01) -> Json:
        return check(check_id, "custom", "shipments", {t: {n: s[n] for n in names} for t, s in expected.items()}, rule="rows_match",
                     key="pick_ticket", tolerance=tolerance)

    checks = [
        check("manifest-date", "text", "manifest_date", "2025-06-25"),
        check("template-fields", "custom", "shipments", None, rule="records", min_count=1,
              nonempty=["pick_ticket", "customer", "total_weight_lbs", "shipping_method", "shipment_details", "shipment_cost",
                        "industry_avg_cost", "savings"]),
        check("min-tickets", "custom", "shipments", None, rule="records", min_count=3, unique="pick_ticket"),
        rows("ticket-set"),
        check("no-duplicates", "custom", "shipments", None, rule="records", unique="pick_ticket"),
        rows("weights", "total_weight_lbs"),
        rows("methods", "shipping_method"),
        check("method-names", "custom", "shipments", None, rule="records", allowed={"shipping_method": ["UPS", "FedEx", "Freight"]}),
        rows("actual-costs", "shipment_cost"),
        rows("industry-costs", "industry_avg_cost"),
        check("savings-formula", "custom", "shipments", None, rule="record_formula", target="savings", formula="difference",
              a="industry_avg_cost", b="shipment_cost"),
        num("total-actual", "totals.actual", totals["actual"]),
        num("total-industry", "totals.industry_avg", totals["industry_avg"]),
        num("total-savings", "totals.savings", totals["savings"]),
        check("savings-reconcile", "custom", rule="all_of", checks=[
            num("i", "totals.industry_avg", totals["industry_avg"]), num("a", "totals.actual", totals["actual"]),
            num("s", "totals.savings", totals["savings"]),
        ]),
        rows("numeric-costs", "shipment_cost", "industry_avg_cost", "savings"),
        check("row-ids", "custom", "shipments", None, rule="records", nonempty=["pick_ticket"]),
        check("row-values", "custom", "shipments", None, rule="records",
              nonempty=["total_weight_lbs", "shipping_method", "shipment_cost", "industry_avg_cost", "savings"]),
        rows("customers", "customer"),
    ]
    for ticket, row in expected.items():
        key = ticket.lower()

        def one(suffix: str, *names: str, ticket: str = ticket, row: Json = row, prefix: str = key) -> Json:
            return check(f"{prefix}-{suffix}", "custom", "shipments", {ticket: {n: row[n] for n in names}}, rule="rows_match",
                         key="pick_ticket", exact_ids=False)

        checks += [
            one("present"), one("customer", "customer"), one("weight", "total_weight_lbs"), one("method", "shipping_method"),
            one("actual", "shipment_cost"), one("industry", "industry_avg_cost"),
            check(f"{key}-savings", "custom", rule="all_of", checks=[
                one("s", "savings"), one("f", "industry_avg_cost", "shipment_cost"),
            ]),
            check(f"{key}-details", "custom", rule="all_of", checks=[
                one("p"), check("d", "custom", "shipments", None, rule="records", nonempty=["shipment_details"]),
            ]),
        ]
    rules = [
        (r"Delivers the final output as a single Excel", "u:file_format"),
        (r"filled copy of the reference template", "c:template-fields,manifest-date"),
        (r"worksheet includes the template.s header fields", "c:template-fields"),
        (r"at least three unique Pick Ticket IDs", "c:min-tickets"),
        (r"set of Pick Ticket IDs in the manifest matches", "c:ticket-set"),
        (r"No Pick Ticket ID is duplicated", "c:no-duplicates"),
        (r"Weight \(lbs\) in the manifest equals the shipment weight", "c:weights"),
        (r"All Weight \(lbs\) entries are numeric", "c:weights"),
        (r"selected Shipping Method conforms to the weight-based rules", "c:methods"),
        (r"Shipment Cost equals the applicable method", "c:actual-costs"),
        (r"Industry Average Cost equals the applicable method", "c:industry-costs"),
        (r"correct tier is selected", "c:methods"),
        (r"Savings equals Industry Average Cost minus Actual Shipping Cost for every row", "c:savings-formula"),
        (r"Total Actual Shipping Costs", "c:total-actual"),
        (r"Total Industry Average equals", "c:total-industry"),
        (r"Total Savings equals the sum", "c:total-savings"),
        (r"Total Savings also equals", "c:savings-reconcile"),
        (r"Columns for costs .* contain numeric values", "c:numeric-costs"),
        (r"Every populated row has a non.blank Pick Ticket", "c:row-ids"),
        (r"Every populated row has non.blank entries", "c:row-values"),
        (r"formatted as USD currency", "u:presentation"),
        (r"If a Percent Savings column is present", "u:not_applicable"),
        (r"If an Actual Cost per Pound column", "u:not_applicable"),
        (r"weight falls outside all ranges", "u:not_applicable"),
        (r"Shipping Method entries, if validated", "c:method-names"),
        (r"Customer Name values match", "c:customers"),
        (r"template metadata cells", "c:manifest-date"),
        (r"Header row is optionally frozen", "u:workbook_mechanics"),
        (r"manifest includes a row for Pick Ticket ([A-C]-\d+)", "c:{1}-present"),
        (r"For ([A-C]-\d+), Customer Name", "c:{1}-customer"),
        (r"For ([A-C]-\d+), Weight", "c:{1}-weight"),
        (r"For ([A-C]-\d+), Method is", "c:{1}-method"),
        (r"For ([A-C]-\d+), Actual Shipping Cost", "c:{1}-actual"),
        (r"For ([A-C]-\d+), Industry Average Cost", "c:{1}-industry"),
        (r"For ([A-C]-\d+), Savings equals", "c:{1}-savings"),
        (r"For ([A-C]-\d+), Tracking #", "u:not_applicable"),
        (r"For ([A-C]-\d+), Shipment Details", "c:{1}-details"),
    ]
    param_rows = [[band, name, cost, avg] for band, name, cost, avg in zip(params[0][1:], params[1][1:], params[2][1:], params[3][1:])]
    return {
        "family": "distributor_warehouse_shipping",
        "title": "Build the daily shipment manifest with weight-based carrier selection",
        "difficulty": "medium",
        "goal": "As shipping clerk, build the 06/25/25 shipment manifest choosing the carrier by weight and recording actual versus industry-average cost savings.",
        "request": src.prompt,
        "artifact_type": "gdp_shipment_manifest",
        "fields": fields,
        "codes": catalog,
        "tables": [
            table("PICKS", "Pick tickets 06/25/25 (WMS)", "Pick ticket lines with ship-to customer and line weights.",
                  ["pick_ticket", "ship_to", "item", "item_description", "location", "item_lbs", "qty_ordered", "qty_picked", "qty_backordered",
                   "total_weight_lbs"], pick_rows),
            table("SHIPPARAM", "Shipping parameters (TMS capture)", "Weight band, carrier method, actual shipment cost as captured "
                  "from the TMS for today's shipment in that band, and industry average cost.",
                  ["weight_band", "method", "tms_shipment_cost", "industry_avg_cost"], param_rows),
        ],
        "documents": [document("TEMPLATE", "Blank daily shipment manifest template", "TMS", {
            "columns": ["Pick Ticket #", "Customer", "Total Weight lbs", "Shipping Method", "Tracking #", "Shipment Details",
                        "Shipment Cost", "Industry Avg Cost", "Savings"], "header": "Date / Shipment Manifest"})],
        "truth": truth,
        "checks": checks,
        "rules": rules,
        "economics": ["total-savings", "methods", "actual-costs"],
        "notes": [
            "Tracking numbers are not in the sources (blank allowed), so the tracking items cannot discriminate and are not applicable.",
            ("Package counts and the LTL carrier in the expert shipment details are not derivable from the sources; details are "
            "scored as present for each ticket."),
            "Optional percent-savings and cost-per-pound columns are outside the contract; no weight falls outside the bands.",
        ],
    }

# --- assembly ------------------------------------------------------------------------

TASKS: list[tuple[str, TaskBuilder]] = [
    ("62f04c2f-e0f7-4710-876c-54ee9c2e8256", t01_exchange_program),
    ("e996036e-8287-4e7f-8d0a-90a57cb53c45", t02_terms_scenarios),
    ("f841ddcf-2a28-4f6d-bac3-61b607219d3e", t03_po_log),
    ("47ef842d-8eac-4b90-bda8-dd934c228c96", t04_weeks_of_supply),
    ("1137e2bb-bdf9-4876-b572-f29b7de5e595", t05_po_entry_audit),
    ("c3525d4d-2012-45df-853e-2d2a0e902991", t06_floorstand_budget),
    ("b3573f20-5d3e-4954-948f-9461fda693d2", t07_brand_questionnaire),
    ("a69be28f-9a84-47c9-992e-b90446cdca9d", t08_territory_fit),
    ("74ed1dc7-1468-48a8-9071-58775c0d667a", t09_order_types),
    ("69a8ef86-4e69-4fe2-9168-080f1e978e67", t10_return_process),
    ("ab81b076-e5d8-473a-9bdb-7ea7c38f6ebc", t11_receiving_procedure),
    ("d7cfae6f-4a82-4289-955e-c799dfe1e0f4", t12_set_selling),
    ("19403010-3e5c-494e-a6d3-13594e99f6af", t13_xr_makeup),
    ("7ed932dd-244f-4d61-bf02-1bc3bab1af14", t14_stockout_plan),
    ("105f8ad0-8dd2-422f-9e88-2be5fbd2b215", t15_fragrance_pricing),
    ("15d37511-75c5-4c7f-81f1-16e00c0d95f3", t16_marketplace_pro_forma),
    ("bb863dd9-31c2-4f64-911a-ce11f457143b", t17_iehk_quotation),
    ("6a900a40-8d2b-4064-a5b1-13a60bc173d8", t18_revised_transport_quote),
    ("5349dd7b-bf0a-4544-9a17-75b7013767e6", t19_carrier_flat_rates),
    ("a4a9195c-5ebe-4b8d-a0c2-4a6b7a49da8b", t20_esd_sop),
    ("552b7dd0-96f4-437c-a749-0691e0e4b381", t21_incident_analysis),
    ("11dcc268-cb07-4d3a-a184-c6d7a19349bc", t22_location_report),
    ("76418a2c-a3c0-4894-b89d-2493369135d9", t23_shipment_manifest),
]

DELIVERY_NOTE = (
    "This request originally asked for office files. In this environment the deliverable is one structured artifact "
    "following the submission_contract section; file type, page layout, charts, and styling are not graded. "
    "Reference attachments named in the request are available as case files and query_gdp_table tables."
)


def _prompt(spec: Json, ids: Json) -> str:
    family = FAMILIES[spec["family"]]
    roles = " and ".join(family["roles"])
    sources = "the brief case file " + ids["brief"]
    if spec["documents"]:
        sources += ", the supporting case files"
    if spec["tables"]:
        sources += ", and the reference tables (list_gdp_tables, query_gdp_table)"
    return (
        f"{spec['goal']} Work incident {ids['incident']}: review {sources}. Record the deliverable as one "
        f"{spec['artifact_type']} structured artifact whose content follows the brief's submission_contract and cites the "
        f"case-file sections you relied on. Then request approval for {family['action']} on {ids['deliverable']} with "
        f"payload artifact_id set to your artifact, execute it once approved, notify {roles} with the headline result "
        "using those canonical role identifiers, and finish citing the artifact and deliverable IDs."
    )


def _weights(checks: list[Json], rubric: list[Json]) -> None:
    totals: dict[str, float] = defaultdict(float)
    for item in rubric:
        if item["status"] != "scored" or item["score"] <= 0:
            continue
        share = item["score"] / len(item["criteria"])
        for criterion in item["criteria"]:
            totals[criterion] += share
    for row in checks:
        row["weight"] = round(totals.get(row["id"], 0.0), 4) or 1.0


def assemble(index: int, src: SourceTask, spec: Json) -> tuple[Json, Json, Json]:
    prefix = f"GDP-{index:03d}"
    ids = {
        "incident": f"GDP-INC-{index:03d}",
        "deliverable": f"DLV-GDP-{index:03d}",
        "brief": f"CF-{prefix}-BRIEF",
    }
    family = FAMILIES[spec["family"]]
    contract = {
        "artifact_type": spec["artifact_type"],
        "deliverable_id": ids["deliverable"],
        "fields": spec["fields"],
        "conventions": GENERAL_CONVENTIONS,
    }
    brief_sections: Json = {
        "request": {"role_request": spec["request"], "delivery_note": DELIVERY_NOTE},
        "submission_contract": contract,
    }
    if spec["codes"]:
        brief_sections["code_catalog"] = spec["codes"]
    case_files = [
        {"id": ids["brief"], "title": f"Request brief: {spec['title']}", "system": "DMS", "sections": brief_sections}
    ]
    for item in spec["documents"]:
        case_files.append(
            {"id": f"CF-{prefix}-{item['suffix']}", "title": item["title"], "system": item["system"], "sections": item["sections"]}
        )
    tables = [
        {
            "id": f"TBL-{prefix}-{item['suffix']}",
            "title": item["title"],
            "description": item["description"],
            "columns": item["columns"],
            "rows": item["rows"],
        }
        for item in spec["tables"]
    ]
    check_ids = [row["id"] for row in spec["checks"]]
    require(len(set(check_ids)) == len(check_ids), f"{src.task_id}: duplicate check ids")
    for row in spec["checks"]:
        passed, detail = evaluate(row, spec["truth"])
        require(passed, f"{src.task_id}: truth fails {row['id']}: {detail}")
    rubric = classify(src.rubric, spec["rules"], check_ids)
    checks = [dict(row) for row in spec["checks"]]
    _weights(checks, rubric)
    for name in spec["economics"]:
        require(name in check_ids, f"{src.task_id}: economics check {name} missing")
    task_id = f"faraday-gdpval-{index:03d}"
    occupation = slug(src.row["occupation"])
    task_fixture = {
        "index": index,
        "task_id": task_id,
        "upstream_task_id": src.task_id,
        "family": spec["family"],
        "occupation": src.row["occupation"],
        "sector": src.row["sector"],
        "title": spec["title"],
        "incident": {
            "id": ids["incident"],
            "type": "gdp_deliverable_request",
            "status": "open",
            "summary": spec["goal"],
            "deliverable_id": ids["deliverable"],
            "artifact_type": spec["artifact_type"],
            "brief_file_id": ids["brief"],
            "protected_action": family["action"],
        },
        "case_files": case_files,
        "tables": tables,
    }
    required_reads = [[case_file["id"], section] for case_file in case_files for section in sorted(case_file["sections"])]
    grader_fixture = {
        "task_id": task_id,
        "upstream_task_id": src.task_id,
        "artifact_type": spec["artifact_type"],
        "truth": spec["truth"],
        "checks": checks,
        "economics": spec["economics"],
        "required_reads": required_reads,
        "required_tables": [item["id"] for item in tables],
        "rubric": rubric,
        "research_frozen": spec.get("research_frozen", ""),
        "notes": spec["notes"],
    }
    manifest = {
        "id": task_id,
        "version": VERSION,
        "family": spec["family"],
        "title": spec["title"],
        "prompt": _prompt(spec, ids),
        "seed": 300000 + index,
        "difficulty": spec["difficulty"],
        "systems": list(spec.get("systems", family["systems"])),
        "max_tool_calls": 40,
        "horizon_minutes": 90,
        "tags": ["source:gdpval", f"upstream:{src.task_id}", f"occupation:{occupation}"],
    }
    return task_fixture, grader_fixture, manifest


def _dump(value: Any, *, compact: bool) -> str:
    if compact:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def run(benchmarks_root: Path, repo_root: Path) -> None:
    index_rows = {
        row["task_id"]: row
        for row in json.loads((benchmarks_root / "distributor-index" / "tasks.json").read_text(encoding="utf-8"))
        if row.get("benchmark") == SOURCE
    }
    fixture_dir = repo_root / "src" / "faraday_industrial_benchmark" / "distributor" / "fixtures" / SOURCE
    fixture_dir.mkdir(parents=True, exist_ok=True)
    for stale in fixture_dir.glob("*.json"):
        stale.unlink()
    written: list[Path] = []
    manifest: list[Json] = []
    for index, (upstream_id, builder) in enumerate(TASKS, start=1):
        src = SourceTask(benchmarks_root, index_rows[upstream_id])
        spec = builder(src)
        task_fixture, grader_fixture, row = assemble(index, src, spec)
        for name, payload, compact in (
            (f"task-{index:03d}", task_fixture, True),
            (f"grader-{index:03d}", grader_fixture, False),
        ):
            path = fixture_dir / f"{name}.json"
            path.write_text(_dump(payload, compact=compact), encoding="utf-8")
            written.append(path)
        manifest.append(row)
    manifest_path = repo_root / "data" / "distributor-gdpval" / "tasks.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(manifest_path)
    write_provenance(SOURCE, UPSTREAM, written)
