"""Shared test fixtures for Industrial Agent Benchmark."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The repository is script-based (no installable package); make the script
# directories importable for unit tests.
for subdir in ("scripts", "eval"):
    path = str(ROOT / subdir)
    if path not in sys.path:
        sys.path.insert(0, path)

# Make the repository root importable so tests can import the `baseline`
# package (does not affect the eval_v2_* / eval/ import paths above).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make shared test helpers (tests/_baseline_helpers.py) importable.
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
