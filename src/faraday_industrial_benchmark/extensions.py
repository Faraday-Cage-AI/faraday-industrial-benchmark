"""Registry for workflow families that live outside ``scenarios.py``.

A family module registers its builder, tools, protected actions, evaluator
checks, event kinds, reference trajectory, and negative-control probe here.
The core world, grader, tool catalog, and agents consult this registry so new
families do not have to edit those shared modules.

Family modules may import ``scenarios`` and ``models`` at module level. The core
modules only import this registry lazily, so there is no import cycle.

Protected actions registered here are scoped to the families that declare them:
they are added to the ``request_approval``/``execute_action`` enum only for those
families, so the public tool contract of every other family is unchanged.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

Json = dict[str, Any]

# Packages whose import registers extension families.
EXTENSION_PACKAGES = ("faraday_industrial_benchmark.distributor",)


@dataclass(frozen=True)
class FamilyExtension:
    """Everything the core needs to run one extension family."""

    family: str
    builder: Callable[..., Any]
    tools: tuple[str, ...]
    notification_roles: tuple[str, ...]
    protected_actions: tuple[str, ...]
    oracle: Callable[..., Json]
    unsafe_probe: Callable[[Json], tuple[str, str]]
    description: str = ""
    extra: Json = field(default_factory=dict)


@dataclass(frozen=True)
class ToolExtension:
    spec: Json
    handler: Callable[..., Json]


@dataclass(frozen=True)
class ActionExtension:
    contract: str
    apply: Callable[..., tuple[bool, str]]


FAMILIES: dict[str, FamilyExtension] = {}
TOOLS: dict[str, ToolExtension] = {}
ACTIONS: dict[str, ActionExtension] = {}
CHECKS: dict[str, Callable[..., tuple[bool, str]]] = {}
EVENTS: dict[str, Callable[..., None]] = {}

_loaded = False


def tool(
    name: str,
    description: str,
    properties: Json,
    required: list[str] | None = None,
) -> Json:
    """Build a tool spec in the same shape as ``tool_specs._tool``."""

    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


def register_tool(spec: Json, handler: Callable[..., Json]) -> None:
    """Register a tool. ``handler(world, **arguments)`` returns a JSON result.

    Names starting with get_, list_, query_, trace_, or read_ cost read latency;
    every other tool costs write latency.
    """

    name = spec["name"]
    existing = TOOLS.get(name)
    if existing is not None and existing.handler is not handler:
        raise ValueError(f"extension tool {name!r} is already registered")
    TOOLS[name] = ToolExtension(spec=deepcopy(spec), handler=handler)


def register_action(
    name: str, contract: str, apply: Callable[..., tuple[bool, str]]
) -> None:
    """Register a protected action. ``apply(world, target, payload)`` returns (ok, detail)."""

    existing = ACTIONS.get(name)
    if existing is not None and existing.apply is not apply:
        raise ValueError(f"extension action {name!r} is already registered")
    ACTIONS[name] = ActionExtension(contract=contract, apply=apply)


def register_check(name: str, check: Callable[..., tuple[bool, str]]) -> None:
    """Register an evaluator check. ``check(world, contract)`` returns (passed, detail)."""

    existing = CHECKS.get(name)
    if existing is not None and existing is not check:
        raise ValueError(f"extension check {name!r} is already registered")
    CHECKS[name] = check


def register_event(kind: str, apply: Callable[..., None]) -> None:
    """Register an event kind. ``apply(world, event, payload)`` mutates world state."""

    existing = EVENTS.get(kind)
    if existing is not None and existing is not apply:
        raise ValueError(f"extension event kind {kind!r} is already registered")
    EVENTS[kind] = apply


def register_family(extension: FamilyExtension) -> None:
    existing = FAMILIES.get(extension.family)
    if existing is not None and existing is not extension:
        raise ValueError(f"extension family {extension.family!r} is already registered")
    FAMILIES[extension.family] = extension
    from .models import PUBLIC_NOTIFICATION_ROLES

    PUBLIC_NOTIFICATION_ROLES[extension.family] = tuple(extension.notification_roles)


def load() -> None:
    """Import every extension package once. Safe to call repeatedly."""

    global _loaded
    if _loaded:
        return
    _loaded = True
    for package in EXTENSION_PACKAGES:
        importlib.import_module(package)


def family(name: str) -> FamilyExtension | None:
    load()
    return FAMILIES.get(name)


def tool_names() -> set[str]:
    load()
    return set(TOOLS)


def action_guide(actions: tuple[str, ...]) -> str:
    return "; ".join(f"{action}({ACTIONS[action].contract})" for action in actions)
