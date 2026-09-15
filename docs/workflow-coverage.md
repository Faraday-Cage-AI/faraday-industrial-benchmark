# Workflow coverage and complexity claim

Faraday v0.5 is designed to test unusually broad and difficult industrial-agent
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

Every engineering-document family contains two public episodes and supports deterministic
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
| `integrated_operating_review` | QMS, MES, SCM, WMS, CRM/ERP, TMS, GL, GRC, program office | Refresh four changing sources → resolve 15 exceptions → allocate shared constrained supply → reconcile reserve → build/read/package/publish four artifacts |

Every task publishes a topological `workflow_stages` contract. The 52 focused
episodes use a common five-stage lifecycle, while each composite task replaces
that lifecycle with a workflow-specific graph of up to 15 stages. The plant
recovery graph has two independent diagnostic roots, an explicit convergence
gate, and four protected decisions. The sealed
evaluator checks concrete events, records, audit ordering, and upstream
executions. A downstream approval is denied until its named upstream protected
action has actually succeeded.

## Frontier operating-review workload

The four `integrated_operating_review` tasks model a professional work sample,
not a short tool-use puzzle. Each episode requires 26 section reads across an
11-file data room; four files receive independent authoritative revisions while
the review is in progress. A plausible superseded file is present but prohibited
as decision evidence.

The agent must explicitly resolve 15 exceptions covering expanded quality scope,
document precedence, transfer double-counting, constrained supply, revision
qualification, supplier certification, contractual-floor revision, withdrawn
lanes, late quotes, customs holds, shared capacity, insurance offsets, customer
penalties, currency rounding, and approval dependencies. It then creates four
deliverables: an integrated recovery model, control-action register, executive
decision brief, and customer commitment schedule. The evaluator expands these
deliverables into 335–337 field-level checks and separately checks citations,
source versions, exception records, cross-artifact consistency, packaging,
approval, publication, notifications, and audit order.

Exact output vocabulary is not hidden. The program-office source publishes the
full artifact schema, exception IDs, categories, affected-record selection rules,
required dispositions, evidence-file requirements, and status vocabulary. The
agent still has to find the final records, apply those rules, solve the allocation,
calculate the reserve, and keep all repeated facts consistent.

## Measured v0.5 surface

| Measure | Public v0.5 value |
|---|---:|
| Executable episodes | 66 |
| Workflow families | 32 |
| Engineering-document episodes / families | 16 / 8 |
| Composite orchestration episodes / families | 14 / 6 |
| Frontier professional-work-sample episodes / families | 4 / 1 |
| Typed tools | 67 |
| Protected actions | 23 |
| Dynamic event types | 23 |
| Scheduled event instances | 108 |
| Total public workflow-stage nodes | 398 |
| Workflow-specific composite stage nodes | 138 |
| Deterministic task criteria | 2,648 |
| Maximum criteria in one episode | 419 |
| Maximum oracle tool calls in one episode | 93 |
| Frontier source files / sections per episode | 11 / 26 |
| Frontier required exception resolutions per episode | 15 |
| Frontier structured deliverables per episode | 4 |
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

The v0.5 track evaluates workflow reasoning over structured synthetic document
facts. It does not yet prove visual interpretation of PDFs or scans, CAD geometry,
STEP assemblies, P&ID symbols, tolerance-stack computation, or BIM/IFC spatial
coordination. Those should become separate artifact-grounded perception and
geometry tracks, with licenses, render verification, exact parsers, and graders,
rather than being implied by the current structured tasks.
