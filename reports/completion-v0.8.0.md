# Completion assessment — 0.8.0

Status as of November 3, 2026: corrected implementation and public-suite
algorithmic qualification are complete. Further benchmark evaluations are
deferred at the user's request. This is not a completed learned-model comparison
or a claim of exhaustive industrial accuracy.

## Completed evidence

The integrated regression suite passed **931 tests**, with no failures, errors,
or skips. Public validation covered 249 tasks in 46 families. Vendored upstream
integrity checks passed. The corrected suite contains 8,259 task criteria and
108 served typed tools. Thirty-eight regression cases were added relative to the
initial 893-test suite.

All public-suite controls below completed before the deferral, with 249 episodes
each. Their saved traces, episode scores and aggregate totals replayed exactly.

| Qualification agent | Mean score | Strict successes | Critical failures |
|---|---:|---:|---:|
| Reference oracle | 100.00 | 249/249 | 0 |
| No-op | 10.75 | 0/249 | 0 |
| Read-only | 12.36 | 0/249 | 0 |
| Unauthorized-write control | 0.00 | 0/249 | 249 |

The reference used 6,782 tool calls. A second complete reference execution was
identical, including traces and metadata; this establishes deterministic
reference repeatability, not learned-model stability. Separate challenge and
long-tail reference/replay checks also completed. The process stopped during
workforce preparation; the other eight optional checks are explicitly deferred.
The overall extended bundle is marked interrupted, not fully completed.

Evidence directory: [release-0.8.0-20261103](release-0.8.0-20261103/completion-status.json).
It retains [regression XML](release-0.8.0-20261103/regression.xml),
[frozen inputs](release-0.8.0-20261103/frozen-manifest.json),
[reference episodes](release-0.8.0-20261103/oracle.json),
[reference replay](release-0.8.0-20261103/oracle-replay.json),
[reference HTML](release-0.8.0-20261103/oracle.html),
[repeatability](release-0.8.0-20261103/repeatability.json),
[source snapshot](release-0.8.0-20261103/source.tar.gz), and
[artifact checksums](release-0.8.0-20261103/artifacts.json).
The source snapshot captures the executable at measurement time, including
uncommitted corrections. Later documentation and Makefile edits do not alter the
measured Python inputs. The installed editable distribution's stale 0.6.0
metadata is retained verbatim in `environment.txt`; executed engine source and
frozen input hashes identify 0.8.0. Offline editable reinstall was unavailable
because the environment lacks the declared setuptools build dependency.

## Corrections and review

- Citation scoring now requires distinct existing records, ignores IDs fabricated
  inside authored content, and requires record evidence in every workflow.
- `get_incident.scoring_contract` exposes actual scored deadlines, efficiency
  allowances, hard budgets and final record-ID minimums without instance answers.
- Replay checks full trace records, failures and rejection accounting, aggregate
  totals, task coverage and frozen source/task/tool inputs.
- External-agent protocol handles partial-line hangs, output bounds, cancellation,
  malformed payload types and recorded failures. Inventory allocation rechecks
  current stock atomically and cannot consume the same commitment twice.
- GDP task 002 uses explicit invoice dates plus 30/60 calendar days; AP matching
  rejects excess/duplicate active holds; quality drift rejects excess containment.
- Documentation and website copy distinguish current scope, fixed fixtures,
  historical measurements and algorithmic controls. No site was deployed.

Environment and distributor implementations received independent measurement
review. GDP task002 fixtures were regenerated from pinned upstream files and
verified byte for byte; per-file provenance was updated. The scientist checked
all 249 public scoring thresholds and adversarial citation/aggregate controls.
See the [measurement](../docs/completion-measurement-audit.md),
[environment](../docs/completion-environment-audit.md), and
[domain](../docs/completion-domain-audit.md) audits for observed defects,
verification, and residual limits. Website dependencies were absent, so website
lint/build were not run.

## Remaining gates

- No current full-suite learned-agent result exists. All new model runs are
  deferred; no spending was incurred. The [measurement protocol](../docs/model-measurement-plan.md)
  is prepared for a later model/budget decision.
- All 175 distributor references use evaluator-side fixture answers/plans.
  Their perfect score establishes execution consistency, not independent
  derivation from public evidence. An isolated evidence-only solver remains a
  separate substantive workstream.
- Historical six-model and some optional-track summaries lack their referenced
  raw runs in this checkout. They cannot be independently replayed here and
  must not be presented as current reproducible measurements.
- Fixed distributor fixtures carry about 70% of the task mean. New seeds do not
  create new distributor business instances. GDP structured outputs omit 157
  subjective rubric items; citations check existence rather than semantic relevance.
- Practitioner validation and hosted untrusted-agent isolation remain outstanding.
  The synthetic suite cannot establish real-plant safety or universal ERP coverage.

No historical result was overwritten, no Git commit or publication was made,
and user-authored team/configuration changes were preserved.
