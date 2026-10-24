"""Regenerates the synthetic legacy/Connect CDR samples (deterministic)."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
# did -> (calls/day, abandon rate, avg wait) legacy, and the Connect-side change
PROFILE = {
    "+441134960001": ((610, 0.06, 55), (1.02, 0.000, -10)),
    "+441134960003": ((240, 0.05, 40), (0.98, 0.004, -5)),
    "+441134960005": ((130, 0.04, 35), (0.71, 0.000, 0)),  # volume drop: a DID not re-pointed
    "+441134960006": ((190, 0.07, 80), (1.01, 0.071, 45)),  # abandonment spike: rollback
    "+441134960009": ((85, 0.03, 30), (1.00, 0.0, 4)),
}


def rows(days: int, start: date, side: int, rng: random.Random) -> list[list[str]]:
    out: list[list[str]] = []
    for did, (base, change) in PROFILE.items():
        volume, abandon, wait = base
        if side == 1:
            volume = round(volume * change[0])
            abandon += change[1]
            wait += change[2]
        for d in range(days):
            day = start + timedelta(days=d)
            for _ in range(max(0, round(rng.gauss(volume, volume * 0.04)))):
                r = rng.random()
                outcome = (
                    "abandoned"
                    if r < abandon
                    else "self_service"
                    if r < abandon + 0.25
                    else "transferred"
                    if r < abandon + 0.28
                    else "answered"
                )
                w = 0 if outcome == "self_service" else max(0, round(rng.gauss(wait, wait * 0.5)))
                out.append([day.isoformat(), did, outcome, str(w)])
    return out


def main() -> None:
    rng = random.Random(42)
    for name, side, start in (
        ("legacy_cdr.csv", 0, date(2026, 9, 28)),
        ("connect_ctr.csv", 1, date(2026, 10, 12)),
    ):
        with (HERE / name).open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "did", "outcome", "wait_seconds"])
            w.writerows(rows(5, start, side, rng))


if __name__ == "__main__":
    main()
