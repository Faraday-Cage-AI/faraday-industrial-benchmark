"""RequestEcho field set is pinned to the policy Section 3.3 allowlist."""
from __future__ import annotations

import dataclasses

import pytest

from baseline.redaction import REQUEST_ECHO_ALLOWLIST
from baseline.types import (
    MISSING_STATUSES,
    PrivateProviderMetadata,
    RequestEcho,
    ResultStatus,
)

# public_artifact_policy_v1.md Section 3.3 allowlist, mapped to field names
# ("decoding profile ID / hash" maps to two fields). Changing this set
# requires a policy revision first.
POLICY_ALLOWLIST_FIELDS = {
    "provider_kind",
    "api_kind",
    "model_id",
    "decoding_profile_id",
    "decoding_profile_hash",
    "params_sent",
    "params_not_sent",
    "max_output_tokens",
    "structured_output_enabled",
    "schema_hash",
    "retry_policy_summary",
}


def _echo(**overrides):
    base = dict(
        provider_kind="dummy",
        api_kind="dummy",
        model_id="dummy-model-a",
        decoding_profile_id="dummy_default_v1",
        decoding_profile_hash="0" * 64,
        params_sent={},
        params_not_sent=("temperature",),
        max_output_tokens=1024,
        structured_output_enabled=False,
        schema_hash="none",
        retry_policy_summary="max_retries=2",
    )
    base.update(overrides)
    return RequestEcho(**base)


def test_request_echo_fields_match_policy_allowlist():
    fields = {f.name for f in dataclasses.fields(RequestEcho)}
    assert fields == POLICY_ALLOWLIST_FIELDS
    assert REQUEST_ECHO_ALLOWLIST == POLICY_ALLOWLIST_FIELDS


def test_request_echo_is_frozen():
    echo = _echo()
    with pytest.raises(dataclasses.FrozenInstanceError):
        echo.model_id = "other"  # type: ignore[misc]


def test_request_echo_has_no_prompt_or_id_fields():
    fields = {f.name for f in dataclasses.fields(RequestEcho)}
    for forbidden in (
        "system_prompt",
        "user_prompt",
        "prompt",
        "messages",
        "headers",
        "request_body",
        "provider_request_id",
        "provider_response_id",
        "account_id",
    ):
        assert forbidden not in fields


def test_private_metadata_is_a_distinct_type():
    assert not issubclass(PrivateProviderMetadata, RequestEcho)
    assert not issubclass(RequestEcho, PrivateProviderMetadata)


def test_result_status_values():
    assert ResultStatus.COMPLETED.value == "completed"
    assert ResultStatus.MISSING_RETRY_EXHAUSTED.value == "missing_retry_exhausted"
    assert ResultStatus.MISSING_PERMANENT.value == "missing_permanent"
    assert MISSING_STATUSES == {
        ResultStatus.MISSING_RETRY_EXHAUSTED,
        ResultStatus.MISSING_PERMANENT,
    }
    assert ResultStatus.COMPLETED not in MISSING_STATUSES
