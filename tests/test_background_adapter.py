"""Offline transport tests: never resubmit a generation after a polling failure."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "background_adapter",
    Path(__file__).parents[1] / "examples/openai_responses_agent_background.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Client:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.creates = 0
        self.reads = []
        self.cancelled = []
        self.responses = self

    def create(self, **kwargs):
        assert kwargs["background"] is True
        self.creates += 1
        return SimpleNamespace(id="response-fixture", status="queued")

    def retrieve(self, response_id):
        self.reads.append(response_id)
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(id=response_id, status=outcome)

    def with_options(self, **kwargs):
        return self

    def cancel(self, response_id):
        self.cancelled.append(response_id)
        return SimpleNamespace(status="cancelled")


def test_poll_retry_does_not_resubmit(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)
    client = Client([RuntimeError("transient"), "in_progress", "completed"])
    result = MODULE.create_background(client, tmp_path / "usage.jsonl", model="fixture")
    assert result.status == "completed"
    assert client.creates == 1
    assert client.reads == ["response-fixture"] * 3
    assert client.cancelled == []


@pytest.mark.parametrize("error", [RuntimeError("persistent"), KeyboardInterrupt()])
def test_failed_poll_or_interrupt_cancels_known_request(monkeypatch, error):
    monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)
    client = Client([error] * 3)
    with pytest.raises(type(error)):
        MODULE.create_background(client, None, model="fixture")
    assert client.creates == 1
    assert client.cancelled == ["response-fixture"]


def test_deadline_cancels_without_new_generation(monkeypatch):
    monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)
    client = Client([])
    with pytest.raises(TimeoutError):
        MODULE.create_background(client, None, model="fixture", max_job_seconds=0)
    assert client.creates == 1
    assert client.reads == []
    assert client.cancelled == ["response-fixture"]
