from decimal import Decimal

import pytest

from faraday_industrial_benchmark.native_review import calculate


def cell(value, formula=None):
    return {"value": Decimal(str(value)), "formula": formula}


def test_independent_recalculation_ignores_cached_formula_value():
    cells = {"B1": cell(4), "B2": cell(5), "B3": cell(999, "SUM(B1:B2)")}
    assert calculate(cells, "B3") == 9
    assert calculate(cells, "B3", {"B1": 10}) == 15
    cells["B3"]["formula"] = "$B$1+$B$2"
    assert calculate(cells, "B3") == 9


@pytest.mark.parametrize(
    "formula",
    ["__import__('os')", "B1.__class__", "[1,2]", "2**999999", "SUM(A1:B5)", "SUM(A1:A999999)"],
)
def test_unsupported_formula_fails_closed(formula):
    with pytest.raises((ValueError, SyntaxError)):
        calculate({"B1": cell(1, formula)}, "B1")


def test_cycles_and_non_numeric_values_fail():
    with pytest.raises(ValueError, match="cyclic"):
        calculate({"B1": cell(1, "B2"), "B2": cell(1, "B1")}, "B1")
    with pytest.raises(ValueError, match="numeric"):
        calculate({"B1": {"value": "42", "formula": None}}, "B1")
