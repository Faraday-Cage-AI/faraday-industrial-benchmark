# Third-party benchmark tracks

This directory contains exact, pinned public snapshots used for compatibility
and comparative evaluation. They are not Faraday-authored tasks and are not part
of the `faraday-native` headline score.

## Rules

1. Keep every upstream in its own namespace under `upstreams/`.
2. Preserve the upstream license, notice, citation, task IDs, and benchmark name.
3. Never pool upstream scores into Faraday's headline score.
4. Never train on an evaluation split merely because redistribution is allowed.
5. Record all changes. The current snapshots only remove Git metadata; the one
   FactoryBench-100 Git LFS pointer is materialized byte-for-byte.
6. Verify snapshots before publishing results:

   ```bash
   faraday-bench upstreams --verify
   ```

The machine-readable [manifest](manifest.json) pins source commits, records
license scope, names included and excluded artifacts, and commits to every
vendored file with a deterministic tree hash. `reference-only` entries document
projects that cannot safely be redistributed in this release.

Each snapshot remains governed by its own license. Faraday's root `LICENSE` and
`DATA_LICENSE` do not replace or narrow those upstream terms.

The source repository contains the snapshots. The Python wheel includes the
manifest and verifier metadata but intentionally excludes roughly 319 MB of
upstream payloads; verify or run compatibility tracks from a full repository
checkout.
