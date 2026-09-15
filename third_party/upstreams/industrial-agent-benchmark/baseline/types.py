"""Core datatypes for the baseline pipeline.

The central design rule (Public Artifact Policy v1, Section 3.3) is enforced
at the type level: everything that may reach a public manifest about a
provider request is carried by :class:`RequestEcho`, whose fields are exactly
the policy allowlist. Provider-side identifiers and any raw material live in
:class:`PrivateProviderMetadata`, which the public manifest serializer never
accepts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class ResultStatus(str, Enum):
    """Terminal status of one (model, task, repeat) generation attempt."""

    COMPLETED = "completed"
    MISSING_RETRY_EXHAUSTED = "missing_retry_exhausted"
    MISSING_PERMANENT = "missing_permanent"


MISSING_STATUSES = frozenset(
    {ResultStatus.MISSING_RETRY_EXHAUSTED, ResultStatus.MISSING_PERMANENT}
)


@dataclass(frozen=True)
class RequestEcho:
    """Redacted execution metadata — the ONLY provider-request information
    allowed into a public manifest.

    Fields mirror the allowlist in public_artifact_policy_v1.md Section 3.3
    one-to-one (the "decoding profile ID / hash" item maps to two fields).
    Do not add fields without a policy revision; tests pin the field set.
    """

    provider_kind: str
    api_kind: str
    model_id: str
    decoding_profile_id: str
    decoding_profile_hash: str
    params_sent: Mapping[str, Any]
    params_not_sent: tuple[str, ...]
    max_output_tokens: int | str
    structured_output_enabled: bool
    schema_hash: str
    retry_policy_summary: str


@dataclass(frozen=True)
class PrivateProviderMetadata:
    """Provider-side metadata that is NEVER published.

    Kept as a separate type so it cannot be passed where a
    :class:`RequestEcho` is expected. ``"none"`` marks fields a provider
    did not produce (the dummy provider produces none of them).
    """

    provider_request_id: str = "none"
    provider_response_id: str = "none"
    raw_response_path: str = "none"
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    """Token usage; ``"unknown"`` when the provider does not report it."""

    input_tokens: int | str = "unknown"
    output_tokens: int | str = "unknown"


@dataclass(frozen=True)
class OutputSchema:
    """A frozen structured-output JSON schema (judge judgements).

    ``sha256`` is the hash of the schema file bytes; it is the only
    schema-related value that appears in public manifests.
    """

    name: str
    schema: Mapping[str, Any]
    sha256: str

    @classmethod
    def from_file(cls, path: Path, name: str | None = None) -> "OutputSchema":
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a JSON object schema")
        return cls(
            name=name or path.stem,
            schema=data,
            sha256=hashlib.sha256(raw).hexdigest(),
        )


@dataclass(frozen=True)
class GenerationRequest:
    system_prompt: str
    user_prompt: str
    task_id: str
    model_key: str
    repeat_index: int
    decoding_profile_id: str
    output_schema: OutputSchema | None = None


@dataclass(frozen=True)
class GenerationResult:
    text: str
    finish_reason: str
    usage: Usage
    served_model_id: str
    request_echo: RequestEcho
    private_metadata: PrivateProviderMetadata
