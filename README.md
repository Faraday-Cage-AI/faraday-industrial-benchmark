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

## Verified results: v0.6.0 (74-task suite)

These scores were measured on v0.6.0, which had 74 tasks in 33 families. They
have not been re-run on v0.7.0 and are not comparable with v0.7.0 scores.

| Model | Result |
|---|---:|
| GPT-5.4 | 67.6 |
| GPT-5.5 | 71.7 |
| Opus 4.7 | 75.2 |
| Sonnet 4.6 | 63.2 |
| Grok 4.5 | 69.7 |
| Gemini 3.1 Pro | 61.4 |

## Suite

Version 0.7.0 ships 249 public tasks in 46 workflow families, with 108 typed
tools in the platform harness contract (67 core and 41 distributor). The
headline score is a plain mean over all 249 tasks, so the 175 Distributor
Operations tasks account for about 70% of it. The reference oracle scores
100.00 with 249/249 strict successes; no-op, read-only, and unauthorized-write
controls score 10.76, 11.75, and 0.00.

## What it evaluates

| Area | Example work |
|---|---|
| Manufacturing and quality | Investigate quality issues, contain affected lots, recover from equipment failures, and apply engineering changes. |
| Supply chain and planning | Respond to supplier delays, reconcile inventory, allocate limited stock, and plan feasible order fulfillment. |
| Logistics and distribution | Reroute shipments, release warehouse work, coordinate distribution centers, and manage recalls and trade controls. |
| Engineering | Reconcile drawings, bills of materials, specifications, and revision histories; prepare traceable corrections. |
| Finance and back office | Resolve invoice exceptions, verify vendor changes, manage customer credit, correct payroll, and reconcile period-close postings. |
| Cross-functional operations | Coordinate recovery across purchasing, production, delivery, and finance while keeping records and commitments consistent. |
| Distributor operations | Screen and fulfill customer orders, buy within supplier constraints, invoice per policy, collect receivables, match receipts to AP, sync channel orders, and produce priced quotes, plans, and analyses. |

## Distributor Operations

Thirteen families (175 tasks) cover wholesale-distributor work. They are native
Faraday rebuilds of tasks selected from three public benchmarks: each has its own
world builder, typed tools, sealed deterministic criteria, and reference oracle.
They are part of the headline suite, not a separate compatibility track.

| Source | Tasks | Families |
|---|---:|---|
| [ERP-Bench](https://github.com/agentic-labs/erp-bench) (CC0) | 82 | `distributor_buy_to_fulfill` |
| [ERPBench-100](https://github.com/blobfishai/erp-agent-simulation) by Blobfish AI (data CC BY 4.0) | 70 | order import, shipment verification, receivables collection, price-list batch, inventory reorder, receiving/AP match, channel order sync |
| [GDPval](https://huggingface.co/datasets/openai/gdpval) (no license declared) | 23 | sales analytics, pricing and quotation, inventory planning, warehouse shipping, policy documents |

Fixtures come from pinned upstream snapshots through
`examples/import_distributor_sources.py`, with per-file SHA-256 provenance in
`data/distributor-sources/<source>/provenance.json`. Distributor fixtures are
fixed per task, so held-out generation for these families reuses the template
scenario with a new seed. GDPval rubric items that need subjective judgment
(presentation, file format, narrative) are recorded but not scored. See
[benchmark tracks](docs/benchmark-tracks.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

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
content under [CC BY 4.0](DATA_LICENSE). Third-party material, including the
source-derived distributor material, retains its original terms; see
[NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md).
