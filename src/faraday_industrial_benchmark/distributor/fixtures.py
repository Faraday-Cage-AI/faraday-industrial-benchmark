"""Committed, source-derived fixtures that distributor scenario builders read.

Fixtures are JSON files under ``distributor/fixtures/<source>/`` and ship with
the package. They are produced by ``examples/import_distributor_sources.py``
from pinned upstream snapshots; builders never read the upstream checkouts.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def fixture_path(source: str, name: str) -> Path:
    return FIXTURE_ROOT / source / f"{name}.json"


@lru_cache(maxsize=512)
def _load_text(source: str, name: str) -> str:
    path = fixture_path(source, name)
    if not path.is_file():
        raise ValueError(f"missing distributor fixture: {source}/{name}")
    return path.read_text(encoding="utf-8")


def load_fixture(source: str, name: str) -> Any:
    """Return a fresh copy of one fixture so builders can mutate it freely."""

    return json.loads(_load_text(source, name))


def fixture_names(source: str) -> list[str]:
    directory = FIXTURE_ROOT / source
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))
