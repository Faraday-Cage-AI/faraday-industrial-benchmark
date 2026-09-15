#!/usr/bin/env python3
"""Minimal external-agent example for the faraday-industrial-jsonl/1 protocol."""

from __future__ import annotations

import json
import sys


def send(value: dict) -> None:
    print(json.dumps(value, separators=(",", ":")), flush=True)


def receive() -> dict:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("runner closed the protocol stream")
    return json.loads(line)


start = receive()
if start.get("type") != "start" or start.get("protocol") != "faraday-industrial-jsonl/1":
    raise SystemExit("unsupported protocol")

send({"type": "tool_call", "id": "call-1", "name": "get_incident", "arguments": {}})
result = receive()
incident = result.get("result", {}).get("incident", {})
send(
    {
        "type": "final",
        "summary": "Read-only protocol demonstration; no operational decision was executed.",
        "evidence": [incident.get("id", "")],
    }
)

