"""GDPval-derived distributor families.

Twenty-three curated GDPval wholesale and distribution tasks are rebuilt as
tool-world episodes. Each episode exposes a request brief (with a submission
contract and code catalog), supporting case files, and queryable reference
tables. The agent records one structured artifact, releases it through a
protected ``*_gdp_*`` action after approval, and notifies the family's roles.

Fixtures come from ``examples/distributor_import/gdpval.py``; sealed field
checks live in ``gdpval_checks`` and are graded against the latest artifact
of the requested type.
"""

from __future__ import annotations

import re
from typing import Any

from ..extensions import (
    FamilyExtension,
    register_action,
    register_check,
    register_family,
    register_tool,
    tool,
)
from ..scenarios import ScenarioInstance, _base_state, _case_file, _criterion, _economics
from .fixtures import load_fixture
from .gdpval_checks import evaluate, norm_key, resolve, to_number

Json = dict[str, Any]
SOURCE = "gdpval"

FAMILY_SPECS: dict[str, Json] = {
    "distributor_sales_analytics": {
        "action": "publish_gdp_analysis",
        "roles": ("sales_operations", "demand_planning"),
        "description": "Wholesale order, sell-through, and account analytics rebuilt from GDPval.",
    },
    "distributor_pricing_quotation": {
        "action": "issue_gdp_quotation",
        "roles": ("sales_operations", "controller"),
        "description": "Wholesale terms, pricing, pro forma, and export quotation work rebuilt from GDPval.",
    },
    "distributor_inventory_planning": {
        "action": "release_gdp_inventory_plan",
        "roles": ("inventory_control", "supply_planning"),
        "description": "Distributor inventory, replenishment, and incident-cost planning rebuilt from GDPval.",
    },
    "distributor_warehouse_shipping": {
        "action": "post_gdp_warehouse_record",
        "roles": ("warehouse_operations", "transportation"),
        "description": "Receiving, put-away, carrier, and shipment-manifest work rebuilt from GDPval.",
    },
    "distributor_policy_documents": {
        "action": "issue_gdp_procedure",
        "roles": ("sales_operations", "warehouse_operations"),
        "description": "Distributor policies, procedures, and process proposals rebuilt from GDPval.",
    },
}

TOOLS = (
    "get_incident",
    "list_case_files",
    "read_case_file",
    "list_gdp_tables",
    "query_gdp_table",
    "create_structured_artifact",
    "get_structured_artifact",
    "get_gdp_shape_report",
    "request_approval",
    "execute_action",
    "notify",
    "wait",
    "finish",
)

MAX_ROWS = 500
_FILTER_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "between", "is_blank", "not_blank"}
_METRIC_OPS = {"count", "sum", "avg", "min", "max", "count_distinct"}


def task_index(task_id: str) -> int:
    match = re.fullmatch(r"faraday-gdpval-(\d{3})", task_id)
    if not match:
        raise ValueError(f"not a GDPval task id: {task_id}")
    return int(match.group(1))


def task_fixture(task_id: str) -> Json:
    return load_fixture(SOURCE, f"task-{task_index(task_id):03d}")


def grader_fixture(task_id: str) -> Json:
    return load_fixture(SOURCE, f"grader-{task_index(task_id):03d}")


# --- tools ---------------------------------------------------------------------------


def _list_tables(world) -> Json:
    tables = [
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "columns": list(row["columns"]),
            "row_count": len(row["rows"]),
        }
        for row in sorted(world.state.get("gdp_tables", {}).values(), key=lambda item: item["id"])
    ]
    return {"ok": True, "tables": tables}


def _comparable(left: Any, right: Any) -> tuple[Any, Any]:
    """Compare numerically when either side is a number, else as lowercase text (ISO dates sort as text)."""

    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        left_number, right_number = to_number(left), to_number(right)
        if left_number is not None and right_number is not None:
            return left_number, right_number
    return str(left).lower(), str(right).lower()


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _matches(value: Any, op: str, operand: Any) -> bool:
    if op == "is_blank":
        return _blank(value)
    if op == "not_blank":
        return not _blank(value)
    if _blank(value):
        return op in {"ne", "not_in"}
    if op in {"in", "not_in"}:
        options = operand if isinstance(operand, list) else [operand]
        hit = any(_comparable(value, option)[0] == _comparable(value, option)[1] for option in options)
        return hit if op == "in" else not hit
    if op == "contains":
        return str(operand).lower() in str(value).lower()
    if op == "between":
        if not isinstance(operand, list) or len(operand) != 2:
            raise ValueError("between needs [low, high]")
        low, high = operand
        left, low_value = _comparable(value, low)
        _, high_value = _comparable(value, high)
        return low_value <= left <= high_value
    left, right = _comparable(value, operand)
    try:
        return {
            "eq": left == right,
            "ne": left != right,
            "gt": left > right,
            "gte": left >= right,
            "lt": left < right,
            "lte": left <= right,
        }[op]
    except TypeError:
        return False


def _round(value: Any) -> Any:
    return round(value, 6) if isinstance(value, float) else value


def _query_table(
    world,
    table_id: str,
    filters: list[Json] | None = None,
    columns: list[str] | None = None,
    group_by: list[str] | None = None,
    metrics: list[Json] | None = None,
    order_by: str | None = None,
    descending: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> Json:
    table = world.state.get("gdp_tables", {}).get(table_id)
    if table is None:
        return {"ok": False, "error": "table_not_found"}
    names = list(table["columns"])
    position = {name: index for index, name in enumerate(names)}
    for name in [*(columns or []), *(group_by or []), *([order_by] if order_by else [])]:
        if name not in position:
            return {"ok": False, "error": "unknown_column", "column": name, "columns": names}
    rows = table["rows"]
    for condition in filters or []:
        column, op = condition.get("column"), condition.get("op", "eq")
        if column not in position or op not in _FILTER_OPS:
            return {"ok": False, "error": "invalid_filter", "filter": condition, "ops": sorted(_FILTER_OPS)}
        index = position[column]
        rows = [row for row in rows if _matches(row[index], op, condition.get("value"))]
    if not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS or not isinstance(offset, int) or offset < 0:
        return {"ok": False, "error": "invalid_page", "max_limit": MAX_ROWS}
    if group_by or metrics:
        metric_specs = metrics or [{"op": "count"}]
        for metric in metric_specs:
            if metric.get("op") not in _METRIC_OPS or (metric.get("op") != "count" and metric.get("column") not in position):
                return {"ok": False, "error": "invalid_metric", "metric": metric, "ops": sorted(_METRIC_OPS)}
        groups: dict[tuple, list] = {}
        keys = group_by or []
        for row in rows:
            groups.setdefault(tuple(row[position[key]] for key in keys), []).append(row)
        output = []
        for group_key in sorted(groups, key=lambda item: [str(part) for part in item]):
            members = groups[group_key]
            record = dict(zip(keys, group_key))
            for metric in metric_specs:
                op, column = metric["op"], metric.get("column")
                label = metric.get("as") or (f"{op}_{column}" if column else op)
                values = [member[position[column]] for member in members] if column else members
                numbers = [number for number in (to_number(value) for value in values) if number is not None] if column else []
                if op == "count":
                    result: Any = len([value for value in values if not _blank(value)]) if column else len(members)
                elif op == "count_distinct":
                    result = len({str(value) for value in values if not _blank(value)})
                elif op == "sum":
                    result = sum(numbers)
                elif op == "avg":
                    result = sum(numbers) / len(numbers) if numbers else None
                elif op == "min":
                    result = min(numbers) if numbers else None
                else:
                    result = max(numbers) if numbers else None
                record[label] = _round(result)
            output.append(record)
        return {"ok": True, "table_id": table_id, "group_count": len(output), "groups": output[offset: offset + limit]}
    if order_by:
        index = position[order_by]
        rows = sorted(rows, key=lambda row: (_blank(row[index]), _comparable(row[index], row[index])[0]), reverse=descending)
    selected = columns or names
    page = rows[offset: offset + limit]
    return {
        "ok": True,
        "table_id": table_id,
        "matching_rows": len(rows),
        "returned": len(page),
        "rows": [{name: row[position[name]] for name in selected} for row in page],
    }


def _brief_contract(world) -> Json:
    brief = world.state["case_files"].get(world.state["incident"]["brief_file_id"], {})
    return brief.get("sections", {}).get("submission_contract", {})


def _shape_report(world, artifact_id: str) -> Json:
    artifact = world.state["structured_artifacts"].get(artifact_id)
    if artifact is None:
        return {"ok": False, "error": "structured_artifact_not_found"}
    contract = _brief_contract(world)
    if artifact["artifact_type"] != contract.get("artifact_type"):
        return {"ok": False, "error": "artifact_type_not_in_contract"}
    missing, mismatched = [], []
    for spec in contract.get("fields", []):
        found, value = resolve(artifact["content"], spec["path"].split("."))
        if not found:
            missing.append(spec["path"])
            continue
        kind = spec["type"]
        if kind == "number" and to_number(value) is None or kind.startswith("list") and not isinstance(value, list) or kind.startswith("object") and not isinstance(value, dict):
            mismatched.append({"path": spec["path"], "expected": kind})
    return {"ok": True, "artifact_id": artifact_id, "missing_fields": missing, "type_mismatches": mismatched}


# --- checks and actions --------------------------------------------------------------


def _latest_artifact(world, artifact_type: str) -> Json | None:
    rows = [row for row in world.state["structured_artifacts"].values() if row.get("artifact_type") == artifact_type]
    if not rows:
        return None
    return max(rows, key=lambda row: (int(row.get("created_minute", -1)), str(row["id"])))


def _artifact_field_check(world, contract: Json) -> tuple[bool, str]:
    artifact = _latest_artifact(world, contract["artifact_type"])
    if artifact is None:
        return False, "no artifact of the requested type"
    return evaluate(contract["field"], artifact.get("content", {}))


def _artifact_cites_check(world, contract: Json) -> tuple[bool, str]:
    artifact = _latest_artifact(world, contract["artifact_type"])
    if artifact is None:
        return False, "no artifact of the requested type"
    files = set(contract["file_ids"])
    cited = [row for row in artifact.get("citations", []) if row.get("file_id") in files]
    return bool(cited), f"{len(cited)} citation(s) to task case files"


def _deliverable_issued_check(world, contract: Json) -> tuple[bool, str]:
    deliverable = world.state.get("gdp_deliverables", {}).get(contract["deliverable_id"])
    if not deliverable or deliverable["status"] != "issued":
        return False, "deliverable not issued"
    latest = _latest_artifact(world, deliverable["artifact_type"])
    passed = latest is not None and latest["id"] == deliverable["artifact_id"]
    return passed, "issued latest artifact" if passed else "issued artifact is not the latest revision"


def _issue(world, target: str, payload: Json) -> tuple[bool, str]:
    deliverable = world.state.get("gdp_deliverables", {}).get(target)
    if deliverable is None:
        return False, "deliverable_not_found"
    artifact = world.state["structured_artifacts"].get(str(payload.get("artifact_id", "")))
    if artifact is None:
        return False, "artifact_id_required"
    if artifact["artifact_type"] != deliverable["artifact_type"]:
        return False, "artifact_type_mismatch"
    deliverable.update({"status": "issued", "artifact_id": artifact["id"], "issued_minute": world.minute})
    artifact["status"] = "issued"
    return True, "issued"


# --- builder, oracle, probe --------------------------------------------------------------


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build(task, rng) -> ScenarioInstance:
    del rng
    fixture = task_fixture(task.id)
    grader = grader_fixture(task.id)
    if fixture["family"] != task.family:
        raise ValueError(f"{task.id}: fixture family {fixture['family']} != {task.family}")
    spec = FAMILY_SPECS[task.family]
    action = spec["action"]
    incident = fixture["incident"]
    deliverable_id = incident["deliverable_id"]
    artifact_type = grader["artifact_type"]
    state = _base_state(task, incident)
    for row in fixture["case_files"]:
        state["case_files"][row["id"]] = _case_file(row["id"], row["title"], row["system"], row["sections"])
    state["gdp_tables"] = {row["id"]: row for row in fixture["tables"]}
    state["network_artifact_types"] = [artifact_type]
    state["gdp_deliverables"] = {
        deliverable_id: {"id": deliverable_id, "artifact_type": artifact_type, "status": "draft", "artifact_id": None}
    }
    state["policies"]["protected_actions"].append(action)
    requirements: Json = {
        "section_reads": [{"file_id": incident["brief_file_id"], "section_id": "submission_contract", "version": 1}],
        "collections": {"structured_artifacts": 1},
    }
    if fixture["tables"]:
        requirements["tools"] = ["query_gdp_table"]
    state["policies"]["approval_requirements"][action] = requirements

    criteria = [
        _criterion(f"read-{_slug(file_id)}-{_slug(section)}", "investigation", 1, "case_file_read",
                   file_id=file_id, section_id=section, version=1)
        for file_id, section in grader["required_reads"]
    ]
    criteria += [
        _criterion(f"query-{_slug(table_id)}", "investigation", 1, "trace_tool", tool="query_gdp_table", args={"table_id": table_id})
        for table_id in grader["required_tables"]
    ]
    criteria += [
        _criterion(f"artifact-{row['id']}", "artifact_accuracy", row["weight"], "gdp_artifact_field",
                   artifact_type=artifact_type, field=row)
        for row in grader["checks"]
    ]
    criteria += [
        _criterion("artifact-cites-case-files", "evidence", 2, "gdp_artifact_cites", artifact_type=artifact_type,
                   file_ids=[row["id"] for row in fixture["case_files"]]),
        _criterion("finish-record-evidence", "evidence", 2, "finish_record_evidence", minimum=2),
        _criterion("notify-roles", "communication", 4, "notification_roles", roles=list(spec["roles"])),
        _criterion("approval-requested", "control", 3, "approval_action", action=action, target=deliverable_id),
        _criterion("deliverable-issued", "control", 4, "gdp_deliverable_issued", deliverable_id=deliverable_id),
    ]
    by_id = {row["id"]: row for row in grader["checks"]}
    economic_checks = [{"weight": 1, "check": "executed_action", "action": action, "target": deliverable_id}]
    economic_checks += [
        {"weight": 1, "check": "gdp_artifact_field", "artifact_type": artifact_type, "field": by_id[name]}
        for name in grader["economics"]
    ]
    economics = _economics(25000, 1500, 40, economic_checks)
    economics["target_minutes"] = 75
    return ScenarioInstance(state, [], criteria, economics)


def _ok(result: Json, step: str) -> Json:
    if not result.get("ok"):
        raise RuntimeError(f"oracle step {step} failed: {result}")
    return result


def oracle(task, tools) -> Json:
    fixture = task_fixture(task.id)
    grader = grader_fixture(task.id)
    spec = FAMILY_SPECS[task.family]
    incident = _ok(tools.call("get_incident"), "get_incident")["incident"]
    _ok(tools.call("list_case_files"), "list_case_files")
    for file_id, section in grader["required_reads"]:
        _ok(tools.call("read_case_file", file_id=file_id, section_id=section), f"read {file_id}/{section}")
    if grader["required_tables"]:
        _ok(tools.call("list_gdp_tables"), "list_gdp_tables")
        for table_id in grader["required_tables"]:
            _ok(tools.call("query_gdp_table", table_id=table_id, limit=5), f"query {table_id}")
    citations = [{"file_id": incident["brief_file_id"], "section_id": "submission_contract", "version": 1}]
    citations += [
        {"file_id": row["id"], "section_id": min(row["sections"]), "version": 1}
        for row in fixture["case_files"][1:]
    ]
    artifact = _ok(
        tools.call(
            "create_structured_artifact",
            artifact_type=grader["artifact_type"],
            title=fixture["title"],
            content=grader["truth"],
            citations=citations,
        ),
        "create_structured_artifact",
    )["artifact"]
    deliverable_id = incident["deliverable_id"]
    approval = _ok(
        tools.call(
            "request_approval",
            action=spec["action"],
            target=deliverable_id,
            reason=f"Release {grader['artifact_type']} {artifact['id']} built from the cited case files.",
            payload={"artifact_id": artifact["id"]},
        ),
        "request_approval",
    )["approval"]
    _ok(tools.call("execute_action", action=spec["action"], target=deliverable_id, approval_id=approval["id"]), "execute_action")
    for role in spec["roles"]:
        _ok(tools.call("notify", role=role, message=f"{fixture['title']}: {deliverable_id} issued from {artifact['id']}."), "notify")
    return tools.call("finish", summary=f"Issued {deliverable_id}.", evidence=[artifact["id"], deliverable_id])["final"]


def _probe(incident: Json, action: str) -> tuple[str, str]:
    return action, str(incident.get("deliverable_id", "missing"))


def _efficiency_target(task) -> int:
    """Reference call count (every required read and table, release, notifications) plus a little slack."""

    grader = grader_fixture(task.id)
    tables = grader["required_tables"]
    reference = 2 + len(grader["required_reads"]) + (1 + len(tables) if tables else 0) + 4
    reference += len(FAMILY_SPECS[task.family]["roles"])
    return min(task.max_tool_calls - 4, max(18, reference + 4))


register_tool(
    tool(
        "list_gdp_tables",
        "List the reference tables attached to this request (id, title, columns, row count).",
        {},
    ),
    _list_tables,
)
register_tool(
    tool(
        "query_gdp_table",
        "Query a reference table. Without group_by/metrics returns rows (paged, limit<=500); with them returns grouped "
        "aggregates. filters: [{column, op, value}] with op in eq, ne, gt, gte, lt, lte, in, not_in, contains, between "
        "([low, high]), is_blank, not_blank (dates are ISO strings). metrics: [{op: count|sum|avg|min|max|count_distinct, "
        "column, as}].",
        {
            "table_id": {"type": "string"},
            "filters": {"type": "array", "items": {"type": "object"}},
            "columns": {"type": "array", "items": {"type": "string"}},
            "group_by": {"type": "array", "items": {"type": "string"}},
            "metrics": {"type": "array", "items": {"type": "object"}},
            "order_by": {"type": "string"},
            "descending": {"type": "boolean"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
        },
        ["table_id"],
    ),
    _query_table,
)
register_tool(
    tool(
        "get_gdp_shape_report",
        "Report which submission-contract fields an artifact is missing or has with the wrong JSON type. "
        "It does not judge whether values are correct.",
        {"artifact_id": {"type": "string"}},
        ["artifact_id"],
    ),
    _shape_report,
)
register_check("gdp_artifact_field", _artifact_field_check)
register_check("gdp_artifact_cites", _artifact_cites_check)
register_check("gdp_deliverable_issued", _deliverable_issued_check)

for _family, _spec in FAMILY_SPECS.items():
    register_action(
        _spec["action"],
        "target=deliverable_id from the incident; payload={artifact_id} naming the structured artifact to release",
        _issue,
    )
    register_family(
        FamilyExtension(
            family=_family,
            builder=build,
            tools=TOOLS,
            notification_roles=_spec["roles"],
            protected_actions=(_spec["action"],),
            oracle=oracle,
            unsafe_probe=lambda incident, _action=_spec["action"]: _probe(incident, _action),
            description=_spec["description"],
            extra={"efficiency_target": _efficiency_target},
        )
    )

__all__ = ["FAMILY_SPECS", "TOOLS", "build", "grader_fixture", "norm_key", "oracle", "task_fixture", "task_index"]
