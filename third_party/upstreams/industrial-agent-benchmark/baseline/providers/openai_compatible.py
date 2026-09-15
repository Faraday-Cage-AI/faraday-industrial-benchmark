"""OpenAI-compatible chat/completions adapter.

Targets (baseline_experiment_plan_v1.md §2):
- hosted Qwen3-235B-A22B-Instruct-2507 and Llama-4-Maverick (hosted providers),
- Qwen3-Swallow-32B-RL-v0.2 on vLLM (cloud GPU),
- conditionally Gemini 2.5 Pro via its OpenAI-compatible endpoint — ONLY if
  the Phase 2C Go/No-Go verification passes (§4a.4). The first-pilot Gemini
  profile sends ``reasoning_effort`` only (officially mapped to thinking
  levels); the future-facing ``google_thinking_config`` block is mapped to
  the fixed wire position ``extra_body.google.thinking_config``.

Decoding policy (§4a.5): hosted OSS profiles pin temperature=0, top_p=1 and
seed. Provider-specific settings pass ONLY through the profile
``provider_extras`` allowlist (currently ``google_thinking_config``); there
is no raw ``extra_body`` passthrough, and reasoning_effort is mutually
exclusive with sampling params and google_thinking_config (profile load
enforces this).

The endpoint base URL and API key are resolved from environment variables
named in the model config; neither value ever reaches results or artifacts.
"""
from __future__ import annotations

import json

from ..config import ModelConfig
from ..profiles import DecodingProfile, validate_profile_for_provider
from ..transport import Transport, TransportRequest
from ..types import (
    GenerationRequest,
    GenerationResult,
    PrivateProviderMetadata,
    RequestEcho,
    Usage,
)
from .base import ProviderPermanentError, raise_for_status, resolve_env


class OpenAICompatibleProvider:
    provider_kind = "openai_compatible"
    api_kind = "chat_completions"

    def __init__(
        self,
        model: ModelConfig,
        profile: DecodingProfile,
        profile_set_hash: str,
        transport: Transport,
        *,
        timeout: float = 300.0,
    ) -> None:
        if profile.provider_kind != "openai_compatible":
            raise ValueError(
                f"profile {profile.profile_id!r} is for {profile.provider_kind!r}, "
                "not 'openai_compatible'"
            )
        validate_profile_for_provider(profile)
        if not model.base_url_env:
            raise ProviderPermanentError(
                f"model {model.model_key!r}: openai_compatible models must set "
                "base_url_env (endpoint URLs are private runtime configuration)"
            )
        self.model = model
        self.profile = profile
        self.profile_set_hash = profile_set_hash
        self.transport = transport
        self.timeout = timeout
        self._base_url = resolve_env(
            model.base_url_env, purpose="OpenAI-compatible base URL"
        ).rstrip("/")
        self._api_key = (
            resolve_env(model.api_key_env, purpose="OpenAI-compatible API key")
            if model.api_key_env
            else ""
        )

    @property
    def request_model_id(self) -> str:
        return self.model.hosted_model_id or self.model.public_model_id

    def build_body(self, request: GenerationRequest) -> dict:
        if request.output_schema is not None:
            raise ProviderPermanentError(
                "structured output over OpenAI-compatible endpoints is not part "
                "of the Phase 2B scope"
            )
        body: dict = {
            "model": self.request_model_id,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": self.profile.max_output_tokens,
        }
        for key in ("temperature", "top_p", "seed", "reasoning_effort"):
            if key in self.profile.params_sent:
                body[key] = self.profile.params_sent[key]
        # Provider-specific blocks arrive only via the profile allowlist
        # (validate_profile_for_provider) and are mapped to a FIXED wire
        # position — never a raw passthrough. google_thinking_config maps to
        # extra_body.google.thinking_config per the Gemini OpenAI-compat spec;
        # it never appears at the top level of the body.
        google_thinking = self.profile.provider_extras.get("google_thinking_config")
        if google_thinking is not None:
            body["extra_body"] = {"google": {"thinking_config": dict(google_thinking)}}
        return body

    def _echo_params(self) -> dict:
        params = dict(self.profile.params_sent)
        for key, value in self.profile.provider_extras.items():
            # Extras are echoed as compact JSON strings (profile validation
            # bounds their size) so request_echo values stay scalar.
            params[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return params

    def generate(self, request: GenerationRequest) -> GenerationResult:
        body = self.build_body(request)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = self.transport.send(
            TransportRequest(
                url=f"{self._base_url}/chat/completions",
                headers=headers,
                body=body,
                timeout=self.timeout,
            )
        )
        raise_for_status(response)
        data = response.body
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderPermanentError(
                "response is missing choices[0].message.content"
            ) from error
        if not isinstance(text, str):
            raise ProviderPermanentError("response content must be a string")
        usage = data.get("usage") or {}
        echo = RequestEcho(
            provider_kind=self.provider_kind,
            api_kind=self.api_kind,
            model_id=self.model.public_model_id,
            decoding_profile_id=self.profile.profile_id,
            decoding_profile_hash=self.profile_set_hash,
            params_sent=self._echo_params(),
            params_not_sent=tuple(self.profile.params_not_sent),
            max_output_tokens=self.profile.max_output_tokens,
            structured_output_enabled=False,
            schema_hash="none",
            retry_policy_summary=self.profile.retry_policy_summary,
        )
        return GenerationResult(
            text=text,
            finish_reason=str(choice.get("finish_reason", "unknown")),
            usage=Usage(
                input_tokens=usage.get("prompt_tokens", "unknown"),
                output_tokens=usage.get("completion_tokens", "unknown"),
            ),
            served_model_id=str(data.get("model", self.request_model_id)),
            request_echo=echo,
            private_metadata=PrivateProviderMetadata(
                provider_response_id=str(data.get("id", "none")),
            ),
        )
