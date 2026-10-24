"""Legacy IVR call tree model.

Partner platforms export their IVR in all sorts of shapes. We normalise them
into this YAML form first (by hand or with a small adapter per vendor), then
everything downstream works on one model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

NodeType = Literal["menu", "queue", "transfer", "message", "hours", "hangup"]
NODE_TYPES: tuple[str, ...] = ("menu", "queue", "transfer", "message", "hours", "hangup")
DTMF_KEYS = set("0123456789*#")
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


class CallTreeError(ValueError):
    """The export can't be turned into a call tree at all."""


@dataclass(frozen=True)
class Node:
    id: str
    type: NodeType
    prompt: str | None = None
    # menu
    options: dict[str, str] = field(default_factory=dict)
    timeout: str | None = None
    retries: int = 1
    # queue
    queue: str | None = None
    # transfer
    number: str | None = None
    # message
    next: str | None = None
    # hours
    open: str | None = None
    closed: str | None = None

    def targets(self) -> list[str]:
        out = list(self.options.values())
        out += [t for t in (self.timeout, self.next, self.open, self.closed) if t]
        return out


@dataclass(frozen=True)
class CallTree:
    name: str
    entry: str
    nodes: dict[str, Node]
    timezone: str = "Europe/London"
    hours: dict[str, str] = field(default_factory=dict)
    holidays: tuple[str, ...] = ()

    def queues(self) -> list[str]:
        return sorted({n.queue for n in self.nodes.values() if n.type == "queue" and n.queue})


def _node(node_id: str, raw: Any) -> Node:
    if not isinstance(raw, dict):
        raise CallTreeError(f"node '{node_id}' must be a mapping")
    kind = raw.get("type")
    if kind not in NODE_TYPES:
        raise CallTreeError(f"node '{node_id}' has unknown type {kind!r}")
    options = {str(k): str(v) for k, v in (raw.get("options") or {}).items()}
    retries = raw.get("retries", 1)
    if not isinstance(retries, int) or not 0 <= retries <= 5:
        raise CallTreeError(f"node '{node_id}': retries must be an integer 0-5")
    return Node(
        id=node_id,
        type=kind,
        prompt=raw.get("prompt"),
        options=options,
        timeout=raw.get("timeout"),
        retries=retries,
        queue=raw.get("queue"),
        number=str(raw["number"]) if "number" in raw else None,
        next=raw.get("next"),
        open=raw.get("open"),
        closed=raw.get("closed"),
    )


def parse(text: str) -> CallTree:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise CallTreeError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise CallTreeError("top level must be a mapping")
    nodes_raw = raw.get("nodes")
    if not isinstance(nodes_raw, dict) or not nodes_raw:
        raise CallTreeError("'nodes' must be a non-empty mapping")
    entry = raw.get("entry")
    if not isinstance(entry, str):
        raise CallTreeError("'entry' must name the first node")
    return CallTree(
        name=str(raw.get("name", "Unnamed IVR")),
        entry=entry,
        nodes={str(k): _node(str(k), v) for k, v in nodes_raw.items()},
        timezone=str(raw.get("timezone", "Europe/London")),
        hours={str(k): str(v) for k, v in (raw.get("hours") or {}).items()},
        holidays=tuple(str(h) for h in raw.get("holidays") or ()),
    )
