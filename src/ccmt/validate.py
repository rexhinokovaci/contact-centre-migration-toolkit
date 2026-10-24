"""Static checks on a call tree before conversion.

Legacy trees accumulate dead branches and half-finished changes over years.
Better to find them here than in a live cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .calltree import DTMF_KEYS, E164, CallTree

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    node: str | None
    message: str

    def __str__(self) -> str:
        where = f"[{self.node}] " if self.node else ""
        return f"{self.severity}: {where}{self.message}"


def validate(tree: CallTree) -> list[Issue]:
    issues: list[Issue] = []

    def add(severity: Severity, node: str | None, message: str) -> None:
        issues.append(Issue(severity, node, message))

    if tree.entry not in tree.nodes:
        add("error", None, f"entry node '{tree.entry}' does not exist")

    for node in tree.nodes.values():
        for target in node.targets():
            if target not in tree.nodes:
                add("error", node.id, f"points at missing node '{target}'")

        if node.type == "menu":
            if not node.options:
                add("error", node.id, "menu has no options")
            bad = [k for k in node.options if k not in DTMF_KEYS]
            if bad:
                add("error", node.id, f"invalid DTMF keys: {', '.join(bad)}")
            if not node.timeout:
                add(
                    "warning",
                    node.id,
                    "no timeout target; callers who don't press anything will be cut off",
                )
            if not node.prompt:
                add("error", node.id, "menu has no prompt")
            if len(node.options) > 5:
                add(
                    "warning",
                    node.id,
                    f"{len(node.options)} options; more than 5 is hard to remember",
                )
        elif node.type == "queue" and not node.queue:
            add("error", node.id, "queue node has no queue name")
        elif node.type == "transfer":
            if not node.number:
                add("error", node.id, "transfer node has no number")
            elif not E164.match(node.number):
                add("error", node.id, f"number {node.number} is not E.164")
        elif node.type == "message" and not node.next:
            add("warning", node.id, "message has no next node; call will disconnect after it")
        elif node.type == "hours" and not (node.open and node.closed):
            add("error", node.id, "hours check needs both 'open' and 'closed'")

    reachable = _reachable(tree)
    for node_id in tree.nodes:
        if node_id not in reachable:
            add("warning", node_id, "unreachable from entry; probably a dead branch")

    loop = _input_free_loop(tree)
    if loop:
        add("error", loop[0], "loop with no caller input: " + " -> ".join([*loop, loop[0]]))

    return issues


def _reachable(tree: CallTree) -> set[str]:
    seen: set[str] = set()
    stack = [tree.entry]
    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in tree.nodes:
            continue
        seen.add(node_id)
        stack.extend(tree.nodes[node_id].targets())
    return seen


def _input_free_loop(tree: CallTree) -> list[str] | None:
    """A cycle through message/hours nodes only would spin forever."""
    passthrough = {n.id: n.targets() for n in tree.nodes.values() if n.type in ("message", "hours")}
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        path.append(n)
        for t in passthrough.get(n, []):
            if t not in passthrough:
                continue
            if state.get(t) == 1:
                return path[path.index(t) :]
            if t not in state and (found := visit(t)):
                return found
        path.pop()
        state[n] = 2
        return None

    for n in passthrough:
        if n not in state and (found := visit(n)):
            return found
    return None
