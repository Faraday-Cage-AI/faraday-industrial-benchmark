"""Provenance and integrity checks for vendored upstream benchmark snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST = PROJECT_ROOT / "third_party" / "manifest.json"
INSTALLED_MANIFEST = (
    Path(sys.prefix) / "share" / "faraday-industrial-benchmark" / "upstreams" / "manifest.json"
)
DEFAULT_MANIFEST = SOURCE_MANIFEST if SOURCE_MANIFEST.exists() else INSTALLED_MANIFEST


def load_upstream_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Load the machine-readable upstream registry."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "faraday-upstream-manifest/1":
        raise ValueError("unsupported upstream manifest schema")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("upstream manifest must contain at least one source")
    identifiers = [source.get("id") for source in sources]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise ValueError("every upstream source must have a non-empty string ID")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("upstream source IDs must be unique")
    return payload


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_fingerprint(root: str | Path) -> dict[str, int | str]:
    """Return a deterministic digest, file count, and byte count for a tree.

    The digest commits to every relative file path and each file's SHA-256.
    Git metadata and common local cache files are excluded from the snapshot.
    """

    directory = Path(root)
    if not directory.is_dir():
        raise ValueError(f"snapshot directory does not exist: {directory}")
    excluded_parts = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
    excluded_names = {".DS_Store"}
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and not excluded_parts.intersection(path.relative_to(directory).parts)
        and path.name not in excluded_names
    )
    tree_digest = hashlib.sha256()
    byte_count = 0
    for path in files:
        relative = path.relative_to(directory).as_posix()
        file_digest = _hash_file(path)
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_digest.encode("ascii"))
        tree_digest.update(b"\n")
        byte_count += os.stat(path, follow_symlinks=False).st_size
    return {
        "tree_sha256": tree_digest.hexdigest(),
        "files": len(files),
        "bytes": byte_count,
    }


def verify_upstream_snapshots(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    snapshots_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Verify every vendored snapshot and report reference-only sources."""

    manifest_file = Path(manifest_path)
    manifest = load_upstream_manifest(manifest_file)
    root = Path(snapshots_root) if snapshots_root else manifest_file.parent
    results: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        status = source["status"]
        if status != "vendored":
            results.append(
                {
                    "id": source["id"],
                    "status": status,
                    "verified": None,
                    "reason": source.get("reason", "not vendored"),
                }
            )
            continue

        snapshot_path = root / source["path"]
        if not snapshot_path.is_dir():
            results.append(
                {
                    "id": source["id"],
                    "status": "missing",
                    "verified": False,
                    "path": str(snapshot_path),
                }
            )
            continue
        actual = snapshot_fingerprint(snapshot_path)
        expected = source["snapshot"]
        results.append(
            {
                "id": source["id"],
                "status": "vendored",
                "verified": actual == expected,
                "path": str(snapshot_path),
                "expected": expected,
                "actual": actual,
            }
        )
    return results
