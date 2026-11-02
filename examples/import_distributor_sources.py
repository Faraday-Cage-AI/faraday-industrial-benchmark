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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPORTERS = {
    "erp-bench": "erp_bench",
    "erpbench-100": "erpbench100",
    "gdpval": "gdpval",
}


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
