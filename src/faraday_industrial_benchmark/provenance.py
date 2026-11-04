"""Content-addressed inputs for new runs; these hashes are not an attestation."""

import hashlib
import inspect
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

from .models import Agent, IncidentTask, Json
from .tool_specs import tool_specs_for_family


def content_hash(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def input_fingerprints(tasks: list[IncidentTask]) -> Json:
    package = Path(__file__).resolve().parent
    files = {
        str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".json"}
    }
    families = sorted({task.family for task in tasks})
    return {
        "task_ids": [task.id for task in tasks],
        "task_versions": sorted({task.version for task in tasks}),
        "task_manifest_sha256": content_hash([asdict(task) for task in tasks]),
        "public_contract_sha256": content_hash([task.public_dict() for task in tasks]),
        "source_files": files,
        "source_sha256": content_hash(files),
        "tool_schema_sha256": content_hash({
            family: tool_specs_for_family(family) for family in families
        }),
    }


def build_run_provenance(tasks: list[IncidentTask], agent: Agent) -> Json:
    from . import __version__

    policy_file = inspect.getsourcefile(type(agent))
    implementation = Path(policy_file) if policy_file else None
    agent_contract = {"name": agent.name, "class": type(agent).__qualname__}
    if implementation and implementation.is_file():
        agent_contract["implementation_sha256"] = hashlib.sha256(
            implementation.read_bytes()
        ).hexdigest()
    if hasattr(agent, "command"):
        # Commands can contain credentials; publish only their digest.
        agent_contract["command_sha256"] = content_hash(agent.command)
        agent_contract["timeout_seconds"] = agent.timeout_seconds
        agent_contract["model_configuration"] = "unspecified by generic executable interface"
    return {
        "schema_version": "faraday-industrial-provenance/1",
        "engine_version": __version__,
        "inputs": input_fingerprints(tasks),
        "agent": agent_contract,
        "attempt_policy": "one attempt per listed task per run; all attempts retained",
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "trust": "self-reported local execution; hashes bind inputs, not agent identity",
    }
