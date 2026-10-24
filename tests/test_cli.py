from __future__ import annotations

import json

from ccmt.cli import main


def test_validate_exit_codes(samples, tmp_path, capsys):
    assert main(["validate", str(samples / "partner-ivr.yaml")]) == 0
    bad = tmp_path / "bad.yaml"
    bad.write_text("entry: x\nnodes:\n  a: {type: hangup}")
    assert main(["validate", str(bad)]) == 1
    assert "entry node 'x' does not exist" in capsys.readouterr().out


def test_convert_writes_file(samples, tmp_path):
    out = tmp_path / "flow.json"
    assert main(["convert", str(samples / "partner-ivr.yaml"), "-o", str(out)]) == 0
    assert json.loads(out.read_text())["Version"] == "2019-10-30"


def test_plan_json(samples, capsys):
    assert (
        main(["plan", str(samples / "numbers.csv"), "--start", "2026-11-02", "--format", "json"])
        == 0
    )
    waves = json.loads(capsys.readouterr().out)
    assert waves[0] == {
        "wave": "Pilot",
        "cutover": "2026-11-02",
        "calls_per_day": 85,
        "numbers": ["+441134960009"],
    }


def test_reconcile_rollback_exit_code(samples):
    assert (
        main(["reconcile", str(samples / "legacy_cdr.csv"), str(samples / "connect_ctr.csv")]) == 2
    )


def test_missing_file_is_a_clean_error(capsys):
    assert main(["validate", "nope.yaml"]) == 1
    assert "error:" in capsys.readouterr().err
