"""Network allocations conserve current stock and reject repeated commitments."""

from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner, BudgetedToolClient
from faraday_industrial_benchmark.world import IndustrialWorld


def approved_allocation():
    task = next(
        task for task in load_tasks(Path(__file__).parents[1] / "data/public/tasks.json")
        if task.family == "network_allocation"
    )
    reference = BenchmarkRunner().run_task(task, OracleAgent())
    world = IndustrialWorld(task)
    tools = BudgetedToolClient(world)
    for call in reference.trace:
        if call.tool == "execute_action":
            return world, tools, deepcopy(call.arguments)
        tools.call_raw(call.tool, call.arguments)
    raise AssertionError("Reference never executes an allocation")


def test_repeat_allocation_with_new_approval_cannot_consume_stock_twice():
    world, tools, execution = approved_allocation()
    assert tools.call("execute_action", **execution)["ok"]
    stock = deepcopy(world.state["distribution_inventory"])
    action = world.state["executed_actions"][-1]
    approval = tools.call(
        "request_approval", action=action["action"], target=action["target"],
        reason="Repeat the completed allocation using a fresh approval.", payload=action["payload"],
    )["approval"]
    result = tools.call("execute_action", action=action["action"], target=action["target"],
                        approval_id=approval["id"])
    assert result["error"] == "distribution_order_already_allocated"
    assert world.state["distribution_inventory"] == stock
    assert all(row["available"] >= 0 for row in stock)


def test_post_approval_stock_loss_rejects_before_any_order_or_stock_mutation():
    world, tools, execution = approved_allocation()
    world.state["distribution_inventory"][-1]["available"] = 0
    stock = deepcopy(world.state["distribution_inventory"])
    orders = deepcopy(world.state["distribution_orders"])
    result = tools.call("execute_action", **execution)
    assert result["error"] == "network_inventory_not_available"
    assert world.state["distribution_inventory"] == stock
    assert world.state["distribution_orders"] == orders


def test_multiple_stock_rows_at_one_dc_are_consumed_once_in_total():
    world, tools, execution = approved_allocation()
    row = world.state["distribution_inventory"][0]
    initial_quantity = row["available"]
    split = deepcopy(row)
    row["available"] = initial_quantity // 2
    split["available"] = initial_quantity - row["available"]
    world.state["distribution_inventory"].append(split)
    initial_stock = sum(row["available"] for row in world.state["distribution_inventory"])
    assert tools.call("execute_action", **execution)["ok"]
    allocated = sum(order.get("allocated_quantity", 0)
                    for order in world.state["distribution_orders"].values())
    remaining = sum(row["available"] for row in world.state["distribution_inventory"])
    assert initial_stock - remaining == allocated
    assert all(row["available"] >= 0 for row in world.state["distribution_inventory"])


def test_missing_later_order_does_not_leave_an_earlier_partial_allocation():
    world, tools, execution = approved_allocation()
    approval = world.state["approvals"][execution["approval_id"]]
    missing_id = approval["payload"]["allocations"][-1]["order_id"]
    world.state["distribution_orders"].pop(missing_id)
    stock = deepcopy(world.state["distribution_inventory"])
    orders = deepcopy(world.state["distribution_orders"])
    result = tools.call("execute_action", **execution)
    assert result["error"] == "distribution_order_not_found"
    assert world.state["distribution_inventory"] == stock
    assert world.state["distribution_orders"] == orders
