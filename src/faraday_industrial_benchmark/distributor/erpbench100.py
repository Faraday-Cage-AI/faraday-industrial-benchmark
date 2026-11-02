"""ERPBench-100 distributor families rebuilt natively on the Faraday world.

Seventy curated ERPBench-100 tasks (blobfishai/erp-agent-simulation) become seven
families. Each task seeds one tenant ERP and evidence room from the committed
fixtures, exposes the tenant read surface and the family's protected writes,
and grades with the 34-criterion ERPScore rubric ported to native checks.
"""

from __future__ import annotations

import json
import random
from typing import Any

from .. import extensions
from ..models import IncidentTask
from ..scenarios import ScenarioInstance, _base_state, _case_file, _criterion, _economics
from . import erpbench100_checks as checks
from . import erpbench100_contract as contract
from . import erpbench100_erp as erp_surface
from .fixtures import load_fixture

Json = dict[str, Any]

# Generous enough for the full reference trajectory (evidence sweep, approvals,
# writes, readbacks and handoffs) while still decaying before the horizon.
TARGET_MINUTES = 90


def upstream_task_id(task: IncidentTask) -> str:
    for tag in task.tags:
        if tag.startswith("upstream:"):
            return tag.split(":", 1)[1]
    raise ValueError(f"{task.id}: missing upstream:<task id> tag")


def task_fixture(task: IncidentTask) -> Json:
    return load_fixture(contract.SOURCE, upstream_task_id(task))


def _documents(tenant: Json, fixture: Json) -> dict[str, Json]:
    files: dict[str, Json] = {}
    for document in [*tenant["documents"], *fixture["documents"]]:
        files[document["id"]] = _case_file(
            document["id"],
            document["title"],
            document["system"],
            document["sections"],
            version=document["version"],
            status=document["status"],
        )
    for message in fixture["chat_messages"]:
        file_id = contract.chat_file_id(message["channel"])
        if file_id not in files:
            files[file_id] = _case_file(file_id, f"{message['channel']} channel history", "chat", {"thread": []})
        entry = {key: value for key, value in message.items() if key != "channel"}
        thread = files[file_id]["sections"]["thread"]
        thread.append(entry)
        thread.sort(key=lambda item: (item["posted_at"], item["message_id"]))
    return dict(sorted(files.items()))


def _subject_record(key: str, fixture: Json, profile: Json) -> str:
    truth = fixture["truth"]
    return {
        "order_import": lambda: truth["customer_po"],
        "shipment_verification": lambda: truth["shipment"],
        "receivables_collection": lambda: truth["customer_number"],
        "inventory_reorder": lambda: truth["organization_code"],
        "receiving_ap_match": lambda: truth["po"],
        "channel_order_sync": lambda: truth["channel"],
        "price_list_batch": lambda: profile["org"],
    }[key]()


def _incident(fixture: Json, tenant: Json, spec: Json) -> Json:
    profile = tenant["profile"]
    key = fixture["family_key"]
    return {
        "id": f"DIST-{fixture['upstream_task_id'].upper()}",
        "type": key,
        "status": "open",
        "as_of": contract.AS_OF,
        "upstream_task_id": fixture["upstream_task_id"],
        "title": fixture["title"],
        "tenant": {
            "code": profile["code"],
            "company": profile["company"],
            "site": profile["site"],
            "organization_code": profile["org"],
            "business_unit": profile["bu"],
            "currency": profile["currency"],
            "sales_channel": profile["channel"],
        },
        "subject_record": _subject_record(key, fixture, profile),
        "request_message_id": f"MSG-{fixture['upstream_task_id']}-REQUEST",
        "contract": {
            "decision_options": [{"id": row["id"], "label": row["label"]} for row in fixture["decision_options"]],
            "status_options": fixture["status_options"],
            "answer_fields": fixture["answer_fields"],
            "register_columns": fixture["register_columns"],
            "artifact_type": contract.artifact_type(key),
            "primary_role": spec["roles"][0],
            "secondary_role": spec["roles"][1],
            "protected_actions": list(spec["actions"]),
            "erp_readback_tools": list(spec["readback_tools"]),
            "handoff_readback_tool": contract.HANDOFF_READ_TOOL,
        },
    }


def _criteria(fixture: Json) -> list[Json]:
    investigations = {row["id"]: row for row in fixture["investigations"]}
    rows = []
    for item in fixture["rubric"]:
        rubric_id = item["id"]
        category, _, name = rubric_id.partition(":")
        mapped = checks.RUBRIC_CHECKS.get(category if category in {"discovery", "calculation"} else rubric_id)
        if mapped is None:
            raise ValueError(f"{fixture['upstream_task_id']}: unmapped rubric criterion {rubric_id}")
        dimension, check = mapped
        extra: Json = {}
        if category == "discovery":
            extra["routes"] = investigations[name]["routes"]
        elif category == "calculation":
            extra.update(field=name, expected=fixture["expected_answer"][name])
        rows.append(_criterion(rubric_id, dimension, item["points"], check, **extra))
    if sum(row["weight"] for row in rows) != 100:
        raise ValueError(f"{fixture['upstream_task_id']}: ERPScore weights do not total 100")
    return rows


def build(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    del rng  # Every value comes from the committed upstream-derived fixtures.
    fixture = task_fixture(task)
    tenant = load_fixture(contract.SOURCE, f"tenant-{fixture['tenant']}")
    key = fixture["family_key"]
    spec = contract.FAMILIES[key]
    if spec["family"] != task.family:
        raise ValueError(f"{task.id}: fixture family {spec['family']} does not match {task.family}")
    profile = tenant["profile"]

    state = _base_state(task, _incident(fixture, tenant, spec))
    state[erp_surface.ERP_KEY] = {
        table: {str(row[contract.TABLE_KEYS[table]]): row for row in tenant["erp"][table]}
        for table in contract.ERP_TABLES
    }
    state["case_files"] = _documents(tenant, fixture)
    state["network_artifact_types"] = [contract.artifact_type(key)]

    operative = state["case_files"][fixture["operative_source"]]
    if operative["status"] != "authoritative":
        raise ValueError(f"{task.id}: operative source {operative['id']} is not authoritative")
    state["policies"]["protected_actions"].extend(spec["actions"])
    for action in spec["actions"]:
        state["policies"]["approval_requirements"][action] = {
            "tools": ["get_incident"],
            "file_versions": {operative["id"]: operative["version"]},
        }
    state[erp_surface.CONTEXT_KEY] = {
        "upstream_task_id": fixture["upstream_task_id"],
        "family_key": key,
        "short": profile["short"],
        "org": profile["org"],
        "channel": profile["channel"],
        "business_unit": profile["bu"],
        "currency": profile["currency"],
        "numbering": tenant["numbering"],
        "artifact_type": contract.artifact_type(key),
        "roles": list(spec["roles"]),
        "primary_action": spec["primary_action"],
        "readback_tools": list(spec["readback_tools"]),
        "handoff_read_tool": contract.HANDOFF_READ_TOOL,
        "write_tables": list(spec["write_tables"]),
        "expected": fixture["expected_answer"],
        "decision_options": [{"id": row["id"], "label": row["label"]} for row in fixture["decision_options"]],
        "status_options": fixture["status_options"],
        "numeric_fields": fixture["numeric_fields"],
        "register_columns": fixture["register_columns"],
        "operative_source": operative["id"],
        "operative_version": operative["version"],
        "trap_file_ids": fixture["trap_file_ids"],
        "truth": fixture["truth"],
    }

    value = max(float(fixture["value_at_risk"]), 1000.0)
    economics = _economics(
        round(value, 2),
        round(value * 0.02, 2),
        round(value / 1000.0, 2),
        [
            {"weight": 0.7, "check": "dist_erpbench_erp_primary"},
            {"weight": 0.3, "check": "dist_erpbench_erp_secondary"},
        ],
    )
    economics["target_minutes"] = TARGET_MINUTES
    return ScenarioInstance(state, [], _criteria(fixture), economics)


# ---------------------------------------------------------------------------
# Reference trajectory
# ---------------------------------------------------------------------------


def _call(tools, name: str, **arguments: Any) -> Json:
    result = tools.call(name, **arguments)
    if not result.get("ok"):
        raise RuntimeError(f"reference call {name}({arguments}) failed: {result}")
    return result


def _readbacks(key: str, fixture: Json) -> list[tuple[str, Json]]:
    truth, expected = fixture["truth"], fixture["expected_answer"]
    if key == "order_import":
        return [("get_dist_tenant_sales_order", {"order_number": expected["primary_record"]})]
    if key == "shipment_verification":
        return [("list_dist_tenant_shipment_lines", {"shipment": truth["shipment"]})]
    if key == "receivables_collection":
        return [("list_dist_tenant_customer_receipts", {"customer_number": truth["customer_number"]})]
    if key == "inventory_reorder":
        return [("get_dist_tenant_requisition", {"requisition_number": expected["primary_record"]})]
    if key == "receiving_ap_match":
        return [("get_dist_tenant_ap_invoice", {"invoice_number": truth["invoice_number"]})]
    if key == "channel_order_sync":
        return [("list_dist_tenant_sales_orders", {"source_system": truth["channel"]})]
    return [("list_dist_tenant_items", {})]


def reference_run(
    task: IncidentTask,
    tools,
    *,
    answer: Json | None = None,
    citations: list[Json] | None = None,
    extra_steps: tuple[Json, ...] = (),
) -> Json:
    """Run the reference trajectory; overrides build negative controls in tests."""

    fixture = task_fixture(task)
    key = fixture["family_key"]
    spec = contract.FAMILIES[key]
    expected = dict(answer if answer is not None else fixture["expected_answer"])
    source = fixture["operative_source"]

    seen: set[str] = set()
    for investigation in fixture["investigations"]:
        route = investigation["routes"][0]
        signature = json.dumps(route, sort_keys=True)
        if signature not in seen:
            seen.add(signature)
            _call(tools, route["tool"], **route["args"])
    source_file = _call(tools, "read_case_file", file_id=source, section_id="content")["file"]
    request_id = f"MSG-{fixture['upstream_task_id']}-REQUEST"

    for step in fixture["oracle_plan"]:
        if step["action"] == "submit_dist_tenant_requisition":
            _call(tools, "list_dist_tenant_requisitions")
        approval = _call(
            tools,
            "request_approval",
            action=step["action"],
            target=step["target"],
            reason=f"{fixture['upstream_task_id']}: {step['action']} on {step['target']} per {source}",
            payload=step["payload"],
        )["approval"]
        if approval["status"] != "approved":
            raise RuntimeError(f"reference approval denied: {approval}")
        _call(tools, "execute_action", action=step["action"], target=step["target"], approval_id=approval["id"])
    for step in extra_steps:
        approval = tools.call(
            "request_approval", action=step["action"], target=step["target"],
            reason="additional write under test", payload=step["payload"],
        ).get("approval", {})
        tools.call("execute_action", action=step["action"], target=step["target"], approval_id=approval.get("id"))
    for tool, arguments in _readbacks(key, fixture):
        _call(tools, tool, **arguments)

    artifact = _call(
        tools,
        "create_structured_artifact",
        artifact_type=contract.artifact_type(key),
        title=f"{fixture['title']} register row {fixture['upstream_task_id']}",
        content=expected,
        citations=citations if citations is not None else [
            {"file_id": source, "section_id": "content", "version": source_file["version"]},
            {"file_id": request_id, "section_id": "message", "version": 1},
        ],
    )["artifact"]
    _call(tools, "get_structured_artifact", artifact_id=artifact["id"])

    option = next(row for row in fixture["decision_options"] if row["id"] == expected["recommended_option"])
    figures = "; ".join(f"{field}={expected[field]}" for field in fixture["numeric_fields"])
    _call(
        tools,
        "notify",
        role=spec["roles"][0],
        message=(
            f"For review ({fixture['upstream_task_id']}): recommended option {option['id']} ({option['label']}); "
            f"primary record {expected['primary_record']}; {figures}; source {expected['source_reference']}."
        ),
    )
    status = next(row for row in fixture["status_options"] if row["id"] == expected["decision_status"])
    _call(
        tools,
        "notify",
        role=spec["roles"][1],
        message=f"For review: decision status {status['id']} ({status['label']}) on {expected['primary_record']}.",
    )
    _call(tools, contract.HANDOFF_READ_TOOL)
    return _call(
        tools,
        "finish",
        summary=f"{fixture['title']}: {expected['recommended_option']} recorded as {expected['primary_record']}.",
        evidence=[expected["primary_record"], expected["source_reference"]],
    )["final"]


def oracle(task: IncidentTask, tools) -> Json:
    return reference_run(task, tools)


def unsafe_probe(incident: Json) -> tuple[str, str]:
    key = incident["type"]
    return contract.FAMILIES[key]["primary_action"], incident["subject_record"]


def _register() -> None:
    erp_surface.register()
    checks.register()
    tools = (*contract.CORE_TOOLS, *contract.READ_TOOLS, contract.HANDOFF_READ_TOOL)
    for key, spec in contract.FAMILIES.items():
        extensions.register_family(
            extensions.FamilyExtension(
                family=spec["family"],
                builder=build,
                tools=tools,
                notification_roles=tuple(spec["roles"]),
                protected_actions=tuple(spec["actions"]),
                oracle=oracle,
                unsafe_probe=unsafe_probe,
                description=f"ERPBench-100 {spec['label']} rebuilt on the native tenant ERP",
                extra={"source": contract.SOURCE, "family_key": key},
            )
        )


_register()
