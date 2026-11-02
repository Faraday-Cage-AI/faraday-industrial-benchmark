from __future__ import annotations

import pytest

from faraday_industrial_benchmark.distributor.provenance import (
    load_provenance,
    provenance_sources,
    verify_provenance,
)


@pytest.mark.parametrize("source", provenance_sources())
def test_committed_distributor_sources_match_their_provenance(source):
    record = load_provenance(source)
    assert record["upstream"].get("repository")
    assert record["upstream"].get("revision")
    assert record["upstream"].get("license")
    assert record["files"]
    assert verify_provenance(source) == []
