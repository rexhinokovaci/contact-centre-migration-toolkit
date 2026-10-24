"""Cutover wave planning.

Numbers move in waves, lowest risk first. Rules that came out of real
cutovers:

* Numbers in the same carrier port group move together, the carrier won't split them.
* The pilot is the smallest non-critical group, so a bad day hurts the fewest callers.
* Each wave is capped at a share of total daily volume.
* Business-critical numbers go last, once the platform has proven itself.
* Never cut over on a Friday, a weekend or a bank holiday.
* Leave a bake period of working days between waves.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, timedelta

from .calltree import E164


class InventoryError(ValueError):
    pass


@dataclass(frozen=True)
class Number:
    did: str
    label: str
    calls_per_day: int
    port_group: str
    critical: bool


@dataclass
class Wave:
    index: int
    name: str
    cutover: date
    numbers: list[Number] = field(default_factory=list)

    @property
    def volume(self) -> int:
        return sum(n.calls_per_day for n in self.numbers)


def load_numbers(text: str) -> list[Number]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    required = {"did", "label", "calls_per_day", "port_group", "critical"}
    if not reader.fieldnames or not required <= set(reader.fieldnames):
        raise InventoryError(f"CSV needs columns: {', '.join(sorted(required))}")
    out: list[Number] = []
    seen: set[str] = set()
    for line, row in enumerate(reader, start=2):
        did = row["did"].strip()
        if not E164.match(did):
            raise InventoryError(f"line {line}: {did!r} is not E.164")
        if did in seen:
            raise InventoryError(f"line {line}: duplicate number {did}")
        seen.add(did)
        try:
            volume = int(row["calls_per_day"])
        except ValueError as e:
            raise InventoryError(f"line {line}: calls_per_day must be an integer") from e
        if volume < 0:
            raise InventoryError(f"line {line}: calls_per_day can't be negative")
        out.append(
            Number(
                did=did,
                label=row["label"].strip(),
                calls_per_day=volume,
                port_group=row["port_group"].strip() or did,
                critical=row["critical"].strip().lower() in {"true", "yes", "1", "y"},
            )
        )
    if not out:
        raise InventoryError("no numbers in inventory")
    return out


def is_cutover_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 4 and d not in holidays  # Mon-Thu


def next_cutover_day(d: date, holidays: set[date]) -> date:
    while not is_cutover_day(d, holidays):
        d += timedelta(days=1)
    return d


def add_working_days(d: date, days: int, holidays: set[date]) -> date:
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            days -= 1
    return d


def plan(
    numbers: list[Number],
    start: date,
    holidays: set[date] | None = None,
    bake_days: int = 5,
    max_wave_share: float = 0.35,
) -> list[Wave]:
    holidays = holidays or set()
    groups: dict[str, list[Number]] = {}
    for n in numbers:
        groups.setdefault(n.port_group, []).append(n)

    def vol(g: list[Number]) -> int:
        return sum(n.calls_per_day for n in g)

    def critical(g: list[Number]) -> bool:
        return any(n.critical for n in g)

    total = max(1, vol(numbers))
    ordered = sorted(groups.values(), key=lambda g: (critical(g), vol(g), g[0].port_group))

    pilot_idx = next((i for i, g in enumerate(ordered) if not critical(g)), 0)
    pilot = ordered.pop(pilot_idx)

    batches: list[list[Number]] = [pilot]
    current: list[Number] = []
    current_critical = False
    for g in ordered:
        crosses_into_critical = critical(g) and not current_critical and current
        over_cap = current and (vol(current) + vol(g)) / total > max_wave_share
        if crosses_into_critical or over_cap:
            batches.append(current)
            current = []
        current = current + g
        current_critical = current_critical or critical(g)
    if current:
        batches.append(current)

    waves: list[Wave] = []
    day = next_cutover_day(start, holidays)
    wave_no = critical_no = 0
    for i, batch in enumerate(batches):
        if i > 0:
            day = next_cutover_day(add_working_days(day, bake_days, holidays), holidays)
        if i == 0:
            name = "Pilot"
        elif any(n.critical for n in batch):
            critical_no += 1
            name = f"Critical {critical_no}"
        else:
            wave_no += 1
            name = f"Wave {wave_no}"
        waves.append(
            Wave(index=i, name=name, cutover=day, numbers=sorted(batch, key=lambda n: n.did))
        )
    return waves
