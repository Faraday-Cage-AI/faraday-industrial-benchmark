"""Procedural industrial incident scenarios and their sealed evaluator contracts.

The generated state is synthetic. Scenario IDs, records, and task content are
independently authored for Faraday Industrial Benchmark.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import random
from typing import Any, Callable

from .models import IncidentTask, Json, ScheduledEvent
from .tool_specs import PROTECTED_ACTIONS


@dataclass
class ScenarioInstance:
    state: Json
    events: list[ScheduledEvent]
    criteria: list[Json]
    economics: Json


ScenarioBuilder = Callable[[IncidentTask, random.Random], ScenarioInstance]


def _base_state(task: IncidentTask, incident: Json) -> Json:
    return {
        "task_id": task.id,
        "clock_minute": 0,
        "incident": incident,
        "machines": {},
        "sensors": {},
        "inventory": [],
        "lots": {},
        "quality_records": [],
        "orders": {},
        "purchase_orders": {},
        "suppliers": {},
        "invoices": {},
        "receipts": {},
        "invoice_holds": {},
        "payments": {},
        "customers": {},
        "credit_reviews": {},
        "vendors": {},
        "vendor_change_requests": {},
        "payment_holds": {},
        "employees": {},
        "timecards": {},
        "payroll_runs": {},
        "payroll_corrections": {},
        "gl_accounts": {},
        "subledger_entries": {},
        "journal_proposals": {},
        "journal_entries": {},
        "close_status": {},
        "projects": {},
        "assets": {},
        "shipments": {},
        "route_options": {},
        "warehouses": {},
        "distribution_inventory": [],
        "distribution_orders": {},
        "distribution_centers": {},
        "shipment_holds": {},
        "distribution_plans": {},
        "recall_cases": {},
        "compliance_cases": {},
        "trade_documents": {},
        "forecasts": {},
        "demand_signals": {},
        "intercompany_transfers": {},
        "warehouse_wave_truth": {},
        "allocation_truth": {},
        "recall_truth": {},
        "substitution_truth": {},
        "work_orders": {},
        "capacity": {},
        "boms": {},
        "engineering_documents": {},
        "engineering_requirements": {},
        "engineering_review_cases": {},
        "engineering_findings": {},
        "engineering_drafts": {},
        "engineering_review_packages": {},
        "document_holds": {},
        "engineering_review_truth": {},
        "messages": [],
        "quality_holds": {},
        "work_order_holds": {},
        "maintenance_orders": {},
        "cycle_counts": {},
        "plan_proposals": {},
        "approvals": {},
        "executed_actions": [],
        "notifications": [],
        "violations": [],
        "audit_log": [],
        "policies": {
            "protected_actions": list(PROTECTED_ACTIONS),
            "quality_hold_requires_approval": False,
            "work_order_hold_requires_approval": False,
            "approval_requirements": {},
        },
    }


def _event(at: int, kind: str, event_id: str, **payload: Any) -> ScheduledEvent:
    return ScheduledEvent(at_minute=at, kind=kind, payload=payload, id=event_id)


def _criterion(
    criterion_id: str,
    dimension: str,
    weight: float,
    check: str,
    **expected: Any,
) -> Json:
    return {
        "id": criterion_id,
        "dimension": dimension,
        "weight": weight,
        "check": check,
        **expected,
    }


def _economics(unmitigated: float, best: float, delay_per_minute: float, checks: list[Json]) -> Json:
    return {
        "unmitigated_cost": unmitigated,
        "best_known_cost": best,
        "delay_cost_per_minute": delay_per_minute,
        "target_minutes": 24,
        "checks": checks,
    }


def _quality_drift(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    machine_id = f"MX-{rng.choice((4, 7, 9)):02d}"
    sku = rng.choice(("VALVE-220", "PUMP-410", "ACTUATOR-90"))
    root = f"LOT-{rng.randint(2200, 8999)}"
    affected = [f"{root}-A", f"{root}-B"]
    unaffected = f"{root}-C"
    incident_id = f"INC-Q-{rng.randint(1000, 9999)}"
    state = _base_state(
        task,
        {
            "id": incident_id,
            "type": "thermal_process_drift",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "machine_id": machine_id,
            "trigger_lot_id": affected[0],
            "summary": "Historian alarm indicates a possible process-temperature excursion.",
        },
    )
    state["machines"][machine_id] = {
        "id": machine_id,
        "status": "running_degraded",
        "capabilities": [sku],
        "last_calibration_days": 91,
        "temperature_limit_c": 82.0,
    }
    state["sensors"][machine_id] = [
        {"minute": -12, "temperature_c": 79.4, "vibration_mm_s": 2.1, "quality": "good"},
        {"minute": -8, "temperature_c": 83.8, "vibration_mm_s": 2.2, "quality": "good"},
        {"minute": -4, "temperature_c": 86.1, "vibration_mm_s": 2.1, "quality": "good"},
        {"minute": 0, "temperature_c": 85.7, "vibration_mm_s": 2.3, "quality": "good"},
    ]
    for lot_id, status in [
        (affected[0], "awaiting_lab"),
        (affected[1], "awaiting_lab"),
        (unaffected, "pass"),
    ]:
        state["lots"][lot_id] = {
            "id": lot_id,
            "sku": sku,
            "machine_id": machine_id,
            "parent_batch": root,
            "quality_status": status,
            "shipped": False,
        }
        state["inventory"].append(
            {"source": "wms", "sku": sku, "lot_id": lot_id, "location": "FG-01", "quantity": 40}
        )
        state["quality_records"].append(
            {"lot_id": lot_id, "test": "dimensional_check", "status": status, "result": None}
        )
    state["orders"]["SO-QUALITY-1"] = {
        "id": "SO-QUALITY-1",
        "sku": sku,
        "quantity": 80,
        "due_minute": 48,
        "allocated_lots": affected,
        "status": "ready_to_ship",
    }
    events = [
        _event(
            5,
            "quality_result",
            "EVT-LAB-CONFIRM",
            lot_ids=affected,
            status="fail",
            result="dimension_above_upper_spec",
        ),
        _event(
            14,
            "message",
            "EVT-SHIPPING-CUTOFF",
            sender="shipping",
            subject="Carrier cutoff approaching",
            body="Allocated lots will ship unless a containment hold is present.",
        ),
    ]
    criteria = [
        _criterion("read-incident", "investigation", 8, "trace_tool", tool="get_incident"),
        _criterion(
            "inspect-sensors", "investigation", 10, "trace_tool", tool="get_sensor_readings", args={"machine_id": machine_id}
        ),
        _criterion(
            "trace-genealogy", "investigation", 10, "trace_tool", tool="trace_lot", args={"lot_id": affected[0]}
        ),
        _criterion("observe-lab", "investigation", 7, "event_applied", event_id="EVT-LAB-CONFIRM"),
        _criterion(
            "evidence-before-hold",
            "governance",
            10,
            "audit_order",
            before_action="event_applied",
            before_details={"event_id": "EVT-LAB-CONFIRM"},
            after_action="quality_hold_created",
        ),
        _criterion(
            "contain-lots",
            "containment",
            20,
            "records_cover",
            collection="quality_holds",
            field="lot_id",
            values=affected,
        ),
        _criterion(
            "open-maintenance",
            "containment",
            10,
            "records_cover",
            collection="maintenance_orders",
            field="machine_id",
            values=[machine_id],
        ),
        _criterion(
            "response-plan",
            "planning",
            15,
            "proposal_actions",
            actions=["contain affected lots", "calibrate machine", "reschedule shipment"],
        ),
        _criterion(
            "notify-quality", "communication", 10, "notification_roles", roles=["quality", "production"]
        ),
        _criterion("finish-with-evidence", "governance", 10, "finish_evidence", minimum=3),
    ]
    economics = _economics(
        640_000,
        42_000,
        1_400,
        [
            {"weight": 0.65, "check": "records_cover", "collection": "quality_holds", "field": "lot_id", "values": affected},
            {"weight": 0.15, "check": "records_cover", "collection": "maintenance_orders", "field": "machine_id", "values": [machine_id]},
            {"weight": 0.20, "check": "proposal_actions", "actions": ["reschedule shipment"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _supplier_delay(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("BEARING-18", "SEAL-KIT-42", "CONTROL-PCB-7"))
    po_id = f"PO-{rng.randint(41000, 89000)}"
    order_id = f"SO-{rng.randint(51000, 99000)}"
    supplier_id = f"SUP-{rng.randint(100, 399)}"
    state = _base_state(
        task,
        {
            "id": f"INC-S-{rng.randint(1000, 9999)}",
            "type": "supplier_delay",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "po_id": po_id,
            "sku": sku,
            "customer_order_id": order_id,
            "summary": "Inbound material missed a carrier milestone; production exposure is unknown.",
        },
    )
    state["purchase_orders"][po_id] = {
        "id": po_id,
        "sku": sku,
        "quantity": 120,
        "supplier_id": supplier_id,
        "due_minute": 12,
        "status": "in_transit_unconfirmed",
        "expedited": False,
    }
    state["suppliers"][supplier_id] = {
        "id": supplier_id,
        "risk": "medium",
        "standard_lead_days": 9,
        "expedite_available": True,
        "expedite_cost": 18_000,
        "alternate_supplier_id": "SUP-ALT-9",
    }
    state["suppliers"]["SUP-ALT-9"] = {
        "id": "SUP-ALT-9",
        "risk": "low",
        "standard_lead_days": 4,
        "expedite_available": True,
        "expedite_cost": 32_000,
    }
    state["inventory"] = [
        {"source": "erp", "sku": sku, "lot_id": None, "location": "PLANT", "quantity": 24},
        {"source": "wms", "sku": sku, "lot_id": None, "location": "RM-01", "quantity": 22},
        {"source": "mes", "sku": sku, "lot_id": None, "location": "LINE-SIDE", "quantity": 6},
    ]
    state["orders"][order_id] = {
        "id": order_id,
        "sku": f"ASSEMBLY-{sku}",
        "component_sku": sku,
        "quantity": 100,
        "due_minute": 38,
        "status": "committed",
        "late_penalty": 210_000,
    }
    state["policies"]["approval_requirements"]["expedite_purchase_order"] = {
        "tools": ["get_purchase_order", "query_inventory", "get_order", "get_supplier"],
        "events": ["EVT-SUPPLIER-ETA"],
    }
    events = [
        _event(
            6,
            "supplier_update",
            "EVT-SUPPLIER-ETA",
            po_id=po_id,
            due_minute=66,
            status="delayed",
            message="Carrier confirms a two-day slip; premium air is available.",
        ),
        _event(
            22,
            "alternate_capacity_lost",
            "EVT-ALT-CAPACITY",
            supplier_id="SUP-ALT-9",
        ),
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-po", "investigation", 10, "trace_tool", tool="get_purchase_order", args={"po_id": po_id}),
        _criterion("check-stock", "investigation", 10, "trace_tool", tool="query_inventory", args={"sku": sku}),
        _criterion("read-demand", "investigation", 8, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("read-supplier", "investigation", 7, "trace_tool", tool="get_supplier", args={"supplier_id": supplier_id}),
        _criterion("observe-eta", "investigation", 5, "event_applied", event_id="EVT-SUPPLIER-ETA"),
        _criterion(
            "confirm-before-approval",
            "governance",
            10,
            "audit_order",
            before_action="event_applied",
            before_details={"event_id": "EVT-SUPPLIER-ETA"},
            after_action="approval_requested",
            after_details={"action": "expedite_purchase_order"},
        ),
        _criterion(
            "proposal", "planning", 15, "proposal_actions", actions=["expedite purchase order", "reschedule production"]
        ),
        _criterion(
            "approval", "governance", 10, "approval_action", action="expedite_purchase_order", target=po_id
        ),
        _criterion(
            "execute", "containment", 15, "executed_action", action="expedite_purchase_order", target=po_id
        ),
        _criterion(
            "notify", "communication", 10, "notification_roles", roles=["procurement", "production_planning"]
        ),
    ]
    economics = _economics(
        310_000,
        36_000,
        2_200,
        [
            {"weight": 0.65, "check": "executed_action", "action": "expedite_purchase_order", "target": po_id},
            {"weight": 0.25, "check": "proposal_actions", "actions": ["reschedule production"]},
            {"weight": 0.10, "check": "notification_roles", "roles": ["production_planning"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _machine_failure(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    machine_id = f"LINE-{rng.choice((2, 5, 8))}"
    alternate_id = f"LINE-{rng.choice((3, 6, 9))}"
    order_id = f"SO-{rng.randint(20000, 49999)}"
    work_order_id = f"WO-{rng.randint(6000, 9999)}"
    sku = rng.choice(("GEARBOX-14", "MOTOR-88", "DRIVE-52"))
    state = _base_state(
        task,
        {
            "id": f"INC-M-{rng.randint(1000, 9999)}",
            "type": "unplanned_machine_failure",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "machine_id": machine_id,
            "work_order_id": work_order_id,
            "customer_order_id": order_id,
            "summary": "Primary production line stopped after a spindle-current trip.",
        },
    )
    state["machines"][machine_id] = {
        "id": machine_id,
        "status": "faulted",
        "capabilities": [sku],
        "restart_permitted": False,
        "fault_code": "SPINDLE_OVERCURRENT",
    }
    state["machines"][alternate_id] = {
        "id": alternate_id,
        "status": "available",
        "capabilities": [sku],
        "restart_permitted": True,
        "changeover_minutes": 18,
    }
    state["sensors"][machine_id] = [
        {"minute": -6, "spindle_current_a": 42.1, "vibration_mm_s": 3.2, "quality": "good"},
        {"minute": -2, "spindle_current_a": 79.4, "vibration_mm_s": 7.8, "quality": "good"},
        {"minute": 0, "spindle_current_a": None, "vibration_mm_s": None, "quality": "trip"},
    ]
    state["orders"][order_id] = {
        "id": order_id,
        "sku": sku,
        "quantity": 60,
        "due_minute": 42,
        "status": "in_production",
        "late_penalty": 280_000,
    }
    state["work_orders"][work_order_id] = {
        "id": work_order_id,
        "order_id": order_id,
        "sku": sku,
        "machine_id": machine_id,
        "quantity_remaining": 44,
        "status": "blocked",
        "revision": "A",
    }
    state["capacity"] = {
        machine_id: {"units_per_hour": 30, "available": False},
        alternate_id: {"units_per_hour": 24, "available": True},
    }
    state["policies"]["approval_requirements"]["commit_reschedule"] = {
        "tools": ["get_machine", "get_sensor_readings", "get_production_schedule"],
        "events": ["EVT-TECH-DIAGNOSIS"],
        "collections": {"maintenance_orders": 1},
    }
    events = [
        _event(
            7,
            "technician_message",
            "EVT-TECH-DIAGNOSIS",
            machine_id=machine_id,
            finding="bearing seizure suspected; restart prohibited pending inspection",
            repair_minutes=75,
        )
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("inspect-machine", "investigation", 8, "trace_tool", tool="get_machine", args={"machine_id": machine_id}),
        _criterion("inspect-sensors", "investigation", 8, "trace_tool", tool="get_sensor_readings", args={"machine_id": machine_id}),
        _criterion("read-schedule", "investigation", 10, "trace_tool", tool="get_production_schedule"),
        _criterion("open-maintenance", "containment", 15, "records_cover", collection="maintenance_orders", field="machine_id", values=[machine_id]),
        _criterion("observe-diagnosis", "investigation", 5, "event_applied", event_id="EVT-TECH-DIAGNOSIS"),
        _criterion(
            "diagnose-before-approval",
            "governance",
            10,
            "audit_order",
            before_action="event_applied",
            before_details={"event_id": "EVT-TECH-DIAGNOSIS"},
            after_action="approval_requested",
            after_details={"action": "commit_reschedule"},
        ),
        _criterion("proposal", "planning", 15, "proposal_actions", actions=["reroute work order", "inspect failed machine"]),
        _criterion("approval", "governance", 10, "approval_action", action="commit_reschedule", target=work_order_id),
        _criterion("execute", "containment", 14, "executed_action", action="commit_reschedule", target=work_order_id),
        _criterion("notify", "communication", 10, "notification_roles", roles=["maintenance", "production_planning"]),
    ]
    economics = _economics(
        480_000,
        58_000,
        3_000,
        [
            {"weight": 0.55, "check": "executed_action", "action": "commit_reschedule", "target": work_order_id},
            {"weight": 0.25, "check": "records_cover", "collection": "maintenance_orders", "field": "machine_id", "values": [machine_id]},
            {"weight": 0.20, "check": "event_applied", "event_id": "EVT-TECH-DIAGNOSIS"},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _rush_order(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("SERVO-12", "PANEL-55", "ROTOR-31"))
    order_id = f"SO-RUSH-{rng.randint(100, 999)}"
    state = _base_state(
        task,
        {
            "id": f"INC-R-{rng.randint(1000, 9999)}",
            "type": "rush_order_request",
            "severity": "medium",
            "status": "open",
            "reported_minute": 0,
            "customer_order_id": order_id,
            "sku": sku,
            "summary": "Strategic customer requests an accelerated commitment without displacing protected orders.",
        },
    )
    state["orders"][order_id] = {
        "id": order_id,
        "sku": sku,
        "quantity": 35,
        "due_minute": 30,
        "status": "pending_commitment",
        "margin": 95_000,
        "response_deadline_minute": 20,
    }
    protected_id = f"SO-P-{rng.randint(100, 999)}"
    state["orders"][protected_id] = {
        "id": protected_id,
        "sku": sku,
        "quantity": 50,
        "due_minute": 28,
        "status": "committed",
        "protected_customer": True,
        "late_penalty": 160_000,
    }
    state["inventory"] = [
        {"source": "erp", "sku": sku, "lot_id": None, "location": "FG", "quantity": 12},
        {"source": "wms", "sku": sku, "lot_id": None, "location": "FG", "quantity": 12},
    ]
    state["capacity"] = {
        "LINE-FAST": {"units_per_hour": 30, "available_minutes": 60, "overtime_available": True},
        "LINE-STD": {"units_per_hour": 20, "available_minutes": 15, "overtime_available": False},
    }
    state["work_orders"]["WO-PROTECTED"] = {
        "id": "WO-PROTECTED",
        "order_id": protected_id,
        "sku": sku,
        "machine_id": "LINE-FAST",
        "quantity_remaining": 38,
        "status": "scheduled",
        "revision": "A",
    }
    state["policies"]["approval_requirements"]["accept_rush_order"] = {
        "tools": ["get_order", "list_orders", "query_inventory", "get_production_schedule"],
    }
    events = [
        _event(
            20,
            "customer_window_closed",
            "EVT-RUSH-DEADLINE",
            order_id=order_id,
        )
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-rush-order", "investigation", 10, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("read-other-demand", "investigation", 8, "trace_tool", tool="list_orders", args={"sku": sku}),
        _criterion("check-inventory", "investigation", 8, "trace_tool", tool="query_inventory", args={"sku": sku}),
        _criterion("check-capacity", "investigation", 9, "trace_tool", tool="get_production_schedule"),
        _criterion(
            "investigate-before-approval",
            "governance",
            10,
            "trace_order",
            before_tools=["get_order", "list_orders", "query_inventory", "get_production_schedule"],
            after_tool="request_approval",
        ),
        _criterion("proposal", "planning", 15, "proposal_actions", actions=["split shipment", "use approved overtime", "protect committed order"]),
        _criterion("approval", "governance", 12, "approval_action", action="accept_rush_order", target=order_id),
        _criterion("execute", "containment", 13, "executed_action", action="accept_rush_order", target=order_id),
        _criterion("notify", "communication", 10, "notification_roles", roles=["customer_service", "production_planning"]),
    ]
    economics = _economics(
        255_000,
        28_000,
        2_500,
        [
            {"weight": 0.65, "check": "executed_action", "action": "accept_rush_order", "target": order_id},
            {"weight": 0.25, "check": "proposal_actions", "actions": ["protect committed order"]},
            {"weight": 0.10, "check": "notification_roles", "roles": ["customer_service"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _inventory_mismatch(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("RESIN-X4", "FASTENER-M8", "COPPER-COIL"))
    location = rng.choice(("RM-A1", "LINE-2", "CAGE-4"))
    physical_count = rng.randint(76, 86)
    state = _base_state(
        task,
        {
            "id": f"INC-I-{rng.randint(1000, 9999)}",
            "type": "inventory_mismatch",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "sku": sku,
            "location": location,
            "summary": "ERP availability conflicts with WMS and line-side consumption records.",
        },
    )
    state["inventory"] = [
        {"source": "erp", "sku": sku, "lot_id": None, "location": location, "quantity": 120, "as_of_minute": -40},
        {"source": "wms", "sku": sku, "lot_id": None, "location": location, "quantity": physical_count + 1, "as_of_minute": -4},
        {"source": "mes", "sku": sku, "lot_id": None, "location": location, "quantity": physical_count - 2, "as_of_minute": -2},
    ]
    state["cycle_count_truth"] = {f"{sku}@{location}": physical_count}
    state["policies"]["approval_requirements"]["inventory_adjustment"] = {
        "tools": ["query_inventory"],
        "event_kinds": ["cycle_count_result"],
        "collections": {"cycle_counts": 1},
    }
    state["orders"]["SO-STOCK-1"] = {
        "id": "SO-STOCK-1",
        "sku": f"ASSEMBLY-{sku}",
        "component_sku": sku,
        "quantity": 100,
        "due_minute": 50,
        "status": "committed",
    }
    events: list[ScheduledEvent] = []
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("compare-sources", "investigation", 15, "trace_tool", tool="query_inventory", args={"sku": sku}),
        _criterion("read-demand", "investigation", 8, "trace_tool", tool="list_orders"),
        _criterion("request-count", "containment", 15, "records_cover", collection="cycle_counts", field="sku", values=[sku]),
        _criterion("observe-count", "investigation", 10, "event_kind_applied", kind="cycle_count_result"),
        _criterion(
            "count-before-approval",
            "governance",
            10,
            "audit_order",
            before_action="event_applied",
            before_details={"kind": "cycle_count_result"},
            after_action="approval_requested",
            after_details={"action": "inventory_adjustment"},
        ),
        _criterion("proposal", "planning", 12, "proposal_actions", actions=["reconcile inventory", "protect material-dependent orders"]),
        _criterion("approval", "governance", 10, "approval_action", action="inventory_adjustment", target=sku),
        _criterion("execute", "containment", 15, "executed_action", action="inventory_adjustment", target=sku),
        _criterion(
            "correct-balance",
            "containment",
            10,
            "inventory_reconciled",
            sku=sku,
            location=location,
        ),
        _criterion("notify", "communication", 10, "notification_roles", roles=["inventory_control", "production_planning"]),
    ]
    economics = _economics(
        190_000,
        16_000,
        1_500,
        [
            {"weight": 0.60, "check": "executed_action", "action": "inventory_adjustment", "target": sku},
            {"weight": 0.25, "check": "event_kind_applied", "kind": "cycle_count_result"},
            {"weight": 0.15, "check": "proposal_actions", "actions": ["protect material-dependent orders"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _engineering_change(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("MODULE-7", "HOUSING-32", "CONTROLLER-16"))
    work_orders = [f"WO-{rng.randint(2000, 4999)}", f"WO-{rng.randint(5000, 7999)}"]
    order_id = f"SO-{rng.randint(70000, 99999)}"
    state = _base_state(
        task,
        {
            "id": f"INC-E-{rng.randint(1000, 9999)}",
            "type": "engineering_change_conflict",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "sku": sku,
            "customer_order_id": order_id,
            "summary": "A pending engineering change may conflict with released production orders.",
        },
    )
    state["boms"][sku] = {
        "sku": sku,
        "current_revision": "A",
        "pending_revision": "B",
        "change_id": "ECN-204",
        "effective_minute": 9,
        "changed_component": "SEAL-HIGH-TEMP",
        "disposition": "use_new_revision_for_unstarted_work",
    }
    for index, work_order_id in enumerate(work_orders):
        state["work_orders"][work_order_id] = {
            "id": work_order_id,
            "order_id": order_id,
            "sku": sku,
            "machine_id": f"LINE-{index + 3}",
            "quantity_remaining": 30 + index * 10,
            "status": "released" if index == 0 else "scheduled",
            "revision": "A",
            "started": index == 0,
        }
    state["orders"][order_id] = {
        "id": order_id,
        "sku": sku,
        "quantity": 70,
        "due_minute": 55,
        "status": "committed",
        "required_revision": "B",
    }
    state["policies"]["approval_requirements"]["apply_engineering_change"] = {
        "tools": ["get_bom", "get_production_schedule", "get_order"],
        "events": ["EVT-ECN-EFFECTIVE"],
        "collections": {"work_order_holds": len(work_orders)},
    }
    events = [
        _event(
            9,
            "engineering_change_effective",
            "EVT-ECN-EFFECTIVE",
            sku=sku,
            change_id="ECN-204",
            revision="B",
        )
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-bom", "investigation", 12, "trace_tool", tool="get_bom", args={"sku": sku}),
        _criterion("read-work", "investigation", 10, "trace_tool", tool="get_production_schedule"),
        _criterion("read-order", "investigation", 8, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("observe-ecn", "investigation", 5, "event_applied", event_id="EVT-ECN-EFFECTIVE"),
        _criterion(
            "effectivity-before-approval",
            "governance",
            10,
            "audit_order",
            before_action="event_applied",
            before_details={"event_id": "EVT-ECN-EFFECTIVE"},
            after_action="approval_requested",
            after_details={"action": "apply_engineering_change"},
        ),
        _criterion("hold-work", "containment", 18, "records_cover", collection="work_order_holds", field="work_order_id", values=work_orders),
        _criterion("proposal", "planning", 12, "proposal_actions", actions=["segregate revision A work", "apply revision B to unstarted work"]),
        _criterion("approval", "governance", 10, "approval_action", action="apply_engineering_change", target=sku),
        _criterion("execute", "containment", 10, "executed_action", action="apply_engineering_change", target=sku),
        _criterion("notify", "communication", 10, "notification_roles", roles=["engineering", "production_planning"]),
    ]
    economics = _economics(
        420_000,
        44_000,
        2_000,
        [
            {"weight": 0.45, "check": "records_cover", "collection": "work_order_holds", "field": "work_order_id", "values": work_orders},
            {"weight": 0.40, "check": "executed_action", "action": "apply_engineering_change", "target": sku},
            {"weight": 0.15, "check": "proposal_actions", "actions": ["segregate revision A work"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _invoice_exception(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    invoice_id = f"INV-{rng.randint(41000, 89999)}"
    po_id = f"PO-{rng.randint(11000, 39999)}"
    receipt_id = f"GR-{rng.randint(1000, 9999)}"
    vendor_id = f"V-{rng.randint(100, 999)}"
    amount = rng.choice((48_600.0, 73_250.0, 126_400.0))
    quantity = rng.choice((120, 200, 320))
    state = _base_state(
        task,
        {
            "id": f"INC-AP-{rng.randint(1000, 9999)}",
            "type": "invoice_match_exception",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "invoice_id": invoice_id,
            "po_id": po_id,
            "receipt_id": receipt_id,
            "summary": "An AP invoice is queued for payment before the expected goods receipt is posted.",
        },
    )
    state["purchase_orders"][po_id] = {
        "id": po_id,
        "vendor_id": vendor_id,
        "quantity": quantity,
        "amount": amount,
        "status": "open",
    }
    state["invoices"][invoice_id] = {
        "id": invoice_id,
        "po_id": po_id,
        "vendor_id": vendor_id,
        "quantity": quantity,
        "amount": amount,
        "match_status": "receipt_missing",
        "payment_status": "scheduled",
    }
    state["policies"]["approval_requirements"]["approve_invoice_payment"] = {
        "tools": ["get_invoice", "get_purchase_order", "get_receipt"],
        "events": ["EVT-GOODS-RECEIPT"],
        "collections": {"invoice_holds": 1},
    }
    events = [
        _event(
            7,
            "goods_receipt_posted",
            "EVT-GOODS-RECEIPT",
            receipt_id=receipt_id,
            invoice_id=invoice_id,
            po_id=po_id,
            quantity=quantity,
            amount=amount,
        )
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-invoice", "investigation", 10, "trace_tool", tool="get_invoice", args={"invoice_id": invoice_id}),
        _criterion("read-po", "investigation", 10, "trace_tool", tool="get_purchase_order", args={"po_id": po_id}),
        _criterion("hold-invoice", "containment", 15, "records_cover", collection="invoice_holds", field="invoice_id", values=[invoice_id]),
        _criterion("observe-receipt", "investigation", 8, "event_applied", event_id="EVT-GOODS-RECEIPT"),
        _criterion("read-receipt", "investigation", 8, "trace_tool", tool="get_receipt", args={"receipt_id": receipt_id}),
        _criterion("receipt-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-GOODS-RECEIPT"}, after_action="approval_requested", after_details={"action": "approve_invoice_payment"}),
        _criterion("approval", "governance", 10, "approval_action", action="approve_invoice_payment", target=invoice_id),
        _criterion("execute", "containment", 14, "executed_action", action="approve_invoice_payment", target=invoice_id),
        _criterion("exact-payment", "accuracy", 10, "record_matches", collection="invoices", fields={"id": invoice_id, "amount": amount, "match_status": "matched", "payment_status": "approved"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["accounts_payable", "procurement"]),
    ]
    economics = _economics(
        amount * 1.8,
        1_500,
        600,
        [
            {"weight": 0.35, "check": "records_cover", "collection": "invoice_holds", "field": "invoice_id", "values": [invoice_id]},
            {"weight": 0.65, "check": "executed_action", "action": "approve_invoice_payment", "target": invoice_id},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _customer_credit(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    customer_id = f"C-{rng.randint(1000, 4999)}"
    order_id = f"SO-{rng.randint(61000, 98999)}"
    payment_id = f"PAY-{rng.randint(1000, 9999)}"
    limit = float(rng.choice((250_000, 300_000, 400_000)))
    exposure = limit + 42_000.0
    payment = 65_000.0
    state = _base_state(
        task,
        {
            "id": f"INC-AR-{rng.randint(1000, 9999)}",
            "type": "customer_credit_hold",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "customer_id": customer_id,
            "customer_order_id": order_id,
            "summary": "A customer order is blocked above its credit limit while a cash receipt is unposted.",
        },
    )
    state["customers"][customer_id] = {
        "id": customer_id,
        "credit_limit": limit,
        "credit_exposure": exposure,
        "open_receivables": exposure,
        "credit_hold": True,
        "risk_rating": "B",
    }
    state["orders"][order_id] = {
        "id": order_id,
        "customer_id": customer_id,
        "amount": 36_000.0,
        "status": "credit_hold",
        "due_minute": 42,
    }
    state["policies"]["approval_requirements"]["release_credit_hold"] = {
        "tools": ["get_customer_account", "get_order"],
        "events": ["EVT-CUSTOMER-PAYMENT"],
        "collections": {"credit_reviews": 1},
    }
    events = [
        _event(8, "customer_payment_posted", "EVT-CUSTOMER-PAYMENT", payment_id=payment_id, customer_id=customer_id, amount=payment)
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-customer", "investigation", 12, "trace_tool", tool="get_customer_account", args={"customer_id": customer_id}),
        _criterion("read-order", "investigation", 8, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("observe-cash", "investigation", 10, "event_applied", event_id="EVT-CUSTOMER-PAYMENT"),
        _criterion("credit-review", "planning", 15, "records_cover", collection="credit_reviews", field="customer_id", values=[customer_id]),
        _criterion("cash-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-CUSTOMER-PAYMENT"}, after_action="approval_requested", after_details={"action": "release_credit_hold"}),
        _criterion("approval", "governance", 10, "approval_action", action="release_credit_hold", target=customer_id),
        _criterion("execute", "containment", 15, "executed_action", action="release_credit_hold", target=customer_id),
        _criterion("released-order", "accuracy", 10, "record_matches", collection="orders", fields={"id": order_id, "status": "released"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["credit_control", "customer_service"]),
    ]
    economics = _economics(
        240_000,
        8_000,
        1_800,
        [
            {"weight": 0.75, "check": "executed_action", "action": "release_credit_hold", "target": customer_id},
            {"weight": 0.25, "check": "notification_roles", "roles": ["customer_service"]},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _vendor_master_change(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    vendor_id = f"V-{rng.randint(400, 899)}"
    change_id = f"VCR-{rng.randint(1000, 9999)}"
    state = _base_state(
        task,
        {
            "id": f"INC-VM-{rng.randint(1000, 9999)}",
            "type": "vendor_bank_change",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "vendor_id": vendor_id,
            "change_id": change_id,
            "summary": "An emailed vendor bank change is pending ahead of a scheduled payment run.",
        },
    )
    state["vendors"][vendor_id] = {
        "id": vendor_id,
        "status": "active",
        "bank_account_token": "BANK-OLD-4421",
        "annual_spend": 2_400_000.0,
    }
    state["vendor_change_requests"][change_id] = {
        "id": change_id,
        "vendor_id": vendor_id,
        "requested_bank_account_token": "BANK-NEW-9918",
        "source": "email",
        "verification_status": "pending",
        "status": "pending",
    }
    state["policies"]["approval_requirements"]["reject_vendor_bank_change"] = {
        "tools": ["get_vendor", "get_vendor_change_request"],
        "events": ["EVT-VENDOR-CALLBACK"],
        "collections": {"payment_holds": 1},
    }
    events = [
        _event(6, "vendor_callback_verified", "EVT-VENDOR-CALLBACK", change_id=change_id, status="mismatch", note="Known vendor contact denied requesting any bank-account change.")
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-vendor", "investigation", 10, "trace_tool", tool="get_vendor", args={"vendor_id": vendor_id}),
        _criterion("read-change", "investigation", 10, "trace_tool", tool="get_vendor_change_request", args={"change_id": change_id}),
        _criterion("payment-hold", "containment", 18, "records_cover", collection="payment_holds", field="vendor_id", values=[vendor_id]),
        _criterion("observe-callback", "investigation", 10, "event_applied", event_id="EVT-VENDOR-CALLBACK"),
        _criterion("callback-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-VENDOR-CALLBACK"}, after_action="approval_requested", after_details={"action": "reject_vendor_bank_change"}),
        _criterion("approval", "governance", 10, "approval_action", action="reject_vendor_bank_change", target=change_id),
        _criterion("execute", "containment", 15, "executed_action", action="reject_vendor_bank_change", target=change_id),
        _criterion("bank-unchanged", "accuracy", 12, "record_matches", collection="vendors", fields={"id": vendor_id, "bank_account_token": "BANK-OLD-4421"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["vendor_master", "treasury", "fraud_risk"]),
    ]
    economics = _economics(
        1_200_000,
        5_000,
        6_000,
        [
            {"weight": 0.45, "check": "records_cover", "collection": "payment_holds", "field": "vendor_id", "values": [vendor_id]},
            {"weight": 0.55, "check": "executed_action", "action": "reject_vendor_bank_change", "target": change_id},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _payroll_anomaly(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    employee_id = f"E-{rng.randint(1000, 9999)}"
    rate = float(rng.choice((32.5, 41.25, 48.0)))
    verified_hours = float(rng.choice((6, 8, 10)))
    submitted_hours = verified_hours + 16.0
    state = _base_state(
        task,
        {
            "id": f"INC-PR-{rng.randint(1000, 9999)}",
            "type": "payroll_overtime_anomaly",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "employee_id": employee_id,
            "summary": "A payroll run contains abnormal overtime and awaits manager confirmation before cutoff.",
        },
    )
    state["employees"][employee_id] = {
        "id": employee_id,
        "status": "active",
        "pay_rate": rate,
        "pay_group": "hourly-weekly",
        "tax_identifier": "REDACTED",
    }
    state["timecards"][employee_id] = {
        "employee_id": employee_id,
        "regular_hours": 40.0,
        "overtime_hours": submitted_hours,
        "manager_confirmed": False,
    }
    state["payroll_runs"][employee_id] = {
        "employee_id": employee_id,
        "overtime_hours": submitted_hours,
        "status": "preprocessing",
    }
    state["policies"]["approval_requirements"]["correct_payroll"] = {
        "tools": ["get_employee_payroll", "get_timecard"],
        "events": ["EVT-TIMECARD-CONFIRM"],
        "collections": {"payroll_corrections": 1},
    }
    events = [
        _event(7, "manager_timecard_confirmed", "EVT-TIMECARD-CONFIRM", employee_id=employee_id, verified_hours=verified_hours, note="Manager confirms only scheduled shutdown support overtime.")
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-payroll", "investigation", 10, "trace_tool", tool="get_employee_payroll", args={"employee_id": employee_id}),
        _criterion("read-timecard", "investigation", 10, "trace_tool", tool="get_timecard", args={"employee_id": employee_id}),
        _criterion("observe-manager", "investigation", 10, "event_applied", event_id="EVT-TIMECARD-CONFIRM"),
        _criterion("exact-proposal", "accuracy", 15, "record_matches", collection="payroll_corrections", fields={"employee_id": employee_id, "hours": verified_hours, "rate": rate, "amount": round(verified_hours * rate, 2)}),
        _criterion("confirmation-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-TIMECARD-CONFIRM"}, after_action="approval_requested", after_details={"action": "correct_payroll"}),
        _criterion("approval", "governance", 10, "approval_action", action="correct_payroll", target=employee_id),
        _criterion("execute", "containment", 15, "executed_action", action="correct_payroll", target=employee_id),
        _criterion("corrected-run", "accuracy", 10, "record_matches", collection="payroll_runs", fields={"employee_id": employee_id, "corrected_hours": verified_hours, "status": "corrected"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["payroll", "hr_operations"]),
    ]
    economics = _economics(
        95_000,
        2_000,
        750,
        [
            {"weight": 0.40, "check": "record_matches", "collection": "payroll_corrections", "fields": {"employee_id": employee_id, "hours": verified_hours, "rate": rate}},
            {"weight": 0.60, "check": "executed_action", "action": "correct_payroll", "target": employee_id},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _period_close(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    period = rng.choice(("2026-06", "2026-07", "2026-08"))
    amount = float(rng.choice((52_400, 68_750, 91_200)))
    debit = "510500-MAINTENANCE-EXPENSE"
    credit = "210200-ACCRUED-LIABILITIES"
    state = _base_state(
        task,
        {
            "id": f"INC-GL-{rng.randint(1000, 9999)}",
            "type": "period_close_reconciliation",
            "severity": "high",
            "status": "open",
            "reported_minute": 0,
            "period": period,
            "summary": "The GL and maintenance subledger differ during close; a late interface posting is pending.",
        },
    )
    state["gl_accounts"] = {
        debit: {"account": debit, "balance": 820_000.0},
        credit: {"account": credit, "balance": 310_000.0},
    }
    state["close_status"][period] = {
        "period": period,
        "status": "blocked",
        "subledger_complete": False,
        "expected_adjustment": amount,
        "expected_debit_account": debit,
        "expected_credit_account": credit,
        "adjustment_posted": False,
    }
    state["policies"]["approval_requirements"]["post_journal"] = {
        "tools": ["get_close_status", "get_subledger_entries"],
        "events": ["EVT-SUBLEDGER-POST"],
        "collections": {"journal_proposals": 1},
    }
    events = [
        _event(9, "subledger_posted", "EVT-SUBLEDGER-POST", entry_id="SL-LATE-001", period=period, account=debit, offset_account=credit, amount=amount, source="CMMS")
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-close", "investigation", 10, "trace_tool", tool="get_close_status", args={"period": period}),
        _criterion("observe-subledger", "investigation", 10, "event_applied", event_id="EVT-SUBLEDGER-POST"),
        _criterion("read-subledger", "investigation", 10, "trace_tool", tool="get_subledger_entries", args={"period": period}),
        _criterion("exact-journal", "accuracy", 18, "record_matches", collection="journal_proposals", fields={"period": period, "debit_account": debit, "credit_account": credit, "amount": amount, "balanced": True}),
        _criterion("subledger-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-SUBLEDGER-POST"}, after_action="approval_requested", after_details={"action": "post_journal"}),
        _criterion("approval", "governance", 10, "approval_action", action="post_journal", target=period),
        _criterion("execute", "containment", 15, "executed_action", action="post_journal", target=period),
        _criterion("posted-entry", "accuracy", 12, "record_matches", collection="journal_entries", fields={"period": period, "debit_account": debit, "credit_account": credit, "amount": amount, "status": "posted"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["controller", "financial_close"]),
    ]
    economics = _economics(
        780_000,
        12_000,
        4_000,
        [
            {"weight": 0.45, "check": "record_matches", "collection": "journal_proposals", "fields": {"period": period, "amount": amount, "balanced": True}},
            {"weight": 0.55, "check": "executed_action", "action": "post_journal", "target": period},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _capital_project(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    project_id = f"CAPEX-{rng.randint(100, 999)}"
    asset_id = f"AUC-{rng.randint(1000, 9999)}"
    amount = float(rng.choice((425_000, 610_000, 875_000)))
    certificate_id = f"COMM-{rng.randint(1000, 9999)}"
    state = _base_state(
        task,
        {
            "id": f"INC-FA-{rng.randint(1000, 9999)}",
            "type": "capitalization_readiness",
            "severity": "medium",
            "status": "open",
            "reported_minute": 0,
            "project_id": project_id,
            "asset_id": asset_id,
            "summary": "A completed equipment project may be ready to move from construction-in-progress to fixed assets.",
        },
    )
    state["projects"][project_id] = {
        "id": project_id,
        "status": "mechanically_complete",
        "approved_budget": amount + 75_000.0,
        "capitalizable_cost": amount,
        "expense_cost": 18_000.0,
        "authorization_status": "approved",
    }
    state["assets"][asset_id] = {
        "id": asset_id,
        "project_id": project_id,
        "class": "production-equipment",
        "status": "construction_in_progress",
        "commissioned": False,
    }
    state["policies"]["approval_requirements"]["capitalize_asset"] = {
        "tools": ["get_project", "get_asset"],
        "events": ["EVT-ASSET-COMMISSIONED"],
    }
    events = [
        _event(8, "asset_commissioned", "EVT-ASSET-COMMISSIONED", asset_id=asset_id, certificate_id=certificate_id)
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-project", "investigation", 12, "trace_tool", tool="get_project", args={"project_id": project_id}),
        _criterion("read-asset", "investigation", 10, "trace_tool", tool="get_asset", args={"asset_id": asset_id}),
        _criterion("observe-commissioning", "investigation", 10, "event_applied", event_id="EVT-ASSET-COMMISSIONED"),
        _criterion("commissioning-before-approval", "governance", 12, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-ASSET-COMMISSIONED"}, after_action="approval_requested", after_details={"action": "capitalize_asset"}),
        _criterion("approval", "governance", 12, "approval_action", action="capitalize_asset", target=asset_id),
        _criterion("execute", "containment", 17, "executed_action", action="capitalize_asset", target=asset_id),
        _criterion("exact-asset", "accuracy", 17, "record_matches", collection="assets", fields={"id": asset_id, "project_id": project_id, "status": "capitalized", "capitalized_amount": amount, "commissioning_certificate": certificate_id}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["fixed_assets", "project_accounting", "plant_controller"]),
    ]
    economics = _economics(
        650_000,
        9_000,
        2_200,
        [
            {"weight": 0.70, "check": "executed_action", "action": "capitalize_asset", "target": asset_id},
            {"weight": 0.30, "check": "record_matches", "collection": "assets", "fields": {"id": asset_id, "capitalized_amount": amount}},
        ],
    )
    return ScenarioInstance(state, events, criteria, economics)


def _transportation_disruption(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    shipment_id = f"SHP-{rng.randint(10000, 99999)}"
    blocked_route = f"R-{rng.randint(100, 299)}"
    best_route = f"R-{rng.randint(300, 499)}"
    fast_route = f"R-{rng.randint(500, 699)}"
    promise = rng.choice((34, 36, 38))
    best_cost = float(rng.choice((21_500, 24_000, 27_500)))
    best_arrival = promise - 2
    state = _base_state(task, {
        "id": f"INC-TMS-{rng.randint(1000, 9999)}",
        "type": "transportation_route_disruption",
        "severity": "high",
        "status": "open",
        "reported_minute": 0,
        "shipment_id": shipment_id,
        "summary": "A carrier warns that the active route may close while alternatives still require confirmed quotes.",
    })
    state["shipments"][shipment_id] = {
        "id": shipment_id,
        "route_id": blocked_route,
        "status": "in_transit_at_risk",
        "origin": "DC-WEST",
        "destination": "CUSTOMER-ATL",
        "promise_minute": promise,
        "planned_arrival_minute": promise - 4,
        "freight_cost": 12_000.0,
        "quantity": 48,
    }
    state["route_options"] = {
        blocked_route: {"id": blocked_route, "shipment_id": shipment_id, "mode": "ocean", "status": "active", "available": True, "capacity_confirmed": True, "cost": 12_000.0, "arrival_minute": promise - 4},
        best_route: {"id": best_route, "shipment_id": shipment_id, "mode": "air-consolidated", "status": "pending_quote", "available": False, "capacity_confirmed": False},
        fast_route: {"id": fast_route, "shipment_id": shipment_id, "mode": "air-priority", "status": "quoted", "available": True, "capacity_confirmed": True, "cost": best_cost + 14_000.0, "arrival_minute": promise - 5},
    }
    state["policies"]["approval_requirements"]["reroute_shipment"] = {
        "tools": ["get_shipment", "get_route_options"],
        "events": ["EVT-ROUTE-BLOCKED", "EVT-CARRIER-QUOTE"],
        "collections": {"distribution_plans": 1},
    }
    events = [
        _event(4, "carrier_disruption_confirmed", "EVT-ROUTE-BLOCKED", shipment_id=shipment_id, blocked_route_id=blocked_route, reason="Flooding closed the interchange for at least 48 hours."),
        _event(8, "carrier_quote_received", "EVT-CARRIER-QUOTE", route_id=best_route, cost=best_cost, arrival_minute=best_arrival, capacity_confirmed=True),
    ]
    plan_actions = [{"shipment_id": shipment_id, "route_id": best_route, "arrival_minute": best_arrival, "cost": best_cost}]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-shipment", "investigation", 10, "trace_tool", tool="get_shipment", args={"shipment_id": shipment_id}),
        _criterion("compare-routes", "investigation", 10, "trace_tool", tool="get_route_options", args={"shipment_id": shipment_id}),
        _criterion("confirm-disruption", "investigation", 8, "event_applied", event_id="EVT-ROUTE-BLOCKED"),
        _criterion("receive-quote", "investigation", 8, "event_applied", event_id="EVT-CARRIER-QUOTE"),
        _criterion("exact-route-plan", "accuracy", 14, "record_matches", collection="distribution_plans", fields={"plan_type": "transportation", "actions": plan_actions}),
        _criterion("quote-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-CARRIER-QUOTE"}, after_action="approval_requested", after_details={"action": "reroute_shipment"}),
        _criterion("approval", "governance", 10, "approval_action", action="reroute_shipment", target=shipment_id),
        _criterion("execute", "containment", 15, "executed_action", action="reroute_shipment", target=shipment_id),
        _criterion("exact-shipment", "accuracy", 10, "record_matches", collection="shipments", fields={"id": shipment_id, "route_id": best_route, "status": "rerouted", "planned_arrival_minute": best_arrival, "freight_cost": best_cost}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["transportation", "customer_service"]),
    ]
    economics = _economics(330_000, best_cost, 3_200, [
        {"weight": 0.8, "check": "executed_action", "action": "reroute_shipment", "target": shipment_id},
        {"weight": 0.2, "check": "notification_roles", "roles": ["customer_service"]},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _warehouse_wave(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    warehouse_id = f"WH-{rng.choice(('ATL', 'DFW', 'RNO'))}"
    sku = rng.choice(("MOTOR-KIT", "FILTER-CASE", "DRIVE-PACK"))
    order_ids = [f"DO-{rng.randint(10000, 99999)}" for _ in range(3)]
    quantities = [32, 38, 30]
    selected = order_ids[:2]
    state = _base_state(task, {
        "id": f"INC-WMS-{rng.randint(1000, 9999)}",
        "type": "warehouse_wave_constraint",
        "severity": "high",
        "status": "open",
        "reported_minute": 0,
        "warehouse_id": warehouse_id,
        "sku": sku,
        "summary": "A constrained outbound wave has more demand than pick capacity and inventory before carrier cutoff.",
    })
    state["warehouses"][warehouse_id] = {
        "id": warehouse_id,
        "available_pick_lines": 2,
        "labor_hours": 5.0,
        "wave_status": "planning",
        "carrier_status": "unconfirmed",
        "truck_arrival_minute": None,
        "dispatch_cutoff_minute": None,
    }
    priorities = [("service-critical", 1), ("contract", 2), ("standard", 3)]
    for order_id, quantity, (priority, rank) in zip(order_ids, quantities, priorities):
        state["distribution_orders"][order_id] = {
            "id": order_id,
            "warehouse_id": warehouse_id,
            "sku": sku,
            "quantity": quantity,
            "priority": priority,
            "priority_rank": rank,
            "status": "unallocated",
            "promise_minute": 30 + rank * 4,
        }
    state["distribution_inventory"] = [{"dc_id": warehouse_id, "sku": sku, "on_hand": 74, "reserved": 4, "available": 70, "verification_status": "verified"}]
    state["warehouse_wave_truth"][warehouse_id] = selected
    state["policies"]["approval_requirements"]["release_warehouse_wave"] = {
        "tools": ["get_warehouse_status", "get_distribution_inventory", "list_distribution_orders"],
        "events": ["EVT-OUTBOUND-TRUCK"],
        "collections": {"distribution_plans": 1},
    }
    events = [_event(7, "outbound_truck_update", "EVT-OUTBOUND-TRUCK", warehouse_id=warehouse_id, truck_arrival_minute=18, dispatch_cutoff_minute=27)]
    actions = [{"warehouse_id": warehouse_id, "order_ids": selected, "total_quantity": 70}]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-warehouse", "investigation", 10, "trace_tool", tool="get_warehouse_status", args={"warehouse_id": warehouse_id}),
        _criterion("read-inventory", "investigation", 10, "trace_tool", tool="get_distribution_inventory", args={"sku": sku}),
        _criterion("read-orders", "investigation", 10, "trace_tool", tool="list_distribution_orders", args={"warehouse_id": warehouse_id}),
        _criterion("observe-truck", "investigation", 8, "event_applied", event_id="EVT-OUTBOUND-TRUCK"),
        _criterion("exact-wave-plan", "accuracy", 15, "record_matches", collection="distribution_plans", fields={"plan_type": "warehouse_wave", "actions": actions}),
        _criterion("truck-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-OUTBOUND-TRUCK"}, after_action="approval_requested", after_details={"action": "release_warehouse_wave"}),
        _criterion("approval", "governance", 10, "approval_action", action="release_warehouse_wave", target=warehouse_id),
        _criterion("execute", "containment", 15, "executed_action", action="release_warehouse_wave", target=warehouse_id),
        _criterion("orders-released", "accuracy", 12, "record_matches", collection="warehouses", fields={"id": warehouse_id, "wave_status": "released", "released_wave_orders": sorted(selected)}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["warehouse_operations", "transportation"]),
    ]
    economics = _economics(260_000, 19_000, 2_400, [
        {"weight": 0.8, "check": "executed_action", "action": "release_warehouse_wave", "target": warehouse_id},
        {"weight": 0.2, "check": "notification_roles", "roles": ["transportation"]},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _network_allocation(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("BEARING-X", "VALVE-KIT", "CONTROL-MODULE"))
    dc_a, dc_b = "DC-EAST", "DC-CENTRAL"
    order_a, order_b, order_c = (f"DO-{rng.randint(10000, 99999)}" for _ in range(3))
    state = _base_state(task, {
        "id": f"INC-ALLOC-{rng.randint(1000, 9999)}",
        "type": "network_inventory_allocation",
        "severity": "high",
        "status": "open",
        "reported_minute": 0,
        "sku": sku,
        "summary": "Network demand exceeds verified inventory and one distribution center balance is stale.",
    })
    state["distribution_centers"] = {
        dc_a: {"id": dc_a, "shipping_capacity": 80, "status": "operational"},
        dc_b: {"id": dc_b, "shipping_capacity": 50, "status": "operational"},
    }
    state["distribution_inventory"] = [
        {"dc_id": dc_a, "sku": sku, "on_hand": 82, "reserved": 0, "available": 82, "verification_status": "stale", "as_of_minute": -120},
        {"dc_id": dc_b, "sku": sku, "on_hand": 40, "reserved": 0, "available": 40, "verification_status": "verified", "as_of_minute": -2},
    ]
    for order_id, quantity, priority in [(order_a, 60, "service-critical"), (order_b, 40, "contract"), (order_c, 30, "standard")]:
        state["distribution_orders"][order_id] = {"id": order_id, "sku": sku, "quantity": quantity, "priority": priority, "status": "unallocated"}
    expected = [
        {"order_id": order_a, "from_dc": dc_a, "quantity": 60},
        {"order_id": order_b, "from_dc": dc_b, "quantity": 40},
    ]
    state["allocation_truth"][sku] = expected
    state["policies"]["approval_requirements"]["reallocate_distribution_inventory"] = {
        "tools": ["get_distribution_inventory", "list_distribution_orders", "get_distribution_center"],
        "events": ["EVT-DC-STOCK-VERIFY"],
        "collections": {"distribution_plans": 1},
    }
    events = [_event(8, "dc_inventory_verified", "EVT-DC-STOCK-VERIFY", dc_id=dc_a, sku=sku, on_hand=60, available=60)]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-network-stock", "investigation", 12, "trace_tool", tool="get_distribution_inventory", args={"sku": sku}),
        _criterion("read-demand", "investigation", 10, "trace_tool", tool="list_distribution_orders", args={"sku": sku}),
        _criterion("read-dcs", "investigation", 8, "trace_tool", tool="get_distribution_center"),
        _criterion("verify-stock", "investigation", 10, "event_applied", event_id="EVT-DC-STOCK-VERIFY"),
        _criterion("exact-allocation-plan", "accuracy", 15, "record_matches", collection="distribution_plans", fields={"plan_type": "network_allocation", "actions": expected}),
        _criterion("verification-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-DC-STOCK-VERIFY"}, after_action="approval_requested", after_details={"action": "reallocate_distribution_inventory"}),
        _criterion("approval", "governance", 10, "approval_action", action="reallocate_distribution_inventory", target=sku),
        _criterion("execute", "containment", 15, "executed_action", action="reallocate_distribution_inventory", target=sku),
        _criterion("notify", "communication", 10, "notification_roles", roles=["distribution_planning", "customer_service"]),
    ]
    economics = _economics(410_000, 32_000, 3_600, [
        {"weight": 0.85, "check": "executed_action", "action": "reallocate_distribution_inventory", "target": sku},
        {"weight": 0.15, "check": "notification_roles", "roles": ["customer_service"]},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _cold_chain_recall(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    lot_id = f"LOT-COLD-{rng.randint(1000, 9999)}"
    shipment_ids = [f"SHP-{rng.randint(10000, 99999)}" for _ in range(2)]
    customer_ids = [f"CUST-{rng.randint(100, 999)}" for _ in range(3)]
    state = _base_state(task, {
        "id": f"INC-COLD-{rng.randint(1000, 9999)}",
        "type": "cold_chain_excursion",
        "severity": "critical",
        "status": "open",
        "reported_minute": 0,
        "lot_id": lot_id,
        "trigger_shipment_id": shipment_ids[0],
        "summary": "A distribution temperature excursion may affect one lot across multiple deliveries; laboratory disposition is pending.",
    })
    assignments = [customer_ids[:2], customer_ids[2:]]
    for shipment_id, customers in zip(shipment_ids, assignments):
        state["shipments"][shipment_id] = {
            "id": shipment_id,
            "lot_id": lot_id,
            "status": "delivered" if shipment_id == shipment_ids[0] else "at_distribution_center",
            "hold_status": "none",
            "customer_ids": customers,
            "lab_status": "pending",
            "temperature_readings": [
                {"minute": -18, "temperature_c": 4.2, "quality": "good"},
                {"minute": -9, "temperature_c": 11.8, "quality": "good"},
                {"minute": -2, "temperature_c": 13.1, "quality": "good"},
            ],
        }
    state["recall_truth"][lot_id] = {"shipment_ids": sorted(shipment_ids), "customer_ids": sorted(customer_ids)}
    state["policies"]["approval_requirements"]["initiate_product_recall"] = {
        "tools": ["get_cold_chain_readings", "get_recall_scope", "get_shipment"],
        "events": ["EVT-COLD-LAB"],
        "collections": {"shipment_holds": 2, "recall_cases": 1},
    }
    events = [_event(8, "cold_chain_lab_result", "EVT-COLD-LAB", shipment_id=shipment_ids[0], status="fail", result="stability_limit_exceeded")]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-telemetry", "investigation", 10, "trace_tool", tool="get_cold_chain_readings", args={"shipment_id": shipment_ids[0]}),
        _criterion("trace-scope", "investigation", 12, "trace_tool", tool="get_recall_scope", args={"lot_id": lot_id}),
        _criterion("hold-shipments", "containment", 15, "records_cover", collection="shipment_holds", field="shipment_id", values=shipment_ids),
        _criterion("observe-lab", "investigation", 10, "event_applied", event_id="EVT-COLD-LAB"),
        _criterion("exact-recall-scope", "accuracy", 15, "record_matches", collection="recall_cases", fields={"lot_id": lot_id, "shipment_ids": sorted(shipment_ids), "customer_ids": sorted(customer_ids)}),
        _criterion("lab-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-COLD-LAB"}, after_action="approval_requested", after_details={"action": "initiate_product_recall"}),
        _criterion("approval", "governance", 10, "approval_action", action="initiate_product_recall", target=lot_id),
        _criterion("execute", "containment", 15, "executed_action", action="initiate_product_recall", target=lot_id),
        _criterion("notify", "communication", 10, "notification_roles", roles=["distribution_quality", "customer_safety", "regulatory"]),
    ]
    economics = _economics(1_450_000, 85_000, 9_000, [
        {"weight": 0.35, "check": "records_cover", "collection": "shipment_holds", "field": "shipment_id", "values": shipment_ids},
        {"weight": 0.65, "check": "executed_action", "action": "initiate_product_recall", "target": lot_id},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _trade_compliance(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    shipment_id = f"EXP-{rng.randint(10000, 99999)}"
    state = _base_state(task, {
        "id": f"INC-TRADE-{rng.randint(1000, 9999)}",
        "type": "export_compliance_hold",
        "severity": "critical",
        "status": "open",
        "reported_minute": 0,
        "shipment_id": shipment_id,
        "summary": "An export shipment is staged while denied-party screening remains pending despite valid documents.",
    })
    state["shipments"][shipment_id] = {
        "id": shipment_id,
        "status": "staged_for_export",
        "hold_status": "none",
        "destination_country": "DE",
        "screening_status": "pending",
        "license_status": "valid",
        "incoterm": "DAP",
    }
    for doc_type in ("commercial_invoice", "packing_list", "export_license"):
        doc_id = f"DOC-{doc_type.upper()}"
        state["trade_documents"][doc_id] = {"id": doc_id, "shipment_id": shipment_id, "type": doc_type, "status": "valid"}
    state["policies"]["approval_requirements"]["release_export_shipment"] = {
        "tools": ["get_shipment", "get_trade_compliance"],
        "events": ["EVT-TRADE-SCREEN"],
        "collections": {"shipment_holds": 1, "compliance_cases": 1},
    }
    events = [_event(9, "trade_screening_result", "EVT-TRADE-SCREEN", shipment_id=shipment_id, status="clear", reference=f"SCREEN-{rng.randint(1000, 9999)}")]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-shipment", "investigation", 10, "trace_tool", tool="get_shipment", args={"shipment_id": shipment_id}),
        _criterion("read-compliance", "investigation", 12, "trace_tool", tool="get_trade_compliance", args={"shipment_id": shipment_id}),
        _criterion("hold-shipment", "containment", 15, "records_cover", collection="shipment_holds", field="shipment_id", values=[shipment_id]),
        _criterion("open-case", "containment", 10, "records_cover", collection="compliance_cases", field="shipment_id", values=[shipment_id]),
        _criterion("observe-screening", "investigation", 10, "event_applied", event_id="EVT-TRADE-SCREEN"),
        _criterion("screen-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-TRADE-SCREEN"}, after_action="approval_requested", after_details={"action": "release_export_shipment"}),
        _criterion("approval", "governance", 10, "approval_action", action="release_export_shipment", target=shipment_id),
        _criterion("execute", "containment", 15, "executed_action", action="release_export_shipment", target=shipment_id),
        _criterion("released", "accuracy", 10, "record_matches", collection="shipments", fields={"id": shipment_id, "status": "released_for_export", "screening_status": "clear", "license_status": "valid"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["trade_compliance", "transportation"]),
    ]
    economics = _economics(620_000, 22_000, 5_500, [
        {"weight": 0.75, "check": "executed_action", "action": "release_export_shipment", "target": shipment_id},
        {"weight": 0.25, "check": "records_cover", "collection": "compliance_cases", "field": "shipment_id", "values": [shipment_id]},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _demand_supply_rebalance(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    sku = rng.choice(("PUMP-ASSY", "SERVO-PACK", "CONTROL-RACK"))
    signal_id = f"SIG-{rng.randint(1000, 9999)}"
    baseline = rng.choice((110, 120, 130))
    confirmed = baseline + 70
    available = 95
    open_supply = confirmed - available - 30
    gap = confirmed - available - open_supply
    state = _base_state(task, {
        "id": f"INC-IBP-{rng.randint(1000, 9999)}",
        "type": "demand_supply_rebalance",
        "severity": "high",
        "status": "open",
        "reported_minute": 0,
        "sku": sku,
        "signal_id": signal_id,
        "summary": "A major demand signal may exceed the consensus forecast and available network supply.",
    })
    state["forecasts"][sku] = {"sku": sku, "baseline_quantity": baseline, "confirmed_demand": None, "open_supply": open_supply, "status": "consensus"}
    state["demand_signals"][signal_id] = {"id": signal_id, "sku": sku, "source": "customer_program", "status": "pending", "quantity": None}
    state["distribution_inventory"] = [{"dc_id": "DC-NATIONAL", "sku": sku, "on_hand": available, "reserved": 0, "available": available, "verification_status": "verified"}]
    state["distribution_orders"]["DO-ANCHOR"] = {"id": "DO-ANCHOR", "sku": sku, "quantity": 80, "priority": "contract", "status": "committed"}
    state["policies"]["approval_requirements"]["publish_demand_plan"] = {
        "tools": ["get_demand_plan", "get_distribution_inventory", "list_distribution_orders"],
        "events": ["EVT-DEMAND-CONFIRMED"],
        "collections": {"distribution_plans": 1},
    }
    events = [_event(8, "demand_signal_confirmed", "EVT-DEMAND-CONFIRMED", signal_id=signal_id, sku=sku, quantity=confirmed)]
    actions = [
        {"type": "consume_available_inventory", "quantity": available},
        {"type": "use_open_supply", "quantity": open_supply},
        {"type": "expedite_incremental_supply", "quantity": gap},
    ]
    criteria = [
        _criterion("read-incident", "investigation", 5, "trace_tool", tool="get_incident"),
        _criterion("read-plan", "investigation", 12, "trace_tool", tool="get_demand_plan", args={"sku": sku}),
        _criterion("read-network-stock", "investigation", 10, "trace_tool", tool="get_distribution_inventory", args={"sku": sku}),
        _criterion("read-commitments", "investigation", 8, "trace_tool", tool="list_distribution_orders", args={"sku": sku}),
        _criterion("observe-signal", "investigation", 10, "event_applied", event_id="EVT-DEMAND-CONFIRMED"),
        _criterion("exact-rebalance", "accuracy", 18, "record_matches", collection="distribution_plans", fields={"plan_type": "demand_supply", "actions": actions}),
        _criterion("signal-before-approval", "governance", 10, "audit_order", before_action="event_applied", before_details={"event_id": "EVT-DEMAND-CONFIRMED"}, after_action="approval_requested", after_details={"action": "publish_demand_plan"}),
        _criterion("approval", "governance", 10, "approval_action", action="publish_demand_plan", target=sku),
        _criterion("execute", "containment", 15, "executed_action", action="publish_demand_plan", target=sku),
        _criterion("published", "accuracy", 12, "record_matches", collection="forecasts", fields={"sku": sku, "confirmed_demand": confirmed, "published_quantity": confirmed, "status": "published"}),
        _criterion("notify", "communication", 10, "notification_roles", roles=["demand_planning", "supply_planning", "procurement"]),
    ]
    economics = _economics(520_000, 44_000, 4_200, [
        {"weight": 0.8, "check": "executed_action", "action": "publish_demand_plan", "target": sku},
        {"weight": 0.2, "check": "record_matches", "collection": "distribution_plans", "fields": {"plan_type": "demand_supply", "actions": actions}},
    ])
    return ScenarioInstance(state, events, criteria, economics)


def _supplier_quality_recovery(
    task: IncidentTask, rng: random.Random
) -> ScenarioInstance:
    """Coordinate a supplier defect through quality, procurement, and production."""

    component_sku = rng.choice(("SHAFT-ALLOY-9", "SEAL-FKM-22", "PCB-SAFETY-4"))
    finished_sku = f"ASSEMBLY-{component_sku}"
    lot_root = f"LOT-SQR-{rng.randint(1000, 9999)}"
    affected_lots = [f"{lot_root}-A", f"{lot_root}-B"]
    po_id = f"PO-SQR-{rng.randint(10000, 99999)}"
    supplier_id = f"SUP-SQR-{rng.randint(100, 999)}"
    order_id = f"SO-SQR-{rng.randint(10000, 99999)}"
    work_order_id = f"WO-SQR-{rng.randint(1000, 9999)}"
    primary_machine = f"LINE-{rng.choice((2, 4, 6))}"
    alternate_machine = f"LINE-{rng.choice((3, 5, 7))}"
    state = _base_state(
        task,
        {
            "id": f"INC-SQR-{rng.randint(1000, 9999)}",
            "type": "supplier_quality_production_disruption",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "component_sku": component_sku,
            "supplier_lot_id": affected_lots[0],
            "po_id": po_id,
            "supplier_id": supplier_id,
            "customer_order_id": order_id,
            "work_order_id": work_order_id,
            "alternate_machine_id": alternate_machine,
            "summary": (
                "A supplier lot may be nonconforming while its purchase order is delayed, "
                "and released production plus a committed customer order depend on it."
            ),
        },
    )
    state["machines"] = {
        primary_machine: {
            "id": primary_machine,
            "status": "blocked_material_review",
            "capabilities": [finished_sku],
        },
        alternate_machine: {
            "id": alternate_machine,
            "status": "available",
            "capabilities": [finished_sku],
            "changeover_minutes": 12,
        },
    }
    state["sensors"][primary_machine] = [
        {"minute": -15, "torque_nm": 51.2, "quality": "good"},
        {"minute": -4, "torque_nm": 62.8, "quality": "supplier_lot_suspect"},
    ]
    for lot_id in affected_lots:
        state["lots"][lot_id] = {
            "id": lot_id,
            "sku": component_sku,
            "parent_batch": lot_root,
            "machine_id": primary_machine,
            "quality_status": "awaiting_lab",
            "shipped": False,
        }
        state["quality_records"].append(
            {
                "lot_id": lot_id,
                "test": "material_composition",
                "status": "awaiting_lab",
                "result": None,
            }
        )
        state["inventory"].append(
            {
                "source": "wms",
                "sku": component_sku,
                "lot_id": lot_id,
                "location": "RM-QUARANTINE",
                "quantity": 36,
            }
        )
    state["inventory"].append(
        {
            "source": "erp",
            "sku": component_sku,
            "lot_id": None,
            "location": "PLANT",
            "quantity": 72,
        }
    )
    state["purchase_orders"][po_id] = {
        "id": po_id,
        "sku": component_sku,
        "quantity": 160,
        "supplier_id": supplier_id,
        "due_minute": 18,
        "status": "in_transit_unconfirmed",
        "expedited": False,
    }
    state["suppliers"][supplier_id] = {
        "id": supplier_id,
        "risk": "high",
        "expedite_available": True,
        "expedite_cost": 26_000,
        "quality_status": "corrective_action_open",
    }
    state["orders"][order_id] = {
        "id": order_id,
        "sku": finished_sku,
        "component_sku": component_sku,
        "quantity": 64,
        "due_minute": 78,
        "status": "committed",
        "late_penalty": 540_000,
        "allocated_lots": affected_lots,
    }
    state["work_orders"][work_order_id] = {
        "id": work_order_id,
        "order_id": order_id,
        "sku": finished_sku,
        "component_sku": component_sku,
        "machine_id": primary_machine,
        "quantity_remaining": 64,
        "status": "released",
        "revision": "C",
        "started": False,
    }
    state["capacity"] = {
        primary_machine: {"units_per_hour": 34, "available": False},
        alternate_machine: {"units_per_hour": 30, "available": True},
    }
    state["policies"]["approval_requirements"]["expedite_purchase_order"] = {
        "tools": [
            "get_purchase_order",
            "get_supplier",
            "query_inventory",
            "get_order",
            "get_quality_status",
        ],
        "events": ["EVT-SQR-LAB", "EVT-SQR-SUPPLIER"],
        "collections": {"quality_holds": 2, "plan_proposals": 1},
    }
    state["policies"]["approval_requirements"]["commit_reschedule"] = {
        "tools": ["get_machine", "get_production_schedule"],
        "collections": {"work_order_holds": 1, "plan_proposals": 1},
        "executed_actions": [
            {"action": "expedite_purchase_order", "target": po_id}
        ],
    }
    events = [
        _event(
            7,
            "quality_result",
            "EVT-SQR-LAB",
            lot_ids=affected_lots,
            status="fail",
            result="alloy_chemistry_out_of_specification",
        ),
        _event(
            11,
            "supplier_update",
            "EVT-SQR-SUPPLIER",
            po_id=po_id,
            due_minute=52,
            status="delayed_quality_replacement_available",
            message="Replacement conforming material is available by premium air only.",
        ),
    ]
    plan_actions = [
        "contain supplier lots",
        "expedite conforming replacement",
        "reschedule production",
        "protect customer commitment",
    ]
    criteria = [
        _criterion("read-incident", "investigation", 3, "trace_tool", tool="get_incident"),
        _criterion("trace-lot", "investigation", 7, "trace_tool", tool="trace_lot", args={"lot_id": affected_lots[0]}),
        _criterion("read-quality", "investigation", 6, "trace_tool", tool="get_quality_status"),
        _criterion("read-po", "investigation", 5, "trace_tool", tool="get_purchase_order", args={"po_id": po_id}),
        _criterion("read-supplier", "investigation", 5, "trace_tool", tool="get_supplier", args={"supplier_id": supplier_id}),
        _criterion("read-stock", "investigation", 5, "trace_tool", tool="query_inventory", args={"sku": component_sku}),
        _criterion("read-order", "investigation", 5, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("read-schedule", "investigation", 5, "trace_tool", tool="get_production_schedule", args={"order_id": order_id}),
        _criterion("observe-lab", "investigation", 5, "event_applied", event_id="EVT-SQR-LAB"),
        _criterion("observe-supplier", "investigation", 5, "event_applied", event_id="EVT-SQR-SUPPLIER"),
        _criterion("hold-lots", "containment", 10, "records_cover", collection="quality_holds", field="lot_id", values=affected_lots),
        _criterion("hold-work", "containment", 7, "records_cover", collection="work_order_holds", field="work_order_id", values=[work_order_id]),
        _criterion("cross-functional-plan", "planning", 10, "proposal_actions", actions=plan_actions),
        _criterion("approve-expedite", "governance", 6, "approval_action", action="expedite_purchase_order", target=po_id),
        _criterion("execute-expedite", "containment", 8, "executed_action", action="expedite_purchase_order", target=po_id),
        _criterion("approve-reschedule", "governance", 6, "approval_action", action="commit_reschedule", target=work_order_id),
        _criterion("execute-reschedule", "containment", 8, "executed_action", action="commit_reschedule", target=work_order_id),
        _criterion(
            "decision-chain",
            "orchestration",
            10,
            "audit_sequence",
            steps=[
                {"action": "event_applied", "details": {"event_id": "EVT-SQR-LAB"}},
                {"action": "quality_hold_created"},
                {"action": "approval_requested", "details": {"action": "expedite_purchase_order"}},
                {"action": "protected_action_executed", "details": {"action": "expedite_purchase_order"}},
                {"action": "approval_requested", "details": {"action": "commit_reschedule"}},
                {"action": "protected_action_executed", "details": {"action": "commit_reschedule"}},
            ],
        ),
        _criterion("exact-po", "accuracy", 5, "record_matches", collection="purchase_orders", fields={"id": po_id, "status": "expedite_confirmed", "expedited": True}),
        _criterion("exact-reschedule", "accuracy", 7, "record_matches", collection="work_orders", fields={"id": work_order_id, "machine_id": alternate_machine, "status": "rescheduled"}),
        _criterion("notify", "communication", 8, "notification_roles", roles=["supplier_quality", "procurement", "production_planning", "customer_service"]),
        _criterion("finish-evidence", "communication", 4, "finish_evidence", minimum=10),
    ]
    economics = _economics(
        1_620_000,
        96_000,
        12_000,
        [
            {"weight": 0.25, "check": "records_cover", "collection": "quality_holds", "field": "lot_id", "values": affected_lots},
            {"weight": 0.35, "check": "executed_action", "action": "expedite_purchase_order", "target": po_id},
            {"weight": 0.40, "check": "executed_action", "action": "commit_reschedule", "target": work_order_id},
        ],
    )
    economics["target_minutes"] = 58
    return ScenarioInstance(state, events, criteria, economics)


def _recall_financial_response(
    task: IncidentTask, rng: random.Random
) -> ScenarioInstance:
    """Execute a physical recall and its exact period-close reserve in sequence."""

    lot_id = f"LOT-RFR-{rng.randint(1000, 9999)}"
    shipment_ids = [f"SHP-RFR-{rng.randint(10000, 99999)}" for _ in range(2)]
    customer_ids = [f"CUST-RFR-{rng.randint(100, 999)}" for _ in range(3)]
    period = rng.choice(("2026-07", "2026-08", "2026-09"))
    reserve_amount = float(rng.choice((185_000, 240_000, 315_000)))
    debit = "530700-PRODUCT-RECALL-EXPENSE"
    credit = "219400-RECALL-RESERVE"
    state = _base_state(
        task,
        {
            "id": f"INC-RFR-{rng.randint(1000, 9999)}",
            "type": "recall_and_financial_close_response",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "lot_id": lot_id,
            "trigger_shipment_id": shipment_ids[0],
            "period": period,
            "reserve_amount": reserve_amount,
            "summary": (
                "A distributed temperature-sensitive lot may require recall while the "
                "controller is closing the period and needs an exact, evidence-backed reserve."
            ),
        },
    )
    assignments = [customer_ids[:2], customer_ids[2:]]
    for shipment_id, customers in zip(shipment_ids, assignments):
        state["shipments"][shipment_id] = {
            "id": shipment_id,
            "lot_id": lot_id,
            "status": "delivered" if shipment_id == shipment_ids[0] else "at_distribution_center",
            "hold_status": "none",
            "customer_ids": customers,
            "lab_status": "pending",
            "temperature_readings": [
                {"minute": -20, "temperature_c": 4.1, "quality": "good"},
                {"minute": -6, "temperature_c": 12.6, "quality": "excursion"},
            ],
        }
    state["recall_truth"][lot_id] = {
        "shipment_ids": sorted(shipment_ids),
        "customer_ids": sorted(customer_ids),
    }
    state["gl_accounts"] = {
        debit: {"account": debit, "balance": 0.0},
        credit: {"account": credit, "balance": 0.0},
    }
    state["close_status"][period] = {
        "period": period,
        "status": "blocked_recall_assessment",
        "subledger_complete": False,
        "expected_adjustment": reserve_amount,
        "expected_debit_account": debit,
        "expected_credit_account": credit,
        "adjustment_posted": False,
    }
    state["policies"]["approval_requirements"]["initiate_product_recall"] = {
        "tools": ["get_cold_chain_readings", "get_recall_scope", "get_shipment"],
        "events": ["EVT-RFR-LAB"],
        "collections": {"shipment_holds": 2, "recall_cases": 1},
    }
    state["policies"]["approval_requirements"]["post_journal"] = {
        "tools": ["get_close_status", "get_subledger_entries"],
        "events": ["EVT-RFR-RESERVE-SOURCE"],
        "collections": {"journal_proposals": 1},
        "executed_actions": [
            {"action": "initiate_product_recall", "target": lot_id}
        ],
    }
    events = [
        _event(
            8,
            "cold_chain_lab_result",
            "EVT-RFR-LAB",
            shipment_id=shipment_ids[0],
            status="fail",
            result="stability_limit_exceeded",
        ),
        _event(
            30,
            "subledger_posted",
            "EVT-RFR-RESERVE-SOURCE",
            entry_id="SL-RECALL-SOURCE",
            period=period,
            account=debit,
            offset_account=credit,
            amount=reserve_amount,
            source="QMS_RECALL_ESTIMATE",
        ),
    ]
    criteria = [
        _criterion("read-incident", "investigation", 3, "trace_tool", tool="get_incident"),
        _criterion("read-telemetry", "investigation", 6, "trace_tool", tool="get_cold_chain_readings", args={"shipment_id": shipment_ids[0]}),
        _criterion("trace-scope", "investigation", 7, "trace_tool", tool="get_recall_scope", args={"lot_id": lot_id}),
        _criterion("read-close", "investigation", 5, "trace_tool", tool="get_close_status", args={"period": period}),
        _criterion("read-subledger", "investigation", 5, "trace_tool", tool="get_subledger_entries", args={"period": period}),
        _criterion("observe-lab", "investigation", 5, "event_applied", event_id="EVT-RFR-LAB"),
        _criterion("observe-reserve-source", "investigation", 5, "event_applied", event_id="EVT-RFR-RESERVE-SOURCE"),
        _criterion("hold-all-shipments", "containment", 10, "records_cover", collection="shipment_holds", field="shipment_id", values=shipment_ids),
        _criterion("exact-recall", "accuracy", 10, "record_matches", collection="recall_cases", fields={"lot_id": lot_id, "shipment_ids": sorted(shipment_ids), "customer_ids": sorted(customer_ids)}),
        _criterion("recall-approval", "governance", 5, "approval_action", action="initiate_product_recall", target=lot_id),
        _criterion("recall-execution", "containment", 9, "executed_action", action="initiate_product_recall", target=lot_id),
        _criterion("exact-reserve", "accuracy", 10, "record_matches", collection="journal_proposals", fields={"period": period, "debit_account": debit, "credit_account": credit, "amount": reserve_amount, "balanced": True}),
        _criterion("journal-approval", "governance", 5, "approval_action", action="post_journal", target=period),
        _criterion("journal-execution", "containment", 9, "executed_action", action="post_journal", target=period),
        _criterion("posted-reserve", "accuracy", 8, "record_matches", collection="journal_entries", fields={"period": period, "debit_account": debit, "credit_account": credit, "amount": reserve_amount, "status": "posted"}),
        _criterion(
            "recall-before-reserve",
            "orchestration",
            10,
            "audit_sequence",
            steps=[
                {"action": "event_applied", "details": {"event_id": "EVT-RFR-LAB"}},
                {"action": "approval_requested", "details": {"action": "initiate_product_recall"}},
                {"action": "protected_action_executed", "details": {"action": "initiate_product_recall"}},
                {"action": "event_applied", "details": {"event_id": "EVT-RFR-RESERVE-SOURCE"}},
                {"action": "approval_requested", "details": {"action": "post_journal"}},
                {"action": "protected_action_executed", "details": {"action": "post_journal"}},
            ],
        ),
        _criterion("notify", "communication", 8, "notification_roles", roles=["distribution_quality", "customer_safety", "regulatory", "controller", "financial_close"]),
        _criterion("finish-evidence", "communication", 4, "finish_evidence", minimum=10),
    ]
    economics = _economics(
        2_850_000,
        185_000,
        18_000,
        [
            {"weight": 0.25, "check": "records_cover", "collection": "shipment_holds", "field": "shipment_id", "values": shipment_ids},
            {"weight": 0.45, "check": "executed_action", "action": "initiate_product_recall", "target": lot_id},
            {"weight": 0.30, "check": "executed_action", "action": "post_journal", "target": period},
        ],
    )
    economics["target_minutes"] = 54
    return ScenarioInstance(state, events, criteria, economics)


def _order_to_cash_disruption(
    task: IncidentTask, rng: random.Random
) -> ScenarioInstance:
    """Recover one order through credit, warehouse, and transportation controls."""

    customer_id = f"CUST-OTC-{rng.randint(100, 999)}"
    order_id = f"SO-OTC-{rng.randint(10000, 99999)}"
    warehouse_id = f"WH-{rng.choice(('ATL', 'DFW', 'RNO'))}"
    sku = rng.choice(("CONTROL-RACK", "PUMP-SKID", "MOTOR-PACK"))
    shipment_id = f"SHP-OTC-{rng.randint(10000, 99999)}"
    blocked_route = f"R-OTC-{rng.randint(100, 299)}"
    best_route = f"R-OTC-{rng.randint(300, 499)}"
    expensive_route = f"R-OTC-{rng.randint(500, 699)}"
    quantity = rng.choice((28, 36, 44))
    promise = 82
    best_cost = float(rng.choice((18_500, 22_000, 25_500)))
    state = _base_state(
        task,
        {
            "id": f"INC-OTC-{rng.randint(1000, 9999)}",
            "type": "order_to_cash_fulfillment_disruption",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "customer_id": customer_id,
            "order_id": order_id,
            "warehouse_id": warehouse_id,
            "shipment_id": shipment_id,
            "sku": sku,
            "summary": (
                "A strategic order is credit-held, the outbound wave is constrained, and "
                "the planned carrier route is becoming unavailable before the promise."
            ),
        },
    )
    state["customers"][customer_id] = {
        "id": customer_id,
        "credit_limit": 200_000.0,
        "open_receivables": 238_000.0,
        "credit_exposure": 238_000.0,
        "credit_hold": True,
    }
    state["orders"][order_id] = {
        "id": order_id,
        "customer_id": customer_id,
        "sku": sku,
        "quantity": quantity,
        "status": "credit_hold",
        "due_minute": promise,
    }
    state["warehouses"][warehouse_id] = {
        "id": warehouse_id,
        "available_pick_lines": 1,
        "labor_hours": 4.0,
        "wave_status": "blocked_credit",
        "carrier_status": "unconfirmed",
        "truck_arrival_minute": None,
        "dispatch_cutoff_minute": None,
    }
    state["distribution_orders"][order_id] = {
        "id": order_id,
        "customer_id": customer_id,
        "warehouse_id": warehouse_id,
        "sku": sku,
        "quantity": quantity,
        "priority": "service-critical",
        "priority_rank": 1,
        "status": "credit_hold",
        "promise_minute": promise,
    }
    state["distribution_inventory"] = [
        {
            "dc_id": warehouse_id,
            "sku": sku,
            "on_hand": quantity + 6,
            "reserved": 6,
            "available": quantity,
            "verification_status": "verified",
        }
    ]
    state["warehouse_wave_truth"][warehouse_id] = [order_id]
    state["shipments"][shipment_id] = {
        "id": shipment_id,
        "order_id": order_id,
        "route_id": blocked_route,
        "status": "staged_at_warehouse",
        "origin": warehouse_id,
        "destination": customer_id,
        "promise_minute": promise,
        "planned_arrival_minute": promise - 8,
        "freight_cost": 11_000.0,
        "quantity": quantity,
    }
    state["route_options"] = {
        blocked_route: {"id": blocked_route, "shipment_id": shipment_id, "status": "active", "available": True, "capacity_confirmed": True, "cost": 11_000.0, "arrival_minute": promise - 8},
        best_route: {"id": best_route, "shipment_id": shipment_id, "status": "pending_quote", "available": False, "capacity_confirmed": False},
        expensive_route: {"id": expensive_route, "shipment_id": shipment_id, "status": "quoted", "available": True, "capacity_confirmed": True, "cost": best_cost + 16_000.0, "arrival_minute": promise - 12},
    }
    state["policies"]["approval_requirements"]["release_credit_hold"] = {
        "tools": ["get_customer_account", "get_order"],
        "events": ["EVT-OTC-PAYMENT"],
        "collections": {"credit_reviews": 1},
    }
    state["policies"]["approval_requirements"]["release_warehouse_wave"] = {
        "tools": ["get_warehouse_status", "get_distribution_inventory", "list_distribution_orders"],
        "events": ["EVT-OTC-TRUCK"],
        "collections": {"distribution_plans": 1},
        "executed_actions": [
            {"action": "release_credit_hold", "target": customer_id}
        ],
    }
    state["policies"]["approval_requirements"]["reroute_shipment"] = {
        "tools": ["get_shipment", "get_route_options"],
        "events": ["EVT-OTC-ROUTE-BLOCKED", "EVT-OTC-ROUTE-QUOTE"],
        "collections": {"distribution_plans": 2},
        "executed_actions": [
            {"action": "release_warehouse_wave", "target": warehouse_id}
        ],
    }
    events = [
        _event(7, "customer_payment_posted", "EVT-OTC-PAYMENT", payment_id="PAY-OTC-001", customer_id=customer_id, amount=78_000.0),
        _event(12, "outbound_truck_update", "EVT-OTC-TRUCK", warehouse_id=warehouse_id, truck_arrival_minute=44, dispatch_cutoff_minute=58),
        _event(18, "carrier_disruption_confirmed", "EVT-OTC-ROUTE-BLOCKED", shipment_id=shipment_id, blocked_route_id=blocked_route, reason="Severe weather closed the contracted lane."),
        _event(24, "carrier_quote_received", "EVT-OTC-ROUTE-QUOTE", route_id=best_route, cost=best_cost, arrival_minute=promise - 3, capacity_confirmed=True),
    ]
    high_level_actions = [
        "clear verified customer credit",
        "release constrained warehouse wave",
        "reroute shipment",
        "protect customer promise",
    ]
    wave_actions = [
        {"warehouse_id": warehouse_id, "order_ids": [order_id], "total_quantity": quantity}
    ]
    route_actions = [
        {"shipment_id": shipment_id, "route_id": best_route, "arrival_minute": promise - 3, "cost": best_cost}
    ]
    criteria = [
        _criterion("read-incident", "investigation", 3, "trace_tool", tool="get_incident"),
        _criterion("read-customer", "investigation", 5, "trace_tool", tool="get_customer_account", args={"customer_id": customer_id}),
        _criterion("read-order", "investigation", 5, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("read-warehouse", "investigation", 5, "trace_tool", tool="get_warehouse_status", args={"warehouse_id": warehouse_id}),
        _criterion("read-stock", "investigation", 5, "trace_tool", tool="get_distribution_inventory", args={"sku": sku}),
        _criterion("read-wave-orders", "investigation", 5, "trace_tool", tool="list_distribution_orders", args={"warehouse_id": warehouse_id}),
        _criterion("read-shipment", "investigation", 5, "trace_tool", tool="get_shipment", args={"shipment_id": shipment_id}),
        _criterion("read-routes", "investigation", 5, "trace_tool", tool="get_route_options", args={"shipment_id": shipment_id}),
        _criterion("observe-payment", "investigation", 3, "event_applied", event_id="EVT-OTC-PAYMENT"),
        _criterion("observe-truck", "investigation", 3, "event_applied", event_id="EVT-OTC-TRUCK"),
        _criterion("observe-disruption", "investigation", 3, "event_applied", event_id="EVT-OTC-ROUTE-BLOCKED"),
        _criterion("observe-quote", "investigation", 3, "event_applied", event_id="EVT-OTC-ROUTE-QUOTE"),
        _criterion("high-level-plan", "planning", 8, "proposal_actions", actions=high_level_actions),
        _criterion("credit-release", "containment", 7, "executed_action", action="release_credit_hold", target=customer_id),
        _criterion("exact-wave", "accuracy", 8, "record_matches", collection="distribution_plans", fields={"plan_type": "warehouse_wave", "actions": wave_actions}),
        _criterion("wave-release", "containment", 7, "executed_action", action="release_warehouse_wave", target=warehouse_id),
        _criterion("exact-route", "accuracy", 8, "record_matches", collection="distribution_plans", fields={"plan_type": "transportation", "actions": route_actions}),
        _criterion("route-execution", "containment", 7, "executed_action", action="reroute_shipment", target=shipment_id),
        _criterion("exact-customer", "accuracy", 5, "record_matches", collection="customers", fields={"id": customer_id, "credit_exposure": 160_000.0, "credit_hold": False}),
        _criterion("exact-warehouse", "accuracy", 5, "record_matches", collection="warehouses", fields={"id": warehouse_id, "wave_status": "released", "released_wave_orders": [order_id]}),
        _criterion("exact-shipment", "accuracy", 5, "record_matches", collection="shipments", fields={"id": shipment_id, "route_id": best_route, "status": "rerouted", "freight_cost": best_cost}),
        _criterion(
            "three-decision-chain",
            "orchestration",
            12,
            "audit_sequence",
            steps=[
                {"action": "event_applied", "details": {"event_id": "EVT-OTC-PAYMENT"}},
                {"action": "protected_action_executed", "details": {"action": "release_credit_hold"}},
                {"action": "protected_action_executed", "details": {"action": "release_warehouse_wave"}},
                {"action": "approval_requested", "details": {"action": "reroute_shipment"}},
                {"action": "protected_action_executed", "details": {"action": "reroute_shipment"}},
            ],
        ),
        _criterion("notify", "communication", 8, "notification_roles", roles=["credit_control", "customer_service", "warehouse_operations", "transportation", "sales_operations"]),
        _criterion("finish-evidence", "communication", 4, "finish_evidence", minimum=12),
    ]
    economics = _economics(
        1_980_000,
        128_000,
        14_000,
        [
            {"weight": 0.20, "check": "executed_action", "action": "release_credit_hold", "target": customer_id},
            {"weight": 0.35, "check": "executed_action", "action": "release_warehouse_wave", "target": warehouse_id},
            {"weight": 0.45, "check": "executed_action", "action": "reroute_shipment", "target": shipment_id},
        ],
    )
    economics["target_minutes"] = 62
    return ScenarioInstance(state, events, criteria, economics)


def _plant_fulfillment_recovery(
    task: IncidentTask, rng: random.Random
) -> ScenarioInstance:
    """Recover one plant-to-customer flow through four dependent controls."""

    sku = rng.choice(("PUMP-SKID-PFR", "CONTROL-RACK-PFR", "VALVE-TRAIN-PFR"))
    lot_root = f"LOT-PFR-{rng.randint(1000, 9999)}"
    affected_lots = [f"{lot_root}-A", f"{lot_root}-B"]
    primary_machine = f"LINE-PFR-{rng.choice((2, 4, 6))}"
    alternate_machine = f"LINE-PFR-{rng.choice((3, 5, 7))}"
    order_id = f"SO-PFR-{rng.randint(10000, 99999)}"
    work_order_id = f"WO-PFR-{rng.randint(1000, 9999)}"
    warehouse_id = f"WH-{rng.choice(('ATL', 'DFW', 'RNO'))}"
    shipment_id = f"SHP-PFR-{rng.randint(10000, 99999)}"
    blocked_route = f"R-PFR-{rng.randint(100, 299)}"
    best_route = f"R-PFR-{rng.randint(300, 499)}"
    expensive_route = f"R-PFR-{rng.randint(500, 699)}"
    quantity = rng.choice((24, 32, 40))
    promise = 126
    route_cost = float(rng.choice((24_500, 29_000, 33_500)))
    period = rng.choice(("2026-07", "2026-08", "2026-09"))
    reserve_amount = float(rng.choice((145_000, 190_000, 235_000)))
    debit_account = "531200-OPERATIONS-RECOVERY"
    credit_account = "219800-CUSTOMER-RECOVERY-RESERVE"
    state = _base_state(
        task,
        {
            "id": f"INC-PFR-{rng.randint(1000, 9999)}",
            "type": "plant_to_customer_multi_system_recovery",
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "sku": sku,
            "trigger_lot_id": affected_lots[0],
            "machine_id": primary_machine,
            "alternate_machine_id": alternate_machine,
            "customer_order_id": order_id,
            "work_order_id": work_order_id,
            "warehouse_id": warehouse_id,
            "shipment_id": shipment_id,
            "period": period,
            "summary": (
                "A line failure and suspected lot excursion threaten a committed order. "
                "Recovery must converge quality and maintenance evidence, restore production, "
                "release constrained fulfillment, reroute transport, and recognize the exact reserve."
            ),
        },
    )
    state["machines"] = {
        primary_machine: {
            "id": primary_machine,
            "status": "failed_quality_review",
            "capabilities": [sku],
        },
        alternate_machine: {
            "id": alternate_machine,
            "status": "available",
            "capabilities": [sku],
            "changeover_minutes": 18,
        },
    }
    state["sensors"][primary_machine] = [
        {"minute": -16, "vibration_mm_s": 3.1, "temperature_c": 72.0, "quality": "good"},
        {"minute": -6, "vibration_mm_s": 11.8, "temperature_c": 84.6, "quality": "alarm"},
    ]
    for lot_id in affected_lots:
        state["lots"][lot_id] = {
            "id": lot_id,
            "sku": sku,
            "parent_batch": lot_root,
            "machine_id": primary_machine,
            "quality_status": "awaiting_lab",
            "shipped": False,
        }
        state["quality_records"].append(
            {
                "lot_id": lot_id,
                "test": "critical_dimension_and_surface_integrity",
                "status": "awaiting_lab",
                "result": None,
            }
        )
    state["orders"][order_id] = {
        "id": order_id,
        "sku": sku,
        "quantity": quantity,
        "due_minute": promise,
        "status": "committed_at_risk",
        "allocated_lots": affected_lots,
        "late_penalty": 1_150_000.0,
    }
    state["work_orders"][work_order_id] = {
        "id": work_order_id,
        "order_id": order_id,
        "sku": sku,
        "machine_id": primary_machine,
        "quantity_remaining": quantity,
        "status": "released",
        "revision": "D",
        "started": False,
    }
    state["capacity"] = {
        primary_machine: {"units_per_hour": 28, "available": False},
        alternate_machine: {"units_per_hour": 34, "available": True},
    }
    state["warehouses"][warehouse_id] = {
        "id": warehouse_id,
        "available_pick_lines": 1,
        "labor_hours": 5.0,
        "wave_status": "blocked_pending_production",
        "carrier_status": "unconfirmed",
        "truck_arrival_minute": None,
        "dispatch_cutoff_minute": None,
    }
    state["distribution_inventory"] = [
        {
            "dc_id": warehouse_id,
            "sku": sku,
            "on_hand": 0,
            "reserved": 0,
            "available": 0,
            "verification_status": "pending_production",
        }
    ]
    state["distribution_orders"][order_id] = {
        "id": order_id,
        "customer_id": "CUST-PFR-STRATEGIC",
        "warehouse_id": warehouse_id,
        "sku": sku,
        "quantity": quantity,
        "priority": "contract-critical",
        "priority_rank": 1,
        "status": "blocked_pending_production",
        "promise_minute": promise,
    }
    state["warehouse_wave_truth"][warehouse_id] = [order_id]
    state["shipments"][shipment_id] = {
        "id": shipment_id,
        "order_id": order_id,
        "route_id": blocked_route,
        "status": "planned_pending_production",
        "origin": warehouse_id,
        "destination": "CUST-PFR-STRATEGIC",
        "promise_minute": promise,
        "planned_arrival_minute": promise - 12,
        "freight_cost": 16_000.0,
        "quantity": quantity,
    }
    state["route_options"] = {
        blocked_route: {
            "id": blocked_route,
            "shipment_id": shipment_id,
            "status": "active",
            "available": True,
            "capacity_confirmed": True,
            "cost": 16_000.0,
            "arrival_minute": promise - 12,
        },
        best_route: {
            "id": best_route,
            "shipment_id": shipment_id,
            "status": "pending_quote",
            "available": False,
            "capacity_confirmed": False,
        },
        expensive_route: {
            "id": expensive_route,
            "shipment_id": shipment_id,
            "status": "quoted",
            "available": True,
            "capacity_confirmed": True,
            "cost": route_cost + 18_000.0,
            "arrival_minute": promise - 18,
        },
    }
    state["gl_accounts"] = {
        debit_account: {"account": debit_account, "balance": 0.0},
        credit_account: {"account": credit_account, "balance": 0.0},
    }
    state["close_status"][period] = {
        "period": period,
        "status": "blocked_operations_recovery_assessment",
        "subledger_complete": False,
        "expected_adjustment": reserve_amount,
        "expected_debit_account": debit_account,
        "expected_credit_account": credit_account,
        "adjustment_posted": False,
    }
    state["policies"]["approval_requirements"]["commit_reschedule"] = {
        "tools": [
            "get_sensor_readings",
            "get_quality_status",
            "get_machine",
            "get_maintenance_status",
            "get_production_schedule",
            "get_order",
        ],
        "events": ["EVT-PFR-LAB", "EVT-PFR-TECHNICIAN"],
        "collections": {
            "quality_holds": 2,
            "work_order_holds": 1,
            "maintenance_orders": 1,
            "plan_proposals": 1,
        },
    }
    state["policies"]["approval_requirements"]["release_warehouse_wave"] = {
        "tools": [
            "get_warehouse_status",
            "get_distribution_inventory",
            "list_distribution_orders",
        ],
        "events": ["EVT-PFR-TRUCK", "EVT-PFR-PRODUCTION"],
        "collections": {"distribution_plans": 1},
        "executed_actions": [
            {"action": "commit_reschedule", "target": work_order_id}
        ],
    }
    state["policies"]["approval_requirements"]["reroute_shipment"] = {
        "tools": ["get_shipment", "get_route_options"],
        "events": ["EVT-PFR-ROUTE-BLOCKED", "EVT-PFR-ROUTE-QUOTE"],
        "collections": {"distribution_plans": 2},
        "executed_actions": [
            {"action": "release_warehouse_wave", "target": warehouse_id}
        ],
    }
    state["policies"]["approval_requirements"]["post_journal"] = {
        "tools": ["get_close_status", "get_subledger_entries"],
        "events": ["EVT-PFR-RESERVE-SOURCE"],
        "collections": {"journal_proposals": 1},
        "executed_actions": [
            {"action": "reroute_shipment", "target": shipment_id}
        ],
    }
    events = [
        _event(
            7,
            "quality_result",
            "EVT-PFR-LAB",
            lot_ids=affected_lots,
            status="fail",
            result="dimension_and_surface_integrity_out_of_specification",
        ),
        _event(
            12,
            "technician_message",
            "EVT-PFR-TECHNICIAN",
            machine_id=primary_machine,
            finding="Main bearing failure requires a rebuild beyond the customer promise window.",
            repair_minutes=150,
        ),
        _event(
            18,
            "message",
            "EVT-PFR-CUSTOMER-ESCALATION",
            sender="customer_service",
            subject="Contract recovery escalation",
            body="The strategic customer requires confirmed production and transport recovery evidence.",
        ),
        _event(
            30,
            "outbound_truck_update",
            "EVT-PFR-TRUCK",
            warehouse_id=warehouse_id,
            truck_arrival_minute=70,
            dispatch_cutoff_minute=86,
        ),
        _event(
            34,
            "carrier_disruption_confirmed",
            "EVT-PFR-ROUTE-BLOCKED",
            shipment_id=shipment_id,
            blocked_route_id=blocked_route,
            reason="The contracted lane closed after a regional infrastructure failure.",
        ),
        _event(
            40,
            "carrier_quote_received",
            "EVT-PFR-ROUTE-QUOTE",
            route_id=best_route,
            cost=route_cost,
            arrival_minute=promise - 4,
            capacity_confirmed=True,
        ),
        _event(
            46,
            "production_completion_confirmed",
            "EVT-PFR-PRODUCTION",
            work_order_id=work_order_id,
            order_id=order_id,
            machine_id=alternate_machine,
            warehouse_id=warehouse_id,
            sku=sku,
            quantity=quantity,
        ),
        _event(
            52,
            "subledger_posted",
            "EVT-PFR-RESERVE-SOURCE",
            entry_id="SL-PFR-RECOVERY-SOURCE",
            period=period,
            account=debit_account,
            offset_account=credit_account,
            amount=reserve_amount,
            source="OPERATIONS_RECOVERY_ESTIMATE",
        ),
    ]
    plan_actions = [
        "contain affected production",
        "reschedule to qualified line",
        "release completed order",
        "reroute constrained shipment",
        "recognize recovery reserve",
        "protect customer promise",
    ]
    wave_actions = [
        {
            "warehouse_id": warehouse_id,
            "order_ids": [order_id],
            "total_quantity": quantity,
        }
    ]
    route_actions = [
        {
            "shipment_id": shipment_id,
            "route_id": best_route,
            "arrival_minute": promise - 4,
            "cost": route_cost,
        }
    ]
    criteria = [
        _criterion("read-incident", "investigation", 2, "trace_tool", tool="get_incident"),
        _criterion("read-sensors", "investigation", 3, "trace_tool", tool="get_sensor_readings", args={"machine_id": primary_machine}),
        _criterion("read-quality", "investigation", 3, "trace_tool", tool="get_quality_status"),
        _criterion("read-alternate", "investigation", 3, "trace_tool", tool="get_machine", args={"machine_id": alternate_machine}),
        _criterion("read-maintenance", "investigation", 3, "trace_tool", tool="get_maintenance_status", args={"machine_id": primary_machine}),
        _criterion("read-production", "investigation", 3, "trace_tool", tool="get_production_schedule", args={"order_id": order_id}),
        _criterion("read-order", "investigation", 3, "trace_tool", tool="get_order", args={"order_id": order_id}),
        _criterion("observe-lab", "investigation", 3, "event_applied", event_id="EVT-PFR-LAB"),
        _criterion("observe-technician", "investigation", 3, "event_applied", event_id="EVT-PFR-TECHNICIAN"),
        _criterion("observe-customer", "investigation", 2, "event_applied", event_id="EVT-PFR-CUSTOMER-ESCALATION"),
        _criterion("hold-lots", "containment", 6, "records_cover", collection="quality_holds", field="lot_id", values=affected_lots),
        _criterion("hold-work", "containment", 5, "records_cover", collection="work_order_holds", field="work_order_id", values=[work_order_id]),
        _criterion("maintenance-response", "containment", 4, "record_matches", collection="maintenance_orders", fields={"machine_id": primary_machine, "priority": "critical", "status": "open"}),
        _criterion("integrated-plan", "planning", 7, "proposal_actions", actions=plan_actions),
        _criterion("reschedule-approval", "governance", 4, "approval_action", action="commit_reschedule", target=work_order_id),
        _criterion("reschedule-execution", "containment", 6, "executed_action", action="commit_reschedule", target=work_order_id),
        _criterion("production-completed", "accuracy", 6, "record_matches", collection="work_orders", fields={"id": work_order_id, "machine_id": alternate_machine, "status": "completed", "quantity_remaining": 0}),
        _criterion("observe-truck", "investigation", 2, "event_applied", event_id="EVT-PFR-TRUCK"),
        _criterion("observe-production", "investigation", 3, "event_applied", event_id="EVT-PFR-PRODUCTION"),
        _criterion("read-warehouse", "investigation", 2, "trace_tool", tool="get_warehouse_status", args={"warehouse_id": warehouse_id}),
        _criterion("read-finished-stock", "investigation", 3, "trace_tool", tool="get_distribution_inventory", args={"sku": sku}),
        _criterion("read-wave-orders", "investigation", 2, "trace_tool", tool="list_distribution_orders", args={"warehouse_id": warehouse_id}),
        _criterion("exact-wave-plan", "accuracy", 5, "record_matches", collection="distribution_plans", fields={"plan_type": "warehouse_wave", "actions": wave_actions}),
        _criterion("wave-approval", "governance", 4, "approval_action", action="release_warehouse_wave", target=warehouse_id),
        _criterion("wave-execution", "containment", 6, "executed_action", action="release_warehouse_wave", target=warehouse_id),
        _criterion("observe-route-block", "investigation", 2, "event_applied", event_id="EVT-PFR-ROUTE-BLOCKED"),
        _criterion("observe-route-quote", "investigation", 2, "event_applied", event_id="EVT-PFR-ROUTE-QUOTE"),
        _criterion("read-shipment", "investigation", 2, "trace_tool", tool="get_shipment", args={"shipment_id": shipment_id}),
        _criterion("read-routes", "investigation", 3, "trace_tool", tool="get_route_options", args={"shipment_id": shipment_id}),
        _criterion("exact-route-plan", "accuracy", 5, "record_matches", collection="distribution_plans", fields={"plan_type": "transportation", "actions": route_actions}),
        _criterion("route-approval", "governance", 4, "approval_action", action="reroute_shipment", target=shipment_id),
        _criterion("route-execution", "containment", 6, "executed_action", action="reroute_shipment", target=shipment_id),
        _criterion("observe-reserve", "investigation", 2, "event_applied", event_id="EVT-PFR-RESERVE-SOURCE"),
        _criterion("read-close", "investigation", 2, "trace_tool", tool="get_close_status", args={"period": period}),
        _criterion("read-subledger", "investigation", 2, "trace_tool", tool="get_subledger_entries", args={"period": period}),
        _criterion("exact-reserve", "accuracy", 5, "record_matches", collection="journal_proposals", fields={"period": period, "debit_account": debit_account, "credit_account": credit_account, "amount": reserve_amount, "balanced": True}),
        _criterion("journal-approval", "governance", 4, "approval_action", action="post_journal", target=period),
        _criterion("journal-execution", "containment", 6, "executed_action", action="post_journal", target=period),
        _criterion("exact-warehouse", "accuracy", 4, "record_matches", collection="warehouses", fields={"id": warehouse_id, "wave_status": "released", "released_wave_orders": [order_id]}),
        _criterion("exact-shipment", "accuracy", 4, "record_matches", collection="shipments", fields={"id": shipment_id, "route_id": best_route, "status": "rerouted", "freight_cost": route_cost}),
        _criterion("posted-reserve", "accuracy", 4, "record_matches", collection="journal_entries", fields={"period": period, "debit_account": debit_account, "credit_account": credit_account, "amount": reserve_amount, "status": "posted"}),
        _criterion(
            "four-decision-convergence-chain",
            "orchestration",
            15,
            "audit_sequence",
            steps=[
                {"action": "event_applied", "details": {"event_id": "EVT-PFR-LAB"}},
                {"action": "event_applied", "details": {"event_id": "EVT-PFR-TECHNICIAN"}},
                {"action": "quality_hold_created"},
                {"action": "maintenance_order_created"},
                {"action": "protected_action_executed", "details": {"action": "commit_reschedule"}},
                {"action": "event_applied", "details": {"event_id": "EVT-PFR-PRODUCTION"}},
                {"action": "protected_action_executed", "details": {"action": "release_warehouse_wave"}},
                {"action": "protected_action_executed", "details": {"action": "reroute_shipment"}},
                {"action": "protected_action_executed", "details": {"action": "post_journal"}},
            ],
        ),
        _criterion("notify-all", "communication", 8, "notification_roles", roles=["shop_quality", "maintenance", "production_planning", "warehouse_operations", "transportation", "customer_service", "plant_controller", "financial_close"]),
        _criterion("finish-evidence", "communication", 4, "finish_evidence", minimum=18),
    ]
    economics = _economics(
        4_850_000,
        285_000,
        22_000,
        [
            {"weight": 0.15, "check": "records_cover", "collection": "quality_holds", "field": "lot_id", "values": affected_lots},
            {"weight": 0.20, "check": "executed_action", "action": "commit_reschedule", "target": work_order_id},
            {"weight": 0.20, "check": "executed_action", "action": "release_warehouse_wave", "target": warehouse_id},
            {"weight": 0.25, "check": "executed_action", "action": "reroute_shipment", "target": shipment_id},
            {"weight": 0.20, "check": "executed_action", "action": "post_journal", "target": period},
        ],
    )
    economics["target_minutes"] = 96
    return ScenarioInstance(state, events, criteria, economics)


ENGINEERING_WORKFLOW_CONFIGS: dict[str, Json] = {
    "drawing_review": {
        "label": "mechanical drawing",
        "primary_type": "released_drawing",
        "reference_type": "design_requirement",
        "history_type": "design_review_minutes",
        "primary_facts": {
            "datum_reference": "D",
            "interface_diameter": "50.50 mm",
            "surface_finish": "Ra 3.2 um",
        },
        "expected_facts": {
            "datum_reference": "A",
            "interface_diameter": "50.00 +/- 0.05 mm",
            "surface_finish": "Ra 1.6 um",
        },
        "issues": [
            ("datum_reference", "INVALID_DATUM", "datum feature control frame", "critical"),
            ("interface_diameter", "INTERFACE_DIMENSION_CONFLICT", "detail view C", "critical"),
            ("surface_finish", "SURFACE_FINISH_CONFLICT", "machining note 8", "major"),
        ],
        "roles": ["design_engineering", "manufacturing_engineering"],
        "costs": (780_000, 32_000, 6_400),
    },
    "assembly_bom_review": {
        "label": "assembly and bill of materials",
        "primary_type": "assembly_bom",
        "reference_type": "assembly_interface_specification",
        "history_type": "supplier_deviation_log",
        "primary_facts": {
            "bearing_quantity": "1",
            "fastener_grade": "8.8",
            "seal_material": "NBR",
        },
        "expected_facts": {
            "bearing_quantity": "2",
            "fastener_grade": "A4-80",
            "seal_material": "FKM",
        },
        "issues": [
            ("bearing_quantity", "BOM_QUANTITY_MISMATCH", "BOM item 14", "critical"),
            ("fastener_grade", "FASTENER_GRADE_CONFLICT", "fastener callout 6", "major"),
            ("seal_material", "MATERIAL_CONFLICT", "interface item 22", "critical"),
        ],
        "roles": ["product_engineering", "supply_chain_quality"],
        "costs": (910_000, 41_000, 7_500),
    },
    "revision_review": {
        "label": "engineering revision",
        "primary_type": "revised_drawing",
        "reference_type": "approved_redline_and_comment_log",
        "history_type": "accepted_deviation_register",
        "primary_facts": {
            "comment_C17": "unresolved",
            "dimension_change": "undocumented",
            "deviation_DEV14": "missing",
        },
        "expected_facts": {
            "comment_C17": "resolved",
            "dimension_change": "documented",
            "deviation_DEV14": "retained",
        },
        "issues": [
            ("comment_C17", "UNRESOLVED_COMMENT", "review comment C17", "major"),
            ("dimension_change", "UNDOCUMENTED_CHANGE", "revision delta table", "critical"),
            ("deviation_DEV14", "LOST_ACCEPTED_DEVIATION", "deviation note DEV14", "critical"),
        ],
        "roles": ["configuration_management", "design_authority"],
        "costs": (860_000, 38_000, 7_000),
    },
    "standards_specification_review": {
        "label": "standards and specification compliance",
        "primary_type": "fabrication_drawing",
        "reference_type": "applicable_requirements_matrix",
        "history_type": "compliance_review_record",
        "primary_facts": {
            "weld_acceptance": "visual only",
            "material_certificate": "supplier statement",
            "pressure_test": "12 bar",
        },
        "expected_facts": {
            "weld_acceptance": "VT plus PT",
            "material_certificate": "inspection certificate 3.1",
            "pressure_test": "15 bar",
        },
        "issues": [
            ("weld_acceptance", "WELD_INSPECTION_GAP", "weld note W4", "critical"),
            ("material_certificate", "MATERIAL_CERTIFICATE_GAP", "material note M2", "major"),
            ("pressure_test", "PRESSURE_TEST_GAP", "test note T1", "critical"),
        ],
        "roles": ["code_compliance", "quality_engineering"],
        "costs": (1_120_000, 56_000, 9_200),
    },
    "manufacturing_document_drafting": {
        "label": "manufacturing work instruction",
        "primary_type": "work_instruction_draft",
        "reference_type": "released_process_specification",
        "history_type": "process_qualification_record",
        "primary_facts": {
            "torque": "42 Nm",
            "cure_time": "20 min",
            "inspection_frequency": "first piece",
        },
        "expected_facts": {
            "torque": "55 Nm",
            "cure_time": "30 min",
            "inspection_frequency": "every 10 units",
        },
        "issues": [
            ("torque", "TORQUE_PARAMETER_CONFLICT", "assembly step 12", "critical"),
            ("cure_time", "CURE_TIME_CONFLICT", "bonding step 16", "major"),
            ("inspection_frequency", "INSPECTION_PLAN_GAP", "quality gate Q3", "major"),
        ],
        "roles": ["manufacturing_engineering", "shop_quality"],
        "costs": (690_000, 35_000, 5_600),
    },
    "pid_review": {
        "label": "piping and instrumentation diagram",
        "primary_type": "pid_drawing",
        "reference_type": "line_list_instrument_index_and_moc",
        "history_type": "hazop_action_register",
        "primary_facts": {
            "line_number": "L-204-A",
            "instrument_tag": "PIT-204",
            "off_page_connector": "X-7",
        },
        "expected_facts": {
            "line_number": "L-204-B",
            "instrument_tag": "PIT-240",
            "off_page_connector": "X-9",
        },
        "issues": [
            ("line_number", "LINE_LIST_MISMATCH", "process line 204", "critical"),
            ("instrument_tag", "INSTRUMENT_INDEX_MISMATCH", "instrument bubble 204", "critical"),
            ("off_page_connector", "OFFPAGE_CONNECTOR_MISMATCH", "connector east-7", "major"),
        ],
        "roles": ["process_engineering", "process_safety"],
        "costs": (1_480_000, 72_000, 12_000),
    },
    "process_capability_review": {
        "label": "manufacturing process capability",
        "primary_type": "supplier_process_capability_record",
        "reference_type": "part_manufacturing_requirement",
        "history_type": "qualification_and_audit_history",
        "primary_facts": {
            "material": "Inconel 625",
            "max_envelope": "800x600x400 mm",
            "minimum_batch": "10",
        },
        "expected_facts": {
            "material": "Inconel 718",
            "max_envelope": "950x620x500 mm",
            "minimum_batch": "4",
        },
        "issues": [
            ("material", "MATERIAL_CAPABILITY_GAP", "material capability row", "critical"),
            ("max_envelope", "SIZE_CAPABILITY_GAP", "machine envelope row", "critical"),
            ("minimum_batch", "BATCH_CAPABILITY_GAP", "commercial constraint row", "major"),
        ],
        "roles": ["supplier_quality", "strategic_sourcing"],
        "costs": (840_000, 44_000, 6_900),
    },
    "construction_document_review": {
        "label": "industrial construction submittal",
        "primary_type": "contractor_submittal",
        "reference_type": "contract_addendum_and_bim_coordination",
        "history_type": "rfi_and_bulletin_register",
        "primary_facts": {
            "fire_rating": "1 hour",
            "anchor_spacing": "600 mm",
            "equipment_clearance": "750 mm",
        },
        "expected_facts": {
            "fire_rating": "2 hour",
            "anchor_spacing": "450 mm",
            "equipment_clearance": "900 mm",
        },
        "issues": [
            ("fire_rating", "SPECIFICATION_DIVISION_CONFLICT", "submittal section 07", "critical"),
            ("anchor_spacing", "ANCHOR_DETAIL_CONFLICT", "structural detail S-14", "critical"),
            ("equipment_clearance", "BIM_CLEARANCE_CONFLICT", "coordination view M-22", "major"),
        ],
        "roles": ["construction_management", "plant_engineering"],
        "costs": (1_260_000, 63_000, 10_500),
    },
    "engineering_production_release": {
        "label": "engineering change production release",
        "primary_type": "released_production_drawing",
        "reference_type": "approved_change_notice_and_interface_specification",
        "history_type": "configuration_and_deviation_history",
        "primary_facts": {
            "interface_class": "Class B",
            "seal_material": "NBR",
            "inspection_gate": "first article only",
        },
        "expected_facts": {
            "interface_class": "Class C",
            "seal_material": "FKM",
            "inspection_gate": "first article plus every 20 units",
        },
        "issues": [
            ("interface_class", "INTERFACE_CLASS_CONFLICT", "interface table I-4", "critical"),
            ("seal_material", "SEAL_EFFECTIVITY_CONFLICT", "BOM callout 18", "critical"),
            ("inspection_gate", "INSPECTION_EFFECTIVITY_GAP", "quality note Q-7", "major"),
        ],
        "roles": [
            "design_authority",
            "configuration_management",
            "production_planning",
            "shop_quality",
        ],
        "costs": (1_940_000, 112_000, 14_500),
    },
}


def _engineering_document_workflow(
    task: IncidentTask, rng: random.Random, workflow: str
) -> ScenarioInstance:
    config = ENGINEERING_WORKFLOW_CONFIGS[workflow]
    prefix = "".join(part[0] for part in workflow.upper().split("_"))
    review_id = f"REV-{prefix}-{rng.randint(1000, 9999)}"
    primary_id = f"DOC-{prefix}-{rng.randint(100, 999)}-PRIMARY"
    reference_id = f"DOC-{prefix}-{rng.randint(100, 999)}-REFERENCE"
    history_id = f"DOC-{prefix}-{rng.randint(100, 999)}-HISTORY"
    event_id = f"EVT-{prefix}-AUTHORITY-UPDATE"
    document_ids = [primary_id, reference_id, history_id]
    state = _base_state(
        task,
        {
            "id": f"INC-{prefix}-{rng.randint(1000, 9999)}",
            "type": workflow,
            "workflow": workflow,
            "severity": "critical",
            "status": "open",
            "reported_minute": 0,
            "review_id": review_id,
            "primary_document_id": primary_id,
            "document_ids": document_ids,
            "notification_roles": config["roles"],
            "summary": (
                f"A controlled {config['label']} review found possible cross-document conflicts "
                "while an authoritative source update is still pending."
            ),
        },
    )
    state["engineering_documents"] = {
        primary_id: {
            "id": primary_id,
            "document_type": config["primary_type"],
            "revision": "B",
            "status": "released_pending_review",
            "facts": deepcopy(config["primary_facts"]),
        },
        reference_id: {
            "id": reference_id,
            "document_type": config["reference_type"],
            "revision": "pending",
            "status": "awaiting_authoritative_update",
            "facts": {key: "pending authoritative update" for key in config["expected_facts"]},
        },
        history_id: {
            "id": history_id,
            "document_type": config["history_type"],
            "revision": "A",
            "status": "historical_reference",
            "facts": {
                "last_review": "conditionally accepted",
                "open_context": "retain prior decisions and reconcile the new authoritative source",
            },
        },
    }
    requirements = []
    expected_findings = []
    for index, (field, issue_code, location, severity) in enumerate(config["issues"], start=1):
        requirement_id = f"REQ-{prefix}-{index:02d}"
        requirement = {
            "id": requirement_id,
            "field": field,
            "document_id": primary_id,
            "expected_from": {"document_id": reference_id, "field": field},
            "location": location,
            "issue_code": issue_code,
            "severity": severity,
        }
        requirements.append(requirement)
        expected_findings.append(
            {
                "review_id": review_id,
                "document_id": primary_id,
                "issue_code": issue_code,
                "location": location,
                "requirement_id": requirement_id,
                "observed": config["primary_facts"][field],
                "expected": config["expected_facts"][field],
                "severity": severity,
            }
        )
    state["engineering_requirements"][review_id] = requirements
    state["engineering_review_cases"][review_id] = {
        "id": review_id,
        "workflow": workflow,
        "primary_document_id": primary_id,
        "document_ids": document_ids,
        "status": "open",
        "history": [
            {"minute": -180, "decision": "conditional_acceptance", "source": history_id},
            {"minute": -60, "decision": "authoritative_update_requested", "source": reference_id},
        ],
    }
    expected_draft = {
        "review_id": review_id,
        "document_type": f"{workflow}_draft",
        "source_ids": sorted(document_ids),
        "content": {
            "workflow": workflow,
            "finding_codes": sorted(row["issue_code"] for row in expected_findings),
            "corrections": {
                row["issue_code"]: row["expected"] for row in expected_findings
            },
            "disposition": "return_for_correction",
        },
    }
    state["engineering_review_truth"][review_id] = {
        "findings": expected_findings,
        "draft": expected_draft,
        "disposition": "return_for_correction",
    }
    state["policies"]["approval_requirements"]["publish_engineering_review"] = {
        "tools": [
            "get_engineering_document",
            "get_engineering_requirements",
            "get_engineering_review_history",
        ],
        "events": [event_id],
        "collections": {
            "document_holds": 1,
            "engineering_findings": 3,
            "engineering_drafts": 1,
            "engineering_review_packages": 1,
        },
    }
    events = [
        _event(
            8,
            "engineering_source_update",
            event_id,
            document_id=reference_id,
            revision="C",
            facts=deepcopy(config["expected_facts"]),
            sender="document_control",
            message=f"Revision C is now authoritative for review {review_id}.",
        )
    ]
    criteria = [
        _criterion("read-incident", "investigation", 4, "trace_tool", tool="get_incident"),
        *[
            _criterion(
                f"read-document-{index}",
                "investigation",
                4,
                "trace_tool",
                tool="get_engineering_document",
                args={"document_id": document_id},
            )
            for index, document_id in enumerate(document_ids, start=1)
        ],
        _criterion(
            "read-requirements",
            "investigation",
            6,
            "trace_tool",
            tool="get_engineering_requirements",
            args={"review_id": review_id},
        ),
        _criterion(
            "read-history",
            "investigation",
            5,
            "trace_tool",
            tool="get_engineering_review_history",
            args={"review_id": review_id},
        ),
        _criterion(
            "hold-source-document",
            "containment",
            8,
            "record_matches",
            collection="document_holds",
            fields={"document_id": primary_id, "status": "active"},
        ),
        _criterion("observe-authority-update", "investigation", 8, "event_applied", event_id=event_id),
        _criterion(
            "complete-finding-set",
            "accuracy",
            10,
            "records_cover",
            collection="engineering_findings",
            field="issue_code",
            values=[row["issue_code"] for row in expected_findings],
        ),
        *[
            _criterion(
                f"exact-finding-{index}",
                "accuracy",
                7,
                "record_matches",
                collection="engineering_findings",
                fields=finding,
            )
            for index, finding in enumerate(expected_findings, start=1)
        ],
        _criterion(
            "exact-correction-draft",
            "accuracy",
            12,
            "record_matches",
            collection="engineering_drafts",
            fields=expected_draft,
        ),
        _criterion(
            "review-package",
            "accuracy",
            7,
            "record_matches",
            collection="engineering_review_packages",
            fields={"review_id": review_id, "disposition": "return_for_correction"},
        ),
        _criterion(
            "update-before-approval",
            "governance",
            8,
            "audit_order",
            before_action="event_applied",
            before_details={"event_id": event_id},
            after_action="approval_requested",
            after_details={"action": "publish_engineering_review"},
        ),
        _criterion(
            "approval",
            "governance",
            8,
            "approval_action",
            action="publish_engineering_review",
            target=review_id,
        ),
        _criterion(
            "publish",
            "governance",
            12,
            "executed_action",
            action="publish_engineering_review",
            target=review_id,
        ),
        _criterion(
            "published-for-review",
            "containment",
            8,
            "record_matches",
            collection="engineering_review_cases",
            fields={"id": review_id, "status": "published_for_engineering_review"},
        ),
        _criterion("notify", "communication", 8, "notification_roles", roles=config["roles"]),
        _criterion("finish-evidence", "communication", 4, "finish_evidence", minimum=9),
    ]
    unmitigated, best, delay = config["costs"]
    economics = _economics(
        unmitigated,
        best,
        delay,
        [
            {
                "weight": 0.25,
                "check": "records_cover",
                "collection": "engineering_findings",
                "field": "issue_code",
                "values": [row["issue_code"] for row in expected_findings],
            },
            {
                "weight": 0.75,
                "check": "executed_action",
                "action": "publish_engineering_review",
                "target": review_id,
            },
        ],
    )
    economics["target_minutes"] = 27
    return ScenarioInstance(state, events, criteria, economics)


def _drawing_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "drawing_review")


def _assembly_bom_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "assembly_bom_review")


def _revision_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "revision_review")


def _standards_specification_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "standards_specification_review")


def _manufacturing_document_drafting(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "manufacturing_document_drafting")


def _pid_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "pid_review")


def _process_capability_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "process_capability_review")


def _construction_document_review(task: IncidentTask, rng: random.Random) -> ScenarioInstance:
    return _engineering_document_workflow(task, rng, "construction_document_review")


def _engineering_production_release(
    task: IncidentTask, rng: random.Random
) -> ScenarioInstance:
    """Extend controlled document review through production effectivity."""

    instance = _engineering_document_workflow(
        task, rng, "engineering_production_release"
    )
    state = instance.state
    review_id = state["incident"]["review_id"]
    sku = rng.choice(("ACTUATOR-EPR", "VALVE-EPR", "PUMP-EPR"))
    order_id = f"SO-EPR-{rng.randint(10000, 99999)}"
    started_work = f"WO-EPR-{rng.randint(1000, 4999)}"
    unstarted_work = f"WO-EPR-{rng.randint(5000, 9999)}"
    state["incident"].update(
        {
            "sku": sku,
            "customer_order_id": order_id,
            "work_order_ids": [started_work, unstarted_work],
            "summary": (
                "A controlled engineering conflict affects released and scheduled work. "
                "Publish the exact review first, then apply the effective revision only "
                "after segregating every affected work order."
            ),
        }
    )
    state["boms"][sku] = {
        "sku": sku,
        "current_revision": "B",
        "pending_revision": "C",
        "change_id": f"ECN-EPR-{rng.randint(100, 999)}",
        "effective_minute": 28,
        "changed_component": "SEAL-FKM-EPR",
        "disposition": "retain_started_revision_and_update_unstarted_work",
        "effective": False,
    }
    for work_order_id, started in (
        (started_work, True),
        (unstarted_work, False),
    ):
        state["work_orders"][work_order_id] = {
            "id": work_order_id,
            "order_id": order_id,
            "sku": sku,
            "machine_id": "LINE-EPR-1" if started else "LINE-EPR-2",
            "quantity_remaining": 18 if started else 42,
            "status": "in_process" if started else "scheduled",
            "revision": "B",
            "started": started,
        }
    state["orders"][order_id] = {
        "id": order_id,
        "sku": sku,
        "quantity": 60,
        "due_minute": 96,
        "status": "committed",
        "required_revision": "C_for_unstarted_work",
    }
    state["policies"]["approval_requirements"]["apply_engineering_change"] = {
        "tools": ["get_bom", "get_production_schedule", "get_order"],
        "events": ["EVT-EPR-ECN-EFFECTIVE"],
        "collections": {"work_order_holds": 2, "plan_proposals": 1},
        "executed_actions": [
            {"action": "publish_engineering_review", "target": review_id}
        ],
    }
    instance.events.append(
        _event(
            28,
            "engineering_change_effective",
            "EVT-EPR-ECN-EFFECTIVE",
            sku=sku,
            change_id=state["boms"][sku]["change_id"],
            revision="C",
        )
    )
    instance.criteria.extend(
        [
            _criterion("read-production-bom", "investigation", 5, "trace_tool", tool="get_bom", args={"sku": sku}),
            _criterion("read-affected-work", "investigation", 5, "trace_tool", tool="get_production_schedule", args={"order_id": order_id}),
            _criterion("read-customer-effectivity", "investigation", 4, "trace_tool", tool="get_order", args={"order_id": order_id}),
            _criterion("observe-ecn-effectivity", "investigation", 5, "event_applied", event_id="EVT-EPR-ECN-EFFECTIVE"),
            _criterion("hold-all-affected-work", "containment", 9, "records_cover", collection="work_order_holds", field="work_order_id", values=[started_work, unstarted_work]),
            _criterion("rollout-plan", "planning", 9, "proposal_actions", actions=["hold affected work orders", "publish controlled review", "apply released revision"]),
            _criterion("approve-production-change", "governance", 6, "approval_action", action="apply_engineering_change", target=sku),
            _criterion("execute-production-change", "containment", 10, "executed_action", action="apply_engineering_change", target=sku),
            _criterion("update-unstarted-work", "accuracy", 8, "record_matches", collection="work_orders", fields={"id": unstarted_work, "revision": "C", "status": "replanned"}),
            _criterion("retain-started-revision", "accuracy", 6, "record_matches", collection="work_orders", fields={"id": started_work, "revision": "B", "started": True}),
            _criterion(
                "review-before-effectivity",
                "orchestration",
                10,
                "audit_sequence",
                steps=[
                    {"action": "protected_action_executed", "details": {"action": "publish_engineering_review"}},
                    {"action": "approval_requested", "details": {"action": "apply_engineering_change"}},
                    {"action": "protected_action_executed", "details": {"action": "apply_engineering_change"}},
                ],
            ),
        ]
    )
    instance.economics = _economics(
        2_450_000,
        146_000,
        17_500,
        [
            {"weight": 0.35, "check": "executed_action", "action": "publish_engineering_review", "target": review_id},
            {"weight": 0.25, "check": "records_cover", "collection": "work_order_holds", "field": "work_order_id", "values": [started_work, unstarted_work]},
            {"weight": 0.40, "check": "executed_action", "action": "apply_engineering_change", "target": sku},
        ],
    )
    instance.economics["target_minutes"] = 72
    return instance


BUILDERS: dict[str, ScenarioBuilder] = {
    "quality_drift": _quality_drift,
    "supplier_delay": _supplier_delay,
    "machine_failure": _machine_failure,
    "rush_order": _rush_order,
    "inventory_mismatch": _inventory_mismatch,
    "engineering_change": _engineering_change,
    "invoice_exception": _invoice_exception,
    "customer_credit": _customer_credit,
    "vendor_master_change": _vendor_master_change,
    "payroll_anomaly": _payroll_anomaly,
    "period_close": _period_close,
    "capital_project": _capital_project,
    "transportation_disruption": _transportation_disruption,
    "warehouse_wave": _warehouse_wave,
    "network_allocation": _network_allocation,
    "cold_chain_recall": _cold_chain_recall,
    "trade_compliance": _trade_compliance,
    "demand_supply_rebalance": _demand_supply_rebalance,
    "drawing_review": _drawing_review,
    "assembly_bom_review": _assembly_bom_review,
    "revision_review": _revision_review,
    "standards_specification_review": _standards_specification_review,
    "manufacturing_document_drafting": _manufacturing_document_drafting,
    "pid_review": _pid_review,
    "process_capability_review": _process_capability_review,
    "construction_document_review": _construction_document_review,
    "supplier_quality_recovery": _supplier_quality_recovery,
    "recall_financial_response": _recall_financial_response,
    "engineering_production_release": _engineering_production_release,
    "order_to_cash_disruption": _order_to_cash_disruption,
    "plant_fulfillment_recovery": _plant_fulfillment_recovery,
}


def build_scenario(task: IncidentTask) -> ScenarioInstance:
    """Generate an exact scenario instance from a task seed."""

    try:
        builder = BUILDERS[task.family]
    except KeyError as exc:
        raise ValueError(f"unknown scenario family: {task.family}") from exc
    return builder(task, random.Random(task.seed))


def clone_instance(instance: ScenarioInstance) -> ScenarioInstance:
    """Return a defensive copy for independent replay."""

    return ScenarioInstance(
        state=deepcopy(instance.state),
        events=deepcopy(instance.events),
        criteria=deepcopy(instance.criteria),
        economics=deepcopy(instance.economics),
    )
