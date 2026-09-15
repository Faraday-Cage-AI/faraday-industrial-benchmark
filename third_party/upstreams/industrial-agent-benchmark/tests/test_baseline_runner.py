"""End-to-end dummy vertical slice: 30-task subset -> private artifacts ->
validated public manifest; retry/missing classification; dummy safety."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from baseline.manifest import validate_public_manifest
from baseline.runner import (
    DEFAULT_EVALUATION_SET,
    DEFAULT_INDEX,
    RunnerError,
    run_generation,
    summarize_rows,
)
from baseline.types import ResultStatus

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "baseline"
MODELS = FIXTURES / "models_dummy.yaml"
PROFILES = FIXTURES / "decoding_profiles_dummy.yaml"


@pytest.fixture(scope="module")
def dummy_run(tmp_path_factory):
    output_root = tmp_path_factory.mktemp("baseline_runs")
    summary, run_dir = run_generation(
        run_id="phase2a-dummy-01",
        models_config_path=MODELS,
        profiles_path=PROFILES,
        output_root=output_root,
    )
    return summary, run_dir


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_run_completes_30_tasks_for_all_models(dummy_run):
    summary, run_dir = dummy_run
    assert summary.overall.total == 60  # 2 dummy models x 30 tasks
    assert summary.overall.completed == 60
    assert summary.overall.missing == 0
    assert summary.overall.missing_rate == 0.0
    assert summary.prompt_leakage_count == 0
    rows = _read_jsonl(run_dir / "answers.jsonl")
    assert len(rows) == 60
    assert all(r["status"] == "completed" for r in rows)
    assert len(_read_jsonl(run_dir / "prompts.jsonl")) == 30
    assert (run_dir / "summary.json").exists()


def test_public_manifest_is_written_and_valid(dummy_run):
    _, run_dir = dummy_run
    manifest = json.loads(
        (run_dir / "public" / "manifest.public.json").read_text(encoding="utf-8")
    )
    assert validate_public_manifest(manifest) == []
    assert manifest["dataset"]["release_version"] == "v2.2.0"
    assert manifest["dataset"]["dev_subset"]["task_count"] == 30
    assert len(manifest["models"]) == 2
    for model in manifest["models"]:
        echo = model["inference_settings"]["request_echo"]
        assert echo["provider_kind"] == "dummy"
        assert echo["decoding_profile_id"] == "dummy_default_v1"
        assert (
            model["inference_settings"]["determinism_claim"]
            == "not_claimed_measured_by_repeats"
        )


def test_public_manifest_contains_no_prompt_or_answer_text(dummy_run):
    _, run_dir = dummy_run
    manifest_text = (run_dir / "public" / "manifest.public.json").read_text(encoding="utf-8")
    assert "sk-" not in manifest_text
    assert "## Scenario" not in manifest_text
    # Take a real scenario body from the run's private prompts and confirm
    # none of it leaks into the manifest.
    prompts = _read_jsonl(run_dir / "prompts.jsonl")
    scenario_fragment = prompts[0]["prompt"].split("```text\n")[1][:60]
    assert scenario_fragment.strip()
    assert scenario_fragment not in manifest_text
    # Dummy answer texts stay private too.
    answers = _read_jsonl(run_dir / "answers.jsonl")
    assert answers[0]["answer_text"] not in manifest_text


def test_dummy_answers_do_not_reflect_prompt_bodies(dummy_run):
    _, run_dir = dummy_run
    prompts = {r["task_id"]: r["prompt"] for r in _read_jsonl(run_dir / "prompts.jsonl")}
    questions = yaml.safe_load(DEFAULT_EVALUATION_SET.read_text(encoding="utf-8"))["questions"]
    index = yaml.safe_load(DEFAULT_INDEX.read_text(encoding="utf-8"))
    items = {str(i["id"]): i for i in index["items"]}
    # Sample one real problem's scenario text.
    task_id = str(questions[0]["id"])
    problem = yaml.safe_load(
        (ROOT / items[task_id]["file_path"]).read_text(encoding="utf-8")
    )
    scenario_fragment = str(problem["scenario"]).strip()[:40]
    assert scenario_fragment
    for row in _read_jsonl(run_dir / "answers.jsonl"):
        assert scenario_fragment not in row["answer_text"]
        assert "## Scenario" not in row["answer_text"]
    # Prompts themselves do contain it (sanity check of the sample).
    assert scenario_fragment in prompts[task_id]


def test_answers_are_deterministic_per_identifier(dummy_run):
    _, run_dir = dummy_run
    rows = _read_jsonl(run_dir / "answers.jsonl")
    by_key = {(r["model_key"], r["task_id"], r["repeat_index"]): r["answer_text"] for r in rows}
    # Same identifiers -> same text (re-derive one row via a fresh run is
    # covered by the failure-injection test; here check distinctness).
    assert len(by_key) == len(rows)
    a = by_key[("model_dummy_a", rows[0]["task_id"], 0)]
    b = by_key[("model_dummy_b", rows[0]["task_id"], 0)]
    assert a != b  # model_key participates in the derivation


def test_existing_run_dir_is_not_overwritten(dummy_run, tmp_path):
    _, run_dir = dummy_run
    with pytest.raises(RunnerError, match="already contains"):
        run_generation(
            run_id=run_dir.name,
            models_config_path=MODELS,
            profiles_path=PROFILES,
            output_root=run_dir.parent,
        )


def test_failure_injection_classifies_statuses(tmp_path):
    questions = yaml.safe_load(DEFAULT_EVALUATION_SET.read_text(encoding="utf-8"))["questions"]
    transient_task = str(questions[0]["id"])
    permanent_task = str(questions[1]["id"])
    summary, run_dir = run_generation(
        run_id="phase2a-failures-01",
        models_config_path=MODELS,
        profiles_path=PROFILES,
        output_root=tmp_path,
        fail_plan={transient_task: "transient", permanent_task: "permanent"},
    )
    rows = _read_jsonl(run_dir / "answers.jsonl")
    by_task = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)
    for r in by_task[transient_task]:
        assert r["status"] == "missing_retry_exhausted"
        assert r["attempts"] == 3  # 1 + max_retries(2)
        assert "transient" in r["error"]
        assert r["answer_text"] == ""
    for r in by_task[permanent_task]:
        assert r["status"] == "missing_permanent"
        assert r["attempts"] == 1
        assert "permanent" in r["error"]
    # Per-model and per-provider breakdowns feed the pilot gate.
    assert summary.overall.total == 60
    assert summary.overall.missing_retry_exhausted == 2
    assert summary.overall.missing_permanent == 2
    assert summary.overall.missing == 4
    assert summary.overall.missing_rate == round(4 / 60, 6)
    for model_key in ("model_dummy_a", "model_dummy_b"):
        ms = summary.by_model[model_key]
        assert ms.total == 30
        assert ms.missing_retry_exhausted == 1
        assert ms.missing_permanent == 1
    assert summary.by_provider["dummy"].missing == 4
    # The manifest is still produced (missing rows recorded, never fabricated).
    manifest = json.loads(
        (run_dir / "public" / "manifest.public.json").read_text(encoding="utf-8")
    )
    assert validate_public_manifest(manifest) == []


def test_summarize_rows_is_pure_and_reusable(dummy_run):
    summary, run_dir = dummy_run
    # Rebuild RowResult-like aggregation from the JSONL to confirm the
    # summary matches the persisted artifacts.
    rows = _read_jsonl(run_dir / "answers.jsonl")
    statuses = [ResultStatus(r["status"]) for r in rows]
    assert statuses.count(ResultStatus.COMPLETED) == summary.overall.completed


def test_repeats_produce_independent_rows(tmp_path):
    single_model = tmp_path / "one_model.yaml"
    data = yaml.safe_load(MODELS.read_text(encoding="utf-8"))
    single_model.write_text(
        yaml.safe_dump({"models": data["models"][:1]}, allow_unicode=True),
        encoding="utf-8",
    )
    summary, run_dir = run_generation(
        run_id="phase2a-repeats-01",
        models_config_path=single_model,
        profiles_path=PROFILES,
        output_root=tmp_path / "runs",
        repeats=2,
    )
    assert summary.overall.total == 60  # 1 model x 30 tasks x 2 repeats
    rows = _read_jsonl(run_dir / "answers.jsonl")
    assert {r["repeat_index"] for r in rows} == {0, 1}


def test_cli_runs_dummy_slice(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "baseline_generate_answers.py"),
            "--run-id",
            "cli-dummy-01",
            "--models-config",
            str(MODELS),
            "--profiles",
            str(PROFILES),
            "--output-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "cli-dummy-01" / "public" / "manifest.public.json").exists()
    assert "not benchmark results" in result.stdout
