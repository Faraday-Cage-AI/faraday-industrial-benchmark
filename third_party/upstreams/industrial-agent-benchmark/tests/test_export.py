"""Tests for scripts/export_hf_dataset_v2.py.

The key guarantee is idempotency: converting the on-disk YAML tasks must
reproduce the committed data/v2/test.jsonl byte for byte, so the canonical
YAML source and the published JSONL cannot drift.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import export_hf_dataset_v2 as ex

ROOT = Path(__file__).resolve().parent.parent
COMMITTED_JSONL = ROOT / "data" / "v2" / "test.jsonl"


def test_export_matches_committed_jsonl():
    lines = []
    for path in ex.iter_problem_files():
        record = ex.convert_record(ex.load_yaml(path))
        ex.validate_record_shape(record, path)
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    generated = "\n".join(lines) + "\n"
    committed = COMMITTED_JSONL.read_text(encoding="utf-8")
    assert generated == committed, (
        "export output differs from committed data/v2/test.jsonl; "
        "run scripts/export_hf_dataset_v2.py and commit the result"
    )


def test_schema_version_constant():
    # The record-level version is the JSONL schema version, pinned at 2.0.0
    # until the record schema itself changes (docs/versioning_policy.md).
    assert ex.SCHEMA_VERSION == "2.0.0"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"choices": ["a", "b"]}, "multiple_choice"),
        ({"numeric_checks": [{"name": "n"}]}, "numeric_reasoning"),
        ({"structured_output_requirements": {"required": True}}, "structured_reasoning"),
        ({"difficulty": 4}, "case_analysis"),
        ({"difficulty": 5}, "case_analysis"),
        ({"difficulty": 3}, "short_answer"),
        ({}, "short_answer"),
    ],
)
def test_infer_task_type(data, expected):
    assert ex.infer_task_type(data) == expected


def test_unique_strings_dedupes_and_skips_non_strings():
    assert ex.unique_strings(["a", "b", "a", "", None, 3, " c "]) == ["a", "b", "c"]


def test_convert_record_maps_core_fields():
    data = {
        "id": "IK-QUAL-001",
        "layer": "industrial_knowledge",
        "category": "quality",
        "domain": "general_manufacturing",
        "subdomain": "molding",
        "difficulty": 3,
        "scenario": "scenario text",
        "question": "question text",
        "reference_answer": "answer text",
        "expected_skills": ["a"],
        "primary_skill": "a",
        "secondary_skills": [],
        "evaluation_rubric": {"must_have": ["x"]},
    }
    record = ex.convert_record(data)
    assert list(record.keys()) == ex.SCHEMA_KEYS
    assert record["category"] == "knowledge"
    assert record["sub_category"] == "quality"
    assert record["context"] == "scenario text"
    assert record["answer"] == "answer text"
    assert record["difficulty"] == "medium"
    assert record["public"] is True


def test_validate_record_shape_rejects_bad_values():
    data = {
        "id": "IK-QUAL-001",
        "layer": "industrial_knowledge",
        "category": "quality",
        "difficulty": 3,
    }
    record = ex.convert_record(data)

    bad_task_type = dict(record, task_type="essay")
    with pytest.raises(ValueError, match="task_type"):
        ex.validate_record_shape(bad_task_type, Path("x.yaml"))

    bad_difficulty = dict(record, difficulty="impossible")
    with pytest.raises(ValueError, match="difficulty"):
        ex.validate_record_shape(bad_difficulty, Path("x.yaml"))
