"""Publication-boundary enforcement (public_artifact_policy_v1 Section 3.3)."""
from __future__ import annotations

import pytest

from baseline.redaction import (
    REQUEST_ECHO_ALLOWLIST,
    RedactionError,
    assert_public_safe,
    assert_request_echo_allowlisted,
    public_request_echo,
)
from baseline.types import PrivateProviderMetadata, RequestEcho


def _echo(**overrides):
    base = dict(
        provider_kind="dummy",
        api_kind="dummy",
        model_id="dummy-model-a",
        decoding_profile_id="dummy_default_v1",
        decoding_profile_hash="0" * 64,
        params_sent={"temperature": 0, "top_p": 1},
        params_not_sent=("top_k", "seed"),
        max_output_tokens=1024,
        structured_output_enabled=False,
        schema_hash="none",
        retry_policy_summary="max_retries=2, exponential backoff",
    )
    base.update(overrides)
    return RequestEcho(**base)


def test_public_request_echo_emits_exactly_the_allowlist():
    out = public_request_echo(_echo())
    assert set(out) == REQUEST_ECHO_ALLOWLIST
    assert out["params_not_sent"] == ["top_k", "seed"]


def test_public_request_echo_rejects_non_echo_objects():
    with pytest.raises(RedactionError):
        public_request_echo({"model_id": "x"})  # type: ignore[arg-type]
    with pytest.raises(RedactionError):
        public_request_echo(PrivateProviderMetadata())  # type: ignore[arg-type]


def test_params_sent_rejects_non_sampling_keys():
    with pytest.raises(RedactionError, match="params_sent key"):
        public_request_echo(_echo(params_sent={"messages": "hi"}))
    with pytest.raises(RedactionError, match="params_sent key"):
        public_request_echo(_echo(params_sent={"system_prompt": "x"}))


def test_params_sent_rejects_smuggled_long_text():
    with pytest.raises(RedactionError, match="suspiciously long"):
        public_request_echo(_echo(params_sent={"thinking": "a" * 200}))


def test_params_sent_rejects_non_scalar_values():
    with pytest.raises(RedactionError, match="scalar"):
        public_request_echo(_echo(params_sent={"thinking": {"budget": 1}}))


def test_allowlist_check_rejects_extra_and_missing_fields():
    good = public_request_echo(_echo())
    assert_request_echo_allowlisted(good)
    with pytest.raises(RedactionError, match="non-allowlisted"):
        assert_request_echo_allowlisted({**good, "prompt_hash_and_body": "x"})
    bad = dict(good)
    del bad["model_id"]
    with pytest.raises(RedactionError, match="missing"):
        assert_request_echo_allowlisted(bad)


def test_assert_public_safe_accepts_clean_structure():
    assert_public_safe(
        {"models": [{"public_model_id": "m", "run_date": "2026-07-05"}], "n": 1}
    )


@pytest.mark.parametrize(
    "blocked_key",
    ["system_prompt", "user_prompt", "scenario", "question", "rubric",
     "reference_answer", "headers", "api_key", "request_id", "response_id",
     "account_id", "request_body"],
)
def test_assert_public_safe_rejects_blocked_keys(blocked_key):
    with pytest.raises(RedactionError, match="blocked key"):
        assert_public_safe({"inner": {blocked_key: "v"}})


def test_assert_public_safe_rejects_credential_shaped_values():
    with pytest.raises(RedactionError, match="credential"):
        assert_public_safe({"note": "sk-abcdefghijklmnop123456"})
    with pytest.raises(RedactionError, match="credential"):
        assert_public_safe(["Bearer abcdefgh12345678"])


def test_assert_public_safe_rejects_long_strings():
    with pytest.raises(RedactionError, match="length limit"):
        assert_public_safe({"summary": "x" * 401})


def test_assert_public_safe_rejects_forbidden_run_texts():
    prompt = "## Scenario\n工場の品質保留ロットに関する長いシナリオ本文です。承認境界を守ってください。"
    with pytest.raises(RedactionError, match="forbidden run text"):
        assert_public_safe({"note": f"quote: {prompt}"}, forbidden_texts=[prompt])


def test_assert_public_safe_rejects_private_metadata_objects():
    with pytest.raises(RedactionError, match="private provider metadata"):
        assert_public_safe({"meta": PrivateProviderMetadata()})
