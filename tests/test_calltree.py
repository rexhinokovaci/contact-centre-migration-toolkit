from __future__ import annotations

import pytest

from ccmt.calltree import CallTreeError, parse
from ccmt.validate import validate


def tree(body: str) -> str:
    return "entry: a\nnodes:\n" + body


def test_sample_parses_and_has_only_the_known_dead_branch(samples):
    t = parse((samples / "partner-ivr.yaml").read_text())
    issues = validate(t)
    assert [str(i) for i in issues] == [
        "warning: [smart-meter-campaign] unreachable from entry; probably a dead branch"
    ]
    assert t.queues()[0] == "Billing"


@pytest.mark.parametrize(
    "text, message",
    [
        ("- not a mapping", "top level must be a mapping"),
        ("entry: a\nnodes: {}", "'nodes' must be a non-empty mapping"),
        ("nodes: {a: {type: hangup}}", "'entry' must name the first node"),
        (tree("  a: {type: teleport}"), "unknown type 'teleport'"),
        (tree("  a: {type: menu, retries: 9}"), "retries must be an integer 0-5"),
        ("entry: [", "invalid YAML"),
    ],
)
def test_parse_errors(text, message):
    with pytest.raises(CallTreeError, match=message):
        parse(text)


def messages(body: str) -> list[str]:
    return [str(i) for i in validate(parse(tree(body)))]


def test_missing_targets_and_bad_keys():
    out = messages('  a: {type: menu, prompt: hi, options: {"1": b, "x": c}}\n  c: {type: hangup}')
    assert "error: [a] points at missing node 'b'" in out
    assert "error: [a] invalid DTMF keys: x" in out
    assert "warning: [a] no timeout target; callers who don't press anything will be cut off" in out


def test_transfer_numbers_must_be_e164():
    assert "error: [a] number 0800 111 999 is not E.164" in messages(
        '  a: {type: transfer, number: "0800 111 999"}'
    )


def test_loop_without_input_is_an_error():
    out = messages(
        "  a: {type: message, prompt: x, next: b}\n  b: {type: message, prompt: y, next: a}"
    )
    assert any("loop with no caller input: a -> b -> a" in m for m in out)


def test_menu_loops_are_fine():
    out = messages(
        '  a: {type: menu, prompt: x, options: {"1": a}, timeout: b}\n  b: {type: hangup}'
    )
    assert not [m for m in out if m.startswith("error")]


def test_too_many_options_warns():
    opts = ", ".join(f'"{i}": z' for i in range(6))
    out = messages(
        f"  a: {{type: menu, prompt: x, options: {{{opts}}}, timeout: z}}\n  z: {{type: hangup}}"
    )
    assert "warning: [a] 6 options; more than 5 is hard to remember" in out
