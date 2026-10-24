# Thin JSON API over ccmt for the browser playground (runs under Pyodide).
import json
from datetime import date

from ccmt.calltree import CallTreeError, parse
from ccmt.convert import convert
from ccmt.lint import lint
from ccmt.reconcile import Side, compare, load, overall
from ccmt.validate import validate
from ccmt.waves import InventoryError, load_numbers, plan


def api_convert(text: str) -> str:
    try:
        tree = parse(text)
    except CallTreeError as e:
        return json.dumps({"error": str(e)})
    issues = validate(tree)
    out = {
        "name": tree.name,
        "entry": tree.entry,
        "nodes": {
            n.id: {
                "type": n.type,
                "prompt": n.prompt,
                "options": n.options,
                "timeout": n.timeout,
                "retries": n.retries,
                "queue": n.queue,
                "number": n.number,
                "next": n.next,
                "open": n.open,
                "closed": n.closed,
            }
            for n in tree.nodes.values()
        },
        "issues": [{"severity": i.severity, "node": i.node, "message": i.message} for i in issues],
    }
    if not any(i.severity == "error" for i in issues):
        result = convert(tree)
        out.update(
            flow=result.flow,
            placeholders=result.placeholders,
            dropped=result.dropped,
            lint=[str(i) for i in lint(result.flow)],
        )
    return json.dumps(out)


def api_plan(text: str, start: str, holidays: str, bake_days: int, max_share: float) -> str:
    try:
        numbers = load_numbers(text)
        hol = {date.fromisoformat(h.strip()) for h in holidays.split(",") if h.strip()}
        waves = plan(numbers, date.fromisoformat(start), hol, bake_days, max_share)
    except (InventoryError, ValueError) as e:
        return json.dumps({"error": str(e)})
    total = sum(n.calls_per_day for n in numbers) or 1
    return json.dumps(
        {
            "total": total,
            "waves": [
                {
                    "name": w.name,
                    "cutover": w.cutover.isoformat(),
                    "weekday": w.cutover.strftime("%A"),
                    "volume": w.volume,
                    "share": round(100 * w.volume / total, 1),
                    "numbers": [
                        {
                            "did": n.did,
                            "label": n.label,
                            "calls": n.calls_per_day,
                            "group": n.port_group,
                            "critical": n.critical,
                        }
                        for n in w.numbers
                    ],
                }
                for w in waves
            ],
        }
    )


def _side(s: Side) -> dict[str, float]:
    return {
        "per_day": round(s.per_day),
        "abandonment": round(s.abandonment, 1),
        "wait": round(s.avg_wait),
    }


def api_reconcile(legacy: str, connect: str) -> str:
    try:
        rows = compare(load(legacy, "legacy"), load(connect, "connect"))
    except ValueError as e:
        return json.dumps({"error": str(e)})
    return json.dumps(
        {
            "overall": overall(rows),
            "rows": [
                {
                    "did": r.did,
                    "legacy": {
                        "per_day": round(r.legacy.per_day),
                        "abandonment": round(r.legacy.abandonment, 1),
                        "wait": round(r.legacy.avg_wait),
                    },
                    "connect": {
                        "per_day": round(r.connect.per_day),
                        "abandonment": round(r.connect.abandonment, 1),
                        "wait": round(r.connect.avg_wait),
                    },
                    "volume_delta_pct": r.volume_delta_pct,
                    "abandonment_delta_pts": r.abandonment_delta_pts,
                    "wait_delta_s": r.wait_delta_s,
                    "verdict": r.verdict,
                    "reasons": list(r.reasons),
                }
                for r in rows
            ],
        }
    )
