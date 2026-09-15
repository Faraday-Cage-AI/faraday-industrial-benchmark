"""Provider factory for the baseline pipeline.

Phase 2B: real adapters (OpenAI Responses / Anthropic Messages /
OpenAI-compatible) exist but are constructible ONLY with an explicitly
injected transport — the runner never injects one, so real-API execution
stays impossible until the Phase 2C gate wires a real transport in.
GeminiNativeProvider remains pending its Go/No-Go verification.
"""
from __future__ import annotations

from typing import Mapping

from ..config import ModelConfig
from ..profiles import DecodingProfile
from ..transport import Transport
from .anthropic_messages import AnthropicMessagesProvider
from .base import (
    NonRunnableProviderError,
    Provider,
    ProviderError,
    ProviderPermanentError,
    ProviderTransientError,
)
from .dummy import BaselineDummyProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_responses import OpenAIResponsesProvider

__all__ = [
    "Provider",
    "ProviderError",
    "ProviderTransientError",
    "ProviderPermanentError",
    "NonRunnableProviderError",
    "BaselineDummyProvider",
    "OpenAIResponsesProvider",
    "AnthropicMessagesProvider",
    "OpenAICompatibleProvider",
    "create_provider",
]

_REAL_PROVIDERS = {
    "openai": OpenAIResponsesProvider,
    "anthropic": AnthropicMessagesProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def create_provider(
    model: ModelConfig,
    profile: DecodingProfile,
    profile_set_hash: str,
    *,
    fail_plan: Mapping[str, str] | None = None,
    transport: Transport | None = None,
) -> Provider:
    if model.provider_kind == "dummy":
        return BaselineDummyProvider(
            model_id=model.public_model_id,
            profile=profile,
            profile_set_hash=profile_set_hash,
            fail_plan=fail_plan,
        )
    if model.provider_kind == "gemini":
        raise NonRunnableProviderError(
            "GeminiNativeProvider is pending the Phase 2C Go/No-Go verification "
            "(baseline_experiment_plan_v1.md Section 4a.4)"
        )
    provider_cls = _REAL_PROVIDERS.get(model.provider_kind)
    if provider_cls is None:
        raise NonRunnableProviderError(
            f"provider_kind {model.provider_kind!r} has no adapter"
        )
    if transport is None:
        raise NonRunnableProviderError(
            f"provider_kind {model.provider_kind!r} requires an explicitly "
            "injected transport; real-API execution is not enabled in this phase"
        )
    return provider_cls(model, profile, profile_set_hash, transport)
