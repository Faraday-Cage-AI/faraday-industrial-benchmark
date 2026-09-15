# Workflow coverage and complexity claim

Faraday v0.4 is designed to test unusually broad and difficult industrial-agent
work, but the project does not claim that it is the world's most complex
industrial benchmark. A superlative is a comparative research result, not a
feature description. It should be used only after a dated audit of current
benchmarks with reproducible measurements and public evidence.

## Engineering-document workflow map

The public workflow categories on the Manufacturing Intelligence
[product](https://www.manufacturingintelligence.org/product/) and
[use-case](https://www.manufacturingintelligence.org/use-cases/) pages informed
this coverage taxonomy. The site is not a benchmark or data source. Faraday's
tasks, records, values, tools, state transitions, graders, and reference
trajectories are independently authored and synthetic.

| Public workflow category | Faraday family | Executable requirement |
|---|---|---|
| Drawing checks | `drawing_review` | Reconcile datum, interface dimension, and surface-finish facts across controlled sources |
| Assembly and BOM review | `assembly_bom_review` | Detect exact quantity, fastener-grade, and material conflicts |
| Revision review | `revision_review` | Preserve resolved comments, documented changes, and accepted deviations |
| Standards and specifications | `standards_specification_review` | Trace each fabrication requirement to its episode-provided controlling source |
| Manufacturing document drafting | `manufacturing_document_drafting` | Convert exact process and inspection conflicts into a controlled correction draft |
| P&ID review | `pid_review` | Reconcile line numbers, instrument tags, and off-page connectors with MOC-linked sources |
| Process capability | `process_capability_review` | Compare material, envelope, and batch constraints before sourcing disposition |
| Construction document review | `construction_document_review` | Reconcile submittal facts with contract addendum, coordination, and decision history |

Every family contains two public episodes and supports unlimited deterministic
held-out seeds. An episode requires the agent to:

1. Discover and read three controlled documents plus a requirement graph and
   prior review decisions.
2. Avoid treating a pending source as authoritative.
3. Place a reversible hold on the source document.
4. Observe a scheduled authoritative revision while logical time advances.
5. Re-read changed evidence and create a complete set of exact findings, each
   bound to a document, location, requirement, observed value, expected value,
   and severity.
6. Create an exact correction draft grounded in the full source set.
7. Assemble a review package, satisfy evidence gates, and obtain human approval.
8. Publish only to controlled engineering review; the original source remains
   held and is never released to production.
9. Notify the responsible roles and finish with record-level evidence.

Approval is deliberately insufficient by itself. The protected publication
validates the complete finding set, every finding field, all draft content and
sources, and the disposition against sealed state. An approved but plausible
wrong package is rejected without mutating the review state.

## Composite enterprise workflow map

| Family | Systems crossed | Enforced decision depth |
|---|---|---|
| `supplier_quality_recovery` | QMS, WMS, procurement, supplier portal, MES, APS, CRM | Confirm quality and supplier events → contain lots/work → expedite supply → reschedule production |
| `recall_financial_response` | Cold-chain monitoring, WMS, TMS, CRM, QMS, GL, close | Trace/hold scope → initiate recall → reconcile reserve source → post journal |
| `engineering_production_release` | PLM, document control, QMS, BOM, MES, APS, CRM | Publish exact review → map and hold work → apply effectivity without rewriting started work |
| `order_to_cash_disruption` | AR, CRM, OMS, WMS, TMS, carrier network | Release credit → release feasible wave → select and execute lowest-cost feasible reroute |
| `plant_fulfillment_recovery` | Historian, QMS, CMMS, MES, APS, WMS, TMS, CRM, close | Converge quality and maintenance → reschedule before output deadline → release wave → reroute → post reserve |

Every task publishes a topological `workflow_stages` contract. The 52 focused
episodes use a common five-stage lifecycle, while each composite task replaces
that lifecycle with a workflow-specific graph of up to 13 stages. The plant
recovery graph has two independent diagnostic roots, an explicit convergence
gate, and four protected decisions. The sealed
evaluator checks concrete events, records, audit ordering, and upstream
executions. A downstream approval is denied until its named upstream protected
action has actually succeeded.

## Measured v0.4 surface

| Measure | Public v0.4 value |
|---|---:|
| Executable episodes | 62 |
| Workflow families | 31 |
| Engineering-document episodes / families | 16 / 8 |
| Composite orchestration episodes / families | 10 / 5 |
| Typed tools | 61 |
| Protected actions | 22 |
| Dynamic event types | 22 |
| Scheduled event instances | 92 |
| Total public workflow-stage nodes | 338 |
| Workflow-specific composite stage nodes | 78 |
| Deterministic task criteria | 974 |
| Source systems represented in an engineering-document episode | 3 controlled documents plus requirements and history |
| Exact discrepancy contracts per engineering-document episode | 3 findings plus 1 correction draft and 1 package |

Counts describe breadth, not validity. Difficulty also comes from interacting
constraints: partial observability, changing state, time cost, stale sources,
cross-document dependencies, exact structured outputs, reversible containment,
authorization boundaries, post-approval payload validation, economic loss, and
tamper-evident replay.

## Comparative claim protocol

Before saying "most complex," publish a versioned comparison table for every
in-scope benchmark using at least these dimensions:

- executable versus static evaluation;
- number and diversity of workflow families;
- number of source systems and cross-document dependencies per episode;
- state changes during an episode and agent-triggered events;
- horizon length and sequential decision depth;
- exact state, trace, and side-effect grading;
- containment, human approval, and authorization-bypass controls;
- validation after approval rather than approval-as-correctness;
- held-out procedural variation and contamination resistance;
- replay integrity, negative controls, oracle solvability, and measured model baselines;
- native multimodal document perception and fidelity of ERP/MES/SCM semantics.

A defensible current description is: **a broad executable industrial-enterprise
benchmark with a deeply controlled engineering-document workflow track**.
Anything stronger waits for the audit.

## Current boundary and roadmap

The v0.4 track evaluates workflow reasoning over structured synthetic document
facts. It does not yet prove visual interpretation of PDFs or scans, CAD geometry,
STEP assemblies, P&ID symbols, tolerance-stack computation, or BIM/IFC spatial
coordination. Those should become separate artifact-grounded perception and
geometry tracks, with licenses, render verification, exact parsers, and graders,
rather than being implied by the current structured tasks.
