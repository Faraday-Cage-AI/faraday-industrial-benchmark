"""Run an OpenAI Responses API model through Faraday's JSONL protocol.

The adapter reads OPENAI_API_KEY from the environment through the official SDK.
Never put a key in a command, config file, task prompt, or benchmark artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from openai import OpenAI


def send(value: dict[str, Any]) -> None:
    print(json.dumps(value, separators=(",", ":")), flush=True)


def receive() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("runner closed the protocol stream")
    return json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        default="xhigh",
    )
    parser.add_argument("--max-output-tokens", type=int, default=32768)
    args = parser.parse_args()

    start = receive()
    if start.get("type") != "start" or start.get("protocol") != "faraday-industrial-jsonl/1":
        raise SystemExit("unsupported protocol")

    task = start["task"]
    function_tools = [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
            # Faraday schemas intentionally include optional filters and two-mode
            # wait arguments, so they are not all strict-function-schema shaped.
            "strict": False,
        }
        for tool in start["tools"]
    ]
    instructions = (
        "You are the responsible operator in a synthetic industrial-enterprise "
        "benchmark. Complete the employee request through the provided tools. "
        "Follow the public workflow DAG, inspect changing evidence, resolve all "
        "exceptions, obey authorization boundaries, and preserve exact record IDs. "
        "Do not guess values that can be read or calculated. A plausible narrative "
        "is not completion. You must call finish exactly once with a concise summary "
        "and concrete evidence IDs after the executable work is complete."
    )
    client = OpenAI()
    response = client.responses.create(
        model=args.model,
        reasoning={"effort": args.reasoning_effort},
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": (
                    "Complete this benchmark task.\n\n" + json.dumps(task, indent=2, sort_keys=True)
                ),
            }
        ],
        tools=function_tools,
        parallel_tool_calls=False,
        max_output_tokens=args.max_output_tokens,
        store=True,
    )
    protocol_index = 0
    while True:
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            send(
                {
                    "type": "final",
                    "summary": response.output_text or "Model stopped without calling finish.",
                    "evidence": [],
                }
            )
            return 0

        outputs = []
        for call in calls:
            protocol_index += 1
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            call_id = f"openai-{protocol_index}"
            send(
                {
                    "type": "tool_call",
                    "id": call_id,
                    "name": call.name,
                    "arguments": arguments,
                }
            )
            tool_message = receive()
            if tool_message.get("type") != "tool_result":
                raise SystemExit("runner returned an invalid tool result")
            result = tool_message["result"]
            if call.name == "finish" and result.get("ok") is True:
                final = result.get("final", {})
                send(
                    {
                        "type": "final",
                        "summary": final.get("summary", arguments.get("summary", "")),
                        "evidence": final.get("evidence", arguments.get("evidence", [])),
                    }
                )
                return 0
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, separators=(",", ":")),
                }
            )

        response = client.responses.create(
            model=args.model,
            reasoning={"effort": args.reasoning_effort},
            previous_response_id=response.id,
            instructions=instructions,
            input=outputs,
            tools=function_tools,
            parallel_tool_calls=False,
            max_output_tokens=args.max_output_tokens,
            store=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
