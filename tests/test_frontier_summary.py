"""Do not turn incompatible or interrupted measurements into model rankings."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "frontier_summary", Path(__file__).parents[1] / "examples/summarize_frontier.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report():
    return {
        "measurement": {
            "adapter_sha256": "fixture",
            "reasoning_effort": "xhigh",
            "per_response_output_limit": 32768,
            "total_output_limit": 100000,
            "timeout_seconds": 1800,
            "wall_seconds": 1,
        },
        "results": [
            {
                "task": {"id": "fixture", "version": "fixture.1"},
                "agent": "gpt-5.4/xhigh/tool-only",
                "score": {
                    "criteria": [],
                    "violations": [],
                    "score": 0,
                    "strict_success": False,
                    "tool_calls": 0,
                },
            }
        ],
    }


@pytest.mark.parametrize("difference", ["budget", "adapter", "version"])
def test_incompatible_attempts_cannot_be_pooled(tmp_path, difference):
    first = report()
    second = deepcopy(first)
    if difference == "budget":
        second["measurement"]["per_response_output_limit"] = 65536
    elif difference == "adapter":
        second["measurement"]["adapter_sha256"] = "other"
    else:
        second["results"][0]["task"]["version"] = "fixture.2"
    (tmp_path / "gpt-first.json").write_text(json.dumps(first))
    (tmp_path / "gpt-second.json").write_text(json.dumps(second))
    with pytest.raises(ValueError, match="Cannot pool"):
        MODULE.summarize([tmp_path])


def test_incomplete_response_is_visible_not_silently_dropped(tmp_path):
    (tmp_path / "gpt-first.json").write_text(json.dumps(report()))
    (tmp_path / "gpt-first-usage.jsonl").write_text(
        json.dumps(
            {
                "usage": {"output_tokens": 32768},
                "status": "incomplete",
            }
        )
        + "\n"
    )
    result = MODULE.summarize([tmp_path])
    assert result["models"]["gpt-5.4"]["completed_episodes"] == 1
    assert result["episodes"][0]["execution_status"] == "incomplete_api_response_observed"
    assert result["measurement_settings"]["per_response_output_limit"] == 32768


def test_interrupted_attempt_is_not_counted(tmp_path):
    value = report()
    value["measurement"]["interrupted"] = True
    (tmp_path / "gpt-first.json").write_text(json.dumps(value))
    assert MODULE.summarize([tmp_path])["episodes"] == []
