# Third-party notices

Faraday distributes the following unmodified public benchmark snapshots as
separate compatibility tracks. They are not Faraday-authored works, and their
original licenses, notices, citations, names, and task identifiers are retained.

## FactoryBench-100 / Factory Agent Simulation

- Source: <https://github.com/blobfishai/factory-agent-simulation>
- Pinned commit: `f2253481cba6f9f2e423ec85c8378b432991ac88`
- Software: Apache License 2.0
- Dataset: Creative Commons Attribution 4.0 International
- Copyright 2026 Blobfish AI
- Preserved files: [`LICENSE`](third_party/upstreams/factorybench-100/LICENSE),
  [`LICENSE-DATA`](third_party/upstreams/factorybench-100/LICENSE-DATA), and
  [`NOTICE`](third_party/upstreams/factorybench-100/NOTICE)

## Industrial Agent Benchmark

- Source: <https://github.com/masahirosakae/industrial-agent-benchmark>
- Pinned commit: `b27e76ffd8eda7ba922b9a07a0aa2c93d15dcacf`
- Software and public dataset: Apache License 2.0
- Author/citation credit: Masahiro Sakae
- Preserved files: [`LICENSE`](third_party/upstreams/industrial-agent-benchmark/LICENSE),
  [`LICENSE_DATASET.md`](third_party/upstreams/industrial-agent-benchmark/LICENSE_DATASET.md),
  and [`CITATION.cff`](third_party/upstreams/industrial-agent-benchmark/CITATION.cff)

## SupChain-Bench

- Source: <https://github.com/Damon-GSY/SC-bench>
- Pinned commit: `28d500d42d1710b99a501204f2bd2ba2b78ad070`
- Repository: Apache License 2.0
- Authors/citation credit: Shengyue Guan, Yihao Liu, and Lang Cao
- Preserved files: [`LICENSE`](third_party/upstreams/supchain-bench/LICENSE),
  [`THIRD-PARTY-NOTICES`](third_party/upstreams/supchain-bench/THIRD-PARTY-NOTICES),
  and [`README.md`](third_party/upstreams/supchain-bench/README.md)

## AssetOpsBench

- Source: <https://github.com/IBM/AssetOpsBench>
- Pinned commit: `8ea62868134ba3e9a83fabe91add339a5ec69234`
- Repository: Apache License 2.0
- Attribution: IBM and AssetOpsBench contributors
- Preserved file: [`LICENSE`](third_party/upstreams/assetopsbench/LICENSE)

## Distributor operations sources

The distributor operations families are native Faraday rebuilds, not unmodified
snapshots. Task material derived from these sources is committed as package
fixtures and recorded, with SHA-256 hashes, in
`data/distributor-sources/<source>/provenance.json`.

### ERP-Bench

- Source: <https://github.com/agentic-labs/erp-bench>
- Pinned commit: `ceba3880af555129b5278e056a0c20f2fb5a0ba9`
- License: CC0 1.0 Universal
- Attribution (courtesy): Agentic Labs
- Use: 82 buy-to-fulfill and supplier-cancellation repair tasks, rebuilt as the
  `distributor_buy_to_fulfill` family

### ERPBench-100 / ERP Agent Simulation

- Source: <https://github.com/blobfishai/erp-agent-simulation>
- Pinned commit: `5bdf458165fee71f6a7965ea30ca33dfbbce1332`
- Software: Apache License 2.0
- Dataset: Creative Commons Attribution 4.0 International
- Attribution: "ERPBench-100 by Blobfish AI". Changes were made: tasks, evidence,
  gold answers, and rubrics were converted into Faraday scenarios and criteria.
- Use: 70 tasks across seven distributor workflow families

### GDPval

- Source: <https://huggingface.co/datasets/openai/gdpval>
- Pinned revision: `11e7900cdcac61bc4daf59e65feb238acda98fbf`
- License: none declared on the dataset card
- Attribution: OpenAI
- Use: 23 distributor-relevant tasks. Prompts are rewritten. Reference data,
  expected deliverable values, and rubrics are committed as grader-only
  reference material. Faraday does not relicense this material, and
  DATA_LICENSE does not cover it. It will be removed on request from the rights
  holder.

The authoritative inventory and integrity commitments are in
[`third_party/manifest.json`](third_party/manifest.json). Separately linked or
downloaded datasets are not relicensed by Faraday and remain subject to their
original terms. No inclusion implies upstream endorsement of Faraday.
