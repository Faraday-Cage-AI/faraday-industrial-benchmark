"""Read-only verifier for the disclosed professional-review XLSX template.

Never executes macros, external links or spreadsheet code. Evaluates only the
small arithmetic/SUM formula language declared by this submission contract.
"""

import ast
import posixpath
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def read_workbook(path):
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 1000 or sum(e.file_size for e in entries) > 20_000_000:
            raise ValueError("workbook exceeds verification size limit")
        if len({e.filename for e in entries}) != len(entries):
            raise ValueError("duplicate ZIP members")
        if any(
            "externallink" in e.filename.lower() or "vbaproject" in e.filename.lower()
            for e in entries
        ):
            raise ValueError("external links and macros are not permitted")

        def xml(name):
            data = archive.read(name)
            if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                raise ValueError("XML declarations are not permitted")
            return ET.fromstring(data)

        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(n.itertext()) for n in xml("xl/sharedStrings.xml").findall("s:si", NS)
            ]
        relationships = {}
        for row in xml("xl/_rels/workbook.xml.rels"):
            if row.attrib.get("TargetMode") == "External":
                raise ValueError("external relationship")
            target = row.attrib["Target"]
            relationships[row.attrib["Id"]] = (
                target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            )
        sheets = {}
        for sheet in xml("xl/workbook.xml").findall("s:sheets/s:sheet", NS):
            name = sheet.attrib["name"]
            if name in sheets:
                raise ValueError("duplicate worksheet name")
            cells = {}
            for cell in xml(relationships[sheet.attrib[f"{{{REL}}}id"]]).findall(".//s:c", NS):
                address = cell.attrib["r"]
                if address in cells:
                    raise ValueError("duplicate cell")
                raw = cell.findtext("s:v", default="", namespaces=NS)
                kind = cell.attrib.get("t", "n")
                if kind == "s":
                    value = strings[int(raw)]
                elif kind == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif kind == "n" and raw:
                    value = Decimal(raw)
                    if not value.is_finite():
                        raise ValueError("nonfinite cell")
                else:
                    value = raw or None
                cells[address] = {"value": value, "formula": cell.findtext("s:f", namespaces=NS)}
            sheets[name] = cells
        return sheets


def calculate(cells, address, overrides=None, visiting=None):
    overrides, visiting = overrides or {}, visiting or set()
    if address in overrides:
        return Decimal(str(overrides[address]))
    if address in visiting or len(visiting) > 50:
        raise ValueError("cyclic or excessively deep formula")
    cell = cells[address]
    formula = cell["formula"]
    if not formula:
        if not isinstance(cell["value"], Decimal):
            raise ValueError("numeric input required")
        return cell["value"]
    if len(formula) > 2000:
        raise ValueError("formula exceeds limit")
    formula = formula.lstrip("=").replace("$", "")

    def expand(match):
        column, start, other, end = match.groups()
        if column != other or not 0 <= int(end) - int(start) <= 100:
            raise ValueError("unsupported SUM range")
        return "(" + "+".join(f"{column}{i}" for i in range(int(start), int(end) + 1)) + ")"

    formula = re.sub(r"SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)", expand, formula, flags=re.IGNORECASE)
    tree = ast.parse(formula, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(str(node.value))
        if isinstance(node, ast.Name) and re.fullmatch(r"[A-Z]+[1-9]\d*", node.id):
            return calculate(cells, node.id, overrides, visiting | {address})
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise ValueError("unsupported formula syntax")

    return evaluate(tree)


class ReportText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data.strip())


def verify_native(task, workbook_path, report_path):
    from .scenarios import build_scenario

    truth = next(iter(build_scenario(task).state["operating_review_truth"].values()))[
        "artifact_contents"
    ]
    impact = truth["integrated_recovery_model"]["financial_impact"]
    sheets = read_workbook(workbook_path)
    checks = []

    def check(name, passed):
        checks.append({"id": name, "passed": bool(passed)})

    def numeric(cells, cell, expected, name):
        actual = calculate(cells, cell)
        check(name, abs(actual - Decimal(str(expected))) < Decimal("0.000001"))
        if cells[cell]["formula"]:
            cached = cells[cell]["value"]
            check(
                name + "-cache",
                isinstance(cached, Decimal) and abs(actual - cached) < Decimal("0.000001"),
            )

    financial = sheets["Financial review"]
    components = [
        impact[k]
        for k in (
            "disposal_cost",
            "inspection_cost",
            "recovery_production_cost",
            "supplier_expedite_cost",
            "premium_freight",
            "customer_penalty_exposure",
        )
    ]
    components += [
        -impact["insurance_recovery"],
        impact.get("finance_bridge", {}).get("expense_cents", 0) / 100,
    ]
    for index, amount in enumerate(components, 6):
        numeric(financial, f"B{index}", amount, f"reserve-input-{index}")
    numeric(financial, "B15", impact["reserve_amount"], "reserve")
    check("reserve-formula", bool(financial["B15"]["formula"]))
    for index in range(6, 14):
        value = calculate(financial, f"B{index}")
        check(
            f"reserve-dependency-{index}",
            calculate(financial, "B15", {f"B{index}": value + 1})
            == calculate(financial, "B15") + 1,
        )
    bridge = impact.get("finance_bridge", {})
    numeric(financial, "B17", bridge.get("settled_cash_cents", 0) / 100, "settled-cash")
    numeric(financial, "B18", bridge.get("remaining_payable_cents", 0) / 100, "payable")
    check("payable-formula", bool(financial["B18"]["formula"]))
    check(
        "payable-cash-dependency",
        calculate(financial, "B18", {"B17": calculate(financial, "B17") + 1})
        == calculate(financial, "B18") - 1,
    )
    customer = sheets["Customer schedule"]
    expected_orders = truth["customer_commitment_schedule"]["orders"]
    check(
        "customer-row-count",
        sum(
            bool(cell["value"])
            for address, cell in customer.items()
            if re.fullmatch(r"A\d+", address) and int(address[1:]) >= 5
        )
        == len(expected_orders),
    )
    for index, row in enumerate(truth["customer_commitment_schedule"]["orders"], 5):
        check(f"order-{index}", customer[f"A{index}"]["value"] == row["order_id"])
        for column, field in (
            ("B", "requested_quantity"),
            ("C", "committed_quantity"),
            ("D", "shortfall_quantity"),
        ):
            numeric(customer, f"{column}{index}", row[field], f"order-{index}-{field}")
        check(f"order-{index}-status", customer[f"F{index}"]["value"] == row["status"])
        check(f"order-{index}-formula", bool(customer[f"D{index}"]["formula"]))
        check(
            f"order-{index}-arrival",
            customer.get(f"E{index}", {}).get("value") == row["latest_arrival_minute"],
        )
        check(
            f"order-{index}-shortfall-dependency",
            calculate(customer, f"D{index}", {f"C{index}": calculate(customer, f"C{index}") + 1})
            == calculate(customer, f"D{index}") - 1,
        )
    data = Path(report_path).read_bytes()
    if len(data) > 2_000_000:
        raise ValueError("report exceeds size limit")
    parser = ReportText()
    parser.feed(data.decode("utf-8"))
    text = " ".join(parser.text)
    check("report-reserve", f"Reserve: USD {impact['reserve_amount']:.2f}" in text)
    check("report-case", truth["integrated_recovery_model"]["case_id"] in text)
    check("report-decision", truth["executive_decision_brief"]["decision_status"] in text)
    return {
        "task": task.id,
        "strict_success": all(c["passed"] for c in checks),
        "checks": checks,
        "scope": "fixed-template arithmetic and report-text verification; not visual or arbitrary Excel evaluation",
    }
