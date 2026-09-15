"""Publication-boundary enforcement for public manifests.

Implements public_artifact_policy_v1.md Section 3.3: the only provider-request
information a public manifest may carry is the ``request_echo`` allowlist.
This module is the single serializer from :class:`RequestEcho` to a plain
dict, plus a defensive scanner applied to whole public manifests before they
are written.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any, Iterable

from .types import PrivateProviderMetadata, RequestEcho

# Exactly the dataclass fields of RequestEcho; pinned by tests against the
# policy Section 3.3 allowlist.
REQUEST_ECHO_ALLOWLIST: frozenset[str] = frozenset(
    f.name for f in dataclasses.fields(RequestEcho)
)

# Keys that must never appear anywhere in a public manifest structure.
BLOCKED_KEYS: frozenset[str] = frozenset(
    {
        "prompt",
        "system_prompt",
        "user_prompt",
        "prompt_text",
        "messages",
        "scenario",
        "question",
        "rubric",
        "evaluation_rubric",
        "reference_answer",
        "answer_text",
        "request_body",
        "raw_request",
        "raw_response",
        "headers",
        "api_key",
        "authorization",
        "endpoint_secret",
        "request_id",
        "response_id",
        "provider_request_id",
        "provider_response_id",
        "account_id",
        "account_identifier",
        "log_id",
        "billing",
        "private_metadata",
    }
)

# Values that look like credentials or bearer tokens.
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S{8,}|AKIA[0-9A-Z]{16})")

# Public manifest values are short identifiers / summaries; any long string
# is treated as smuggled payload text.
MAX_PUBLIC_STRING_LEN = 400

# Keys inside RequestEcho.params_sent must name sampling / reasoning /
# thinking settings, not payload material.
ALLOWED_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "temperature",
        "top_p",
        "top_k",
        "seed",
        "reasoning_effort",
        "effort",
        "thinking",
        "google_thinking_config",
        "max_output_tokens",
    }
)


class RedactionError(ValueError):
    """A value violates the public publication boundary."""


def public_request_echo(echo: RequestEcho) -> dict[str, Any]:
    """Serialize a RequestEcho to the public-manifest dict.

    This is the only supported path from provider results to a public
    manifest; it iterates the frozen dataclass fields so nothing outside the
    allowlist can be emitted, and validates params_sent contents.
    """
    if not isinstance(echo, RequestEcho):
        raise RedactionError(
            f"public_request_echo requires a RequestEcho, got {type(echo).__name__}"
        )
    params_sent = dict(echo.params_sent)
    for key, value in params_sent.items():
        if key not in ALLOWED_PARAM_KEYS:
            raise RedactionError(f"params_sent key not allowed: {key!r}")
        if not isinstance(value, (str, int, float, bool)):
            raise RedactionError(f"params_sent[{key!r}] must be a scalar")
        if isinstance(value, str) and len(value) > 80:
            raise RedactionError(f"params_sent[{key!r}] value is suspiciously long")
    out: dict[str, Any] = {}
    for f in dataclasses.fields(RequestEcho):
        value = getattr(echo, f.name)
        if f.name == "params_sent":
            value = params_sent
        elif f.name == "params_not_sent":
            value = list(value)
        out[f.name] = value
    return out


def assert_request_echo_allowlisted(echo_dict: dict[str, Any]) -> None:
    """Fail if a serialized request_echo has any field outside the allowlist."""
    extra = set(echo_dict) - REQUEST_ECHO_ALLOWLIST
    if extra:
        raise RedactionError(f"request_echo contains non-allowlisted fields: {sorted(extra)}")
    missing = REQUEST_ECHO_ALLOWLIST - set(echo_dict)
    if missing:
        raise RedactionError(f"request_echo is missing allowlisted fields: {sorted(missing)}")


def assert_public_safe(obj: Any, *, forbidden_texts: Iterable[str] = ()) -> None:
    """Recursively scan a JSON-able structure destined for publication.

    Raises RedactionError on: blocked keys, credential-shaped values,
    over-long strings (smuggled payload text), private metadata objects, or
    any occurrence of the caller-supplied forbidden texts (e.g., the actual
    prompt and answer bodies of the run).
    """
    forbidden = [t for t in forbidden_texts if t and len(t) >= 20]
    _scan(obj, path="$", forbidden_texts=forbidden)


def _scan(obj: Any, *, path: str, forbidden_texts: list[str]) -> None:
    if isinstance(obj, PrivateProviderMetadata):
        raise RedactionError(f"private provider metadata at {path} must not be published")
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in BLOCKED_KEYS:
                raise RedactionError(f"blocked key {key!r} at {path}")
            _scan(value, path=f"{path}.{key}", forbidden_texts=forbidden_texts)
        return
    if isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            _scan(value, path=f"{path}[{i}]", forbidden_texts=forbidden_texts)
        return
    if isinstance(obj, str):
        if len(obj) > MAX_PUBLIC_STRING_LEN:
            raise RedactionError(f"string at {path} exceeds public length limit")
        if SECRET_VALUE_RE.search(obj):
            raise RedactionError(f"credential-shaped value at {path}")
        for text in forbidden_texts:
            if text in obj:
                raise RedactionError(f"forbidden run text found at {path}")
        return
    if obj is None or isinstance(obj, (int, float, bool)):
        return
    raise RedactionError(f"non-JSON-serializable value at {path}: {type(obj).__name__}")
