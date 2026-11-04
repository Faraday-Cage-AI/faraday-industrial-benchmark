# Reproducing the corrected suite

The 0.8.0 engine evaluates 249 public episodes across 46 families. Task descriptor
versions are preserved when their content was unchanged; report both engine and
task versions rather than inferring one from the other. Historical qualification
and learned-model summaries remain under their original paths and contracts.

From a clean checkout, install Python 3.11 or newer and the development extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,openai]'
python examples/release_evidence.py --output reports/my-release --include-development-tracks
```

Use a new output directory. The command refuses an existing destination, makes
no model API calls, and exits nonzero if any required check fails. Retain a failed
bundle as evidence; use a new directory for a corrected run.

The bundle contains frozen input fingerprints and task descriptors, the exact
source snapshot (including uncommitted code, tests, fixtures and vendored upstreams),
installed package versions, regression XML/logs, qualification results, four
public-suite control runs with full traces, authoritative replay reports, a second
reference execution comparison, a difficulty profile, and the platform contract.
`artifacts.json` records file sizes and SHA-256 digests. These local hashes detect
changes relative to the bundle; they are not a signature or external attestation.

Reproduce from `source.tar.gz` in a separate directory and run the same command
there. Installing the archived source establishes the engine version; installed
distribution metadata from an older editable environment may differ, and is
recorded verbatim in `environment.txt`. Runtime engine version and package input
hashes are authoritative for the measured executable. Dependency installation
requires the listed packages; archives do not include an interpreter or wheels.

Verify a saved public run using its exact engine, task manifest, fixtures and
source:

```bash
faraday-bench replay reports/my-release/oracle.json
```

Replay checks full tool records, state hashes, scores, final answers and events,
then recomputes suite/family/capability summaries. It rejects duplicated tasks,
inconsistent agent labels and altered frozen inputs. `covers_supplied_manifest`
distinguishes a full result from a partial run. `--task` verifies selected traces
only and explicitly labels that reduced verification scope. Neither replay nor
provenance authenticates an external model's identity.

With `--include-development-tracks`, the ten active optional contracts listed in
the benchmark card get their own saved reference runs and replay checks. These
are separate results, never additional headline episodes. Their underlying task
versions remain distinct. Legacy superseded manifests and separately namespaced
upstream benchmarks are not pooled into this release's measurements.

The reference is an algorithmic qualification agent. All distributor reference
paths use evaluator-side fixture answers/plans, so perfect reference scores
establish consistency and executability, not independent derivation or learned
agent performance. The repeated reference check measures deterministic execution,
not model sampling stability. Existence of a cited ID does not establish semantic
relevance. New seeds do not create new distributor fixtures.

Generic executable runs record a command digest and disclose unspecified model
configuration. To reproduce a learned-agent measurement, additionally archive the
actual adapter/prompt/configuration and provider usage alongside every attempt.
The [model measurement plan](model-measurement-plan.md) defines that gate. A local
subprocess is cooperative execution; use the isolation in the threat model for
untrusted submissions.
