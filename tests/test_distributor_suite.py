from __future__ import annotations

import json
from pathlib import Path

from faraday_industrial_benchmark import extensions
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import load_tasks

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFESTS = {
    "source:erp-bench": ROOT / "data/distributor-erp-bench/tasks.json",
    "source:erpbench-100": ROOT / "data/distributor-erpbench100/tasks.json",
    "source:gdpval": ROOT / "data/distributor-gdpval/tasks.json",
}


def _public_records() -> list[dict]:
    path = DEFAULT_TASKS / "tasks.json" if DEFAULT_TASKS.is_dir() else DEFAULT_TASKS
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_suite_carries_every_source_manifest_unchanged():
    public = _public_records()
    for tag, path in SOURCE_MANIFESTS.items():
        expected = json.loads(path.read_text(encoding="utf-8"))
        actual = [record for record in public if tag in record.get("tags", ())]
        assert actual == expected, f"{tag} drifted; rerun examples/import_distributor_sources.py"
    distributor = [
        record
        for record in public
        if any(tag in record.get("tags", ()) for tag in SOURCE_MANIFESTS)
    ]
    assert len(distributor) == 175
    first = public.index(distributor[0])
    assert public[first:] == distributor, "distributor tasks must follow every native task"


def test_every_distributor_family_is_registered_and_public():
    extensions.load()
    public_families = {task.family for task in load_tasks(DEFAULT_TASKS)}
    distributor = {family for family in public_families if family.startswith("distributor_")}
    assert distributor == set(extensions.FAMILIES)
    assert len(distributor) == 13
