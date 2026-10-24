"""Before/after traffic reconciliation for a migrated number.

Both sides are normalised to the same columns first:
    date, did, outcome, wait_seconds
where outcome is one of answered | abandoned | self_service | transferred.
Partners define "abandoned" differently (some exclude calls under 5s), so
agree the definition before trusting the comparison.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

Verdict = Literal["pass", "investigate", "rollback"]
OUTCOMES = {"answered", "abandoned", "self_service", "transferred"}
_RANK: dict[Verdict, int] = {"pass": 0, "investigate": 1, "rollback": 2}


@dataclass(frozen=True)
class Thresholds:
    volume_pct: float = 10.0
    abandonment_pts_investigate: float = 2.0
    abandonment_pts_rollback: float = 5.0
    wait_seconds: float = 30.0


@dataclass(frozen=True)
class Side:
    days: int
    calls: int
    abandoned: int
    wait_total: float

    @property
    def per_day(self) -> float:
        return self.calls / self.days if self.days else 0.0

    @property
    def abandonment(self) -> float:
        return 100.0 * self.abandoned / self.calls if self.calls else 0.0

    @property
    def avg_wait(self) -> float:
        return self.wait_total / self.calls if self.calls else 0.0


@dataclass(frozen=True)
class Row:
    did: str
    legacy: Side
    connect: Side
    volume_delta_pct: float
    abandonment_delta_pts: float
    wait_delta_s: float
    verdict: Verdict
    reasons: tuple[str, ...]


def load(text: str, source: str) -> dict[str, Side]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    need = {"date", "did", "outcome", "wait_seconds"}
    if not reader.fieldnames or not need <= set(reader.fieldnames):
        raise ValueError(f"{source}: CSV needs columns {', '.join(sorted(need))}")
    days: dict[str, set[str]] = defaultdict(set)
    calls: dict[str, int] = defaultdict(int)
    abandoned: dict[str, int] = defaultdict(int)
    wait: dict[str, float] = defaultdict(float)
    for line, row in enumerate(reader, start=2):
        outcome = row["outcome"].strip().lower()
        if outcome not in OUTCOMES:
            raise ValueError(f"{source} line {line}: unknown outcome {outcome!r}")
        did = row["did"].strip()
        days[did].add(row["date"].strip())
        calls[did] += 1
        abandoned[did] += outcome == "abandoned"
        wait[did] += float(row["wait_seconds"] or 0)
    return {d: Side(len(days[d]), calls[d], abandoned[d], wait[d]) for d in calls}


def compare(
    legacy: dict[str, Side], connect: dict[str, Side], t: Thresholds | None = None
) -> list[Row]:
    t = t or Thresholds()
    rows: list[Row] = []
    empty = Side(0, 0, 0, 0.0)
    for did in sorted(set(legacy) | set(connect)):
        a, b = legacy.get(did, empty), connect.get(did, empty)
        vol = (
            100.0 * (b.per_day - a.per_day) / a.per_day
            if a.per_day
            else (100.0 if b.per_day else 0.0)
        )
        ab = b.abandonment - a.abandonment
        wait = b.avg_wait - a.avg_wait
        verdict, reasons = _assess(a, b, vol, ab, wait, t)
        rows.append(
            Row(did, a, b, round(vol, 1), round(ab, 1), round(wait, 1), verdict, tuple(reasons))
        )
    return rows


def _assess(
    a: Side, b: Side, vol: float, ab: float, wait: float, t: Thresholds
) -> tuple[Verdict, list[str]]:
    findings: list[tuple[Verdict, str]] = []
    if not b.calls:
        findings.append(("investigate", "no traffic seen on Connect"))
    elif not a.calls:
        findings.append(("investigate", "no legacy baseline"))
    if abs(vol) > t.volume_pct and a.calls and b.calls:
        findings.append(("investigate", f"volume {vol:+.1f}% (routing leak or missed number?)"))
    if ab > t.abandonment_pts_rollback:
        findings.append(("rollback", f"abandonment {ab:+.1f} pts"))
    elif ab > t.abandonment_pts_investigate:
        findings.append(("investigate", f"abandonment {ab:+.1f} pts"))
    if wait > t.wait_seconds:
        findings.append(("investigate", f"average wait {wait:+.0f}s"))
    verdict: Verdict = max((v for v, _ in findings), key=lambda v: _RANK[v], default="pass")
    return verdict, [why for _, why in findings]


def overall(rows: list[Row]) -> Verdict:
    return max((r.verdict for r in rows), key=lambda v: _RANK[v], default="pass")
