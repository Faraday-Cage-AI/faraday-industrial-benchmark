from faraday_industrial_benchmark.agents import NoopAgent, OracleAgent, ReadOnlyAgent, UnsafeAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner


TASKS = load_tasks(DEFAULT_TASKS)


def test_reference_oracle_strictly_passes_every_public_task():
    run = BenchmarkRunner().run_suite(TASKS, OracleAgent())
    assert run["summary"]["mean_score"] == 100.0
    assert run["summary"]["strict_successes"] == len(TASKS)
    assert run["summary"]["critical_failures"] == 0
    assert run["summary"]["families"] == 31
    assert len(run["family_summaries"]) == 31
    assert all(summary["mean_score"] == 100.0 for summary in run["family_summaries"].values())
    assert run["capability_summaries"]
    assert all(summary["attainment_rate"] == 1.0 for summary in run["capability_summaries"].values())


def test_stability_report_requires_repeatable_success():
    runner = BenchmarkRunner()
    report = runner.run_stability(TASKS[:2], OracleAgent(), attempts=3)
    assert report["summary"]["runs"] == 6
    assert report["summary"]["strict_run_rate"] == 1.0
    assert report["summary"]["all_attempts_strict_rate"] == 1.0
    assert report["summary"]["score_stddev"] == 0.0


def test_negative_controls_have_diagnostic_range():
    runner = BenchmarkRunner()
    noop = runner.run_suite(TASKS, NoopAgent())
    read_only = runner.run_suite(TASKS, ReadOnlyAgent())
    unsafe = runner.run_suite(TASKS, UnsafeAgent())
    assert noop["summary"]["mean_score"] < 20
    assert noop["summary"]["mean_score"] < read_only["summary"]["mean_score"] < 30
    assert unsafe["summary"]["mean_score"] == 0
    assert unsafe["summary"]["critical_failures"] == len(TASKS)


def test_scores_are_identical_across_repeated_runs():
    runner = BenchmarkRunner()
    first = runner.run_suite(TASKS, OracleAgent())
    second = runner.run_suite(TASKS, OracleAgent())
    assert first["summary"] == second["summary"]
    assert [result["final_state_hash"] for result in first["results"]] == [
        result["final_state_hash"] for result in second["results"]
    ]
