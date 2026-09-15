"""Provider protocol, error taxonomy, and shared adapter helpers."""
from __future__ import annotations

import os
from typing import Any, Mapping, Protocol, runtime_checkable

from ..transport import TransportResponse, classify_http_status, error_message_from_body
from ..types import GenerationRequest, GenerationResult


class ProviderError(RuntimeError):
    """Base class for provider failures."""


class ProviderTransientError(ProviderError):
    """Retryable failure (rate limit, timeout, 5xx, truncated body)."""


class ProviderPermanentError(ProviderError):
    """Non-retryable failure (auth error, invalid request, content refusal)."""


class NonRunnableProviderError(ProviderError):
    """Requested provider is not runnable in the current phase."""


@runtime_checkable
class Provider(Protocol):
    provider_kind: str
    api_kind: str

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Execute one generation. Raises ProviderTransientError /
        ProviderPermanentError on failure."""
        ...


def resolve_env(env_name: str, *, purpose: str) -> str:
    """Resolve a credential/endpoint environment variable or fail permanently.

    The resolved value is used only inside transport requests; it is never
    attached to results, echoes, or artifacts.
    """
    value = os.environ.get(env_name, "")
    if not value:
        raise ProviderPermanentError(
            f"environment variable {env_name} ({purpose}) is not set"
        )
    return value


def raise_for_status(response: TransportResponse) -> None:
    """Map an HTTP error status to the provider error taxonomy."""
    kind = classify_http_status(response.status)
    if kind == "ok":
        return
    message = f"HTTP {response.status}: {error_message_from_body(response.body)}"
    if kind == "transient":
        raise ProviderTransientError(message)
    raise ProviderPermanentError(message)


def deep_keys(obj: Any) -> set[str]:
    """All mapping keys appearing anywhere in a nested structure (used to
    assert forbidden parameters are absent from request bodies)."""
    keys: set[str] = set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            keys.add(str(key))
            keys |= deep_keys(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            keys |= deep_keys(value)
    return keys
