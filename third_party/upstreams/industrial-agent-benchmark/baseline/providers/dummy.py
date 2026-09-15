"""Deterministic no-network dummy provider.

Safety property (tested): the dummy answer text and all metadata are derived
ONLY from non-sensitive identifiers (task_id, model_key, repeat_index). The
system prompt and user prompt bodies are never echoed, logged, or reflected
into outputs or metadata.
"""
from __future__ import annotations

import hashlib
from typing import Mapping

from ..profiles import DecodingProfile
from ..types import (
    GenerationRequest,
    GenerationResult,
    PrivateProviderMetadata,
    RequestEcho,
    Usage,
)
from .base import ProviderPermanentError, ProviderTransientError


class BaselineDummyProvider:
    """Deterministic plumbing-test provider.

    ``fail_plan`` optionally maps task_id -> "transient" | "permanent" to
    exercise the runner's retry / missing classification in tests. Transient
    failures raise on every attempt (so retries exhaust deterministically).
    """

    provider_kind = "dummy"
    api_kind = "dummy"

    def __init__(
        self,
        model_id: str,
        profile: DecodingProfile,
        profile_set_hash: str,
        fail_plan: Mapping[str, str] | None = None,
    ) -> None:
        self.model_id = model_id
        self.profile = profile
        self.profile_set_hash = profile_set_hash
        self.fail_plan = dict(fail_plan or {})

    def generate(self, request: GenerationRequest) -> GenerationResult:
        mode = self.fail_plan.get(request.task_id)
        if mode == "transient":
            raise ProviderTransientError(
                f"injected transient failure for {request.task_id}"
            )
        if mode == "permanent":
            raise ProviderPermanentError(
                f"injected permanent failure for {request.task_id}"
            )
        # Deterministic text from non-sensitive identifiers only; the prompt
        # bodies are deliberately not consulted.
        seed = f"{request.task_id}:{request.model_key}:{request.repeat_index}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        text = (
            "ダミー回答(配管検証用・ベンチマーク結果ではありません)。 "
            f"identifier={seed} digest={digest[:16]}"
        )
        echo = RequestEcho(
            provider_kind=self.provider_kind,
            api_kind=self.api_kind,
            model_id=self.model_id,
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
            finish_reason="stop",
            usage=Usage(input_tokens="unknown", output_tokens="unknown"),
            served_model_id=self.model_id,
            request_echo=echo,
            private_metadata=PrivateProviderMetadata(),
        )
