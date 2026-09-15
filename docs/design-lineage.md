# Design lineage and originality boundary

Faraday Industrial Benchmark adopts established public-benchmark engineering patterns:

- isolated synthetic worlds;
- typed tool contracts;
- agent-visible requests separated from authoritative state;
- deterministic state and trace checks;
- reference trajectories and negative controls;
- portable run artifacts and public task descriptors.

These patterns are visible in projects such as FactoryBench, Harbor benchmarks,
SWE-bench-style executable evaluation, and industrial QA datasets. Faraday Industrial Benchmark's
native code, schemas, scenario records, incident narratives, tools, graders, and
reference trajectories were independently authored.

Its evaluation target is **dynamic industrial-enterprise work** across plant
operations, ERP back office, supply chain, logistics, and distribution: evidence and business conditions change during
an episode; agent actions consume logical time; some events are triggered by
investigation; approvals are evidence-gated and can resolve during modeled
request latency; later external evidence remains asynchronous; exact operational
or financial records matter; and authorization bypass overrides aggregate task
performance.

The v0.3 engineering-document workflow taxonomy was informed by the public
[Manufacturing Intelligence product](https://www.manufacturingintelligence.org/product/)
and [use-case](https://www.manufacturingintelligence.org/use-cases/) descriptions.
Those pages are product descriptions, not an evaluation dataset. Faraday copies
no site text, customer material, proprietary workflow, drawing, specification,
or implementation; its state, task prose, facts, tools, graders, and trajectories
are independently authored synthetic benchmark content.

Relevant public work reviewed during design:

- FactoryBench-100: <https://github.com/blobfishai/factory-agent-simulation>
- Industrial Agent Benchmark: <https://github.com/masahirosakae/industrial-agent-benchmark>
- SupChain-Bench: <https://aclanthology.org/2026.findings-acl.371/>
- SPAS-Bench: <https://github.com/ADT-GenAI/SPAS-Bench>
- AssetOpsBench: <https://github.com/IBM/AssetOpsBench>
- CFAgentBench: <https://arxiv.org/abs/2606.22000>
- PHMForge: <https://arxiv.org/abs/2604.01532>

For reproducibility, the repository also mirrors four compatible public
benchmarks under `third_party/upstreams`. Those snapshots remain isolated from
Faraday-native code and scoring, preserve upstream attribution and licensing,
and are committed to exact source revisions and content hashes. Their presence
does not change the originality claim for `faraday-native` and must not be
described as Faraday-authored work.

The detailed pattern-to-feature mapping, native clean-room rules, and copied
compatibility-track boundary are in [`research-landscape.md`](research-landscape.md)
and [`../third_party/manifest.json`](../third_party/manifest.json).

Do not describe the benchmark as the first industrial, manufacturing, ERP, SCM,
or tool-use benchmark. Claims should focus narrowly on the implemented mechanics
and should be updated after a formal literature review.
