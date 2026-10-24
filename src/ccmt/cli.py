"""ccmt command line.

ccmt validate samples/partner-ivr.yaml
ccmt convert  samples/partner-ivr.yaml -o out/main-ivr.json
ccmt plan     samples/numbers.csv --start 2026-11-02 --holiday 2026-12-25
ccmt reconcile samples/legacy_cdr.csv samples/connect_ctr.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import __version__
from .calltree import CallTree, CallTreeError, parse
from .convert import convert
from .lint import lint
from .reconcile import compare, load, overall
from .validate import validate
from .waves import InventoryError, load_numbers, plan


def _tree(path: str) -> CallTree:
    return parse(Path(path).read_text(encoding="utf-8"))


def cmd_validate(args: argparse.Namespace) -> int:
    issues = validate(_tree(args.tree))
    for i in issues:
        print(i)
    errors = sum(i.severity == "error" for i in issues)
    print(f"{errors} error(s), {len(issues) - errors} warning(s)")
    return 1 if errors else 0


def cmd_convert(args: argparse.Namespace) -> int:
    tree = _tree(args.tree)
    errors = [i for i in validate(tree) if i.severity == "error"]
    if errors:
        for i in errors:
            print(i, file=sys.stderr)
        print("fix validation errors before converting", file=sys.stderr)
        return 1
    result = convert(tree)
    problems = lint(result.flow)
    body = json.dumps(result.flow, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(body + "\n", encoding="utf-8")
        print(f"wrote {args.output}: {result.block_count} blocks")
    else:
        print(body)
    print("placeholders: " + ", ".join(result.placeholders), file=sys.stderr)
    if result.dropped:
        print("dropped unreachable nodes: " + ", ".join(result.dropped), file=sys.stderr)
    for p in problems:
        print(f"lint: {p}", file=sys.stderr)
    return 1 if problems else 0


def cmd_plan(args: argparse.Namespace) -> int:
    try:
        numbers = load_numbers(Path(args.inventory).read_text(encoding="utf-8"))
    except InventoryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    holidays = {date.fromisoformat(h) for h in args.holiday}
    waves = plan(numbers, date.fromisoformat(args.start), holidays, args.bake_days, args.max_share)
    total = sum(n.calls_per_day for n in numbers)
    if args.format == "json":
        print(
            json.dumps(
                [
                    {
                        "wave": w.name,
                        "cutover": w.cutover.isoformat(),
                        "calls_per_day": w.volume,
                        "numbers": [n.did for n in w.numbers],
                    }
                    for w in waves
                ],
                indent=2,
            )
        )
        return 0
    for w in waves:
        share = 100 * w.volume / total if total else 0
        print(f"{w.name:<10} {w.cutover:%a %d %b %Y}  {w.volume:>6} calls/day ({share:4.1f}%)")
        for n in w.numbers:
            flag = "  [critical]" if n.critical else ""
            print(f"             {n.did}  {n.label}{flag}")
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    rows = compare(
        load(Path(args.legacy).read_text(encoding="utf-8"), "legacy"),
        load(Path(args.connect).read_text(encoding="utf-8"), "connect"),
    )
    if args.format == "json":
        print(
            json.dumps(
                [
                    {
                        "did": r.did,
                        "verdict": r.verdict,
                        "volume_delta_pct": r.volume_delta_pct,
                        "abandonment_delta_pts": r.abandonment_delta_pts,
                        "wait_delta_s": r.wait_delta_s,
                        "reasons": list(r.reasons),
                    }
                    for r in rows
                ],
                indent=2,
            )
        )
    else:
        print(f"{'number':<15} {'calls/day':>16} {'abandon %':>14} {'wait s':>12}  verdict")
        for r in rows:
            print(
                f"{r.did:<15} {r.legacy.per_day:>7.0f} -> {r.connect.per_day:<6.0f}"
                f" {r.legacy.abandonment:>5.1f} -> {r.connect.abandonment:<5.1f}"
                f" {r.legacy.avg_wait:>4.0f} -> {r.connect.avg_wait:<4.0f}  {r.verdict}"
                + (f"  ({'; '.join(r.reasons)})" if r.reasons else "")
            )
    verdict = overall(rows)
    print(f"overall: {verdict}", file=sys.stderr)
    return {"pass": 0, "investigate": 0, "rollback": 2}[verdict]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ccmt", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--version", action="version", version=f"ccmt {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="check a call tree for errors and dead branches")
    v.add_argument("tree")
    v.set_defaults(fn=cmd_validate)

    c = sub.add_parser("convert", help="convert a call tree to Connect Flow Language")
    c.add_argument("tree")
    c.add_argument("-o", "--output")
    c.set_defaults(fn=cmd_convert)

    pl = sub.add_parser("plan", help="plan number cutover waves")
    pl.add_argument("inventory")
    pl.add_argument("--start", required=True, help="earliest cutover date, YYYY-MM-DD")
    pl.add_argument("--holiday", action="append", default=[], help="YYYY-MM-DD, repeatable")
    pl.add_argument("--bake-days", type=int, default=5)
    pl.add_argument(
        "--max-share", type=float, default=0.35, help="max share of daily volume per wave"
    )
    pl.add_argument("--format", choices=["text", "json"], default="text")
    pl.set_defaults(fn=cmd_plan)

    r = sub.add_parser("reconcile", help="compare legacy and Connect traffic per number")
    r.add_argument("legacy")
    r.add_argument("connect")
    r.add_argument("--format", choices=["text", "json"], default="text")
    r.set_defaults(fn=cmd_reconcile)

    args = p.parse_args(argv)
    try:
        return int(args.fn(args))
    except (CallTreeError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
