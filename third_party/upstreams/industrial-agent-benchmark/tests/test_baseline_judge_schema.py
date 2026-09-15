"""Judgement schema and judge template: strict-compatible, non-runnable."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from baseline.redaction import SECRET_VALUE_RE
from baseline.types import OutputSchema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "experiments" / "baseline_v2_2_0" / "schemas" / "judgement_v1.schema.json"
TEMPLATE_PATH = ROOT / "experiments" / "baseline_v2_2_0" / "judge.template.yaml"

# Keys the frozen eval pipeline requires in every judgement.
EXPECTED_JUDGEMENT_FIELDS = {
    "question_id",
    "final_score",
    "must_have_missing_count",
    "numeric_check_failed_ratio",
    "generic_penalty_triggered",
    "critical_failure_triggered",
    "score_cap_applied",
    "structured_output_missing_count",
    "judge_summary",
    "evidence_summary",
}


def test_schema_is_strict_compatible():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    # Strict Structured Outputs requires required == all properties.
    assert set(schema["required"]) == set(schema["properties"])
    assert set(schema["properties"]) == EXPECTED_JUDGEMENT_FIELDS


def test_output_schema_hash_is_stable():
    a = OutputSchema.from_file(SCHEMA_PATH)
    b = OutputSchema.from_file(SCHEMA_PATH)
    assert a.sha256 == b.sha256
    assert len(a.sha256) == 64
    assert a.name == "judgement_v1.schema"


def test_judge_template_is_non_runnable_and_secret_free():
    raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert not SECRET_VALUE_RE.search(raw)
    data = yaml.safe_load(raw)
    assert data["non_runnable"] is True
    judge_ids = [j["judge_model_id"] for j in data["judges"]]
    assert judge_ids == ["gpt-5.4", "claude-sonnet-5"]
    for judge in data["judges"]:
        assert judge["structured_output"]["schema_file"] == "schemas/judgement_v1.schema.json"
