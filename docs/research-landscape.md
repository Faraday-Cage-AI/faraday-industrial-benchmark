# Public benchmark pattern matrix

The official `faraday-native` suite uses a clean-room synthesis process: study
public benchmark architecture, measurement methodology, and release practice;
then independently author its tasks, records, tools, state transitions, graders,
and trajectories. Separately, license-compatible upstream projects may be
mirrored verbatim as clearly labeled compatibility tracks. They never become
Faraday-native content or contribute to the headline score. Hidden, private,
restricted, or license-incompatible artifacts are never copied.

| Public work | Pattern worth adopting | Faraday v0.4 status | Next implementation |
|---|---|---|---|
| [FactoryBench-100](https://github.com/blobfishai/factory-agent-simulation) | Executable multi-system worlds, sealed deterministic verifiers, source artifacts, readback checks, many negative controls, portable release bundles | Native patterns independently implemented; exact upstream snapshot vendored at a pinned commit | SQLite episode snapshots, MCP and Harbor packaging, additional omission/wrong-value controls |
| [Industrial Agent Benchmark](https://github.com/masahirosakae/industrial-agent-benchmark) | Separate knowledge, reasoning, and agent capability views; canonical versioning and artifact policy | Native capability summaries plus an exact, pinned upstream compatibility snapshot | Add a native diagnostic knowledge/reasoning track without diluting the executable-agent score |
| [SupChain-Bench](https://aclanthology.org/2026.findings-acl.371/) | Long-horizon supply-chain orchestration and SOP-grounded versus SOP-free evaluation | Six focused supply/distribution families, five composite enterprise DAG families, and an exact pinned upstream snapshot | Add paired guided/unguided policy ablations and cross-company counterparty simulation |
| [SPAS-Bench](https://github.com/ADT-GenAI/SPAS-Bench) | Hierarchical capability taxonomy and broad model baseline reporting | Thirty domain families and machine-readable family/capability slices, including orchestration | Publish measured open and hosted v0.4 model baselines with uncertainty and cost |
| [AssetOpsBench](https://github.com/IBM/AssetOpsBench) | MCP tool servers, specialist agents, time-series models, multi-agent orchestration, competition infrastructure | Native typed tools plus an exact, pinned upstream public snapshot | MCP transport, specialist-agent track, richer native time-series payloads, competition adapter |
| [CFAgentBench](https://arxiv.org/abs/2606.22000) | Executable finance software, state-diff grading, forbidden side effects, money-movement guards, private splits, repeated-trial reliability | Exact finance records, protected money actions, hidden-seed generation, `stability` repeated-trial reports | Private remote scoring split and forbidden-side-effect contracts across every finance family |
| [PHMForge](https://arxiv.org/abs/2604.01532) | Multi-asset reasoning, tool-sequence analysis, held-out equipment generalization | Sequence checks, machine scenarios, procedural seeds | Structural multi-asset episodes and explicit equipment-class holdout splits |
| [FactoryBench machine-reasoning dataset](https://arxiv.org/abs/2605.07675) | State, intervention, counterfactual, and decision layers grounded in telemetry | Stateful sensor investigation and operational decisions | Counterfactual and intervention diagnostic slices using synthetic telemetry |
| [Manufacturing Intelligence product workflows](https://www.manufacturingintelligence.org/product/) | Public taxonomy spanning drawing, assembly/BOM, revision, requirements, drafting, P&ID, process-capability, and construction reviews | Eight independently authored executable workflow families; taxonomy inspiration only, with no product code or data copied | Add native PDF/CAD/BIM artifacts and perception graders without weakening deterministic workflow grading |

## Adoption rules

1. Link and cite the source pattern in design documentation.
2. Keep Faraday-native implementations clean-room and synthetic.
3. Mirror upstream code or data only when redistribution terms are explicit and
   compatible; preserve its namespace, task identity, license, notices, and citation.
4. Pin every mirrored snapshot to a commit and deterministic content hash.
5. Never mix upstream results into the Faraday-native headline score.
6. Add a negative control demonstrating that each new native evaluator detects failure.
7. Require a native oracle trajectory and exact replay before release.
8. Record the pattern, copied-track boundary, and originality boundary in the changelog.

## Priority order

The next major release should prioritize environment realism over raw task count:
isolated SQLite state, synthetic source artifacts, source-pinned API semantics,
MCP/Harbor packaging, and ten or more measured negative controls. After that,
add multi-agent and multimodal tracks, model baselines, and a private leaderboard
split. This order improves benchmark validity before marketing scale.
