"""Verify completeness, frozen inputs and exact replay before publishing model results."""

import argparse
import hashlib
import json
from pathlib import Path

from faraday_industrial_benchmark.grader import grade_episode
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner, BudgetedToolClient
from faraday_industrial_benchmark.world import IndustrialWorld


def replay_budget_exit(task, episode, usage_path, measurement):
    """Reconstruct the runner's off-trace exit marker only with token-cap evidence."""
    assert usage_path.is_file(), "No usage evidence for terminal-error reconstruction"
    calls = [json.loads(line) for line in usage_path.read_text().splitlines()]
    assert (
        sum(c["usage"].get("output_tokens", 0) for c in calls) >= measurement["total_output_limit"]
    )
    expected_error = "RuntimeError: agent exited before final response (code=1)"
    return replay_terminal_marker(task, episode, expected_error)


def replay_timeout_exit(task, episode, measurement):
    """Reconstruct an episode deadline marker only with elapsed-time evidence."""
    timeout = measurement["timeout_seconds"]
    assert timeout > 0 and measurement["wall_seconds"] >= timeout
    expected_error = f"TimeoutError: agent command exceeded {timeout:g}s"
    return replay_terminal_marker(task, episode, expected_error)


def replay_terminal_marker(task, episode, expected_error):
    errors = [v for v in episode["score"]["violations"] if v["code"] == "agent_error"]
    assert len(errors) == 1 and errors[0]["message"] == expected_error
    trace = episode["trace"]
    assert trace[-1]["tool"] == "finish"
    assert trace[-1]["arguments"] == {"summary": "Agent execution failed.", "evidence": []}
    world = IndustrialWorld(task)
    client = BudgetedToolClient(world)
    for index, entry in enumerate(trace):
        if index == len(trace) - 1:
            assert world.minute == errors[0]["minute"]
            world._violation("agent_error", expected_error, critical=False)
        actual = client.call(entry["tool"], **entry["arguments"])
        assert actual == entry["result"] and world.trace[-1].state_hash == entry["state_hash"]
    return {"score": grade_episode(world).to_dict(), "final_state_hash": world.state_hash}


def audit(directory, task_path, *, selected_ids=None):
    frozen = json.loads((directory / "frozen-manifest.json").read_text())
    root = Path(__file__).resolve().parents[1]
    assert hashlib.sha256(task_path.read_bytes()).hexdigest() == frozen["tasks_sha256"]
    assert set(frozen["source_hashes"]) == {
        str(path.relative_to(root))
        for path in (root / "src/faraday_industrial_benchmark").glob("*.py")
    }, "Incomplete source freeze"
    for name, digest in frozen["source_hashes"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
    assert (
        hashlib.sha256(
            (root / frozen.get("adapter_path", "examples/openai_responses_agent.py")).read_bytes()
        ).hexdigest()
        == frozen["adapter_sha256"]
    )
    tasks = {task.id: task for task in load_tasks(task_path)}
    expected_ids = set(tasks) if selected_ids is None else set(selected_ids)
    assert expected_ids and expected_ids <= set(tasks), "Unknown or empty task selection"
    assert set(frozen["task_ids"]) == expected_ids, "Run does not cover the full supplied suite"
    assert len(frozen["task_ids"]) == len(expected_ids)
    assert frozen["models"] == ["gpt-5.4", "gpt-5.5"]
    rows = []
    runner = BenchmarkRunner()
    for model in frozen["models"]:
        for task_id in frozen["task_ids"]:
            path = directory / f"{model}-{task_id}.json"
            assert path.is_file(), f"Incomplete run: missing {path.name}"
            report = json.loads(path.read_text())
            assert not report["measurement"]["interrupted"], path.name
            assert report["measurement"]["adapter_sha256"] == frozen["adapter_sha256"]
            settings = frozen.get(
                "measurement_settings",
                {
                    "reasoning_effort": "xhigh",
                    "per_response_output_limit": 32768,
                    "total_output_limit": 100000,
                    "timeout_seconds": 1800,
                },
            )
            assert set(settings) == {
                "reasoning_effort",
                "per_response_output_limit",
                "total_output_limit",
                "timeout_seconds",
            }, "Incomplete measurement settings"
            assert settings["reasoning_effort"] == "xhigh"
            for key, value in settings.items():
                assert report["measurement"][key] == value, key
            assert len(report["results"]) == 1
            episode = report["results"][0]
            assert episode["task"]["id"] == task_id
            assert episode["task"]["version"] == tasks[task_id].version
            assert episode["agent"] == f"{model}/xhigh/tool-only"
            replay = runner.replay(tasks[task_id], episode["trace"])
            exact = replay["exact_match"]
            verification = "exact_tool_replay"
            if not exact:
                if any(
                    v["message"].startswith("TimeoutError:") for v in episode["score"]["violations"]
                ):
                    replay = replay_timeout_exit(tasks[task_id], episode, report["measurement"])
                    verification = "episode_timeout_marker_reconstructed"
                else:
                    replay = replay_budget_exit(
                        tasks[task_id],
                        episode,
                        path.with_name(path.stem + "-usage.jsonl"),
                        report["measurement"],
                    )
                    verification = "token_cap_exit_reconstructed"
            assert replay["score"] == episode["score"], (
                f"Saved score differs from replay: {path.name}"
            )
            assert replay["final_state_hash"] == episode["final_state_hash"]
            rows.append(
                {
                    "model": model,
                    "task_id": task_id,
                    "exact_replay": exact,
                    "verification": verification,
                    "score_verified": True,
                }
            )
    return {"frozen_inputs_verified": True, "episodes_verified": len(rows), "episodes": rows}


def audit_collection(directories, task_path):
    """Verify disjoint batches jointly cover the entire unchanged task manifest."""
    expected = {task.id for task in load_tasks(task_path)}
    seen, episodes = set(), []
    settings = None
    for directory in directories:
        frozen = json.loads((directory / "frozen-manifest.json").read_text())
        current_settings = frozen.get(
            "measurement_settings",
            {
                "reasoning_effort": "xhigh",
                "per_response_output_limit": 32768,
                "total_output_limit": 100000,
                "timeout_seconds": 1800,
            },
        )
        if settings is None:
            settings = current_settings
        assert settings == current_settings, "Different measurement settings across batches"
        selected = set(frozen["task_ids"])
        assert not seen & selected, "Duplicate tasks across batches"
        result = audit(directory, task_path, selected_ids=selected)
        seen.update(selected)
        episodes.extend(result["episodes"])
    assert seen == expected, "Batches do not cover the full supplied suite"
    return {
        "frozen_inputs_verified": True,
        "full_suite_coverage_verified": True,
        "episodes_verified": len(episodes),
        "episodes": episodes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", type=Path, nargs="+")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_collection(args.directories, args.tasks)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "episodes"}))
