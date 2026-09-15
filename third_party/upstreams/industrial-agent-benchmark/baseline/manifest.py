"""Public manifest construction and validation.

Implements baseline_manifest_spec_v1.md. The builder only accepts
provider-request information as serialized ``request_echo`` allowlist dicts
(produced by :func:`baseline.redaction.public_request_echo`); it has no code
path that accepts a GenerationResult or PrivateProviderMetadata.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .redaction import (
    RedactionError,
    assert_public_safe,
    assert_request_echo_allowlisted,
)

DETERMINISM_CLAIM = "not_claimed_measured_by_repeats"

REQUIRED_TOP_LEVEL = (
    "experiment_id",
    "protocol",
    "dataset",
    "models",
    "judge",
    "contamination",
    "created_at",
)

REQUIRED_PROTOCOL_FIELDS = (
    "experiment_plan_version",
    "contamination_policy_version",
    "answer_prompt_template_version",
    "answer_system_prompt_version",
    "judge_prompt_template_version",
    "scoring_rules_version",
    "decoding_profiles_hash",
    "retry_policy",
    "config_hashes",
    "started_at",
)

REQUIRED_DATASET_FIELDS = (
    "release_version",
    "git_commit",
    "test_jsonl_sha256",
    "task_count",
    "dev_subset",
)

REQUIRED_MODEL_FIELDS = (
    "public_model_id",
    "provider",
    "snapshot",
    "access_path",
    "run_date",
    "release_date",
    "training_cutoff",
    "inference_settings",
)

REQUIRED_INFERENCE_FIELDS = (
    "api_type",
    "decoding_profile_id",
    "request_echo",
    "params_not_sent",
    "max_output_tokens",
    "determinism_claim",
)

REQUIRED_JUDGE_FIELDS = (
    "judge_model_id",
    "provider",
    "snapshot",
    "run_date",
    "family_overlap_disclosure",
    "anonymization",
    "structured_output",
    "inference_settings",
)

REQUIRED_CONTAMINATION_FIELDS = (
    "exposure_statement_version",
    "ngram_overlap",
    "self_reference_count",
    "verbatim_reproduction_count",
    "usage_evidence",
)

_UTC_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)$")


class ManifestError(ValueError):
    """The public manifest violates baseline_manifest_spec_v1."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_model_entry(
    *,
    public_model_id: str,
    provider: str,
    snapshot: str,
    access_path: str,
    run_date: str,
    release_date: str,
    training_cutoff: str,
    api_type: str,
    decoding_profile_id: str,
    request_echo: dict[str, Any],
    params_not_sent: list[str],
    max_output_tokens: int | str,
) -> dict[str, Any]:
    """Build one public models[] entry. ``request_echo`` must already be an
    allowlist dict from :func:`baseline.redaction.public_request_echo`."""
    assert_request_echo_allowlisted(request_echo)
    return {
        "public_model_id": public_model_id,
        "provider": provider,
        "snapshot": snapshot,
        "access_path": access_path,
        "run_date": run_date,
        "release_date": release_date,
        "training_cutoff": training_cutoff,
        "inference_settings": {
            "api_type": api_type,
            "decoding_profile_id": decoding_profile_id,
            "request_echo": request_echo,
            "params_not_sent": list(params_not_sent),
            "max_output_tokens": max_output_tokens,
            "determinism_claim": DETERMINISM_CLAIM,
        },
    }


def build_public_manifest(
    *,
    experiment_id: str,
    protocol: dict[str, Any],
    dataset: dict[str, Any],
    models: list[dict[str, Any]],
    judge: dict[str, Any],
    contamination: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "protocol": protocol,
        "dataset": dataset,
        "models": models,
        "judge": judge,
        "contamination": contamination,
        "created_at": created_at or utc_now_iso(),
    }


def validate_public_manifest(
    manifest: dict[str, Any], *, forbidden_texts: Iterable[str] = ()
) -> list[str]:
    """Return a list of violations (empty list = valid)."""
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in manifest:
            errors.append(f"missing top-level field: {key}")
    if errors:
        return errors

    _require_fields(manifest["protocol"], REQUIRED_PROTOCOL_FIELDS, "protocol", errors)
    _require_fields(manifest["dataset"], REQUIRED_DATASET_FIELDS, "dataset", errors)
    _require_fields(manifest["judge"], REQUIRED_JUDGE_FIELDS, "judge", errors)
    _require_fields(
        manifest["contamination"], REQUIRED_CONTAMINATION_FIELDS, "contamination", errors
    )

    models = manifest["models"]
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty list")
        models = []
    for i, model in enumerate(models):
        where = f"models[{i}]"
        if not isinstance(model, dict):
            errors.append(f"{where} must be a mapping")
            continue
        _require_fields(model, REQUIRED_MODEL_FIELDS, where, errors)
        settings = model.get("inference_settings")
        if isinstance(settings, dict):
            _require_fields(
                settings, REQUIRED_INFERENCE_FIELDS, f"{where}.inference_settings", errors
            )
            if settings.get("determinism_claim") not in (None, DETERMINISM_CLAIM):
                errors.append(
                    f"{where}.inference_settings.determinism_claim must be "
                    f"{DETERMINISM_CLAIM!r}"
                )
            echo = settings.get("request_echo")
            if isinstance(echo, dict):
                try:
                    assert_request_echo_allowlisted(echo)
                except RedactionError as exc:
                    errors.append(f"{where}: {exc}")
            elif echo is not None:
                errors.append(f"{where}.inference_settings.request_echo must be a mapping")

    for ts_field, value in (
        ("created_at", manifest.get("created_at")),
        ("protocol.started_at", manifest.get("protocol", {}).get("started_at")),
    ):
        if isinstance(value, str) and value != "unknown" and not _UTC_ISO_RE.match(value):
            errors.append(f"{ts_field} must be UTC ISO 8601, got {value!r}")

    _reject_nulls(manifest, "$", errors)

    try:
        assert_public_safe(manifest, forbidden_texts=forbidden_texts)
    except RedactionError as exc:
        errors.append(f"publication-boundary violation: {exc}")
    return errors


def write_public_manifest(
    manifest: dict[str, Any], path: Path, *, forbidden_texts: Iterable[str] = ()
) -> None:
    errors = validate_public_manifest(manifest, forbidden_texts=forbidden_texts)
    if errors:
        raise ManifestError(
            "public manifest failed validation:\n" + "\n".join(f"- {e}" for e in errors)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _require_fields(
    obj: Any, fields: tuple[str, ...], where: str, errors: list[str]
) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{where} must be a mapping")
        return
    for field_name in fields:
        if field_name not in obj:
            errors.append(f"{where} missing required field: {field_name}")
        elif obj[field_name] is None:
            errors.append(
                f'{where}.{field_name} must not be null (use the literal "unknown")'
            )


def _reject_nulls(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is None:
                errors.append(f'{path}.{key} is null (use the literal "unknown")')
            else:
                _reject_nulls(value, f"{path}.{key}", errors)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _reject_nulls(value, f"{path}[{i}]", errors)
