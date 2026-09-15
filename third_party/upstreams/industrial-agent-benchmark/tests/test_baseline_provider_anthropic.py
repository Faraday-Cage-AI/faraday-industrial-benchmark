"""AnthropicMessagesProvider: forbidden sampling params never sent;
Opus adaptive thinking / Sonnet constraints; response normalization."""
from __future__ import annotations

from pathlib import Path

import pytest

from _baseline_helpers import FakeTransport, anthropic_ok, http_error
from baseline.config import load_models_config
from baseline.profiles import ProfileError, load_profiles
from baseline.providers.anthropic_messages import AnthropicMessagesProvider
from baseline.providers.base import (
    ProviderPermanentError,
    ProviderTransientError,
    deep_keys,
)
from baseline.redaction import public_request_echo
from baseline.types import GenerationRequest

FIXTURES = Path(__file__).parent / "fixtures" / "baseline"

SYSTEM = "You are answering Industrial Agent Benchmark tasks."
USER = "## Scenario\n設備停止時の復旧判断シナリオ本文。"

FORBIDDEN_BODY_KEYS = {"temperature", "top_p", "top_k", "budget_tokens"}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("TEST_ANTHROPIC_API_KEY", "test-key-not-a-real-credential")
    models = load_models_config(FIXTURES / "models_phase2b.yaml", for_execution=False)
    profiles = load_profiles(FIXTURES / "decoding_profiles_phase2b.yaml")
    by_key = {m.model_key: m for m in models.models}
    return by_key, profiles


def _request(model_key: str) -> GenerationRequest:
    return GenerationRequest(
        system_prompt=SYSTEM,
        user_prompt=USER,
        task_id="IR-NCP-001",
        model_key=model_key,
        repeat_index=0,
        decoding_profile_id="anthropic_opus_v1",
    )


def test_opus_body_has_adaptive_thinking_and_no_forbidden_params(setup):
    by_key, profiles = setup
    transport = FakeTransport([anthropic_ok()])
    provider = AnthropicMessagesProvider(
        by_key["model_anthropic_opus_test"],
        profiles.get("anthropic_opus_v1"),
        profiles.file_sha256,
        transport,
    )
    provider.generate(_request("model_anthropic_opus_test"))
    body = transport.last_body
    assert body["thinking"] == {"type": "adaptive"}
    # effort lives ONLY under output_config, never at the top level.
    assert body["output_config"] == {"effort": "high"}
    assert "effort" not in body
    assert body["max_tokens"] == 8192
    assert body["system"] == SYSTEM
    assert body["messages"] == [{"role": "user", "content": USER}]
    assert deep_keys(body) & FORBIDDEN_BODY_KEYS == set()
    assert transport.requests[0].url == "https://api.anthropic.com/v1/messages"
    assert transport.last_headers["anthropic-version"] == "2023-06-01"


def test_sonnet_body_omits_thinking_and_budget_tokens(setup):
    by_key, profiles = setup
    transport = FakeTransport([anthropic_ok()])
    provider = AnthropicMessagesProvider(
        by_key["model_anthropic_sonnet_test"],
        profiles.get("anthropic_sonnet_v1"),
        profiles.file_sha256,
        transport,
    )
    result = provider.generate(_request("model_anthropic_sonnet_test"))
    body = transport.last_body
    assert "thinking" not in body  # provider default (adaptive) not manually set
    assert body["output_config"] == {"effort": "high"}
    assert "effort" not in body  # never at the top level
    assert deep_keys(body) & FORBIDDEN_BODY_KEYS == set()
    echo = public_request_echo(result.request_echo)
    assert "budget_tokens" in echo["params_not_sent"]
    assert set(echo["params_sent"]) == {"effort"}


def test_no_forbidden_or_manual_thinking_keys_anywhere_in_bodies(setup):
    by_key, profiles = setup
    for model_key, profile_id in (
        ("model_anthropic_opus_test", "anthropic_opus_v1"),
        ("model_anthropic_sonnet_test", "anthropic_sonnet_v1"),
    ):
        transport = FakeTransport([anthropic_ok()])
        provider = AnthropicMessagesProvider(
            by_key[model_key], profiles.get(profile_id), profiles.file_sha256, transport
        )
        provider.generate(_request(model_key))
        keys = deep_keys(transport.last_body)
        assert keys & FORBIDDEN_BODY_KEYS == set()
        assert keys & {"max_thinking_tokens", "budget_tokens"} == set()
        assert "effort" not in transport.last_body  # top-level check


@pytest.mark.parametrize(
    "param,value",
    [("temperature", 0), ("top_p", 1), ("top_k", 40), ("budget_tokens", 1024)],
)
def test_profiles_with_forbidden_anthropic_params_fail_at_load(setup, tmp_path, param, value):
    by_key, _ = setup
    path = tmp_path / "bad.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: anthropic\n"
        "    api_kind: messages\n"
        "    max_output_tokens: 100\n"
        "    params_sent:\n"
        f"      {param}: {value}\n"
        "    params_not_sent: [temperature, top_p, top_k]\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError):
        AnthropicMessagesProvider(
            by_key["model_anthropic_opus_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_non_adaptive_thinking_is_rejected(setup, tmp_path):
    by_key, _ = setup
    path = tmp_path / "bad.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: anthropic\n"
        "    api_kind: messages\n"
        "    max_output_tokens: 100\n"
        "    params_sent:\n"
        "      thinking: manual\n"
        "    params_not_sent: [temperature, top_p, top_k]\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match="adaptive"):
        AnthropicMessagesProvider(
            by_key["model_anthropic_opus_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_params_not_sent_must_declare_the_sampling_trio(setup, tmp_path):
    by_key, _ = setup
    path = tmp_path / "bad.yaml"
    path.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: anthropic\n"
        "    api_kind: messages\n"
        "    max_output_tokens: 100\n"
        "    params_sent:\n"
        "      effort: high\n"
        "    params_not_sent: [temperature]\n",
        encoding="utf-8",
    )
    profiles = load_profiles(path)
    with pytest.raises(ProfileError, match="params_not_sent"):
        AnthropicMessagesProvider(
            by_key["model_anthropic_opus_test"], profiles.get("p"),
            profiles.file_sha256, FakeTransport(),
        )


def test_response_normalization(setup):
    by_key, profiles = setup
    transport = FakeTransport(
        [anthropic_ok("思考後の回答", stop_reason="max_tokens", response_id="msg_secret456")]
    )
    provider = AnthropicMessagesProvider(
        by_key["model_anthropic_opus_test"],
        profiles.get("anthropic_opus_v1"),
        profiles.file_sha256,
        transport,
    )
    result = provider.generate(_request("model_anthropic_opus_test"))
    assert result.text == "思考後の回答"
    assert result.finish_reason == "length"
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 60
    assert result.served_model_id == "test-anthropic-model-20260601"
    assert result.private_metadata.provider_response_id == "msg_secret456"
    assert "msg_secret456" not in str(public_request_echo(result.request_echo))


def test_http_status_classification(setup):
    by_key, profiles = setup
    provider = AnthropicMessagesProvider(
        by_key["model_anthropic_opus_test"],
        profiles.get("anthropic_opus_v1"),
        profiles.file_sha256,
        FakeTransport([http_error(503, "overloaded")]),
    )
    with pytest.raises(ProviderTransientError, match="503"):
        provider.generate(_request("model_anthropic_opus_test"))


def test_structured_output_not_implemented_in_phase_2b(setup):
    from baseline.types import OutputSchema

    by_key, profiles = setup
    provider = AnthropicMessagesProvider(
        by_key["model_anthropic_sonnet_test"],
        profiles.get("anthropic_sonnet_v1"),
        profiles.file_sha256,
        FakeTransport(),
    )
    schema = OutputSchema(name="j", schema={"type": "object"}, sha256="0" * 64)
    request = GenerationRequest(
        system_prompt=SYSTEM, user_prompt=USER, task_id="X", model_key="k",
        repeat_index=0, decoding_profile_id="anthropic_sonnet_v1",
        output_schema=schema,
    )
    with pytest.raises(ProviderPermanentError, match="P0-2"):
        provider.generate(request)
