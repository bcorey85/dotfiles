---
type: "Change"
change_type: "fixed"
title: "A finished /code run that a skill the main session is running goes on with that skill's next step"
description: "When the /code run wrote no new stop, the relay prints NO_STOP_RULE: relay the Skill result, and for a finished run go on with the invoking skill's next step, otherwise say the Skill result word for word."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-26T04:31:39-06:00"}
seq: 7
kind: "fix"
components: ["script/code-relay"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_relay.py::RelayTest::test_only_a_moved_aside_stop_exits_1_and_relays_nothing"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

In `code_relay.py`, FALLBACK became NO_STOP_RULE on the three no-new-stop exits (no stop file, only a moved-aside `stop.prev.md`, a stop relayed already). The rule says: relay the Skill result in place of a stop; with a `To go on:` line, say it word for word and make no other tool call; otherwise, for a finished run that a skill the main session is running invoked, go on with that skill's next step. No skill file changes.

## Evidence

judgment. Nobody measured it.

## Result

Not measured.

## Watch

None.

## Back-out

Revert the NO_STOP_RULE text in `code_relay.py` to FALLBACK on the three no-new-stop exits, and revert the matching edits in `tests/scripts/test_code_relay.py`.
