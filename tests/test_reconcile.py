from __future__ import annotations

import pytest

from ccmt.reconcile import compare, load, overall


def test_sample_verdicts(samples):
    rows = compare(
        load((samples / "legacy_cdr.csv").read_text(), "legacy"),
        load((samples / "connect_ctr.csv").read_text(), "connect"),
    )
    verdicts = {r.did: r.verdict for r in rows}
    assert verdicts["+441134960001"] == "pass"
    assert verdicts["+441134960005"] == "investigate"  # volume drop: number not re-pointed
    assert verdicts["+441134960006"] == "rollback"  # abandonment spike
    assert overall(rows) == "rollback"


def csv(*rows: str) -> str:
    return "date,did,outcome,wait_seconds\n" + "\n".join(rows)


def test_missing_connect_traffic_is_flagged():
    rows = compare(
        load(csv("2026-10-01,+1,answered,10"), "l"), load(csv("2026-10-01,+2,answered,10"), "c")
    )
    reasons = {r.did: r.reasons for r in rows}
    assert reasons["+1"] == ("no traffic seen on Connect",)
    assert reasons["+2"] == ("no legacy baseline",)


def test_unknown_outcome_rejected():
    with pytest.raises(ValueError, match="unknown outcome 'hung_up'"):
        load(csv("2026-10-01,+1,hung_up,0"), "legacy")


def test_empty_is_pass():
    assert overall([]) == "pass"
