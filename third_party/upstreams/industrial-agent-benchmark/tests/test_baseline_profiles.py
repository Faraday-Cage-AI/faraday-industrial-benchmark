"""Decoding profile loading, validation, and non_runnable rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from baseline.profiles import (
    NonRunnableProfileError,
    ProfileError,
    load_profiles,
)

FIXTURES = Path(__file__).parent / "fixtures" / "baseline"
PROFILES = FIXTURES / "decoding_profiles_dummy.yaml"


def test_load_fixture_profiles():
    ps = load_profiles(PROFILES)
    assert set(ps.profiles) == {"dummy_default_v1", "openai_template_v0"}
    assert len(ps.file_sha256) == 64


def test_file_hash_is_stable():
    assert load_profiles(PROFILES).file_sha256 == load_profiles(PROFILES).file_sha256


def test_dummy_profile_is_runnable():
    profile = load_profiles(PROFILES).get_runnable("dummy_default_v1")
    assert profile.provider_kind == "dummy"
    assert profile.max_retries == 2
    assert "temperature" in profile.params_not_sent


def test_non_runnable_template_profile_is_rejected_at_execution():
    ps = load_profiles(PROFILES)
    with pytest.raises(NonRunnableProfileError, match="non_runnable"):
        ps.get_runnable("openai_template_v0")
    # But it is still inspectable (for docs/validation tooling).
    assert ps.get("openai_template_v0").non_runnable is True


def test_non_dummy_provider_kinds_are_not_runnable_in_phase_2a(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(
        "profiles:\n"
        "  anthro_v0:\n"
        "    provider_kind: anthropic\n"
        "    api_kind: messages\n"
        "    max_output_tokens: 100\n",
        encoding="utf-8",
    )
    ps = load_profiles(path)
    with pytest.raises(NonRunnableProfileError, match="not runnable"):
        ps.get_runnable("anthro_v0")


def test_unknown_profile_id_raises():
    with pytest.raises(ProfileError, match="unknown decoding profile"):
        load_profiles(PROFILES).get("nope")


@pytest.mark.parametrize(
    "body,message",
    [
        ("profiles:\n  p:\n    provider_kind: mystery\n    api_kind: dummy\n    max_output_tokens: 10\n", "provider_kind"),
        ("profiles:\n  p:\n    provider_kind: dummy\n    api_kind: grpc\n    max_output_tokens: 10\n", "api_kind"),
        ("profiles:\n  p:\n    provider_kind: dummy\n    api_kind: dummy\n    max_output_tokens: 0\n", "max_output_tokens"),
        ("profiles:\n  p:\n    provider_kind: dummy\n    api_kind: dummy\n    max_output_tokens: true\n", "max_output_tokens"),
        ("profiles: {}\n", "no profiles"),
        ("[]\n", "profiles"),
    ],
)
def test_invalid_profile_files_are_rejected(tmp_path, body, message):
    path = tmp_path / "bad.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ProfileError, match=message):
        load_profiles(path)
