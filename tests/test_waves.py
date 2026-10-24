from __future__ import annotations

from datetime import date

import pytest

from ccmt.waves import InventoryError, add_working_days, load_numbers, next_cutover_day, plan


def test_sample_plan(samples):
    waves = plan(load_numbers((samples / "numbers.csv").read_text()), date(2026, 11, 2))
    assert [w.name for w in waves] == ["Pilot", "Wave 1", "Wave 2", "Critical 1", "Critical 2"]
    assert waves[0].numbers[0].label == "Welsh language line"
    # Port group PG-C (payments + meter readings) moves together.
    pg_c = [w.index for w in waves for n in w.numbers if n.port_group == "PG-C"]
    assert len(set(pg_c)) == 1
    # Critical numbers only in the critical waves, at the end.
    assert all(not n.critical for w in waves[:3] for n in w.numbers)
    assert [w.cutover for w in waves] == sorted(w.cutover for w in waves)


def test_never_on_friday_weekend_or_holiday():
    assert next_cutover_day(date(2026, 11, 6), set()) == date(2026, 11, 9)  # Fri -> Mon
    xmas = {date(2026, 12, 24)}
    assert next_cutover_day(date(2026, 12, 24), xmas) == date(2026, 12, 28)


def test_bake_period_counts_working_days():
    assert add_working_days(date(2026, 11, 5), 5, set()) == date(2026, 11, 12)


def test_wave_volume_cap():
    csv = "did,label,calls_per_day,port_group,critical\n" + "\n".join(
        f"+4411349600{i:02d},n{i},100,G{i},false" for i in range(10)
    )
    waves = plan(load_numbers(csv), date(2026, 11, 2), max_wave_share=0.3)
    assert all(w.volume <= 300 for w in waves)


@pytest.mark.parametrize(
    "csv, message",
    [
        ("did,label\n+441134960000,x", "CSV needs columns"),
        ("did,label,calls_per_day,port_group,critical\n01134960000,x,1,a,no", "not E.164"),
        (
            "did,label,calls_per_day,port_group,critical\n+441134960000,x,lots,a,no",
            "must be an integer",
        ),
        (
            "did,label,calls_per_day,port_group,critical\n+441134960000,x,1,a,no\n+441134960000,y,1,b,no",
            "duplicate",
        ),
        ("did,label,calls_per_day,port_group,critical", "no numbers"),
    ],
)
def test_inventory_errors(csv, message):
    with pytest.raises(InventoryError, match=message):
        load_numbers(csv)
