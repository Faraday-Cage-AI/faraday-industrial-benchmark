"""Model config loading: secrets rejection, unknown rule, non_runnable templates."""
from __future__ import annotations

from pathlib import Path

import pytest

from baseline.config import (
    ConfigError,
    NonRunnableConfigError,
    load_models_config,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "baseline"
MODELS = FIXTURES / "models_dummy.yaml"
TEMPLATE = ROOT / "experiments" / "baseline_v2_2_0" / "models.template.yaml"


def test_load_dummy_models_config():
    cfg = load_models_config(MODELS)
    assert [m.model_key for m in cfg.models] == ["model_dummy_a", "model_dummy_b"]
    model = cfg.models[0]
    assert model.provider_kind == "dummy"
    assert model.release_date == "unknown"
    assert model.api_key_env is None


def test_non_runnable_template_is_rejected_for_execution():
    assert TEMPLATE.exists(), "template must exist as documentation"
    with pytest.raises(NonRunnableConfigError, match="non_runnable"):
        load_models_config(TEMPLATE, for_execution=True)


def test_non_runnable_template_is_loadable_for_inspection():
    cfg = load_models_config(TEMPLATE, for_execution=False)
    assert cfg.models[0].public_model_id == "to-be-decided-after-phase-2c"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(body, encoding="utf-8")
    return path


_VALID_ENTRY = """\
    public_model_id: m
    provider_kind: dummy
    api_kind: dummy
    decoding_profile_id: p
    snapshot: unknown
    access_path: local_dummy
    release_date: unknown
    training_cutoff: unknown
"""


def test_credential_shaped_literal_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        "models:\n  - model_key: a\n" + _VALID_ENTRY + "    note: sk-abcdefghijklmnop1234\n",
    )
    with pytest.raises(ConfigError, match="credential-shaped"):
        load_models_config(path)


def test_direct_api_key_key_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        "models:\n  - model_key: a\n" + _VALID_ENTRY + "    api_key: not-even-secret-shaped\n",
    )
    with pytest.raises(ConfigError, match="api_key"):
        load_models_config(path)


def test_env_reference_must_be_env_var_name(tmp_path):
    path = _write(
        tmp_path,
        "models:\n  - model_key: a\n" + _VALID_ENTRY + "    api_key_env: lowercase-name\n",
    )
    with pytest.raises(ConfigError, match="environment variable NAME"):
        load_models_config(path)


def test_valid_env_reference_is_accepted(tmp_path):
    path = _write(
        tmp_path,
        "models:\n  - model_key: a\n" + _VALID_ENTRY + "    api_key_env: EXAMPLE_KEY_ENV\n",
    )
    cfg = load_models_config(path)
    assert cfg.models[0].api_key_env == "EXAMPLE_KEY_ENV"


def test_missing_metadata_must_be_literal_unknown(tmp_path):
    body = "models:\n  - model_key: a\n" + _VALID_ENTRY.replace(
        "    release_date: unknown\n", ""
    )
    path = _write(tmp_path, body)
    with pytest.raises(ConfigError, match='release_date.*unknown'):
        load_models_config(path)


def test_null_metadata_is_rejected(tmp_path):
    body = "models:\n  - model_key: a\n" + _VALID_ENTRY.replace(
        "release_date: unknown", "release_date: null"
    )
    path = _write(tmp_path, body)
    with pytest.raises(ConfigError, match="release_date"):
        load_models_config(path)


def test_duplicate_model_keys_are_rejected(tmp_path):
    entry = "  - model_key: a\n" + _VALID_ENTRY
    path = _write(tmp_path, "models:\n" + entry + entry)
    with pytest.raises(ConfigError, match="duplicate model_key"):
        load_models_config(path)


def test_unknown_provider_kind_is_rejected(tmp_path):
    body = "models:\n  - model_key: a\n" + _VALID_ENTRY.replace(
        "provider_kind: dummy", "provider_kind: mystery"
    )
    path = _write(tmp_path, body)
    with pytest.raises(ConfigError, match="provider_kind"):
        load_models_config(path)


def test_empty_models_list_is_rejected(tmp_path):
    path = _write(tmp_path, "models: []\n")
    with pytest.raises(ConfigError, match="non-empty"):
        load_models_config(path)
