"""Injectable HTTP transport for provider adapters.

Providers never talk to the network directly: they build a
:class:`TransportRequest` and hand it to a transport object. Tests inject a
fake transport that captures request bodies; the real
:class:`UrllibTransport` is the only network code path and is NOT exercised
by the test suite (no network in CI).

Headers (which carry API keys) exist only inside TransportRequest objects.
They are never copied into GenerationResult, RequestEcho, or any artifact.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

# HTTP status codes treated as transient (aligned with the frozen
# eval_v2_common retry classification and baseline_experiment_plan_v1 §7).
RETRYABLE_HTTP_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class TransportConnectionError(RuntimeError):
    """Network-level failure (DNS, connect, timeout, truncated body).

    Providers classify this as transient.
    """


@dataclass(frozen=True)
class TransportRequest:
    url: str
    headers: Mapping[str, str] = field(repr=False)  # carries credentials; keep out of logs
    body: Mapping[str, Any] = field(repr=False)
    timeout: float = 300.0


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: Mapping[str, Any]


@runtime_checkable
class Transport(Protocol):
    def send(self, request: TransportRequest) -> TransportResponse:
        ...


def classify_http_status(status: int) -> str:
    """Return "ok" / "transient" / "permanent" for an HTTP status code."""
    if 200 <= status < 300:
        return "ok"
    if status in RETRYABLE_HTTP_STATUS:
        return "transient"
    return "permanent"


class UrllibTransport:
    """Real HTTP transport (stdlib only). Never used in tests/CI.

    HTTP error statuses are returned as TransportResponse (the provider
    classifies them); connection-level failures raise
    TransportConnectionError.
    """

    def send(self, request: TransportRequest) -> TransportResponse:
        req = urllib.request.Request(
            request.url,
            data=json.dumps(dict(request.body)).encode("utf-8"),
            headers=dict(request.headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=request.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return TransportResponse(status=response.status, body=payload)
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {"error": {"message": str(error.reason)}}
            return TransportResponse(status=error.code, body=payload)
        except urllib.error.URLError as error:
            raise TransportConnectionError(f"connection failed: {error.reason}") from error
        except TimeoutError as error:
            raise TransportConnectionError("request timed out") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TransportConnectionError("response body was not valid JSON") from error


def error_message_from_body(body: Mapping[str, Any]) -> str:
    """Extract a short, safe error message from a provider error body."""
    error = body.get("error", body)
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str):
            return message[:200]
    return "provider error"
