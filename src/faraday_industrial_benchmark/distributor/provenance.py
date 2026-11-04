"""Provenance records for source material imported into distributor families.

Each source keeps ``data/distributor-sources/<source>/provenance.json`` with the
upstream repository, pinned revision, license, and a SHA-256 for every committed
file derived from it (package fixtures and copied raw material alike).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCES_ROOT = PROJECT_ROOT / "data" / "distributor-sources"
SCHEMA_VERSION = "faraday-distributor-provenance/1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_provenance(source: str, upstream: dict[str, Any], files: list[Path]) -> Path:
    """Record hashes for ``files`` (absolute paths inside the repository)."""

    entries = {}
    for path in sorted({Path(item).resolve() for item in files}):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        entries[relative] = {"sha256": file_sha256(path), "bytes": path.stat().st_size}
    record = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "upstream": upstream,
        "files": entries,
    }
    destination = SOURCES_ROOT / source / "provenance.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def load_provenance(source: str) -> dict[str, Any]:
    path = SOURCES_ROOT / source / "provenance.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported provenance schema for {source}")
    return record


def verify_provenance(source: str) -> list[str]:
    """Return a list of problems; empty means every recorded file matches."""

    record = load_provenance(source)
    problems = []
    for relative, expected in sorted(record["files"].items()):
        path = PROJECT_ROOT / relative
        if not path.is_file():
            problems.append(f"missing: {relative}")
        elif file_sha256(path) != expected["sha256"]:
            problems.append(f"changed: {relative}")
    return problems


def provenance_sources() -> list[str]:
    if not SOURCES_ROOT.is_dir():
        return []
    return sorted(
        path.parent.name for path in SOURCES_ROOT.glob("*/provenance.json")
    )
