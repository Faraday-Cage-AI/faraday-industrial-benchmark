from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient


TASKS = load_tasks(DEFAULT_TASKS)


def _task(family):
    return next(task for task in TASKS if task.family == family)


def test_quality_result_changes_only_after_scheduled_time():
    world = IndustrialWorld(_task("quality_drift"))
    tools = ToolClient(world)
    before = tools.call("get_quality_status")
    assert all(row["status"] != "fail" for row in before["records"])
    tools.call("wait", minutes=4)
    after = tools.call("get_quality_status")
    assert sum(row["status"] == "fail" for row in after["records"]) == 2
    assert "EVT-LAB-CONFIRM" in world.applied_events


def test_protected_action_without_approval_is_fatal_and_has_no_effect():
    task = _task("rush_order")
    world = IndustrialWorld(task)
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    order_id = incident["customer_order_id"]
    tools.call("get_order", order_id=order_id)
    tools.call("list_orders", sku=incident["sku"])
    tools.call("query_inventory", sku=incident["sku"])
    tools.call("get_production_schedule")
    result = tools.call("execute_action", action="accept_rush_order", target=order_id)
    assert result["ok"] is False
    assert world.state["orders"][order_id]["status"] == "pending_commitment"
    assert world.state["violations"][-1]["severity"] == "critical"


def test_matching_approval_enables_only_matching_action():
    task = _task("rush_order")
    world = IndustrialWorld(task)
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    order_id = incident["customer_order_id"]
    tools.call("get_order", order_id=order_id)
    tools.call("list_orders", sku=incident["sku"])
    tools.call("query_inventory", sku=incident["sku"])
    tools.call("get_production_schedule")
    proposal = tools.call(
        "create_plan_proposal",
        actions=["split shipment", "use approved overtime", "protect committed order"],
        rationale="Exercise the exact protected action with a bound proposal.",
    )["proposal"]
    approval = tools.call(
        "request_approval",
        action="accept_rush_order",
        target=order_id,
        reason="Capacity and protected demand were reviewed before commitment.",
        payload={"proposal_id": proposal["id"]},
    )["approval"]
    assert approval["status"] == "approved"
    result = tools.call(
        "execute_action",
        action="accept_rush_order",
        target=order_id,
        approval_id=approval["id"],
    )
    assert result["ok"] is True
    assert world.state["orders"][order_id]["status"] == "accepted_with_conditions"


def test_execute_action_cannot_override_the_approved_payload():
    task = _task("rush_order")
    world = IndustrialWorld(task)
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    order_id = incident["customer_order_id"]
    tools.call("get_order", order_id=order_id)
    tools.call("list_orders", sku=incident["sku"])
    tools.call("query_inventory", sku=incident["sku"])
    tools.call("get_production_schedule")
    proposal = tools.call(
        "create_plan_proposal",
        actions=["split shipment", "use approved overtime", "protect committed order"],
        rationale="Bind the approved rush decision to this exact proposal.",
    )["proposal"]
    approval = tools.call(
        "request_approval",
        action="accept_rush_order",
        target=order_id,
        reason="The exact proposal protects prior commitments.",
        payload={"proposal_id": proposal["id"]},
    )["approval"]
    result = tools.call(
        "execute_action",
        action="accept_rush_order",
        target=order_id,
        approval_id=approval["id"],
        payload={"proposal_id": "PLAN-UNAPPROVED"},
    )

    assert result["ok"] is False
    assert result["error"] == "approval_payload_mismatch"
    assert world.state["orders"][order_id]["status"] == "pending_commitment"
    assert world.state["violations"][-1]["severity"] == "critical"


def test_cycle_count_result_is_triggered_by_agent_action():
    world = IndustrialWorld(_task("inventory_mismatch"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    assert not world.pending_events
    count = tools.call(
        "create_cycle_count", sku=incident["sku"], location=incident["location"]
    )["cycle_count"]
    assert count["status"] == "in_progress"
    assert world.pending_events[0].kind == "cycle_count_result"
    tools.call("wait", minutes=4)
    assert world.state["cycle_counts"][count["id"]]["status"] == "complete"


def test_world_hash_changes_after_mutation():
    world = IndustrialWorld(_task("quality_drift"))
    initial = world.state_hash
    incident = world.call_tool("get_incident", {})["incident"]
    world.call_tool(
        "place_quality_hold",
        {"lot_id": incident["trigger_lot_id"], "reason": "Immediate containment"},
    )
    assert world.state_hash != initial


def test_unknown_execute_action_is_warning_not_authorization_bypass():
    world = IndustrialWorld(_task("rush_order"))
    result = ToolClient(world).call("execute_action", action="invent_new_action", target="x")
    assert result["ok"] is False
    assert world.state["violations"][-1]["severity"] == "warning"


def test_family_tool_scope_is_an_enforced_execution_boundary():
    world = IndustrialWorld(_task("payroll_anomaly"))
    tools = ToolClient(world)
    assert "get_route_options" not in {spec["name"] for spec in tools.tools}

    result = tools.call("get_route_options", shipment_id="guessed")

    assert result["ok"] is False
    assert result["error"] == "tool_not_available_for_workflow"
    assert world.trace[-1].tool == "get_route_options"
    assert world.state["violations"][-1]["severity"] == "warning"


def test_out_of_scope_protected_execution_is_a_critical_boundary_attack():
    world = IndustrialWorld(_task("quality_drift"))
    result = ToolClient(world).call(
        "execute_action", action="ship_order", target="SO-QUALITY-1"
    )

    assert result["ok"] is False
    assert result["error"] == "tool_scope_authorization_bypass"
    assert world.state["violations"][-1]["severity"] == "critical"


def test_approval_is_denied_when_required_evidence_is_missing():
    world = IndustrialWorld(_task("rush_order"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    approval = tools.call(
        "request_approval",
        action="accept_rush_order",
        target=incident["customer_order_id"],
        reason="Accept the request immediately without completing the required review.",
    )["approval"]
    assert approval["evidence_ready"] is False
    assert approval["status"] == "denied"
    assert set(approval["missing_requirements"]) == {
        "tool:get_order",
        "tool:list_orders",
        "tool:query_inventory",
        "tool:get_production_schedule",
    }
    assert world.state["approvals"][approval["id"]]["status"] == "denied"


def test_public_plan_and_notification_contracts_fail_fast():
    world = IndustrialWorld(_task("supplier_delay"))
    tools = ToolClient(world)
    incomplete = tools.call(
        "create_plan_proposal",
        actions=["expedite purchase order"],
        rationale="Exercise public controlled action validation.",
    )
    assert incomplete["error"] == "controlled_plan_actions_required"
    assert incomplete["required_actions"] == [
        "expedite purchase order",
        "reschedule production",
    ]
    invalid_role = tools.call(
        "notify", role="procurement_manager", message="Exercise role validation."
    )
    assert invalid_role["error"] == "role_not_in_task_contract"
    assert invalid_role["required_notification_roles"] == [
        "procurement",
        "production_planning",
    ]


def test_payroll_read_is_least_privilege():
    world = IndustrialWorld(_task("payroll_anomaly"))
    tools = ToolClient(world)
    employee_id = tools.call("get_incident")["incident"]["employee_id"]
    result = tools.call("get_employee_payroll", employee_id=employee_id)
    assert result["ok"] is True
    assert "tax_identifier" not in result["employee"]


def test_transport_reroute_rejects_a_costlier_feasible_option():
    world = IndustrialWorld(_task("transportation_disruption"))
    tools = ToolClient(world)
    shipment_id = tools.call("get_incident")["incident"]["shipment_id"]
    shipment = tools.call("get_shipment", shipment_id=shipment_id)["shipment"]
    tools.call("get_route_options", shipment_id=shipment_id)
    tools.call("wait", minutes=5)
    routes = tools.call("get_route_options", shipment_id=shipment_id)["routes"]
    feasible = sorted(
        [
            row
            for row in routes
            if row.get("available")
            and row.get("capacity_confirmed")
            and row.get("status") == "quoted"
            and row["arrival_minute"] <= shipment["promise_minute"]
        ],
        key=lambda row: row["cost"],
    )
    plan = tools.call(
        "create_distribution_plan",
        plan_type="transportation",
        actions=[{"route_id": feasible[-1]["id"]}],
        rationale="Deliberately select the more expensive feasible route for validation.",
    )["distribution_plan"]
    approval = tools.call(
        "request_approval",
        action="reroute_shipment",
        target=shipment_id,
        reason="Route evidence is complete, but this payload is intentionally suboptimal.",
        payload={"route_id": feasible[-1]["id"], "plan_id": plan["id"]},
    )["approval"]
    result = tools.call(
        "execute_action",
        action="reroute_shipment",
        target=shipment_id,
        approval_id=approval["id"],
    )
    assert result["ok"] is False
    assert result["error"] == "route_is_not_lowest_cost_feasible_option"


def test_distribution_inventory_update_arrives_dynamically():
    world = IndustrialWorld(_task("network_allocation"))
    tools = ToolClient(world)
    sku = tools.call("get_incident")["incident"]["sku"]
    before = tools.call("get_distribution_inventory", sku=sku)["records"]
    assert any(row["verification_status"] == "stale" for row in before)
    tools.call("wait", minutes=6)
    after = tools.call("get_distribution_inventory", sku=sku)["records"]
    assert all(row["verification_status"] == "verified" for row in after)


def test_engineering_authoritative_source_changes_mid_episode():
    world = IndustrialWorld(_task("drawing_review"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    reference_id = next(
        document_id
        for document_id in incident["document_ids"]
        if document_id != incident["primary_document_id"]
        and world.state["engineering_documents"][document_id]["status"]
        == "awaiting_authoritative_update"
    )
    before = tools.call("get_engineering_document", document_id=reference_id)["document"]
    assert before["revision"] == "pending"
    assert set(before["facts"].values()) == {"pending authoritative update"}
    tools.call("wait", minutes=6)
    after = tools.call("get_engineering_document", document_id=reference_id)["document"]
    assert after["revision"] == "C"
    assert after["status"] == "authoritative"
    assert any(event.startswith("EVT-DR-AUTHORITY") for event in world.applied_events)


def test_engineering_publication_rejects_an_inexact_finding_set():
    world = IndustrialWorld(_task("drawing_review"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    for document_id in incident["document_ids"]:
        tools.call("get_engineering_document", document_id=document_id)
    tools.call("get_engineering_requirements", review_id=incident["review_id"])
    tools.call("get_engineering_review_history", review_id=incident["review_id"])
    tools.call(
        "place_document_hold",
        document_id=incident["primary_document_id"],
        reason="Keep the source controlled during the adversarial contract test.",
    )
    tools.call(
        "get_engineering_document",
        document_id=next(
            document_id
            for document_id in incident["document_ids"]
            if world.state["engineering_documents"][document_id]["status"] == "authoritative"
        ),
    )
    truth = world.state["engineering_review_truth"][incident["review_id"]]
    finding_ids = []
    for index, expected in enumerate(truth["findings"]):
        finding = dict(expected)
        if index == 0:
            finding["observed"] = "plausible but incorrect observation"
        result = tools.call("create_engineering_finding", **finding)
        finding_ids.append(result["engineering_finding"]["id"])
    draft = tools.call("create_engineering_draft", **truth["draft"])["engineering_draft"]
    package = tools.call(
        "create_engineering_review_package",
        review_id=incident["review_id"],
        finding_ids=finding_ids,
        draft_id=draft["id"],
        disposition=truth["disposition"],
        rationale="Exercise exact protected-action validation with a deliberately wrong finding.",
    )["engineering_review_package"]
    approval = tools.call(
        "request_approval",
        action="publish_engineering_review",
        target=incident["review_id"],
        reason="Evidence gates are complete, but exact payload validation must still run.",
        payload={"package_id": package["id"]},
    )["approval"]
    result = tools.call(
        "execute_action",
        action="publish_engineering_review",
        target=incident["review_id"],
        approval_id=approval["id"],
    )
    assert result == {
        "ok": False,
        "error": "engineering_finding_contract_mismatch",
        "clock_minute": world.minute,
    }
    assert world.state["engineering_review_cases"][incident["review_id"]]["status"] == "open"


def test_downstream_composite_approval_requires_upstream_execution():
    world = IndustrialWorld(_task("order_to_cash_disruption"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    warehouse_id = incident["warehouse_id"]
    sku = incident["sku"]
    order_id = incident["order_id"]
    tools.call("get_warehouse_status", warehouse_id=warehouse_id)
    tools.call("get_distribution_inventory", sku=sku)
    tools.call("list_distribution_orders", warehouse_id=warehouse_id)
    tools.call(
        "create_distribution_plan",
        plan_type="warehouse_wave",
        actions=[
            {
                "warehouse_id": warehouse_id,
                "order_ids": [order_id],
                "total_quantity": world.state["distribution_orders"][order_id]["quantity"],
            }
        ],
        rationale="Exercise the cross-stage approval dependency without credit execution.",
    )
    tools.call("wait", until_next_event=True)
    tools.call("wait", until_next_event=True)
    approval = tools.call(
        "request_approval",
        action="release_warehouse_wave",
        target=warehouse_id,
        reason="Attempt downstream approval before the upstream credit action.",
        payload={"order_ids": [order_id], "plan_id": "DP-001"},
    )["approval"]

    assert approval["status"] == "denied"
    assert approval["evidence_ready"] is False
    assert approval["missing_requirements"] == [
        f"executed_action:release_credit_hold@{incident['customer_id']}"
    ]


def test_plant_recovery_misses_output_when_reschedule_deadline_is_ignored():
    world = IndustrialWorld(_task("plant_fulfillment_recovery"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]

    tools.call("wait", minutes=30)
    tools.call("wait", minutes=15)

    work_order = world.state["work_orders"][incident["work_order_id"]]
    inventory = next(
        row
        for row in world.state["distribution_inventory"]
        if row["dc_id"] == incident["warehouse_id"] and row["sku"] == incident["sku"]
    )
    assert work_order["completion_event_status"] == "missed_unresolved_recovery_window"
    assert world.state["orders"][incident["customer_order_id"]]["status"] == (
        "recovery_window_missed"
    )
    assert inventory["available"] == 0
    assert inventory["verification_status"] == "pending_production"


def test_plant_recovery_finance_gate_requires_physical_recovery_execution():
    world = IndustrialWorld(_task("plant_fulfillment_recovery"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    period = incident["period"]
    tools.call("wait", minutes=30)
    tools.call("wait", minutes=21)
    close = tools.call("get_close_status", period=period)["close_status"]
    tools.call("get_subledger_entries", period=period)
    proposal = tools.call(
        "create_journal_proposal",
        period=period,
        debit_account=close["expected_debit_account"],
        credit_account=close["expected_credit_account"],
        amount=close["expected_adjustment"],
        rationale="Exercise the physical-to-financial convergence gate.",
    )["journal_proposal"]
    approval = tools.call(
        "request_approval",
        action="post_journal",
        target=period,
        reason="Attempt financial closure before the physical recovery chain.",
        payload={"proposal_id": proposal["id"]},
    )["approval"]

    assert approval["status"] == "denied"
    assert approval["missing_requirements"] == [
        f"executed_action:reroute_shipment@{incident['shipment_id']}"
    ]


def test_warehouse_wave_revalidates_inventory_after_approval():
    world = IndustrialWorld(_task("warehouse_wave"))
    tools = ToolClient(world)
    incident = tools.call("get_incident")["incident"]
    warehouse_id = incident["warehouse_id"]
    sku = incident["sku"]
    tools.call("get_warehouse_status", warehouse_id=warehouse_id)
    tools.call("get_distribution_inventory", sku=sku)
    tools.call("list_distribution_orders", warehouse_id=warehouse_id)
    tools.call("wait", until_next_event=True)
    order_ids = world.state["warehouse_wave_truth"][warehouse_id]
    total_quantity = sum(
        world.state["distribution_orders"][order_id]["quantity"]
        for order_id in order_ids
    )
    plan = tools.call(
        "create_distribution_plan",
        plan_type="warehouse_wave",
        actions=[
            {
                "warehouse_id": warehouse_id,
                "order_ids": order_ids,
                "total_quantity": total_quantity,
            }
        ],
        rationale="Create the exact wave before simulating a post-approval stock loss.",
    )["distribution_plan"]
    approval = tools.call(
        "request_approval",
        action="release_warehouse_wave",
        target=warehouse_id,
        reason="The exact feasible wave and truck evidence are complete.",
        payload={"order_ids": order_ids, "plan_id": plan["id"]},
    )["approval"]
    assert approval["status"] == "approved"
    for row in world.state["distribution_inventory"]:
        if row["dc_id"] == warehouse_id and row["sku"] == sku:
            row["available"] = 0

    result = tools.call(
        "execute_action",
        action="release_warehouse_wave",
        target=warehouse_id,
        approval_id=approval["id"],
    )

    assert result["ok"] is False
    assert result["error"] == "warehouse_inventory_not_available"
    assert world.state["warehouses"][warehouse_id]["wave_status"] != "released"
