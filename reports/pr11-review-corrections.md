# PR #11 review corrections

This follow-up closes the four findings in the review of commit `18cfaa1`.
It records regression validation; learned-model evaluations remain deferred.
The earlier qualification bundle and source archive retain their original bytes.

## Corrected behavior

1. **Citation spoofing:** the grader enumerates authoritative collections and
   their actual identity fields. Nested action objects, document content, payloads,
   unknown registries and arbitrary foreign keys cannot mint citable records.
   Seeded shipment genealogy explicitly supplies lot identities where the lot
   exists through that public genealogy. Custom families declare their own
   top-level registries through trusted `extra.record_collections` metadata;
   declarations apply only to the active family and never recurse into bodies.
2. **Partial order mutations:** sales/purchase draft creation validates every
   supplied field and derived amount before allocating an ID. Updates validate a
   detached candidate before committing it. Rejected requests preserve business
   records, totals, audit entries and ID counters while retaining normal tool
   rejection traces and latency.
3. **Failure replay in the viewer:** the runner and viewer share `replay_call`,
   including raw malformed arguments and evaluator-only failure markers. Event
   timing is retained. The viewer also warns when full trace metadata or state
   differs despite identical tool results.
4. **Stale viewer caches:** the cache hashes sorted paths and file contents for
   recursive Python modules and JSON fixtures, together with task/run inputs and
   the helper. Same-size edits with preserved timestamps, additions and deletions
   invalidate cached results.

## Validation and merge checks

The [regression XML](pr11-review-regression.xml) and
[validation record](pr11-review-validation.json) identify the final local test
result and executable input hashes. The final suite passed **979 tests**,
with no failures, errors or skips. Independent measurement review accepted the
four corrections and the custom-extension follow-up. New adversarial cases
exercise the public tool boundary, rejected draft operations, malformed/failing
traces, and recursive cache invalidation.

Viewer checks, 27 tests and its production build passed. The Svelte autofixer
reported no issues. The historical-run viewer test now explicitly recognizes
the archived run's existing scoring-contract drift; fresh episode tests establish
exact current replay. Archived runs were preserved.

The existing website CI failed its production dependency audit. The website now
pins Next.js and its lint configuration to 16.4.5, resolves source-map-js to 1.2.2,
and uses the patched Next.js sharp dependency. Its production audit reports zero
vulnerabilities; lint and production build pass. A viewer CI job now runs its
type checks, tests and build with the pinned package manager and explicit Python.

The first integrated test run exposed the custom-extension registry compatibility
gap. It was corrected with explicit trusted declarations and independently
reviewed negative controls before the final regression run. No new benchmark
scores replace the archived qualification results. To replay that historical
bundle, use its archived source rather than the corrected current checkout.
