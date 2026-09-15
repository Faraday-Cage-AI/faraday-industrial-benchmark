"""Baseline evaluation package for the initial public benchmark baseline.

This package is completely independent from the frozen ``scripts/eval_v2_*``
pipeline and from ``eval/``. It implements the Phase 2A foundation:
no-network answer generation with the dummy provider, private run artifacts,
and public manifest generation governed by:

- docs/public_artifact_policy_v1.md  (canonical publication policy)
- docs/baseline_manifest_spec_v1.md  (manifest fields and validation)
- docs/baseline_experiment_plan_v1.md (frozen protocol)

Real provider adapters (OpenAI / Anthropic / OpenAI-compatible / Gemini) are
Phase 2B+ and are intentionally absent here.
"""

__all__ = [
    "types",
    "redaction",
    "profiles",
    "config",
    "manifest",
    "runner",
    "providers",
]
