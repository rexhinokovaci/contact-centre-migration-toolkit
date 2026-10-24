"""Structural lint for Connect flows. Mirrors src/flows/flow.ts in
amazon-connect-voice-platform so generated flows pass the same CI gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .convert import targets

TERMINAL = {"DisconnectParticipant", "TransferContactToQueue", "EndFlowExecution"}
NEEDS_ERRORS = {
    "InvokeLambdaFunction",
    "ConnectParticipantWithLexBot",
    "UpdateContactTargetQueue",
    "TransferContactToQueue",
    "TransferParticipantToThirdParty",
    "CheckHoursOfOperation",
    "GetParticipantInput",
}


@dataclass(frozen=True)
class LintIssue:
    rule: str
    action: str | None
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.action or ''} {self.message}".replace("  ", " ")


def lint(flow: dict[str, Any]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    actions: list[dict[str, Any]] = flow.get("Actions", [])
    ids: dict[str, dict[str, Any]] = {}
    for a in actions:
        if a["Identifier"] in ids:
            issues.append(LintIssue("unique-ids", a["Identifier"], "duplicate identifier"))
        ids[a["Identifier"]] = a

    start = flow.get("StartAction")
    if start not in ids:
        issues.append(LintIssue("start-action", None, f"StartAction {start!r} not found"))
    elif ids[start]["Type"] != "UpdateFlowLoggingBehavior":
        issues.append(LintIssue("logging-first", start, "first block should enable flow logging"))

    for a in actions:
        ts = targets(a)
        for t in ts:
            if t not in ids:
                issues.append(
                    LintIssue("dangling-transition", a["Identifier"], f"points at missing {t!r}")
                )
        if a["Type"] not in TERMINAL and not ts:
            issues.append(
                LintIssue("dead-end", a["Identifier"], f"{a['Type']} has no onward transition")
            )
        if a["Type"] in NEEDS_ERRORS and not a.get("Transitions", {}).get("Errors"):
            issues.append(
                LintIssue("error-branch", a["Identifier"], f"{a['Type']} must handle errors")
            )

    seen: set[str] = set()
    stack = [start] if isinstance(start, str) else []
    while stack:
        i = stack.pop()
        if i in seen or i not in ids:
            continue
        seen.add(i)
        stack.extend(targets(ids[i]))
    for i in ids:
        if i not in seen:
            issues.append(LintIssue("unreachable", i, "not reachable from StartAction"))
    return issues
