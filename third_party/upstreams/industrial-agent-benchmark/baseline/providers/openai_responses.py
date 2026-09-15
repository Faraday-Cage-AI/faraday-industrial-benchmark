"""OpenAI Responses API adapter (gpt-5.5 evaluated / gpt-5.4 judge).

Decoding policy: baseline_experiment_plan_v1.md §4a.2 — reasoning effort
pinned from the frozen profile; the judge enforces Structured Outputs with a
strict JSON schema. ``store: false`` is always sent so provider-side request
retention is disabled.

Public/private boundary: the request body and headers exist only inside the
TransportRequest. RequestEcho carries the §3.3 allowlist; the provider
response ID goes to PrivateProviderMetadata only.
"""
from __future__ import annotations

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
from .base import raise_for_status, resolve_env

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"


class OpenAIResponsesProvider:
    provider_kind = "openai"
    api_kind = "responses"

    def __init__(
        self,
        model: ModelConfig,
        profile: DecodingProfile,
        profile_set_hash: str,
        transport: Transport,
        *,
        timeout: float = 300.0,
    ) -> None:
        if profile.provider_kind != "openai":
            raise ValueError(
                f"profile {profile.profile_id!r} is for {profile.provider_kind!r}, "
                "not 'openai'"
            )
        validate_profile_for_provider(profile)
        self.model = model
        self.profile = profile
        self.profile_set_hash = profile_set_hash
        self.transport = transport
        self.timeout = timeout
        self._api_key = resolve_env(
            model.api_key_env or DEFAULT_API_KEY_ENV, purpose="OpenAI API key"
        )
        self._base_url = (
            resolve_env(model.base_url_env, purpose="OpenAI base URL")
            if model.base_url_env
            else DEFAULT_BASE_URL
        ).rstrip("/")

    def build_body(self, request: GenerationRequest) -> dict:
        body: dict = {
            "model": self.model.public_model_id,
            "input": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_output_tokens": self.profile.max_output_tokens,
            # Provider-side storage of requests/responses is disabled.
            "store": False,
        }
        effort = self.profile.params_sent.get("reasoning_effort")
        if effort is not None:
            body["reasoning"] = {"effort": effort}
        if request.output_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.output_schema.name,
                    "schema": dict(request.output_schema.schema),
                    "strict": True,
                }
            }
        return body

    def generate(self, request: GenerationRequest) -> GenerationResult:
        body = self.build_body(request)
        response = self.transport.send(
            TransportRequest(
                url=f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                body=body,
                timeout=self.timeout,
            )
        )
        raise_for_status(response)
        data = response.body
        text = ""
        for item in data.get("output", []):
            if isinstance(item, dict) and item.get("type") == "message":
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "output_text":
                        text += str(content.get("text", ""))
        status = data.get("status", "unknown")
        if status == "completed":
            finish_reason = "stop"
        elif status == "incomplete":
            details = data.get("incomplete_details") or {}
            finish_reason = str(details.get("reason", "incomplete"))
        else:
            finish_reason = str(status)
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
            structured_output_enabled=request.output_schema is not None,
            schema_hash=(
                request.output_schema.sha256 if request.output_schema else "none"
            ),
            retry_policy_summary=self.profile.retry_policy_summary,
        )
        return GenerationResult(
            text=text,
            finish_reason=finish_reason,
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
