# Faraday Industrial Benchmark

[Benchmark website](https://www.faradaycompute.com/faraday-industrial-benchmark) · [Benchmark card](BENCHMARK_CARD.md) · [Agent protocol](docs/jsonl-protocol.md)

**Built to be the most comprehensive benchmark for industrial operations.**

Faraday evaluates how well AI agents complete industrial workflows across ERP,
manufacturing, supply chain, logistics, engineering, and finance—from investigating
a problem to executing a verified resolution across connected systems.

Agents work inside a simulated company. They investigate changing records,
resolve exceptions, plan around operational constraints, obtain required
approvals, and carry out actions across connected systems. The benchmark checks
the resulting system state and the evidence behind each action.

## Verified RESULTS

| Model | Result |
|---|---:|
| GPT-5.4 | 67.6 |
| GPT-5.5 | 71.7 |
| Opus 4.7 | 75.2 |
| Sonnet 4.6 | 63.2 |

## What it evaluates

| Area | Example work |
|---|---|
| Manufacturing and quality | Investigate quality issues, contain affected lots, recover from equipment failures, and apply engineering changes. |
| Supply chain and planning | Respond to supplier delays, reconcile inventory, allocate limited stock, and plan feasible order fulfillment. |
| Logistics and distribution | Reroute shipments, release warehouse work, coordinate distribution centers, and manage recalls and trade controls. |
| Engineering | Reconcile drawings, bills of materials, specifications, and revision histories; prepare traceable corrections. |
| Finance and back office | Resolve invoice exceptions, verify vendor changes, manage customer credit, correct payroll, and reconcile period-close postings. |
| Cross-functional operations | Coordinate recovery across purchasing, production, delivery, and finance while keeping records and commitments consistent. |

## How it works

1. **Investigate:** read records and trace the evidence behind a business problem.
2. **Plan:** account for inventory, capacity, cost, delivery windows, and other
   constraints as new information arrives.
3. **Execute:** obtain the required approvals and apply permitted changes through
   tools that update the simulated systems.
4. **Verify:** reconcile the outcome, communicate the result, and leave an
   auditable record.

Each tool call advances simulated time. Deterministic checks evaluate completed
work, record consistency, authorization, and operational outcomes. Saved runs can
be replayed to reproduce the evaluation. Agents connect through a
[newline-delimited JSON protocol](docs/jsonl-protocol.md).

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'

faraday-bench validate
faraday-bench list
faraday-bench run --agent oracle --output runs/oracle.json --html runs/oracle.html
faraday-bench replay runs/oracle.json
```

The reference agent runs without a model API key.

## Connect an agent

Any executable that reads and writes newline-delimited JSON can connect:

```bash
faraday-bench run \
  --agent-command "python examples/jsonl_read_only_agent.py" \
  --agent-name my-agent \
  --output runs/my-agent.json \
  --html runs/my-agent.html
```

The example demonstrates the protocol. Replace it with your agent to evaluate
its ability to complete the workflows. The runner sends the task and available
tools; the agent makes tool calls, receives results, and submits a final response.
See the [protocol documentation](docs/jsonl-protocol.md) for implementation details.

## Documentation

- [Benchmark card](BENCHMARK_CARD.md)
- [Workflow coverage](docs/workflow-coverage.md)
- [Evaluation methodology](docs/scoring.md)
- [Agent protocol](docs/jsonl-protocol.md)
- [Benchmark tracks](docs/benchmark-tracks.md)
- [Third-party tracks and licenses](third_party/README.md)

Faraday-native code is licensed under [Apache-2.0](LICENSE), and authored task
content under [CC BY 4.0](DATA_LICENSE). Third-party material retains its original
terms; see [third-party notices](THIRD_PARTY_NOTICES.md).
