"""Model configuration loading for baseline runs.

Rules implemented here (Phase 2A scope):

- Public config files never contain credentials; credentials are referenced
  only indirectly via environment-variable *names* in ``*_env`` keys.
  A defensive scan rejects any credential-shaped literal in the file.
- Metadata that is not ascertainable is the literal string ``"unknown"``
  (baseline_manifest_spec_v1.md Section 4) — never null or omitted.
- Config files marked ``non_runnable: true`` (templates for future real-model
  configs) are rejected at load-for-execution time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .profiles import KNOWN_API_KINDS, KNOWN_PROVIDER_KINDS
from .redaction import SECRET_VALUE_RE

ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Fields that must be present on every model entry; string fields may be the
# literal "unknown" but must not be null or missing.
REQUIRED_MODEL_FIELDS = (
    "model_key",
    "public_model_id",
    "provider_kind",
    "api_kind",
    "decoding_profile_id",
    "snapshot",
    "access_path",
    "release_date",
    "training_cutoff",
)

# Key names whose values must be environment-variable names, never secrets.
_ENV_KEY_SUFFIX = "_env"
_SECRETLIKE_KEYS = frozenset({"api_key", "token", "secret", "authorization", "password"})


class ConfigError(ValueError):
    """A baseline model config file is invalid."""


class NonRunnableConfigError(ConfigError):
    """The config is a non-runnable template and must not be executed."""


@dataclass(frozen=True)
class ModelConfig:
    model_key: str
    public_model_id: str
    provider_kind: str
    api_kind: str
    decoding_profile_id: str
    snapshot: str
    access_path: str
    release_date: str
    training_cutoff: str
    api_key_env: str | None
    base_url_env: str | None
    # Hosted-OSS serving-side model identifier (request "model" field) when it
    # differs from the public HF model ID; None means public_model_id is used.
    hosted_model_id: str | None = None


@dataclass(frozen=True)
class ModelsConfig:
    models: tuple[ModelConfig, ...]
    source_path: Path


def load_models_config(path: Path, *, for_execution: bool = True) -> ModelsConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")
    _reject_secret_literals(data, path=str(path))
    if for_execution and bool(data.get("non_runnable", False)):
        raise NonRunnableConfigError(
            f"{path} is marked non_runnable (template). Runnable real-model configs "
            "are created only after the Phase 2C Go decision."
        )
    raw_models = data.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ConfigError(f"{path} must define a non-empty 'models' list")
    models = tuple(_parse_model(entry, path) for entry in raw_models)
    keys = [m.model_key for m in models]
    if len(keys) != len(set(keys)):
        raise ConfigError(f"{path}: duplicate model_key entries")
    return ModelsConfig(models=models, source_path=path)


def _parse_model(entry: Any, path: Path) -> ModelConfig:
    if not isinstance(entry, dict):
        raise ConfigError(f"{path}: each models[] entry must be a mapping")
    for field_name in REQUIRED_MODEL_FIELDS:
        value = entry.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ConfigError(
                f"{path}: model entry missing required field {field_name!r} "
                '(use the literal string "unknown" if not ascertainable)'
            )
    provider_kind = str(entry["provider_kind"])
    if provider_kind not in KNOWN_PROVIDER_KINDS:
        raise ConfigError(f"{path}: unknown provider_kind {provider_kind!r}")
    api_kind = str(entry["api_kind"])
    if api_kind not in KNOWN_API_KINDS:
        raise ConfigError(f"{path}: unknown api_kind {api_kind!r}")
    api_key_env = _parse_env_name(entry.get("api_key_env"), "api_key_env", path)
    base_url_env = _parse_env_name(entry.get("base_url_env"), "base_url_env", path)
    return ModelConfig(
        model_key=str(entry["model_key"]),
        public_model_id=str(entry["public_model_id"]),
        provider_kind=provider_kind,
        api_kind=api_kind,
        decoding_profile_id=str(entry["decoding_profile_id"]),
        snapshot=str(entry["snapshot"]),
        access_path=str(entry["access_path"]),
        release_date=str(entry["release_date"]),
        training_cutoff=str(entry["training_cutoff"]),
        api_key_env=api_key_env,
        base_url_env=base_url_env,
        hosted_model_id=(
            str(entry["hosted_model_id"]) if entry.get("hosted_model_id") else None
        ),
    )


def _parse_env_name(value: Any, key: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not ENV_NAME_RE.match(value):
        raise ConfigError(
            f"{path}: {key} must be an environment variable NAME "
            f"(e.g. OPENAI_API_KEY), got {value!r}"
        )
    return value


def _reject_secret_literals(obj: Any, *, path: str) -> None:
    """Reject credential-shaped values or direct secret keys anywhere in a
    public config file."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in _SECRETLIKE_KEYS and not key_l.endswith(_ENV_KEY_SUFFIX):
                raise ConfigError(
                    f"{path}: key {key!r} must not appear in a public config; "
                    f"use {key}_env with an environment variable name instead"
                )
            _reject_secret_literals(value, path=f"{path}.{key}")
        return
    if isinstance(obj, list):
        for i, value in enumerate(obj):
            _reject_secret_literals(value, path=f"{path}[{i}]")
        return
    if isinstance(obj, str) and SECRET_VALUE_RE.search(obj):
        raise ConfigError(f"{path}: credential-shaped literal detected")
