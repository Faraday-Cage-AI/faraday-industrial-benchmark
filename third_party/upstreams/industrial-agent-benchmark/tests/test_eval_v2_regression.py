"""Regression guard: the baseline package must not change the frozen
eval_v2_* pipeline's public symbols or CLIs."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import eval_v2_common

ROOT = Path(__file__).resolve().parent.parent


def test_frozen_public_symbols_exist():
    for name in (
        "DummyProvider",
        "FuguCompatibleProvider",
        "LLMResponse",
        "ProviderError",
        "get_provider",
        "load_evaluation_questions",
        "render_answer_prompt",
        "normalize_judgement",
    ):
        assert hasattr(eval_v2_common, name), f"eval_v2_common.{name} disappeared"


def test_frozen_version_identifiers_unchanged():
    assert eval_v2_common.BENCHMARK_RELEASE_VERSION == "v2.2.0"
    assert eval_v2_common.ANSWER_PROMPT_TEMPLATE_VERSION == "iab_v1_1_answer_prompt_v1"
    assert eval_v2_common.JUDGE_PROMPT_TEMPLATE_VERSION == "iab_v1_1_judge_v2"


def test_get_provider_contract_unchanged(monkeypatch):
    provider = eval_v2_common.get_provider("dummy", "model-x")
    assert isinstance(provider, eval_v2_common.DummyProvider)
    response = provider.generate("hello")
    assert response.provider == "dummy"
    with pytest.raises(ValueError, match="Unsupported provider"):
        eval_v2_common.get_provider("baseline", "model-x")
    # fugu still validates its env contract.
    monkeypatch.delenv("FUGU_API_KEY", raising=False)
    with pytest.raises(ValueError, match="FUGU_API_KEY"):
        eval_v2_common.FuguCompatibleProvider(model="m")


@pytest.mark.parametrize(
    "script,expected_flags",
    [
        ("eval_v2_generate_answers.py", ["--run-id", "--model-id", "--provider", "--dry-run"]),
        ("eval_v2_run_judge.py", ["--run-id", "--judge-provider", "--write-dummy-judgements"]),
        ("eval_v2_retry_failed_answers.py", ["--run-id", "--model-id", "--question-ids"]),
    ],
)
def test_frozen_cli_help_unchanged(script, expected_flags):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    for flag in expected_flags:
        assert flag in result.stdout, f"{script} lost flag {flag}"
    # Provider choices remain dummy/fugu only in the frozen pipeline.
    if script == "eval_v2_generate_answers.py":
        assert "{dummy,fugu}" in result.stdout
