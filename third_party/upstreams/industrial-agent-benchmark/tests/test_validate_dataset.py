"""Tests for scripts/validate_dataset.py.

Covers both directions:
- the real dataset passes validation (golden path, via subprocess)
- deliberately broken task data is rejected (validator self-test)
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import validate_dataset as vd

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / "benchmark_data" / "knowledge" / "quality" / "IK-QUAL-001.yaml"


def load_sample() -> dict:
    with SAMPLE_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_validate(data: dict, path: Path = SAMPLE_PATH) -> vd.Result:
    result = vd.Result()
    vd.validate_problem(path, data, set(), result)
    return result


def test_real_dataset_passes():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_dataset.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Errors:  0" in proc.stdout


def test_valid_problem_has_no_errors():
    result = run_validate(load_sample())
    assert result.errors == []


@pytest.mark.parametrize("field", vd.REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(field):
    data = load_sample()
    del data[field]
    result = run_validate(data)
    assert result.errors, f"missing {field!r} was not detected"


@pytest.mark.parametrize("difficulty", [0, 6, "3", 3.5, True])
def test_invalid_difficulty_is_rejected(difficulty):
    data = load_sample()
    data["difficulty"] = difficulty
    result = run_validate(data)
    assert any("difficulty" in e for e in result.errors)


def test_duplicate_id_is_rejected():
    data = load_sample()
    seen_ids = set()
    result = vd.Result()
    vd.validate_problem(SAMPLE_PATH, data, seen_ids, result)
    vd.validate_problem(SAMPLE_PATH, copy.deepcopy(data), seen_ids, result)
    assert any("duplicate id" in e for e in result.errors)


def test_empty_must_have_is_rejected():
    data = load_sample()
    data["evaluation_rubric"]["must_have"] = []
    result = run_validate(data)
    assert any("must_have" in e for e in result.errors)


def test_empty_critical_failures_is_rejected():
    data = load_sample()
    data["evaluation_rubric"]["critical_failures"] = []
    result = run_validate(data)
    assert any("critical_failures" in e for e in result.errors)


def test_primary_skill_not_in_expected_skills_is_rejected():
    data = load_sample()
    data["primary_skill"] = "skill_not_listed_anywhere"
    result = run_validate(data)
    assert any("primary_skill" in e for e in result.errors)


def test_id_prefix_mismatch_is_rejected():
    data = load_sample()
    data["id"] = "IR-QUAL-001"
    result = run_validate(data)
    assert any("does not start with" in e for e in result.errors)


def test_invalid_layer_is_rejected():
    data = load_sample()
    data["layer"] = "industrial_marketing"
    result = run_validate(data)
    assert any("invalid layer" in e for e in result.errors)


def test_invalid_schema_version_is_rejected():
    data = load_sample()
    data["schema_version"] = "9.9"
    result = run_validate(data)
    assert any("schema_version" in e for e in result.errors)


def test_score_cap_rule_out_of_range_is_rejected():
    data = load_sample()
    data["score_cap_rules"] = [{"condition": "x", "max_score": 6}]
    result = run_validate(data)
    assert any("max_score" in e for e in result.errors)
