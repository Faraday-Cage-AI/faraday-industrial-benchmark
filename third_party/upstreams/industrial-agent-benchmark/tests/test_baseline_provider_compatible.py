"""OpenAICompatibleProvider: env-resolved base URL, pinned decoding,
extras allowlist (no raw extra_body passthrough)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from _baseline_helpers import FakeTransport, chat_completions_ok, http_error
from baseline.config import load_models_config
from baseline.profiles import ProfileError, load_profiles
from baseline.providers.base import ProviderPermanentError, ProviderTransientError
from baseline.providers.openai_compatible import OpenAICompatibleProvider
from baseline.redaction import REQUEST_ECHO_ALLOWLIST, public_request_echo
from baseline.types import GenerationRequest

FIXTURES = Path(__file__).parent / "fixtures" / "baseline"

SYSTEM = "You are answering Industrial Agent Benchmark tasks."
USER = "## Scenario\n工程能力の再計算シナリオ本文。"


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("TEST_COMPAT_API_KEY", "test-key-not-a-real-credential")
    monkeypatch.setenv("TEST_COMPAT_BASE_URL", "http://localhost:9/v1")
    models = load_models_config(FIXTURES / "models_phase2b.yaml", for_execution=False)
    profiles = load_profiles(FIXTURES / "decoding_profiles_phase2b.yaml")
    by_key = {m.model_key: m for m in models.models}
    return by_key, profiles


def _request(model_key: str) -> GenerationRequest:
    return GenerationRequest(
        system_prompt=SYSTEM,
        user_prompt=USER,
        task_id="IA-WD-001",
        model_key=model_key,
        repeat_index=0,
        decoding_profile_id="compatible_hosted_v1",
    )


def test_body_pins_decoding_and_uses_hosted_model_id(setup):
    by_key, profiles = setup
    transport = FakeTransport([chat_completions_ok()])
    provider = OpenAICompatibleProvider(
        by_key["model_hosted_test"],
        profiles.get("compatible_hosted_v1"),
        profiles.file_sha256,
        transport,
    )
    result = provider.generate(_request("model_hosted_test"))
    body = transport.last_body
    assert body["model"] == "hosted/test-model-fp8"  # hosted_model_id override
    assert body["temperature"] == 0
    assert body["top_p"] == 1
    assert body["seed"] == 20260705
    assert body["max_tokens"] == 4096
    assert transport.requests[0].url == "http://localhost:9/v1/chat/completions"
    # Echo reports the PUBLIC model id, not the serving alias.
    echo = public_request_echo(result.request_echo)
    assert echo["model_id"] == "test-org/test-hosted-model"
    assert echo["params_sent"]["temperature"] == 0
    assert echo["params_sent"]["seed"] == 20260705


def test_missing_base_url_env_config_is_rejected(setup, tmp_path):
    by_key, profiles = setup
    model = by_key["model_hosted_test"]
    from dataclasses import replace

    without_base = replace(model, base_url_env=None)
    with pytest.raises(ProviderPermanentError, match="base_url_env"):
        OpenAICompatibleProvider(
            without_base, profiles.get("compatible_hosted_v1"),
            profiles.file_sha256, FakeTransport(),
        )


def test_unset_base_url_env_var_fails_permanently(setup, monkeypatch):
    by_key, profiles = setup
    monkeypatch.delenv("TEST_COMPAT_BASE_URL", raising=False)
    with pytest.raises(ProviderPermanentError, match="TEST_COMPAT_BASE_URL"):
        OpenAICompatibleProvider(
            by_key["model_hosted_test"], profiles.get("compatible_hosted_v1"),
            profiles.file_sha256, FakeTransport(),
        )


def _profiles_with_extras(tmp_path, extras_yaml: str):
    path = tmp_path / "extras.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai_compatible\n"
        "    api_kind: chat_completions\n"
        "    max_output_tokens: 100\n"
        "    params_sent: {temperature: 0, top_p: 1}\n"
        "    provider_extras:\n" + extras_yaml,
        encoding="utf-8",
    )
    return load_profiles(path)


@pytest.mark.parametrize(
    "extras_yaml,message",
    [
        # Credential/endpoint-like nested keys are rejected by name.
        ("      google_thinking_config: {google_api_key: x}\n", "forbidden key name"),
        ("      google_thinking_config: {authorization: y}\n", "forbidden key name"),
        ("      google_thinking_config: {proxy_url: z}\n", "forbidden key name"),
        ("      google_thinking_config: {session_token: t}\n", "forbidden key name"),
        # Unknown nested keys are rejected even when harmless-looking.
        ("      google_thinking_config: {custom_mode: fast}\n", "unknown google_thinking_config key"),
        # thinking_level is explicitly unsupported for gemini-2.5-pro profiles.
        ("      google_thinking_config: {thinking_level: high}\n", "thinking_level"),
        # include_thoughts: true is forbidden for baseline profiles.
        ("      google_thinking_config: {include_thoughts: true}\n", "include_thoughts"),
        # Arbitrary non-mapping / nested-structure passthrough is rejected.
        ("      google_thinking_config: enabled\n", "must be a mapping"),
        ("      google_thinking_config: {thinking_budget: {inner: 1}}\n", "type"),
        ("      google_thinking_config: {thinking_budget: high}\n", "type"),
        ("      google_thinking_config: {thinking_budget: true}\n", "invalid type bool"),
        ("      google_thinking_config: {thinking_budget: -1}\n", ">= 0"),
        ("      google_thinking_config: {include_thoughts: 1}\n", "type"),
        # The legacy top-level name is no longer an allowlisted extra.
        ("      thinking_config: {thinking_budget: 128}\n", "not allowed"),
    ],
)
def test_google_thinking_config_recursive_allowlist_rejections(setup, tmp_path, extras_yaml, message):
    by_key, _ = setup
    profiles = _profiles_with_extras(tmp_path, extras_yaml)
    with pytest.raises(ProfileError, match=message):
        OpenAICompatibleProvider(
            by_key["model_hosted_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_reasoning_effort_and_google_thinking_config_are_mutually_exclusive(setup, tmp_path):
    by_key, _ = setup
    path = tmp_path / "mixed.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai_compatible\n"
        "    api_kind: chat_completions\n"
        "    max_output_tokens: 100\n"
        "    params_sent: {reasoning_effort: high}\n"
        "    provider_extras:\n"
        "      google_thinking_config: {thinking_budget: 8192}\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match="mutually exclusive"):
        OpenAICompatibleProvider(
            by_key["model_gemini_probe_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_reasoning_effort_must_not_mix_with_sampling_params(setup, tmp_path):
    by_key, _ = setup
    path = tmp_path / "mixed2.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai_compatible\n"
        "    api_kind: chat_completions\n"
        "    max_output_tokens: 100\n"
        "    params_sent: {reasoning_effort: high, temperature: 0}\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match="must not be combined"):
        OpenAICompatibleProvider(
            by_key["model_gemini_probe_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_gemini_baseline_profile_sends_reasoning_effort_only(setup):
    by_key, profiles = setup
    transport = FakeTransport([chat_completions_ok(model="test-gemini-compat")])
    provider = OpenAICompatibleProvider(
        by_key["model_gemini_probe_test"],
        profiles.get("compatible_gemini_baseline_v1"),
        profiles.file_sha256,
        transport,
    )
    result = provider.generate(_request("model_gemini_probe_test"))
    body = transport.last_body
    assert body["reasoning_effort"] == "high"  # top-level, per compat spec
    assert "extra_body" not in body
    assert "thinking_config" not in deep_keys_of(body)
    assert "temperature" not in body and "top_p" not in body and "seed" not in body
    echo = public_request_echo(result.request_echo)
    assert echo["params_sent"] == {"reasoning_effort": "high"}
    assert set(echo) == REQUEST_ECHO_ALLOWLIST


def test_future_google_thinking_config_maps_to_extra_body_google(setup):
    by_key, profiles = setup
    transport = FakeTransport([chat_completions_ok(model="test-gemini-compat")])
    provider = OpenAICompatibleProvider(
        by_key["model_gemini_probe_test"],
        profiles.get("compatible_gemini_future_v1"),
        profiles.file_sha256,
        transport,
    )
    result = provider.generate(_request("model_gemini_probe_test"))
    body = transport.last_body
    # Exact fixed wire placement; never a top-level thinking_config.
    assert body["extra_body"] == {
        "google": {"thinking_config": {"thinking_budget": 8192}}
    }
    assert "thinking_config" not in body
    assert "reasoning_effort" not in body
    echo = public_request_echo(result.request_echo)
    parsed = json.loads(echo["params_sent"]["google_thinking_config"])
    assert parsed == {"thinking_budget": 8192}
    assert len(echo["params_sent"]["google_thinking_config"]) <= 80
    # Echo carries only allowlisted setting values + profile ID/hash.
    assert echo["decoding_profile_id"] == "compatible_gemini_future_v1"
    assert echo["decoding_profile_hash"] == profiles.file_sha256
    echo_text = str(echo)
    for fragment in (
        "api_key", "authorization", "secret", "http", "Bearer",
        "test-key-not-a-real-credential", "localhost", "thought",
        "## Scenario",
    ):
        assert fragment not in echo_text.replace("include_thoughts", "")


def deep_keys_of(obj):
    from baseline.providers.base import deep_keys

    return deep_keys(obj)


@pytest.mark.parametrize(
    "extras_yaml,message",
    [
        ("      extra_body: {foo: 1}\n", "not allowed"),
        ("      logit_bias: {\"5\": 10}\n", "not allowed"),
    ],
)
def test_non_allowlisted_extras_are_rejected(setup, tmp_path, extras_yaml, message):
    by_key, _ = setup
    path = tmp_path / "bad.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai_compatible\n"
        "    api_kind: chat_completions\n"
        "    max_output_tokens: 100\n"
        "    params_sent: {temperature: 0, top_p: 1}\n"
        "    provider_extras:\n" + extras_yaml,
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match=message):
        OpenAICompatibleProvider(
            by_key["model_hosted_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


@pytest.mark.parametrize(
    "params,message",
    [
        ("{temperature: 0.7, top_p: 1}", "temperature"),
        ("{temperature: 0, top_p: 0.9}", "top_p"),
    ],
)
def test_unpinned_decoding_is_rejected(setup, tmp_path, params, message):
    by_key, _ = setup
    path = tmp_path / "bad.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai_compatible\n"
        "    api_kind: chat_completions\n"
        "    max_output_tokens: 100\n"
        f"    params_sent: {params}\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match=message):
        OpenAICompatibleProvider(
            by_key["model_hosted_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_response_normalization_and_error_classification(setup):
    by_key, profiles = setup
    transport = FakeTransport(
        [chat_completions_ok("ホスト回答", response_id="chatcmpl_secret789")]
    )
    provider = OpenAICompatibleProvider(
        by_key["model_hosted_test"], profiles.get("compatible_hosted_v1"),
        profiles.file_sha256, transport,
    )
    result = provider.generate(_request("model_hosted_test"))
    assert result.text == "ホスト回答"
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 90
    assert result.usage.output_tokens == 45
    assert result.private_metadata.provider_response_id == "chatcmpl_secret789"
    assert "chatcmpl_secret789" not in str(public_request_echo(result.request_echo))

    provider = OpenAICompatibleProvider(
        by_key["model_hosted_test"], profiles.get("compatible_hosted_v1"),
        profiles.file_sha256, FakeTransport([http_error(500, "backend down")]),
    )
    with pytest.raises(ProviderTransientError, match="500"):
        provider.generate(_request("model_hosted_test"))


def test_malformed_response_is_permanent(setup):
    from baseline.transport import TransportResponse

    by_key, profiles = setup
    provider = OpenAICompatibleProvider(
        by_key["model_hosted_test"], profiles.get("compatible_hosted_v1"),
        profiles.file_sha256,
        FakeTransport([TransportResponse(status=200, body={"choices": []})]),
    )
    with pytest.raises(ProviderPermanentError, match="choices"):
        provider.generate(_request("model_hosted_test"))
