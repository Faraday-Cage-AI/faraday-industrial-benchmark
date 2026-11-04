"""Import pinned distributor benchmark sources into committed fixtures.

Usage:
    python examples/import_distributor_sources.py --source all
    python examples/import_distributor_sources.py --source erp-bench --benchmarks ../benchmarks

Each source importer lives in ``examples/distributor_import/<module>.py`` and
exposes ``run(benchmarks_root: Path, repo_root: Path) -> None``. Importers need
the ``import`` extra (``pip install -e '.[import]'``); the benchmark runtime does not.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPORTERS = {
    "erp-bench": "erp_bench",
    "erpbench-100": "erpbench100",
    "gdpval": "gdpval",
}
# Per-source manifests, in the order they are appended to the public suite.
SOURCE_MANIFESTS = (
    "data/distributor-erp-bench/tasks.json",
    "data/distributor-erpbench100/tasks.json",
    "data/distributor-gdpval/tasks.json",
)
PUBLIC_MANIFEST = "data/public/tasks.json"
DISTRIBUTOR_SOURCE_TAGS = ("source:erp-bench", "source:erpbench-100", "source:gdpval")


def is_distributor_task(record: dict) -> bool:
    return any(tag in DISTRIBUTOR_SOURCE_TAGS for tag in record.get("tags", ()))


def sync_public_manifest(repo_root: Path) -> int:
    """Replace the distributor tasks in the public suite with the source manifests."""

    public_path = repo_root / PUBLIC_MANIFEST
    text = public_path.read_text(encoding="utf-8")
    # Native records are hand-formatted, so keep their exact text and only
    # rewrite the distributor tail, which must follow every native record.
    decoder = json.JSONDecoder()
    position = text.index("[") + 1
    native_end = position
    seen_distributor = False
    while True:
        while text[position] in " \t\r\n,":
            position += 1
        if text[position] == "]":
            break
        record, end = decoder.raw_decode(text, position)
        if is_distributor_task(record):
            seen_distributor = True
        elif seen_distributor:
            raise ValueError(f"native task {record['id']} follows distributor tasks")
        else:
            native_end = end
        position = end
    distributor = []
    for manifest in SOURCE_MANIFESTS:
        distributor.extend(json.loads((repo_root / manifest).read_text(encoding="utf-8")))
    tail = json.dumps(distributor, indent=2, ensure_ascii=False)[1:-1].rstrip()
    public_path.write_text(text[:native_end] + "," + tail + "\n]\n", encoding="utf-8")
    return len(distributor)


def _load(module: str):
    path = REPO_ROOT / "examples" / "distributor_import" / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"distributor_import_{module}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load importer {path}")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=[*IMPORTERS, "all"], default="all")
    parser.add_argument(
        "--benchmarks",
        type=Path,
        default=REPO_ROOT.parent / "benchmarks",
        help="Directory containing the downloaded upstream benchmark snapshots.",
    )
    args = parser.parse_args()
    sources = list(IMPORTERS) if args.source == "all" else [args.source]
    for source in sources:
        _load(IMPORTERS[source]).run(args.benchmarks.resolve(), REPO_ROOT)
        print(f"imported {source}")
    count = sync_public_manifest(REPO_ROOT)
    print(f"synced {count} distributor tasks into {PUBLIC_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
