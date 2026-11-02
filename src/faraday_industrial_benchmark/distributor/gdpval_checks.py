"""Deterministic artifact-field checks shared by the GDPval-derived families.

The importer runs the same evaluator against the sealed truth artifact, so a
fixture can only be committed when its oracle content passes every check.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

Json = dict[str, Any]

_NUMBER_NOISE = re.compile(r"[\s$,%]")


def norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = _NUMBER_NOISE.sub("", value)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def resolve(content: Any, path: list[Any]) -> tuple[bool, Any]:
    """Walk ``path`` with case- and punctuation-insensitive dictionary keys."""

    current = content
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or not 0 <= part < len(current):
                return False, None
            current = current[part]
            continue
        if not isinstance(current, dict):
            return False, None
        if part in current:
            current = current[part]
            continue
        wanted = norm_key(part)
        matches = [key for key in current if norm_key(key) == wanted]
        if len(matches) != 1:
            return False, None
        current = current[matches[0]]
    return True, current


def _normalized_items(value: Any, *, strip_zeros: bool = False) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if any(isinstance(item, (dict, list)) for item in value):
        return None
    items = [norm_key(item) for item in value]
    if strip_zeros:
        items = [item.lstrip("0") or "0" for item in items]
    return items


def _number_close(actual: Any, expected: float, tolerance: float) -> tuple[bool, str]:
    number = to_number(actual)
    if number is None:
        return False, f"not numeric: {actual!r}"
    return abs(number - expected) <= tolerance + 1e-9, f"{number} vs {expected} (tol {tolerance})"


CustomRule = Callable[[Any, Json], tuple[bool, str]]
CUSTOM_RULES: dict[str, CustomRule] = {}


def custom_rule(name: str) -> Callable[[CustomRule], CustomRule]:
    def register(function: CustomRule) -> CustomRule:
        CUSTOM_RULES[name] = function
        return function

    return register


def evaluate(check: Json, content: Any) -> tuple[bool, str]:
    """Evaluate one sealed field check against an artifact's content."""

    kind = check["kind"]
    if kind == "custom":
        return CUSTOM_RULES[check["rule"]](content, check)
    found, actual = resolve(content, check["path"])
    if not found:
        return False, "missing field " + ".".join(str(part) for part in check["path"])
    expected = check.get("expected")
    if kind == "number":
        return _number_close(actual, float(expected), float(check.get("tolerance", 0.0)))
    if kind == "text":
        return norm_key(actual) == norm_key(expected), f"{actual!r} vs {expected!r}"
    if kind == "bool":
        return actual is expected, f"{actual!r} vs {expected!r}"
    if kind == "member":
        allowed = {norm_key(item) for item in expected}
        return norm_key(actual) in allowed and not isinstance(actual, (dict, list)), f"{actual!r} not in {expected!r}"
    if kind == "nonempty":
        return _nonempty(actual), "empty value" if not _nonempty(actual) else "present"
    if kind in {"set", "list", "includes", "excludes", "overlaps"}:
        strip_zeros = bool(check.get("strip_leading_zeros"))
        items = _normalized_items(actual, strip_zeros=strip_zeros)
        if items is None:
            return False, "not a flat list"
        wanted = _normalized_items(list(expected), strip_zeros=strip_zeros) or []
        if kind == "set":
            return set(items) == set(wanted) and len(items) == len(set(items)), (
                f"missing={sorted(set(wanted) - set(items))} extra={sorted(set(items) - set(wanted))}"
            )
        if kind == "list":
            return items == wanted, f"order/content mismatch: {actual!r}"
        if kind == "includes":
            missing = sorted(set(wanted) - set(items))
            return not missing, f"missing={missing}"
        present = sorted(set(wanted) & set(items))
        if kind == "overlaps":
            return bool(present), f"none of {sorted(wanted)}"
        return not present, f"forbidden={present}"
    if kind == "keys":
        if not isinstance(actual, dict):
            return False, "not an object"
        keys = {norm_key(key) for key in actual}
        wanted = {norm_key(item) for item in expected}
        return keys == wanted, f"missing={sorted(wanted - keys)} extra={sorted(keys - wanted)}"
    raise ValueError(f"unsupported gdp check kind: {kind}")


def _field(content: Any, *path: Any) -> Any:
    found, value = resolve(content, list(path))
    return value if found else None


# --- custom rules -----------------------------------------------------------


def _scenarios(content: Any) -> list[Json]:
    rows = _field(content, "scenarios")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _scenario_numbers(row: Json, key: str, quarters: list[str]) -> list[float | None]:
    return [to_number(_field(row, key, quarter)) for quarter in quarters]


@custom_rule("terms_scenarios")
def _terms_scenarios(content: Any, check: Json) -> tuple[bool, str]:
    """Validate the agent's own three-scenario terms model against its stated inputs."""

    aspect = check["aspect"]
    shipments: dict[str, float] = check["shipments"]
    quarters = list(shipments)
    rows = _scenarios(content)
    if len(rows) != 3:
        return False, f"{len(rows)} scenarios (need exactly 3)"
    margins = [to_number(_field(row, "retailer_margin")) for row in rows]
    allowances = [to_number(_field(row, "marketing_allowance_rate")) for row in rows]
    terms = [to_number(_field(row, "payment_terms_days")) for row in rows]
    names = [norm_key(_field(row, "name")) for row in rows]
    if aspect == "labels":
        return all(names) and len(set(names)) == 3, f"names={names}"
    if aspect == "margin_range":
        ok = all(value is not None and 0.40 - 1e-9 <= value <= 0.50 + 1e-9 for value in margins)
        return ok, f"margins={margins}"
    if aspect == "margin_varied":
        return None not in margins and len(set(margins)) > 1, f"margins={margins}"
    if aspect == "allowance_range":
        ok = all(value is not None and -1e-9 <= value <= 0.04 + 1e-9 for value in allowances)
        return ok, f"allowances={allowances}"
    if aspect == "allowance_varied":
        return None not in allowances and len(set(allowances)) > 1, f"allowances={allowances}"
    if aspect == "terms_valid":
        return all(value in (30.0, 60.0) for value in terms), f"terms={terms}"
    if aspect == "terms_both":
        return {30.0, 60.0} <= set(terms), f"terms={terms}"
    if aspect == "distinct":
        combos = list(zip(margins, allowances, terms))
        return len(set(combos)) == 3, f"combos={combos}"
    if aspect == "selected":
        selected = norm_key(_field(content, "selected_scenario"))
        return bool(selected) and selected in names, f"selected={selected!r}"
    tolerance = float(check.get("tolerance", 1.0))
    failures: list[str] = []
    for row, margin, allowance, term in zip(rows, margins, allowances, terms):
        label = _field(row, "name")
        if margin is None or allowance is None or term is None:
            failures.append(f"{label}: inputs missing")
            continue
        wholesale = _scenario_numbers(row, "wholesale_revenue", quarters)
        allowance_rows = _scenario_numbers(row, "marketing_allowance", quarters)
        net = _scenario_numbers(row, "net_wholesale_revenue", quarters)
        expected_w = [shipments[q] * (1 - margin) for q in quarters]
        expected_a = [shipments[q] * allowance for q in quarters]
        if aspect == "wholesale":
            series, expected, annual_key = wholesale, expected_w, "annual_wholesale_revenue"
        elif aspect == "allowance":
            series, expected, annual_key = allowance_rows, expected_a, "annual_marketing_allowance"
        elif aspect == "net":
            series = net
            expected = [w - a for w, a in zip(expected_w, expected_a)]
            annual_key = "annual_net_wholesale_revenue"
        elif aspect == "cash":
            lag = 1 if term == 30.0 else 2
            receipts = _field(row, "cash_receipts")
            if not isinstance(receipts, dict):
                failures.append(f"{label}: cash_receipts missing")
                continue
            expected_cash: dict[str, float] = {}
            for index, quarter in enumerate(quarters):
                expected_cash[f"Q{index + 1 + lag}"] = expected_w[index]
            actual = {norm_key(key): to_number(value) for key, value in receipts.items()}
            for quarter, amount in expected_cash.items():
                value = actual.get(norm_key(quarter))
                if value is None or abs(value - amount) > tolerance:
                    failures.append(f"{label}: cash {quarter}={value} expected {amount}")
            extra = [
                key for key, value in actual.items()
                if key not in {norm_key(q) for q in expected_cash} and value not in (None, 0.0)
            ]
            if extra:
                failures.append(f"{label}: unexpected receipts in {extra}")
            continue
        else:
            raise ValueError(f"unknown terms aspect {aspect}")
        for quarter, value, target in zip(quarters, series, expected):
            if value is None or abs(value - target) > tolerance:
                failures.append(f"{label}: {quarter}={value} expected {round(target, 2)}")
        annual = to_number(_field(row, annual_key))
        if annual is None or abs(annual - sum(expected)) > tolerance:
            failures.append(f"{label}: {annual_key}={annual} expected {round(sum(expected), 2)}")
    return not failures, "; ".join(failures[:4]) or "consistent"


@custom_rule("all_of")
def _all_of(content: Any, check: Json) -> tuple[bool, str]:
    failures = []
    for part in check["checks"]:
        passed, detail = evaluate(part, content)
        if not passed:
            failures.append(f"{part['id']}: {detail}")
    return not failures, "; ".join(failures) or "all parts pass"


@custom_rule("map_numbers")
def _map_numbers(content: Any, check: Json) -> tuple[bool, str]:
    """An object keyed by identifier whose numeric values match, with no extra keys."""

    found, mapping = resolve(content, check["path"])
    if not found or not isinstance(mapping, dict):
        return False, "missing object"
    tolerance = float(check.get("tolerance", 0.01))
    actual = {norm_key(key): value for key, value in mapping.items()}
    failures = []
    for key, value in check["values"].items():
        ok, detail = _number_close(actual.get(norm_key(key)), float(value), tolerance)
        if not ok:
            failures.append(f"{key}: {detail}")
    extra = sorted(set(actual) - {norm_key(key) for key in check["values"]})
    if extra:
        failures.append(f"unexpected keys {extra[:5]}")
    return not failures, "; ".join(failures[:4]) or "values match"


@custom_rule("rows_match")
def _rows_match(content: Any, check: Json) -> tuple[bool, str]:
    """Compare records keyed by id against sealed expected records.

    With ``key`` set, a list of records is keyed by that field and repeated ids fail.
    """

    found, rows = resolve(content, check["path"])
    failures: list[str] = []
    key_field = check.get("key")
    if found and key_field and isinstance(rows, list):
        keyed: Json = {}
        for row in rows:
            if not isinstance(row, dict):
                return False, "record is not an object"
            record_id = norm_key(_field(row, key_field))
            if record_id in keyed:
                failures.append(f"duplicate {key_field} {record_id}")
            keyed[record_id] = row
        rows = keyed
    if not found or not isinstance(rows, dict):
        return False, "missing records object"
    tolerance = float(check.get("tolerance", 0.01))
    actual = {norm_key(key): value for key, value in rows.items()}
    for record_id, fields in check["expected"].items():
        row = actual.get(norm_key(record_id))
        if not isinstance(row, dict):
            failures.append(f"{record_id}: missing")
            continue
        for field, value in fields.items():
            present, got = resolve(row, [field])
            if value is None:
                if present and got not in (None, "") and norm_key(got) not in {"na", "none", "notapplicable"}:
                    failures.append(f"{record_id}.{field}: expected blank, got {got!r}")
                continue
            if not present:
                failures.append(f"{record_id}.{field}: missing")
            elif isinstance(value, bool):
                if got is not value:
                    failures.append(f"{record_id}.{field}: {got!r} vs {value!r}")
            elif isinstance(value, (int, float)):
                ok, _ = _number_close(got, float(value), tolerance)
                if not ok:
                    failures.append(f"{record_id}.{field}: {got!r} vs {value!r}")
            elif isinstance(value, list):
                items = _normalized_items(got)
                if items is None or set(items) != {norm_key(item) for item in value}:
                    failures.append(f"{record_id}.{field}: {got!r} vs {value!r}")
            elif norm_key(got) != norm_key(value):
                failures.append(f"{record_id}.{field}: {got!r} vs {value!r}")
    if check.get("exact_ids", True):
        extra = sorted(set(actual) - {norm_key(record_id) for record_id in check["expected"]})
        if extra:
            failures.append(f"unexpected records {extra[:5]}")
    return not failures, "; ".join(failures[:4]) or f"{len(check['expected'])} records match"


@custom_rule("price_band")
def _price_band(content: Any, check: Json) -> tuple[bool, str]:
    """Each proposed price per ounce must sit within a band around its benchmark."""

    failures: list[str] = []
    for sku, rule in check["skus"].items():
        found, row = resolve(content, [*check["path"], sku])
        if not found or not isinstance(row, dict):
            failures.append(f"{sku}: missing")
            continue
        price = to_number(_field(row, check["price_field"]))
        if price is None:
            failures.append(f"{sku}: price missing")
            continue
        if "benchmark" in rule:
            per_oz = price / rule["ounces"]
            low = rule["benchmark"] * (1 - check["band"])
            high = rule["benchmark"] * (1 + check["band"])
            if not low - 1e-9 <= per_oz <= high + 1e-9:
                failures.append(f"{sku}: {per_oz:.2f}/oz outside {low:.2f}-{high:.2f}")
        if "floor" in rule and price <= rule["floor"]:
            failures.append(f"{sku}: price {price} not above {rule['floor']}")
    return not failures, "; ".join(failures[:4]) or "within band"


def _nonempty(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return value is True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _records(value: Any) -> list[Json] | None:
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        return None
    return value


def _codes_of(value: Any) -> list[str]:
    if isinstance(value, list):
        return [norm_key(item) for item in value if not isinstance(item, (dict, list))]
    if value is None or isinstance(value, dict):
        return []
    return [norm_key(value)]


@custom_rule("records")
def _records_rule(content: Any, check: Json) -> tuple[bool, str]:
    """Structural rules over a list (or id-keyed object) of records the agent authored."""

    found, value = resolve(content, check["path"])
    rows = _records(value) if found else None
    if rows is None:
        return False, "missing records"
    failures: list[str] = []
    if len(rows) < int(check.get("min_count", 1)):
        failures.append(f"{len(rows)} records < {check.get('min_count', 1)}")
    for name in check.get("nonempty", []):
        empty = [index for index, row in enumerate(rows) if not _nonempty(_field(row, name))]
        if empty:
            failures.append(f"{name} empty in records {empty[:5]}")
    for name in check.get("some_nonempty", []):
        if not any(_nonempty(_field(row, name)) for row in rows):
            failures.append(f"no record has {name}")
    unique = check.get("unique")
    if unique:
        values = [norm_key(_field(row, unique)) for row in rows]
        if len(set(values)) != len(values) or "" in values:
            failures.append(f"{unique} not unique: {values}")
    for name, forbidden in check.get("forbid", {}).items():
        bad = {norm_key(item) for item in forbidden}
        hits = sorted({code for row in rows for code in _codes_of(_field(row, name)) if code in bad})
        if hits:
            failures.append(f"{name} uses forbidden {hits}")
    for name, allowed in check.get("allowed", {}).items():
        ok = {norm_key(item) for item in allowed}
        stray = sorted({code for row in rows for code in _codes_of(_field(row, name)) if code not in ok})
        if stray:
            failures.append(f"{name} outside catalog {stray[:5]}")
    for name, required in check.get("require_values", {}).items():
        seen = {code for row in rows for code in _codes_of(_field(row, name))}
        missing = sorted({norm_key(item) for item in required} - seen)
        if missing:
            failures.append(f"{name} missing {missing}")
    for name, options in check.get("require_any", {}).items():
        seen = {code for row in rows for code in _codes_of(_field(row, name))}
        if not seen & {norm_key(item) for item in options}:
            failures.append(f"{name} has none of {options}")
    for name, minimum in check.get("min_distinct", {}).items():
        seen = {code for row in rows for code in _codes_of(_field(row, name))}
        if len(seen) < int(minimum):
            failures.append(f"{name} has {len(seen)} distinct values < {minimum}")
    return not failures, "; ".join(failures[:4]) or f"{len(rows)} records ok"


@custom_rule("ranking")
def _ranking(content: Any, check: Json) -> tuple[bool, str]:
    """An ordered list matching ranked groups; items within a group may appear in any order."""

    found, value = resolve(content, check["path"])
    items = _normalized_items(value) if found else None
    if items is None:
        return False, "missing ranking list"
    optional = {norm_key(item) for item in check.get("optional", [])}
    items = [item for item in items if item not in optional]
    position = 0
    for group in check["groups"]:
        wanted = {norm_key(item) for item in group} - optional
        if not wanted:
            continue
        chunk = items[position:position + len(wanted)]
        if set(chunk) != wanted:
            return False, f"position {position}: {chunk} vs {sorted(wanted)}"
        position += len(wanted)
    if position != len(items):
        return False, f"extra items {items[position:]}"
    return True, "ranking matches"


@custom_rule("if_then")
def _if_then(content: Any, check: Json) -> tuple[bool, str]:
    applies, _ = evaluate(check["when"], content)
    if not applies:
        return True, "condition not triggered"
    return evaluate(check["then"], content)


@custom_rule("sequence")
def _sequence(content: Any, check: Json) -> tuple[bool, str]:
    """Ordering constraints over a list of step codes."""

    found, value = resolve(content, check["path"])
    items = _normalized_items(value) if found else None
    if not items:
        return False, "missing step list"
    failures: list[str] = []
    if "first" in check and items[0] != norm_key(check["first"]):
        failures.append(f"first step {items[0]!r} is not {check['first']!r}")
    if "last" in check and items[-1] != norm_key(check["last"]):
        failures.append(f"last step {items[-1]!r} is not {check['last']!r}")
    for code in check.get("includes", []):
        if norm_key(code) not in items:
            failures.append(f"missing {code}")
    for code in check.get("excludes", []):
        if norm_key(code) in items:
            failures.append(f"forbidden {code}")
    for before, after in check.get("before", []):
        a, b = norm_key(before), norm_key(after)
        if a in items and b in items and items.index(a) > items.index(b):
            failures.append(f"{before} after {after}")
        elif a not in items or b not in items:
            failures.append(f"{before}/{after} not both present")
    return not failures, "; ".join(failures[:4]) or "sequence ok"


_FORMULAS: dict[str, Callable[[float, float], float]] = {
    "ratio": lambda a, b: a / b,
    "pct_change": lambda a, b: 100 * (a - b) / b,
    "pct_of": lambda a, b: 100 * a / b,
    "product": lambda a, b: a * b,
    "difference": lambda a, b: a - b,
}


@custom_rule("record_formula")
def _record_formula(content: Any, check: Json) -> tuple[bool, str]:
    """Each record's ``target`` field must equal ``formula(a, b)`` of its own fields."""

    found, value = resolve(content, check["path"])
    rows = _records(value) if found else None
    if not rows:
        return False, "missing records"
    tolerance = float(check.get("tolerance", 0.01))
    function = _FORMULAS[check["formula"]]
    failures: list[str] = []
    for index, row in enumerate(rows):
        a = to_number(_field(row, check["a"]))
        b = to_number(_field(row, check["b"]))
        got = to_number(_field(row, check["target"]))
        if a is None or b is None or got is None or (b == 0 and check["formula"] != "product"):
            failures.append(f"record {index}: inputs missing")
            continue
        expected = function(a, b)
        if abs(got - expected) > tolerance:
            failures.append(f"record {index}: {check['target']}={got} expected {round(expected, 4)}")
    return not failures, "; ".join(failures[:4]) or f"{len(rows)} records consistent"
