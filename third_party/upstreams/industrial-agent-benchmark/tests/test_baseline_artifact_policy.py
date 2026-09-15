"""Private run artifacts must live under git-ignored paths."""
from __future__ import annotations

import subprocess
from pathlib import Path

from baseline.runner import DEFAULT_OUTPUT_ROOT

ROOT = Path(__file__).resolve().parent.parent


def _is_ignored(relpath: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", relpath],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


def test_baseline_run_paths_are_git_ignored():
    assert _is_ignored("experiments/baseline_v2_2_0/runs/some-run/answers.jsonl")
    assert _is_ignored("experiments/baseline_v2_2_0/runs/some-run/public/manifest.public.json")
    assert _is_ignored("experiments/other_experiment/runs/x/file.txt")


def test_default_output_root_is_inside_ignored_runs_dir():
    rel = DEFAULT_OUTPUT_ROOT.relative_to(ROOT).as_posix()
    assert rel == "experiments/baseline_v2_2_0/runs"
    assert _is_ignored(f"{rel}/probe.txt")


def test_template_config_is_not_ignored():
    # The non-runnable template is documentation and must stay committable.
    assert not _is_ignored("experiments/baseline_v2_2_0/models.template.yaml")
