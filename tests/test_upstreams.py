from __future__ import annotations

import json
from pathlib import Path

from faraday_industrial_benchmark.upstreams import (
    load_upstream_manifest,
    snapshot_fingerprint,
)


def test_manifest_separates_vendored_and_reference_only_sources() -> None:
    manifest = load_upstream_manifest()
    by_id = {source["id"]: source for source in manifest["sources"]}

    assert by_id["factorybench-100"]["status"] == "vendored"
    assert by_id["industrial-agent-benchmark"]["status"] == "vendored"
    assert by_id["supchain-bench"]["status"] == "vendored"
    assert by_id["assetopsbench"]["status"] == "vendored"
    assert by_id["spas-bench-full"]["status"] == "reference-only"
    assert manifest["policy"]["pooled_score_allowed"] is False


def test_snapshot_fingerprint_detects_content_changes(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "nested" / "b.json").write_text(json.dumps({"b": 2}), encoding="utf-8")

    before = snapshot_fingerprint(tmp_path)
    (tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")
    after = snapshot_fingerprint(tmp_path)

    assert before["files"] == after["files"] == 2
    assert before["tree_sha256"] != after["tree_sha256"]
