from __future__ import annotations

from ccmt.calltree import parse
from ccmt.convert import convert, queue_placeholder
from ccmt.lint import lint


def test_sample_converts_to_a_lint_clean_flow(samples):
    result = convert(parse((samples / "partner-ivr.yaml").read_text()))
    assert lint(result.flow) == []
    assert result.dropped == ["smart-meter-campaign"]
    assert "QUEUE_SMART_METER_CAMPAIGN" not in result.placeholders
    assert result.flow["StartAction"] == "sys-logging"


def test_menu_retries_are_unrolled(samples):
    flow = convert(parse((samples / "partner-ivr.yaml").read_text())).flow
    by_id = {a["Identifier"]: a for a in flow["Actions"]}
    first, second, third = (
        by_id["main-menu"],
        by_id["main-menu--retry1"],
        by_id["main-menu--retry2"],
    )
    assert first["Transitions"]["NextAction"] == "main-menu--retry1"
    assert second["Parameters"]["Text"].startswith("Sorry, I didn't get that.")
    # Last attempt falls through to the timeout target.
    assert third["Transitions"]["NextAction"] == "general"
    keys = {
        c["Condition"]["Operands"][0]: c["NextAction"] for c in first["Transitions"]["Conditions"]
    }
    assert keys == {
        "1": "billing-menu",
        "2": "meter-readings",
        "3": "home-moves",
        "9": "gas-emergency",
    }


def test_queue_nodes_handle_capacity_and_errors(samples):
    flow = convert(parse((samples / "partner-ivr.yaml").read_text())).flow
    by_id = {a["Identifier"]: a for a in flow["Actions"]}
    assert by_id["billing"]["Parameters"]["QueueId"] == "${QUEUE_BILLING}"
    errors = {
        e["ErrorType"]: e["NextAction"] for e in by_id["billing--transfer"]["Transitions"]["Errors"]
    }
    assert errors == {"QueueAtCapacity": "sys-queue-full", "NoMatchingError": "sys-technical-error"}


def test_unused_system_blocks_are_pruned():
    t = parse("entry: a\nnodes:\n  a: {type: hangup}")
    ids = [a["Identifier"] for a in convert(t).flow["Actions"]]
    assert ids == ["sys-logging", "a"]


def test_queue_placeholder_names():
    assert queue_placeholder("Financial Support") == "QUEUE_FINANCIAL_SUPPORT"
    assert queue_placeholder("  Pay/ments  ") == "QUEUE_PAY_MENTS"


def test_lint_catches_structural_problems():
    flow = {
        "StartAction": "a",
        "Actions": [
            {
                "Identifier": "a",
                "Type": "MessageParticipant",
                "Parameters": {},
                "Transitions": {"NextAction": "ghost"},
            },
            {"Identifier": "b", "Type": "GetParticipantInput", "Parameters": {}, "Transitions": {}},
        ],
    }
    rules = {(i.rule, i.action) for i in lint(flow)}
    assert {
        ("logging-first", "a"),
        ("dangling-transition", "a"),
        ("dead-end", "b"),
        ("error-branch", "b"),
        ("unreachable", "b"),
    } <= rules


def test_failed_transfer_tells_caller_the_number(samples):
    flow = convert(parse((samples / "partner-ivr.yaml").read_text())).flow
    by_id = {a["Identifier"]: a for a in flow["Actions"]}
    errors = {
        e["ErrorType"]: e["NextAction"]
        for e in by_id["gas-emergency--transfer"]["Transitions"]["Errors"]
    }
    assert set(errors.values()) == {"gas-emergency--failed"}
    assert "0 8 0 0, 1 1 1, 9 9 9" in by_id["gas-emergency--failed"]["Parameters"]["Text"]


def test_spoken_number():
    from ccmt.convert import spoken_number

    assert spoken_number("+44800111999") == "0 8 0 0, 1 1 1, 9 9 9"
    assert spoken_number("+441134960000") == "0 1 1 3, 4 9 6, 0 0 0 0"
