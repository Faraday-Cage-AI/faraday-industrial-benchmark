"""Deterministic generation of held-out benchmark task manifests."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
import re

from .models import IncidentTask


def generate_tasks(
    templates: list[IncidentTask],
    *,
    per_family: int,
    root_seed: int,
    split: str = "heldout",
    version: str = "0.6.0",
) -> list[IncidentTask]:
    """Generate reproducible task descriptors without exposing seeds to agents."""

    if per_family < 1:
        raise ValueError("per_family must be positive")
    if not re.fullmatch(r"[a-z0-9-]+", split):
        raise ValueError("split must contain only lowercase letters, numbers, and hyphens")
    by_family: dict[str, IncidentTask] = {}
    for task in templates:
        by_family.setdefault(task.family, task)
    rng = random.Random(root_seed)
    generated: list[IncidentTask] = []
    used_seeds: set[int] = set()
    for family in sorted(by_family):
        template = by_family[family]
        for index in range(1, per_family + 1):
            seed = rng.randrange(1, 2**31)
            while seed in used_seeds:
                seed = rng.randrange(1, 2**31)
            used_seeds.add(seed)
            family_slug = family.replace("_", "-")
            generated.append(
                replace(
                    template,
                    id=f"faraday-{split}-{family_slug}-{index:04d}",
                    version=version,
                    seed=seed,
                    tags=tuple(sorted(set(template.tags) | {split, "procedural"})),
                )
            )
    return generated


def generation_commitment(tasks: list[IncidentTask]) -> str:
    """Hash the private task IDs and seeds for pre-run commitment."""

    material = [{"id": task.id, "seed": task.seed, "version": task.version} for task in tasks]
    payload = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_task_manifest(tasks: list[IncidentTask], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for task in tasks:
        record = asdict(task)
        record["systems"] = list(task.systems)
        record["tags"] = list(task.tags)
        records.append(record)
    destination.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
