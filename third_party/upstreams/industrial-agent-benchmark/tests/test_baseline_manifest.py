"""Public manifest construction and validation (baseline_manifest_spec_v1)."""
from __future__ import annotations

import copy

import pytest

from baseline.manifest import (
    DETERMINISM_CLAIM,
    ManifestError,
    build_model_entry,
    build_public_manifest,
    validate_public_manifest,
    write_public_manifest,
)
from baseline.redaction import public_request_echo
from baseline.types import RequestEcho


def _echo_dict():
    return public_request_echo(
        RequestEcho(
            provider_kind="dummy",
            api_kind="dummy",
            model_id="dummy-model-a",
            decoding_profile_id="dummy_default_v1",
            decoding_profile_hash="0" * 64,
            params_sent={},
            params_not_sent=("temperature", "top_p"),
            max_output_tokens=1024,
            structured_output_enabled=False,
            schema_hash="none",
            retry_policy_summary="max_retries=2",
        )
    )


def _valid_manifest():
    model = build_model_entry(
        public_model_id="dummy-model-a",
        provider="dummy",
        snapshot="unknown",
        access_path="local_dummy",
        run_date="2026-07-05",
        release_date="unknown",
        training_cutoff="unknown",
        api_type="dummy",
        decoding_profile_id="dummy_default_v1",
        request_echo=_echo_dict(),
        params_not_sent=["temperature", "top_p"],
        max_output_tokens=1024,
    )
    return build_public_manifest(
        experiment_id="test-run-01",
        protocol={
            "experiment_plan_version": "baseline_experiment_plan_v1",
            "contamination_policy_version": "contamination_policy_v1",
            "answer_prompt_template_version": "baseline_answer_prompt_v1_draft",
            "answer_system_prompt_version": "baseline_answer_system_prompt_v1_draft",
            "judge_prompt_template_version": "unknown",
            "scoring_rules_version": "unknown",
            "decoding_profiles_hash": "0" * 64,
            "retry_policy": "transient retried; permanent not",
            "config_hashes": {"models.yaml": "1" * 64},
            "started_at": "2026-07-05T00:00:00+00:00",
        },
        dataset={
            "release_version": "v2.2.0",
            "git_commit": "unknown",
            "test_jsonl_sha256": "2" * 64,
            "task_count": 180,
            "dev_subset": {"id": "evaluation_set_v2.yaml", "task_count": 30, "role": "dev only"},
        },
        models=[model],
        judge={
            "judge_model_id": "unknown",
            "provider": "unknown",
            "snapshot": "unknown",
            "run_date": "unknown",
            "family_overlap_disclosure": "unknown",
            "anonymization": "anonymized keys only",
            "structured_output": "unknown",
            "inference_settings": "unknown",
        },
        contamination={
            "exposure_statement_version": "contamination_policy_v1",
            "ngram_overlap": "unknown",
            "self_reference_count": "unknown",
            "verbatim_reproduction_count": "unknown",
            "usage_evidence": "unknown",
        },
        created_at="2026-07-05T00:00:01+00:00",
    )


def test_valid_manifest_passes():
    assert validate_public_manifest(_valid_manifest()) == []


def test_model_entry_pins_determinism_claim():
    m = _valid_manifest()["models"][0]
    assert m["inference_settings"]["determinism_claim"] == DETERMINISM_CLAIM


def test_missing_top_level_field_is_reported():
    m = _valid_manifest()
    del m["contamination"]
    assert any("contamination" in e for e in validate_public_manifest(m))


@pytest.mark.parametrize(
    "section,field",
    [
        ("protocol", "decoding_profiles_hash"),
        ("protocol", "started_at"),
        ("dataset", "test_jsonl_sha256"),
        ("judge", "family_overlap_disclosure"),
        ("contamination", "usage_evidence"),
    ],
)
def test_missing_section_fields_are_reported(section, field):
    m = _valid_manifest()
    del m[section][field]
    errors = validate_public_manifest(m)
    assert any(field in e for e in errors)


def test_null_values_are_rejected_in_favor_of_unknown():
    m = _valid_manifest()
    m["dataset"]["git_commit"] = None
    errors = validate_public_manifest(m)
    assert any("unknown" in e and "git_commit" in e for e in errors)


def test_request_echo_with_extra_field_is_rejected():
    m = _valid_manifest()
    m["models"][0]["inference_settings"]["request_echo"]["provider_request_id_x"] = "r-1"
    errors = validate_public_manifest(m)
    assert any("non-allowlisted" in e for e in errors)


def test_non_utc_timestamp_is_rejected():
    m = _valid_manifest()
    m["protocol"]["started_at"] = "2026-07-05T09:00:00+09:00"
    errors = validate_public_manifest(m)
    assert any("UTC ISO 8601" in e for e in errors)


def test_prompt_text_in_manifest_is_rejected_via_forbidden_texts():
    m = _valid_manifest()
    prompt = "## Scenario 長い本文テキストがここに含まれます。承認境界と監査証跡。"
    m["dataset"]["dev_subset"]["role"] = f"dev only — {prompt}"
    errors = validate_public_manifest(m, forbidden_texts=[prompt])
    assert any("forbidden run text" in e for e in errors)


def test_write_public_manifest_refuses_invalid(tmp_path):
    m = _valid_manifest()
    m["models"][0]["inference_settings"]["request_echo"]["extra"] = "x"
    with pytest.raises(ManifestError):
        write_public_manifest(m, tmp_path / "manifest.json")
    assert not (tmp_path / "manifest.json").exists()


def test_write_public_manifest_writes_valid(tmp_path):
    path = tmp_path / "public" / "manifest.public.json"
    write_public_manifest(_valid_manifest(), path)
    assert path.exists()
    deep = copy.deepcopy(_valid_manifest())
    assert validate_public_manifest(deep) == []
