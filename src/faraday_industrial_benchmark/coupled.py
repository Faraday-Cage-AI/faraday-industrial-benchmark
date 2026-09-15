"""Coupled customer service contracts and exact resource-state optimization."""

from itertools import product


def group_charge(group, modes):
    shipped = [mode for mode in modes if mode != "defer"]
    if len(shipped) < group["minimum_orders"]:
        return None
    # A paired installation kit must arrive together, or both components defer.
    if group["paired_first_two"] and modes[0] != modes[1]:
        return None
    deferred = len(modes) - len(shipped)
    return group["service_credit_cents"][deferred]


def surcharge(case, assignments):
    by_id = {row["order_id"]: row["mode"] for row in assignments}
    total = 0
    for group in case["coupling"]["customers"]:
        charge = group_charge(group, [by_id[oid] for oid in group["orders"]])
        if charge is None:
            return None
        total += charge
    used = set(by_id.values()) - {"defer"}
    return total + sum(case["coupling"]["activation_fees_cents"][mode] for mode in used)


def solve_branch(case, reservations, scenario):
    from .contingent import MODES, capacities, choice, reservation_fee

    limits = capacities(case, reservations, scenario)
    orders = {row["order_id"]: row for row in case["orders"]}
    states = {(0, 0, 0): (0, [])}
    for group in case["coupling"]["customers"]:
        options = {}
        for modes in product(MODES, repeat=len(group["orders"])):
            credit = group_charge(group, modes)
            if credit is None:
                continue
            choices = [
                choice(case, scenario, orders[oid], mode)
                for oid, mode in zip(group["orders"], modes)
            ]
            if any(option is None for option in choices):
                continue
            usage = tuple(sum(option[1][i] for option in choices) for i in range(3))
            cost = credit + sum(option[0] for option in choices)
            if usage not in options or cost < options[usage][0]:
                options[usage] = (
                    cost,
                    [{"order_id": oid, "mode": mode} for oid, mode in zip(group["orders"], modes)],
                )
        following = {}
        for used, (cost, rows) in states.items():
            for usage, (charge, assignments) in options.items():
                new = tuple(a + b for a, b in zip(used, usage))
                if any(a > b for a, b in zip(new, limits)):
                    continue
                if (
                    sum(a * b for a, b in zip(new, case["finance"]["emissions_per_pack"]))
                    > case["finance"]["emissions_cap"]
                ):
                    continue
                if new not in following or cost + charge < following[new][0]:
                    following[new] = cost + charge, rows + assignments
        states = following
    if not states:
        return None
    fees = case["coupling"]["activation_fees_cents"]
    final = [
        (cost + sum(fees[mode] for i, mode in enumerate(MODES[:3]) if used[i]), rows)
        for used, (cost, rows) in states.items()
    ]
    cost, rows = min(final, key=lambda item: item[0])
    return cost + reservation_fee(case, reservations), rows


def harden(contents, rng):
    """All extra constraints are disclosed in authoritative source sections."""
    orders = [r for r in contents["CRM"]["orders"] if r["status"] == "open"]
    # Keep source ordering scrambled: group membership is contractual, not positional.
    orders = sorted(orders, key=lambda row: row["order_id"])
    for index in (10, 11):
        orders.append(
            {
                **orders[-1],
                "order_id": orders[0]["order_id"][:-2] + str(index),
                "packs": rng.randint(2, 4),
                "must_serve": False,
                "penalty_cents_per_pack": rng.randrange(20000, 80001, 5000),
            }
        )
    contents["CRM"]["orders"].extend(orders[-2:])
    customers = []
    for i in range(4):
        customers.append(
            {
                "id": f"customer-{i}",
                "orders": [r["order_id"] for r in orders[i * 3 : i * 3 + 3]],
                "minimum_orders": 1,
                "paired_first_two": i in (0, 2),
                "service_credit_cents": [
                    0,
                    rng.randrange(40000, 90001, 5000),
                    rng.randrange(180000, 320001, 5000),
                    900000,
                ],
            }
        )
    contents["GRC"]["coupling"] = {
        "customers": customers,
        "activation_fees_cents": {
            "stock": 15000,
            "standard": rng.randrange(25000, 70001, 5000),
            "express": rng.randrange(70000, 140001, 5000),
        },
        "rules": "Each customer must receive minimum_orders in EVERY scenario. If paired_first_two, the first two listed orders must use exactly the same mode (including defer); they form an installation kit. Add the service credit indexed by the number of deferred orders ON TOP of individual deferral penalties. Add each used mode's activation fee ONCE per scenario, not per order. Minimize worst-case cost, then break ties by minimizing the sum of all scenario costs. Strict optimality is exact, with no regret allowance.",
    }
    contents["WMS"]["movements"][0]["packs"] += 8
    contents["ERP"]["controls"]["emissions_cap"] += 25
    scenarios = contents["RISK"]["scenarios"]
    scenarios.extend(
        [
            {
                "id": "compound_port_quality",
                "stock_loss_packs": 5,
                "standard_loss_packs": 4,
                "express_loss_packs": 2,
                "delay_by_mode": {"standard": 35},
                "closed_modes": [],
                "penalty_multiplier": 2,
            },
            {
                "id": "compound_carrier_quality",
                "stock_loss_packs": 4,
                "standard_loss_packs": 0,
                "express_loss_packs": 0,
                "delay_by_mode": {"express": 15},
                "closed_modes": ["standard"],
                "penalty_multiplier": 2,
            },
        ]
    )
    contents["GRC"]["mandate"]["objective"] = (
        "Minimize maximum cost over all six scenarios, then minimize the sum of scenario costs among worst-case ties. Strict success requires exact optimality for BOTH objectives. Follow the additional customer coupling contract."
    )
    contents["RISK"]["rules"] = (
        "All six scenarios are mutually exclusive. Commit one common reservation and six feasible contingent branches before revelation. Apply customer coupling, service credits and mode activation fees in every branch."
    )
