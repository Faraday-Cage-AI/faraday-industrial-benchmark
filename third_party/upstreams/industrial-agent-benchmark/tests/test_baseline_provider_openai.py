"""OpenAIResponsesProvider: body construction, Structured Outputs, safety."""
from __future__ import annotations

from pathlib import Path

import pytest

from _baseline_helpers import FakeTransport, http_error, openai_responses_ok
from baseline.config import load_models_config
from baseline.profiles import ProfileError, load_profiles
from baseline.providers.base import ProviderPermanentError, ProviderTransientError
from baseline.providers.openai_responses import OpenAIResponsesProvider
from baseline.redaction import REQUEST_ECHO_ALLOWLIST, public_request_echo
from baseline.types import GenerationRequest, OutputSchema

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "baseline"
SCHEMA_PATH = ROOT / "experiments" / "baseline_v2_2_0" / "schemas" / "judgement_v1.schema.json"

SYSTEM = "You are answering Industrial Agent Benchmark tasks."
USER = "## Scenario\n品質保留ロットの出荷可否を判断してください。長文シナリオ本文。"


@pytest.fixture
def provider_setup(monkeypatch):
    monkeypatch.setenv("TEST_OPENAI_API_KEY", "test-key-not-a-real-credential")
    models = load_models_config(FIXTURES / "models_phase2b.yaml", for_execution=False)
    model = next(m for m in models.models if m.model_key == "model_openai_test")
    profiles = load_profiles(FIXTURES / "decoding_profiles_phase2b.yaml")
    return model, profiles


def _request(output_schema=None):
    return GenerationRequest(
        system_prompt=SYSTEM,
        user_prompt=USER,
        task_id="IK-QUAL-001",
        model_key="model_openai_test",
        repeat_index=0,
        decoding_profile_id="openai_answer_v1",
        output_schema=output_schema,
    )


def test_answer_body_construction(provider_setup):
    model, profiles = provider_setup
    transport = FakeTransport([openai_responses_ok()])
    provider = OpenAIResponsesProvider(
        model, profiles.get("openai_answer_v1"), profiles.file_sha256, transport
    )
    provider.generate(_request())
    body = transport.last_body
    assert body["model"] == "test-openai-model"
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "high"}
    assert body["max_output_tokens"] == 8192
    assert [m["role"] for m in body["input"]] == ["system", "user"]
    assert body["input"][1]["content"] == USER
    assert "text" not in body  # no structured output for answers
    assert transport.requests[0].url == "https://api.openai.com/v1/responses"
    assert transport.last_headers["Authorization"].endswith("test-key-not-a-real-credential")


def test_judge_structured_outputs_configuration(provider_setup):
    model, profiles = provider_setup
    schema = OutputSchema.from_file(SCHEMA_PATH, name="judgement_v1")
    transport = FakeTransport([openai_responses_ok('{"question_id":"IK-QUAL-001"}')])
    provider = OpenAIResponsesProvider(
        model, profiles.get("openai_judge_v1"), profiles.file_sha256, transport
    )
    result = provider.generate(_request(output_schema=schema))
    fmt = transport.last_body["text"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["strict"] is True
    assert fmt["name"] == "judgement_v1"
    assert fmt["schema"]["additionalProperties"] is False
    assert set(fmt["schema"]["required"]) == set(fmt["schema"]["properties"])
    echo = public_request_echo(result.request_echo)
    assert echo["structured_output_enabled"] is True
    assert echo["schema_hash"] == schema.sha256


def test_response_normalization_and_private_metadata(provider_setup):
    model, profiles = provider_setup
    transport = FakeTransport(
        [openai_responses_ok("正規化テスト回答", response_id="resp_secret123")]
    )
    provider = OpenAIResponsesProvider(
        model, profiles.get("openai_answer_v1"), profiles.file_sha256, transport
    )
    result = provider.generate(_request())
    assert result.text == "正規化テスト回答"
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.served_model_id == "test-openai-model-2026-06-01"
    # Response ID stays in private metadata, never in the echo.
    assert result.private_metadata.provider_response_id == "resp_secret123"
    echo = public_request_echo(result.request_echo)
    assert set(echo) == REQUEST_ECHO_ALLOWLIST
    assert "resp_secret123" not in str(echo)
    assert USER not in str(echo)
    assert "test-key-not-a-real-credential" not in str(echo)


def test_incomplete_response_maps_finish_reason(provider_setup):
    model, profiles = provider_setup
    ok = openai_responses_ok()
    body = dict(ok.body)
    body["status"] = "incomplete"
    body["incomplete_details"] = {"reason": "max_output_tokens"}
    transport = FakeTransport([type(ok)(status=200, body=body)])
    provider = OpenAIResponsesProvider(
        model, profiles.get("openai_answer_v1"), profiles.file_sha256, transport
    )
    result = provider.generate(_request())
    assert result.finish_reason == "max_output_tokens"


def test_http_status_classification(provider_setup):
    model, profiles = provider_setup
    provider = OpenAIResponsesProvider(
        model,
        profiles.get("openai_answer_v1"),
        profiles.file_sha256,
        FakeTransport([http_error(429, "rate limited")]),
    )
    with pytest.raises(ProviderTransientError, match="429"):
        provider.generate(_request())
    provider = OpenAIResponsesProvider(
        model,
        profiles.get("openai_answer_v1"),
        profiles.file_sha256,
        FakeTransport([http_error(400, "bad request")]),
    )
    with pytest.raises(ProviderPermanentError, match="400"):
        provider.generate(_request())


def test_missing_api_key_env_fails_permanently(provider_setup, monkeypatch):
    model, profiles = provider_setup
    monkeypatch.delenv("TEST_OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderPermanentError, match="TEST_OPENAI_API_KEY"):
        OpenAIResponsesProvider(
            model, profiles.get("openai_answer_v1"), profiles.file_sha256, FakeTransport()
        )


def test_profile_kind_mismatch_and_bad_params_rejected(provider_setup, tmp_path):
    model, profiles = provider_setup
    with pytest.raises(ValueError, match="not 'openai'"):
        OpenAIResponsesProvider(
            model, profiles.get("anthropic_opus_v1"), profiles.file_sha256, FakeTransport()
        )
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "profiles:\n"
        "  p:\n"
        "    provider_kind: openai\n"
        "    api_kind: responses\n"
        "    max_output_tokens: 100\n"
        "    params_sent:\n"
        "      temperature: 0\n",
        encoding="utf-8",
    )
    bad_profiles = load_profiles(bad)
    with pytest.raises(ProfileError, match="not allowed"):
        OpenAIResponsesProvider(
            model, bad_profiles.get("p"), bad_profiles.file_sha256, FakeTransport()
        )
