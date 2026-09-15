"""Decoding profile loading and validation.

Phase 2A scope: the dummy profile is the only runnable profile. Profiles for
real providers may exist as templates but must carry ``non_runnable: true``
and are rejected at execution time. Detailed per-provider validation
(Anthropic forbidden sampling keys, OpenAI reasoning settings, ...) is
Phase 2B.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

KNOWN_PROVIDER_KINDS = frozenset(
    {"dummy", "openai", "anthropic", "openai_compatible", "gemini"}
)
KNOWN_API_KINDS = frozenset({"dummy", "responses", "messages", "chat_completions"})

# Provider kinds runnable in Phase 2A.
RUNNABLE_PROVIDER_KINDS = frozenset({"dummy"})


class ProfileError(ValueError):
    """A decoding profile file is invalid."""


class NonRunnableProfileError(ProfileError):
    """The profile exists but must not be executed in this phase."""


@dataclass(frozen=True)
class DecodingProfile:
    profile_id: str
    provider_kind: str
    api_kind: str
    non_runnable: bool
    max_output_tokens: int
    params_sent: dict[str, Any]
    params_not_sent: tuple[str, ...]
    max_retries: int
    backoff_base_seconds: float
    retry_policy_summary: str
    # Provider-specific structured setting blocks (e.g. Gemini thinking_config),
    # passed only through the per-provider allowlist — never a raw extra_body.
    provider_extras: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.provider_extras is None:
            object.__setattr__(self, "provider_extras", {})


@dataclass(frozen=True)
class ProfileSet:
    profiles: dict[str, DecodingProfile]
    file_sha256: str

    def get_runnable(self, profile_id: str) -> DecodingProfile:
        profile = self.get(profile_id)
        if profile.non_runnable:
            raise NonRunnableProfileError(
                f"profile {profile_id!r} is marked non_runnable and cannot be executed"
            )
        if profile.provider_kind not in RUNNABLE_PROVIDER_KINDS:
            raise NonRunnableProfileError(
                f"profile {profile_id!r} targets provider_kind "
                f"{profile.provider_kind!r}, which is not runnable in this phase "
                f"(runnable: {sorted(RUNNABLE_PROVIDER_KINDS)})"
            )
        return profile

    def get(self, profile_id: str) -> DecodingProfile:
        if profile_id not in self.profiles:
            raise ProfileError(f"unknown decoding profile: {profile_id!r}")
        return self.profiles[profile_id]


def load_profiles(path: Path) -> ProfileSet:
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes)
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ProfileError(f"{path} must contain a mapping with a 'profiles' mapping")
    profiles: dict[str, DecodingProfile] = {}
    for profile_id, body in data["profiles"].items():
        profiles[str(profile_id)] = _parse_profile(str(profile_id), body, path)
    if not profiles:
        raise ProfileError(f"{path} defines no profiles")
    return ProfileSet(profiles=profiles, file_sha256=hashlib.sha256(raw_bytes).hexdigest())


def _parse_profile(profile_id: str, body: Any, path: Path) -> DecodingProfile:
    if not isinstance(body, dict):
        raise ProfileError(f"profile {profile_id!r} in {path} must be a mapping")
    provider_kind = str(body.get("provider_kind", ""))
    if provider_kind not in KNOWN_PROVIDER_KINDS:
        raise ProfileError(
            f"profile {profile_id!r}: unknown provider_kind {provider_kind!r}"
        )
    api_kind = str(body.get("api_kind", ""))
    if api_kind not in KNOWN_API_KINDS:
        raise ProfileError(f"profile {profile_id!r}: unknown api_kind {api_kind!r}")
    non_runnable = bool(body.get("non_runnable", False))
    max_output_tokens = body.get("max_output_tokens")
    if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool) or max_output_tokens <= 0:
        raise ProfileError(
            f"profile {profile_id!r}: max_output_tokens must be a positive integer"
        )
    params_sent = body.get("params_sent", {})
    if not isinstance(params_sent, dict):
        raise ProfileError(f"profile {profile_id!r}: params_sent must be a mapping")
    params_not_sent = body.get("params_not_sent", [])
    if not isinstance(params_not_sent, list) or not all(
        isinstance(p, str) for p in params_not_sent
    ):
        raise ProfileError(
            f"profile {profile_id!r}: params_not_sent must be a list of strings"
        )
    max_retries = body.get("max_retries", 2)
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
        raise ProfileError(f"profile {profile_id!r}: max_retries must be an integer >= 0")
    backoff_base_seconds = float(body.get("backoff_base_seconds", 0.0))
    retry_policy_summary = str(
        body.get(
            "retry_policy_summary",
            f"max_retries={max_retries}, exponential backoff base={backoff_base_seconds}s",
        )
    )
    provider_extras = body.get("provider_extras", {})
    if not isinstance(provider_extras, dict):
        raise ProfileError(f"profile {profile_id!r}: provider_extras must be a mapping")
    return DecodingProfile(
        profile_id=profile_id,
        provider_kind=provider_kind,
        api_kind=api_kind,
        non_runnable=non_runnable,
        max_output_tokens=max_output_tokens,
        params_sent=dict(params_sent),
        params_not_sent=tuple(params_not_sent),
        max_retries=max_retries,
        backoff_base_seconds=backoff_base_seconds,
        retry_policy_summary=retry_policy_summary,
        provider_extras=dict(provider_extras),
    )


# ---------------------------------------------------------------------------
# Per-provider profile validation (Phase 2B)
# ---------------------------------------------------------------------------

# Sampling parameters that must never be sent to the Anthropic Messages API
# under this baseline (baseline_experiment_plan_v1.md §4a.3).
ANTHROPIC_FORBIDDEN_PARAMS = frozenset(
    {"temperature", "top_p", "top_k", "budget_tokens", "max_thinking_tokens"}
)
ANTHROPIC_REQUIRED_NOT_SENT = ("temperature", "top_p", "top_k")

# Allowed params_sent keys per provider kind. For openai_compatible,
# ``reasoning_effort`` exists for the Gemini OpenAI-compatibility endpoint
# (official mapping to Gemini thinking levels); it is mutually exclusive with
# sampling params and with google_thinking_config (see validation below).
_ALLOWED_PARAMS_BY_KIND = {
    "dummy": frozenset(),
    "openai": frozenset({"reasoning_effort"}),
    "anthropic": frozenset({"thinking", "effort"}),
    "openai_compatible": frozenset({"temperature", "top_p", "seed", "reasoning_effort"}),
    "gemini": frozenset(),  # native provider profile rules pend the Go/No-Go
}

# Provider-specific extra blocks allowed per provider kind. This is the ONLY
# path for provider-specific settings; a raw extra_body passthrough does not
# exist. google_thinking_config is a FUTURE option (not used by the first
# pilot's Gemini profile, which is reasoning_effort-only); on the wire it maps
# to extra_body.google.thinking_config (see OpenAICompatibleProvider).
_ALLOWED_EXTRAS_BY_KIND = {
    "dummy": frozenset(),
    "openai": frozenset(),
    "anthropic": frozenset(),
    "openai_compatible": frozenset({"google_thinking_config"}),
    "gemini": frozenset(),
}

# Extras must stay small enough to be echoed as a compact JSON string in
# request_echo.params_sent (redaction limit: 80 chars).
MAX_EXTRA_ECHO_LEN = 80

# Key-name fragments that must never appear anywhere inside provider_extras
# (credentials / endpoints belong in environment variables, never profiles).
_FORBIDDEN_EXTRA_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "credential",
    "password",
    "header",
    "endpoint",
    "url",
)

# Recursive allowlist for the google_thinking_config block: a flat mapping
# whose keys and value types are pinned here. Anything else — unknown nested
# keys, nested mappings, arbitrary dict passthrough — is rejected at profile
# load. thinking_level is rejected explicitly (not supported for the
# gemini-2.5-pro baseline; use thinking_budget). include_thoughts: true is
# forbidden for baseline profiles (thought summaries must never enter run
# artifacts destined for publication paths).
GOOGLE_THINKING_CONFIG_ALLOWED_KEYS: dict[str, tuple[type, ...]] = {
    "thinking_budget": (int,),
    "include_thoughts": (bool,),
}


def _validate_extra_key_name(profile_id: str, path: str, key: str) -> None:
    key_l = key.lower()
    for fragment in _FORBIDDEN_EXTRA_KEY_FRAGMENTS:
        if fragment in key_l:
            raise ProfileError(
                f"profile {profile_id!r}: forbidden key name {key!r} at {path} "
                "(credential/endpoint-like keys are never allowed in provider_extras)"
            )


def _validate_google_thinking_config(profile_id: str, value: Any) -> None:
    if not isinstance(value, dict):
        raise ProfileError(
            f"profile {profile_id!r}: google_thinking_config must be a mapping of "
            "allowlisted settings, not an arbitrary value"
        )
    for key, item in value.items():
        key_name = str(key)
        if key_name == "thinking_level":
            raise ProfileError(
                f"profile {profile_id!r}: thinking_level is not supported for "
                "gemini-2.5-pro baseline profiles; use thinking_budget"
            )
        _validate_extra_key_name(
            profile_id, f"provider_extras.google_thinking_config.{key_name}", key_name
        )
        allowed_types = GOOGLE_THINKING_CONFIG_ALLOWED_KEYS.get(key_name)
        if allowed_types is None:
            raise ProfileError(
                f"profile {profile_id!r}: unknown google_thinking_config key "
                f"{key_name!r} (allowed: {sorted(GOOGLE_THINKING_CONFIG_ALLOWED_KEYS)})"
            )
        if isinstance(item, bool) and bool not in allowed_types:
            raise ProfileError(
                f"profile {profile_id!r}: google_thinking_config.{key_name} has "
                f"invalid type bool"
            )
        if not isinstance(item, allowed_types):
            raise ProfileError(
                f"profile {profile_id!r}: google_thinking_config.{key_name} must be "
                f"of type {'/'.join(t.__name__ for t in allowed_types)}"
            )
        if key_name == "thinking_budget" and item < 0:
            raise ProfileError(
                f"profile {profile_id!r}: thinking_budget must be >= 0"
            )
        if key_name == "include_thoughts" and item is True:
            raise ProfileError(
                f"profile {profile_id!r}: include_thoughts: true is forbidden for "
                "baseline profiles (thought summaries must stay out of run artifacts)"
            )


def validate_profile_for_provider(profile: DecodingProfile) -> None:
    """Enforce provider-kind decoding rules on a profile.

    Called by every real provider adapter at construction time; profile files
    that violate the frozen decoding policy fail before any request is built.
    """
    kind = profile.provider_kind
    allowed_params = _ALLOWED_PARAMS_BY_KIND.get(kind, frozenset())
    sent_keys = set(profile.params_sent)
    extra_keys = set(profile.provider_extras)

    unexpected = sent_keys - allowed_params
    if unexpected:
        raise ProfileError(
            f"profile {profile.profile_id!r}: params_sent keys not allowed for "
            f"provider_kind {kind!r}: {sorted(unexpected)}"
        )
    allowed_extras = _ALLOWED_EXTRAS_BY_KIND.get(kind, frozenset())
    unexpected_extras = extra_keys - allowed_extras
    if unexpected_extras:
        raise ProfileError(
            f"profile {profile.profile_id!r}: provider_extras keys not allowed for "
            f"provider_kind {kind!r}: {sorted(unexpected_extras)} "
            "(raw extra_body passthrough is prohibited)"
        )

    if kind == "anthropic":
        forbidden = (sent_keys | extra_keys) & ANTHROPIC_FORBIDDEN_PARAMS
        if forbidden:
            raise ProfileError(
                f"profile {profile.profile_id!r}: forbidden Anthropic parameters "
                f"present: {sorted(forbidden)}"
            )
        thinking = profile.params_sent.get("thinking")
        if thinking is not None and thinking != "adaptive":
            raise ProfileError(
                f"profile {profile.profile_id!r}: Anthropic thinking must be "
                f"'adaptive' when set, got {thinking!r}"
            )
        missing_not_sent = set(ANTHROPIC_REQUIRED_NOT_SENT) - set(profile.params_not_sent)
        if missing_not_sent:
            raise ProfileError(
                f"profile {profile.profile_id!r}: params_not_sent must include "
                f"{sorted(missing_not_sent)} for Anthropic profiles"
            )

    if kind == "openai_compatible":
        has_reasoning = "reasoning_effort" in profile.params_sent
        # Gemini-compat profiles use reasoning_effort ONLY (official mapping to
        # thinking levels); it must not coexist with sampling params or with
        # google_thinking_config (reasoning_effort and thinking_budget /
        # thinking_level cannot be combined).
        if has_reasoning:
            others = set(profile.params_sent) - {"reasoning_effort"}
            if others:
                raise ProfileError(
                    f"profile {profile.profile_id!r}: reasoning_effort must not be "
                    f"combined with {sorted(others)} in an openai_compatible profile"
                )
            if "google_thinking_config" in profile.provider_extras:
                raise ProfileError(
                    f"profile {profile.profile_id!r}: reasoning_effort and "
                    "google_thinking_config are mutually exclusive"
                )
        if "temperature" in profile.params_sent and profile.params_sent["temperature"] != 0:
            raise ProfileError(
                f"profile {profile.profile_id!r}: openai_compatible profiles must "
                "pin temperature to 0"
            )
        if "top_p" in profile.params_sent and profile.params_sent["top_p"] != 1:
            raise ProfileError(
                f"profile {profile.profile_id!r}: openai_compatible profiles must "
                "pin top_p to 1"
            )
        for key, value in profile.provider_extras.items():
            key_name = str(key)
            _validate_extra_key_name(
                profile.profile_id, f"provider_extras.{key_name}", key_name
            )
            if key_name == "google_thinking_config":
                _validate_google_thinking_config(profile.profile_id, value)
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded) > MAX_EXTRA_ECHO_LEN:
                raise ProfileError(
                    f"profile {profile.profile_id!r}: provider_extras[{key!r}] too "
                    f"large to echo (>{MAX_EXTRA_ECHO_LEN} chars as JSON)"
                )
