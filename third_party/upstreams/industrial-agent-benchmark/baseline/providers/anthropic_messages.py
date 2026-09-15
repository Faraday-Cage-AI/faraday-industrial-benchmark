"""Anthropic Messages API adapter (claude-opus-4-8 evaluated /
claude-sonnet-5 second judge).

Decoding policy: baseline_experiment_plan_v1.md §4a.3 —

- Opus 4.8 profiles explicitly enable ``thinking: adaptive`` and pin
  ``effort: high``.
- Sonnet 5 profiles pin ``effort: high`` only; adaptive thinking stays the
  provider default (no ``thinking`` key is sent) and manual thinking budgets
  (``budget_tokens``) are never sent.
- ``temperature`` / ``top_p`` / ``top_k`` are never sent to Anthropic.

These rules are enforced three times: at profile load
(``validate_profile_for_provider``), at body construction (a hard check that
no forbidden key appears anywhere in the built body), and by fake-transport
tests that capture real request bodies.
"""
from __future__ import annotations

from ..config import ModelConfig
from ..profiles import (
    ANTHROPIC_FORBIDDEN_PARAMS,
    DecodingProfile,
    validate_profile_for_provider,
)
from ..transport import Transport, TransportRequest
from ..types import (
    GenerationRequest,
    GenerationResult,
    PrivateProviderMetadata,
    RequestEcho,
    Usage,
)
from .base import ProviderPermanentError, deep_keys, raise_for_status, resolve_env

DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_API_KEY_ENV = "ANTHROPIC_API_KEY"
ANTHROPIC_VERSION = "2023-06-01"

_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
}


class AnthropicMessagesProvider:
    provider_kind = "anthropic"
    api_kind = "messages"

    def __init__(
        self,
        model: ModelConfig,
        profile: DecodingProfile,
        profile_set_hash: str,
        transport: Transport,
        *,
        timeout: float = 300.0,
    ) -> None:
        if profile.provider_kind != "anthropic":
            raise ValueError(
                f"profile {profile.profile_id!r} is for {profile.provider_kind!r}, "
                "not 'anthropic'"
            )
        validate_profile_for_provider(profile)
        self.model = model
        self.profile = profile
        self.profile_set_hash = profile_set_hash
        self.transport = transport
        self.timeout = timeout
        self._api_key = resolve_env(
            model.api_key_env or DEFAULT_API_KEY_ENV, purpose="Anthropic API key"
        )
        self._base_url = (
            resolve_env(model.base_url_env, purpose="Anthropic base URL")
            if model.base_url_env
            else DEFAULT_BASE_URL
        ).rstrip("/")

    def build_body(self, request: GenerationRequest) -> dict:
        if request.output_schema is not None:
            raise ProviderPermanentError(
                "Anthropic structured output (tool-use schema enforcement, P0-2) "
                "is not implemented in Phase 2B"
            )
        body: dict = {
            "model": self.model.public_model_id,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
            "max_tokens": self.profile.max_output_tokens,
        }
        thinking = self.profile.params_sent.get("thinking")
        if thinking is not None:
            # Opus 4.8: adaptive thinking explicitly enabled (mandatory for
            # this baseline). Sonnet 5 profiles omit the key entirely.
            body["thinking"] = {"type": thinking}
        effort = self.profile.params_sent.get("effort")
        if effort is not None:
            # Official wire placement: effort lives under output_config, never
            # at the top level of the request body.
            body["output_config"] = {"effort": effort}
        forbidden = deep_keys(body) & ANTHROPIC_FORBIDDEN_PARAMS
        if forbidden:
            raise ProviderPermanentError(
                f"internal error: forbidden Anthropic parameters in request body: "
                f"{sorted(forbidden)}"
            )
        return body

    def generate(self, request: GenerationRequest) -> GenerationResult:
        body = self.build_body(request)
        response = self.transport.send(
            TransportRequest(
                url=f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
                body=body,
                timeout=self.timeout,
            )
        )
        raise_for_status(response)
        data = response.body
        text = "".join(
            str(block.get("text", ""))
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        stop_reason = str(data.get("stop_reason", "unknown"))
        usage = data.get("usage") or {}
        echo = RequestEcho(
            provider_kind=self.provider_kind,
            api_kind=self.api_kind,
            model_id=self.model.public_model_id,
            decoding_profile_id=self.profile.profile_id,
            decoding_profile_hash=self.profile_set_hash,
            params_sent=dict(self.profile.params_sent),
            params_not_sent=tuple(self.profile.params_not_sent),
            max_output_tokens=self.profile.max_output_tokens,
            structured_output_enabled=False,
            schema_hash="none",
            retry_policy_summary=self.profile.retry_policy_summary,
        )
        return GenerationResult(
            text=text,
            finish_reason=_STOP_REASON_MAP.get(stop_reason, stop_reason),
            usage=Usage(
                input_tokens=usage.get("input_tokens", "unknown"),
                output_tokens=usage.get("output_tokens", "unknown"),
            ),
            served_model_id=str(data.get("model", self.model.public_model_id)),
            request_echo=echo,
            private_metadata=PrivateProviderMetadata(
                provider_response_id=str(data.get("id", "none")),
            ),
        )
