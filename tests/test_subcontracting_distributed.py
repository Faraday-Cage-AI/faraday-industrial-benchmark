from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.subcontracting import (
    contract_from_sections,
    reconcile_subcontracting,
)
from faraday_industrial_benchmark.world import IndustrialWorld

TASKS = load_tasks(Path(__file__).parents[1] / "data/subcontracting-v2/tasks.json")


def sections(world):
    return {f["system"]: deepcopy(f["sections"]) for f in world.state["case_files"].values()}


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_join_and_late_history_materially_change_results(task):
    world = IndustrialWorld(task)
    initial = sections(world)
    old = reconcile_subcontracting(contract_from_sections(initial))
    world.advance(40)
    current = sections(world)
    config = current["ERP-GL"]["reserve_policy"]["subcontract_contract"]
    assert "events" not in config and "opening_lots" not in config
    assert "quality" not in current["WMS"]["subcontract_stock"][0]
    assert len(current["SCM"]["subcontract_events"]) > len(initial["SCM"]["subcontract_events"])
    final = reconcile_subcontracting(contract_from_sections(current))
    # A numeric business impact, not just a different exclusion label or citation.
    assert any(
        old[field] != final[field]
        for field in (
            "available_finished_quantity",
            "cogs_cents",
            "finished_inventory_cents",
            "service_payable_cents",
        )
    )
    current["QMS"]["subcontract_quality"].pop("COMP-A")
    with pytest.raises(ValueError, match="source keys"):
        contract_from_sections(current)


def test_all_four_causal_variants_are_represented():
    variants = set()
    for task in TASKS:
        current = sections(IndustrialWorld(task))
        variants.add(
            current["ERP-GL"]["reserve_policy"]["subcontract_contract"]["lifecycle_variant"]
        )
    assert variants == {
        "quality_release",
        "reversal_not_approved",
        "hold_release_retry",
        "reversal_after_correction",
    }
