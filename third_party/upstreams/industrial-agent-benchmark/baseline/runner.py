"""Answer-generation runner for the baseline pipeline (Phase 2A: dummy only).

Output layout (all under an ignored private run directory by default):

    <output_root>/<run_id>/
        answers.jsonl        # private: full answer texts + per-row status
        prompts.jsonl        # private: rendered prompt bodies
        summary.json         # private: status counts, missing rates
        public/manifest.public.json   # validated public manifest

The public manifest is validated against baseline_manifest_spec_v1 and
scanned against the actual prompt/answer texts of the run before writing.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .config import ModelConfig, ModelsConfig, load_models_config
from .manifest import (
    build_model_entry,
    build_public_manifest,
    sha256_of_file,
    utc_now_iso,
    write_public_manifest,
)
from .profiles import DecodingProfile, ProfileSet, load_profiles
from .providers import create_provider
from .providers.base import (
    Provider,
    ProviderPermanentError,
    ProviderTransientError,
)
from .redaction import public_request_echo
from .types import GenerationRequest, RequestEcho, ResultStatus

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVALUATION_SET = ROOT / "evaluation_set_v2.yaml"
DEFAULT_INDEX = ROOT / "benchmark_data" / "index.yaml"
DEFAULT_TEST_JSONL = ROOT / "data" / "v2" / "test.jsonl"
DEFAULT_OUTPUT_ROOT = ROOT / "experiments" / "baseline_v2_2_0" / "runs"

BENCHMARK_RELEASE_VERSION = "v2.2.0"
EXPERIMENT_PLAN_VERSION = "baseline_experiment_plan_v1"
CONTAMINATION_POLICY_VERSION = "contamination_policy_v1"
# Draft template identifiers; frozen (renamed without "_draft") at protocol
# freeze before any official baseline run.
ANSWER_PROMPT_TEMPLATE_VERSION = "baseline_answer_prompt_v1_draft"
ANSWER_SYSTEM_PROMPT_VERSION = "baseline_answer_system_prompt_v1_draft"

SYSTEM_PROMPT = (
    "You are answering Industrial Agent Benchmark tasks. "
    "Answer in Japanese. If the question requests JSON, return valid JSON only when possible."
)

# Terms that must never leak from rubrics/reference answers into prompts.
PROMPT_FORBIDDEN_TERMS = (
    "reference_answer",
    "evaluation_rubric",
    "must_have",
    "nice_to_have",
    "critical_failures",
    "score_cap_rules",
    "numeric_checks",
    "disallowed_answers",
    "expected_value",
)


class RunnerError(RuntimeError):
    """Fatal, non-per-row runner failure."""


@dataclass
class RowResult:
    model_key: str
    public_model_id: str
    provider_kind: str
    task_id: str
    repeat_index: int
    status: ResultStatus
    answer_text: str
    finish_reason: str
    input_tokens: int | str
    output_tokens: int | str
    error: str
    attempts: int
    started_at: str
    finished_at: str
    latency_seconds: float


@dataclass
class StatusSummary:
    total: int = 0
    completed: int = 0
    missing_retry_exhausted: int = 0
    missing_permanent: int = 0

    @property
    def missing(self) -> int:
        return self.missing_retry_exhausted + self.missing_permanent

    @property
    def missing_rate(self) -> float:
        return round(self.missing / self.total, 6) if self.total else 0.0

    def add(self, status: ResultStatus) -> None:
        self.total += 1
        if status is ResultStatus.COMPLETED:
            self.completed += 1
        elif status is ResultStatus.MISSING_RETRY_EXHAUSTED:
            self.missing_retry_exhausted += 1
        elif status is ResultStatus.MISSING_PERMANENT:
            self.missing_permanent += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "missing_retry_exhausted": self.missing_retry_exhausted,
            "missing_permanent": self.missing_permanent,
            "missing": self.missing,
            "missing_rate": self.missing_rate,
        }


@dataclass
class RunSummary:
    """Aggregation consumed later by the pilot gate (Phase 2B)."""

    overall: StatusSummary = field(default_factory=StatusSummary)
    by_model: dict[str, StatusSummary] = field(default_factory=dict)
    by_provider: dict[str, StatusSummary] = field(default_factory=dict)
    prompt_leakage_count: int = 0

    def add(self, row: RowResult) -> None:
        self.overall.add(row.status)
        self.by_model.setdefault(row.model_key, StatusSummary()).add(row.status)
        self.by_provider.setdefault(row.provider_kind, StatusSummary()).add(row.status)

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.as_dict(),
            "by_model": {k: v.as_dict() for k, v in sorted(self.by_model.items())},
            "by_provider": {k: v.as_dict() for k, v in sorted(self.by_provider.items())},
            "prompt_leakage_count": self.prompt_leakage_count,
        }


def summarize_rows(rows: list[RowResult]) -> RunSummary:
    summary = RunSummary()
    for row in rows:
        summary.add(row)
    return summary


def render_answer_prompt(problem: dict[str, Any]) -> str:
    metadata = {
        "question_id": problem.get("id", ""),
        "layer": problem.get("layer", ""),
        "category": problem.get("category", ""),
        "domain": problem.get("domain", ""),
        "subdomain": problem.get("subdomain", ""),
        "difficulty": problem.get("difficulty", ""),
        "estimated_time_min": problem.get("estimated_time_min", ""),
        "title": problem.get("title", ""),
    }
    metadata_yaml = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip()
    scenario = str(problem.get("scenario", "")).strip()
    question = str(problem.get("question", "")).strip()
    return (
        "# Industrial Agent Benchmark Baseline Answer Prompt\n\n"
        "## Question Metadata\n\n"
        "```yaml\n"
        f"{metadata_yaml}\n"
        "```\n\n"
        "## Scenario\n\n"
        "```text\n"
        f"{scenario}\n"
        "```\n\n"
        "## Question\n\n"
        "```text\n"
        f"{question}\n"
        "```\n"
    )


def check_prompt_leakage(prompt: str) -> list[str]:
    lowered = prompt.lower()
    return [term for term in PROMPT_FORBIDDEN_TERMS if term in lowered]


def load_questions(evaluation_set: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(evaluation_set.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise RunnerError(f"{evaluation_set} must contain a 'questions' list")
    return data["questions"]


def _load_problems(
    questions: list[dict[str, Any]], index_path: Path
) -> dict[str, dict[str, Any]]:
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    items = {str(i["id"]): i for i in index.get("items", []) if isinstance(i, dict)}
    problems: dict[str, dict[str, Any]] = {}
    for q in questions:
        task_id = str(q["id"])
        if task_id not in items:
            raise RunnerError(f"task {task_id} not found in {index_path}")
        problem_path = index_path.parent.parent / str(items[task_id]["file_path"])
        problems[task_id] = yaml.safe_load(problem_path.read_text(encoding="utf-8"))
    return problems


def _generate_with_retry(
    provider: Provider,
    request: GenerationRequest,
    profile: DecodingProfile,
    *,
    sleep=time.sleep,
) -> tuple[Any, ResultStatus, str, int]:
    """Returns (result_or_None, status, error_message, attempts)."""
    attempts = 0
    last_error = ""
    for attempt in range(profile.max_retries + 1):
        attempts += 1
        try:
            return provider.generate(request), ResultStatus.COMPLETED, "", attempts
        except ProviderPermanentError as exc:
            return None, ResultStatus.MISSING_PERMANENT, f"{type(exc).__name__}: {exc}", attempts
        except ProviderTransientError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < profile.max_retries and profile.backoff_base_seconds > 0:
                sleep(profile.backoff_base_seconds * (2**attempt))
    return None, ResultStatus.MISSING_RETRY_EXHAUSTED, last_error, attempts


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        commit = out.stdout.strip()
        return commit if out.returncode == 0 and commit else "unknown"
    except OSError:
        return "unknown"


def _echo_from_profile(model: ModelConfig, profile: DecodingProfile, profile_hash: str) -> RequestEcho:
    """Fallback request_echo when a model produced no completed row."""
    return RequestEcho(
        provider_kind=model.provider_kind,
        api_kind=model.api_kind,
        model_id=model.public_model_id,
        decoding_profile_id=profile.profile_id,
        decoding_profile_hash=profile_hash,
        params_sent=dict(profile.params_sent),
        params_not_sent=tuple(profile.params_not_sent),
        max_output_tokens=profile.max_output_tokens,
        structured_output_enabled=False,
        schema_hash="none",
        retry_policy_summary=profile.retry_policy_summary,
    )


def run_generation(
    *,
    run_id: str,
    models_config_path: Path,
    profiles_path: Path,
    evaluation_set_path: Path = DEFAULT_EVALUATION_SET,
    index_path: Path = DEFAULT_INDEX,
    test_jsonl_path: Path = DEFAULT_TEST_JSONL,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    repeats: int = 1,
    fail_plan: Mapping[str, str] | None = None,
    sleep=time.sleep,
) -> tuple[RunSummary, Path]:
    """Run answer generation for every configured model over the evaluation
    set. Returns (summary, run_dir). Phase 2A: dummy provider only."""
    if repeats < 1:
        raise RunnerError("repeats must be >= 1")
    models_config: ModelsConfig = load_models_config(models_config_path, for_execution=True)
    profile_set: ProfileSet = load_profiles(profiles_path)
    questions = load_questions(evaluation_set_path)
    problems = _load_problems(questions, index_path)

    run_dir = output_root / run_id
    if (run_dir / "answers.jsonl").exists():
        raise RunnerError(f"{run_dir} already contains answers.jsonl; choose a new run id")
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = utc_now_iso()
    prompts: dict[str, str] = {}
    leakage_count = 0
    for task_id, problem in problems.items():
        prompt = render_answer_prompt(problem)
        leaked = check_prompt_leakage(prompt)
        if leaked:
            leakage_count += len(leaked)
        prompts[task_id] = prompt

    rows: list[RowResult] = []
    echo_by_model: dict[str, RequestEcho] = {}
    for model in models_config.models:
        profile = profile_set.get_runnable(model.decoding_profile_id)
        provider = create_provider(
            model, profile, profile_set.file_sha256, fail_plan=fail_plan
        )
        for repeat_index in range(repeats):
            for q in questions:
                task_id = str(q["id"])
                request = GenerationRequest(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompts[task_id],
                    task_id=task_id,
                    model_key=model.model_key,
                    repeat_index=repeat_index,
                    decoding_profile_id=profile.profile_id,
                )
                row_started = utc_now_iso()
                t0 = time.perf_counter()
                result, status, error, attempts = _generate_with_retry(
                    provider, request, profile, sleep=sleep
                )
                latency = round(max(0.0, time.perf_counter() - t0), 4)
                if result is not None and model.model_key not in echo_by_model:
                    echo_by_model[model.model_key] = result.request_echo
                rows.append(
                    RowResult(
                        model_key=model.model_key,
                        public_model_id=model.public_model_id,
                        provider_kind=model.provider_kind,
                        task_id=task_id,
                        repeat_index=repeat_index,
                        status=status,
                        answer_text=result.text if result is not None else "",
                        finish_reason=result.finish_reason if result is not None else "none",
                        input_tokens=result.usage.input_tokens if result is not None else "unknown",
                        output_tokens=result.usage.output_tokens if result is not None else "unknown",
                        error=error,
                        attempts=attempts,
                        started_at=row_started,
                        finished_at=utc_now_iso(),
                        latency_seconds=latency,
                    )
                )

    summary = summarize_rows(rows)
    summary.prompt_leakage_count = leakage_count

    _write_private_artifacts(run_dir, run_id, rows, prompts, summary)
    _write_manifest(
        run_dir=run_dir,
        run_id=run_id,
        started_at=started_at,
        models_config=models_config,
        models_config_path=models_config_path,
        profile_set=profile_set,
        profiles_path=profiles_path,
        test_jsonl_path=test_jsonl_path,
        evaluation_set_path=evaluation_set_path,
        question_count=len(questions),
        echo_by_model=echo_by_model,
        forbidden_texts=[*prompts.values(), *(r.answer_text for r in rows)],
    )
    return summary, run_dir


def _write_private_artifacts(
    run_dir: Path,
    run_id: str,
    rows: list[RowResult],
    prompts: dict[str, str],
    summary: RunSummary,
) -> None:
    with (run_dir / "prompts.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for task_id, prompt in prompts.items():
            f.write(
                json.dumps(
                    {"run_id": run_id, "task_id": task_id, "prompt": prompt},
                    ensure_ascii=False,
                )
                + "\n"
            )
    with (run_dir / "answers.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            record = {
                "run_id": run_id,
                "model_key": row.model_key,
                "public_model_id": row.public_model_id,
                "provider_kind": row.provider_kind,
                "task_id": row.task_id,
                "repeat_index": row.repeat_index,
                "status": row.status.value,
                "answer_text": row.answer_text,
                "finish_reason": row.finish_reason,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "error": row.error,
                "attempts": row.attempts,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "latency_seconds": row.latency_seconds,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    (run_dir / "summary.json").write_text(
        json.dumps({"run_id": run_id, **summary.as_dict()}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_manifest(
    *,
    run_dir: Path,
    run_id: str,
    started_at: str,
    models_config: ModelsConfig,
    models_config_path: Path,
    profile_set: ProfileSet,
    profiles_path: Path,
    test_jsonl_path: Path,
    evaluation_set_path: Path,
    question_count: int,
    echo_by_model: dict[str, RequestEcho],
    forbidden_texts: list[str],
) -> Path:
    run_date = started_at[:10]
    model_entries = []
    for model in models_config.models:
        profile = profile_set.get(model.decoding_profile_id)
        echo = echo_by_model.get(model.model_key) or _echo_from_profile(
            model, profile, profile_set.file_sha256
        )
        model_entries.append(
            build_model_entry(
                public_model_id=model.public_model_id,
                provider=model.provider_kind,
                snapshot=model.snapshot,
                access_path=model.access_path,
                run_date=run_date,
                release_date=model.release_date,
                training_cutoff=model.training_cutoff,
                api_type=model.api_kind,
                decoding_profile_id=profile.profile_id,
                request_echo=public_request_echo(echo),
                params_not_sent=list(profile.params_not_sent),
                max_output_tokens=profile.max_output_tokens,
            )
        )
    manifest = build_public_manifest(
        experiment_id=run_id,
        protocol={
            "experiment_plan_version": EXPERIMENT_PLAN_VERSION,
            "contamination_policy_version": CONTAMINATION_POLICY_VERSION,
            "answer_prompt_template_version": ANSWER_PROMPT_TEMPLATE_VERSION,
            "answer_system_prompt_version": ANSWER_SYSTEM_PROMPT_VERSION,
            "judge_prompt_template_version": "unknown",
            "scoring_rules_version": "unknown",
            "decoding_profiles_hash": profile_set.file_sha256,
            "retry_policy": "transient errors retried with exponential backoff per decoding profile; permanent errors not retried",
            "config_hashes": {
                models_config_path.name: sha256_of_file(models_config_path),
                profiles_path.name: profile_set.file_sha256,
            },
            "started_at": started_at,
        },
        dataset={
            "release_version": BENCHMARK_RELEASE_VERSION,
            "git_commit": _git_commit(),
            "test_jsonl_sha256": (
                sha256_of_file(test_jsonl_path) if test_jsonl_path.exists() else "unknown"
            ),
            "task_count": 180,
            "dev_subset": {
                "id": evaluation_set_path.name,
                "task_count": question_count,
                "role": "public development subset; pipeline verification only, scores never reported",
            },
        },
        models=model_entries,
        judge={
            "judge_model_id": "unknown",
            "provider": "unknown",
            "snapshot": "unknown",
            "run_date": "unknown",
            "family_overlap_disclosure": "unknown",
            "anonymization": "judge receives anonymized model keys only; mapping stored privately",
            "structured_output": "unknown",
            "inference_settings": "unknown",
        },
        contamination={
            "exposure_statement_version": CONTAMINATION_POLICY_VERSION,
            "ngram_overlap": "unknown",
            "self_reference_count": "unknown",
            "verbatim_reproduction_count": "unknown",
            "usage_evidence": "unknown",
        },
    )
    manifest_path = run_dir / "public" / "manifest.public.json"
    write_public_manifest(manifest, manifest_path, forbidden_texts=forbidden_texts)
    return manifest_path
