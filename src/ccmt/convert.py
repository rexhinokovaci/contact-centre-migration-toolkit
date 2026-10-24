"""Call tree -> Amazon Connect Flow Language.

Environment-specific values (queue ARNs, hours) are left as ${PLACEHOLDER}
tokens, the same convention amazon-connect-voice-platform renders at deploy
time. Menu retries are unrolled into separate input blocks, because
GetParticipantInput has no retry counter of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .calltree import CallTree, Node

Action = dict[str, Any]

ERROR = "sys-technical-error"
BUSY = "sys-queue-full"
END = "sys-disconnect"
START = "sys-logging"


@dataclass(frozen=True)
class Conversion:
    flow: dict[str, Any]
    placeholders: list[str]
    queues: dict[str, str]  # legacy queue name -> placeholder
    dropped: list[str]  # unreachable legacy nodes left out of the flow

    @property
    def block_count(self) -> int:
        return len(self.flow["Actions"])


def spoken_number(e164: str) -> str:
    """+44800111999 -> "0 8 0 0, 1 1 1, 9 9 9" for UK numbers, digit groups otherwise."""
    digits = "0" + e164[3:] if e164.startswith("+44") else e164.lstrip("+")
    groups = [digits[:4], digits[4:7], digits[7:]]
    return ", ".join(" ".join(g) for g in groups if g)


def queue_placeholder(name: str) -> str:
    return "QUEUE_" + re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def _errors(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"NextAction": target, "ErrorType": kind} for kind, target in pairs]


def _message(ident: str, text: str, nxt: str) -> Action:
    return {
        "Identifier": ident,
        "Type": "MessageParticipant",
        "Parameters": {"Text": text},
        "Transitions": {"NextAction": nxt, "Errors": _errors(("NoMatchingError", nxt))},
    }


def convert(tree: CallTree, timeout_seconds: int = 6) -> Conversion:
    actions: list[Action] = []
    queues: dict[str, str] = {}
    live = _reachable_nodes(tree)

    def fallback(node: Node) -> str:
        return node.timeout or ERROR

    for node in tree.nodes.values():
        if node.id not in live:
            continue
        if node.type == "menu":
            attempts = node.retries + 1
            for i in range(attempts):
                ident = node.id if i == 0 else f"{node.id}--retry{i}"
                nxt = f"{node.id}--retry{i + 1}" if i + 1 < attempts else fallback(node)
                prompt = node.prompt or ""
                if i > 0:
                    prompt = "Sorry, I didn't get that. " + prompt
                actions.append(
                    {
                        "Identifier": ident,
                        "Type": "GetParticipantInput",
                        "Parameters": {
                            "Text": prompt,
                            "StoreInput": "False",
                            "InputTimeLimitSeconds": str(timeout_seconds),
                        },
                        "Transitions": {
                            "NextAction": nxt,
                            "Conditions": [
                                {
                                    "NextAction": target,
                                    "Condition": {"Operator": "Equals", "Operands": [key]},
                                }
                                for key, target in node.options.items()
                            ],
                            "Errors": _errors(
                                ("InputTimeLimitExceeded", nxt),
                                ("NoMatchingCondition", nxt),
                                ("NoMatchingError", fallback(node)),
                            ),
                        },
                    }
                )
        elif node.type == "queue":
            assert node.queue
            ph = queue_placeholder(node.queue)
            queues[node.queue] = ph
            actions.append(
                {
                    "Identifier": node.id,
                    "Type": "UpdateContactTargetQueue",
                    "Parameters": {"QueueId": "${" + ph + "}"},
                    "Transitions": {
                        "NextAction": f"{node.id}--transfer",
                        "Errors": _errors(("NoMatchingError", ERROR)),
                    },
                }
            )
            actions.append(
                {
                    "Identifier": f"{node.id}--transfer",
                    "Type": "TransferContactToQueue",
                    "Parameters": {},
                    "Transitions": {
                        "NextAction": ERROR,
                        "Errors": _errors(("QueueAtCapacity", BUSY), ("NoMatchingError", ERROR)),
                    },
                }
            )
        elif node.type == "transfer":
            assert node.number
            transfer_id = f"{node.id}--transfer" if node.prompt else node.id
            failed_id = f"{node.id}--failed"
            if node.prompt:
                actions.append(_message(node.id, node.prompt, transfer_id))
            actions.append(
                {
                    "Identifier": transfer_id,
                    "Type": "TransferParticipantToThirdParty",
                    "Parameters": {
                        "ThirdPartyPhoneNumber": node.number,
                        "ThirdPartyConnectionTimeLimitSeconds": "30",
                        "ContinueFlowExecution": "False",
                    },
                    "Transitions": {
                        "NextAction": END,
                        "Errors": _errors(
                            ("CallFailed", failed_id),
                            ("ConnectionTimeLimitExceeded", failed_id),
                            ("NoMatchingError", failed_id),
                        ),
                    },
                }
            )
            # A failed transfer must still tell the caller where to go; for an
            # emergency line, a generic error message is not acceptable.
            actions.append(
                _message(
                    failed_id,
                    "Sorry, I couldn't connect you. Please hang up and call "
                    + spoken_number(node.number)
                    + ".",
                    END,
                )
            )
        elif node.type == "message":
            actions.append(_message(node.id, node.prompt or "", node.next or END))
        elif node.type == "hours":
            assert node.open and node.closed
            actions.append(
                {
                    "Identifier": node.id,
                    "Type": "CheckHoursOfOperation",
                    "Parameters": {"HoursOfOperationId": "${HOURS_ARN}"},
                    "Transitions": {
                        "NextAction": node.open,
                        "Conditions": [
                            {
                                "NextAction": node.open,
                                "Condition": {"Operator": "Equals", "Operands": ["True"]},
                            },
                            {
                                "NextAction": node.closed,
                                "Condition": {"Operator": "Equals", "Operands": ["False"]},
                            },
                        ],
                        # If the hours lookup fails, err on the side of letting the call in.
                        "Errors": _errors(("NoMatchingError", node.open)),
                    },
                }
            )
        elif node.type == "hangup":
            actions.append(
                {
                    "Identifier": node.id,
                    "Type": "DisconnectParticipant",
                    "Parameters": {},
                    "Transitions": {},
                }
            )

    system = [
        {
            "Identifier": START,
            "Type": "UpdateFlowLoggingBehavior",
            "Parameters": {"FlowLoggingBehavior": "Enabled"},
            "Transitions": {"NextAction": tree.entry},
        },
        _message(ERROR, "Sorry, we're having a technical problem. Please try again shortly.", END),
        _message(BUSY, "We're very busy right now. Please call back later.", END),
        {"Identifier": END, "Type": "DisconnectParticipant", "Parameters": {}, "Transitions": {}},
    ]
    flow = {
        "Version": "2019-10-30",
        "StartAction": START,
        "Metadata": {
            "name": tree.name,
            "description": "Generated by ccmt from a legacy call tree.",
        },
        "Actions": _prune([system[0], *actions, *system[1:]], START),
    }
    uses_hours = any(n.type == "hours" for n in tree.nodes.values() if n.id in live)
    placeholders = sorted({*queues.values(), *(["HOURS_ARN"] if uses_hours else [])})
    return Conversion(
        flow=flow,
        placeholders=placeholders,
        queues=dict(sorted(queues.items())),
        dropped=sorted(set(tree.nodes) - live),
    )


def _reachable_nodes(tree: CallTree) -> set[str]:
    seen: set[str] = set()
    stack = [tree.entry]
    while stack:
        n = stack.pop()
        if n in seen or n not in tree.nodes:
            continue
        seen.add(n)
        stack.extend(tree.nodes[n].targets())
    return seen


def targets(action: Action) -> list[str]:
    t = action.get("Transitions", {})
    out = [t.get("NextAction")]
    out += [c["NextAction"] for c in t.get("Conditions", [])]
    out += [e["NextAction"] for e in t.get("Errors", [])]
    return list(dict.fromkeys(x for x in out if x))


def _prune(actions: list[Action], start: str) -> list[Action]:
    """Drop generated system blocks nothing points at."""
    by_id = {a["Identifier"]: a for a in actions}
    seen: set[str] = set()
    stack = [start]
    while stack:
        i = stack.pop()
        if i in seen or i not in by_id:
            continue
        seen.add(i)
        stack.extend(targets(by_id[i]))
    return [a for a in actions if a["Identifier"] in seen or not a["Identifier"].startswith("sys-")]
