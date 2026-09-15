"""Shared fake-transport helpers for baseline provider tests (no network)."""
from __future__ import annotations

from typing import Any

from baseline.transport import TransportRequest, TransportResponse


class FakeTransport:
    """Captures every TransportRequest and replays scripted responses.

    ``script`` items are TransportResponse objects or Exception instances
    (raised in order). An exhausted script fails the test loudly.
    """

    def __init__(self, script: list[Any] | None = None) -> None:
        self.requests: list[TransportRequest] = []
        self._script = list(script or [])

    def send(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        if not self._script:
            raise AssertionError("FakeTransport script exhausted")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def last_body(self) -> dict[str, Any]:
        assert self.requests, "no request captured"
        return dict(self.requests[-1].body)

    @property
    def last_headers(self) -> dict[str, str]:
        assert self.requests, "no request captured"
        return dict(self.requests[-1].headers)


def openai_responses_ok(
    text: str = "回答テキスト",
    *,
    model: str = "test-openai-model-2026-06-01",
    response_id: str = "resp_secret123",
    status: str = "completed",
) -> TransportResponse:
    return TransportResponse(
        status=200,
        body={
            "id": response_id,
            "model": model,
            "status": status,
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    )


def anthropic_ok(
    text: str = "回答テキスト",
    *,
    model: str = "test-anthropic-model-20260601",
    response_id: str = "msg_secret456",
    stop_reason: str = "end_turn",
) -> TransportResponse:
    return TransportResponse(
        status=200,
        body={
            "id": response_id,
            "model": model,
            "stop_reason": stop_reason,
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 120, "output_tokens": 60},
        },
    )


def chat_completions_ok(
    text: str = "回答テキスト",
    *,
    model: str = "hosted/test-model-fp8",
    response_id: str = "chatcmpl_secret789",
    finish_reason: str = "stop",
) -> TransportResponse:
    return TransportResponse(
        status=200,
        body={
            "id": response_id,
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {"prompt_tokens": 90, "completion_tokens": 45},
        },
    )


def http_error(status: int, message: str = "error") -> TransportResponse:
    return TransportResponse(status=status, body={"error": {"message": message}})
