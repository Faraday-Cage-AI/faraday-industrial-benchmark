import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "sample_budget", Path(__file__).parents[1] / "examples/sample_budget.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reservations_survive_restart_and_unknown_charges(tmp_path):
    path = tmp_path / "ledger.json"
    budget = module.SampleBudget.create(path, {"a": "25"}, {"a/1": "12.5", "a/2": "12.5"})
    budget.reserve("first", "a", "a/1", "10")
    restarted = module.SampleBudget(path)
    with pytest.raises(module.BudgetExceeded):
        restarted.reserve("second", "a", "a/1", "3")
    with pytest.raises(ValueError):
        restarted.reserve("first", "a", "a/1", "1")
    restarted.settle("first", "4")
    restarted.reserve("second", "a", "a/1", "8.5")
    with pytest.raises(module.BudgetExceeded):
        restarted.reserve("third", "a", "a/1", "0.01")


def test_shared_total_cap_and_no_overwrite(tmp_path):
    path = tmp_path / "ledger.json"
    budget = module.SampleBudget.create(
        path, {"a": "80", "b": "80"}, {"a/1": "80", "b/1": "80"}, total="90"
    )
    budget.reserve("first", "a", "a/1", "60")
    with pytest.raises(module.BudgetExceeded):
        budget.reserve("second", "b", "b/1", "31")
    with pytest.raises(FileExistsError):
        module.SampleBudget.create(path, {}, {})
    with pytest.raises(ValueError):
        module.SampleBudget.create(tmp_path / "too-large.json", {}, {}, total="101")


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1"])
def test_invalid_amounts_fail_closed(amount):
    with pytest.raises(ValueError):
        module.dollars(amount)
