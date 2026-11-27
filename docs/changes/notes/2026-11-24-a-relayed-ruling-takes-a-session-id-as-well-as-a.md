---
type: "Change"
change_type: "fixed"
title: "A relayed ruling takes a session id as well as a name"
description: "`--relayed-by` accepts the session id of a live row as well as a name, so two live sessions that share a name can still relay a ruling, and the ruling rows record the row's name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:22:18-06:00"}
seq: 1
kind: "fix"
components: ["script/review-fix", "shared/review-loop"]
evidence: ["tests/scripts/test_human_turn_lookup.py", "tests/scripts/test_ruling_relay.py"]
watches: []
test: "tests/scripts/test_human_turn_lookup.py::HumanTurnLookupTest.test_a_name_two_live_rows_share_refuses_and_names_the_id_form_while_the_id_of_one_is_accepted"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`human_turn_lookup.relaying_row` looks a `--relayed-by` word up as a live session id first, then as a name. A name that several live rows hold refuses and names the `--relayed-by <sessionId>` form. A live row with that id but no name refuses. `verified_human_turn` returns the relaying session with the turn, and `RelayedRuling` carries `session_name`, which the `ask-ruling-relayed` row, the `plan-ruling-relayed` row and the plan's `Ruled by` words record. `session_registry.row_for_session_id` finds the live row.

## Evidence

`test_human_turn_lookup.py` pins the id lookup, the two same-name rows (the name refuses with the id form, the id of one is accepted), the nameless id row and the dead id. `test_ruling_relay.py` runs an `asks-done` relay by id and reads the recorded name.

## Result

Before, a name held by two live rows refused with no way to relay; now the id of one row relays and records that row's name.

## Watch

—

## Back-out

Revert `row_for_session_id`, `RelayingSession` and `relaying_row` (back to `session_id_of_name`), the `session_name` field of `RelayedRuling` and its readers in `ruling_relay.py` and `review_fix_plan_impacts.py`, the `RELAY_USAGE` words and the `review-fork-run.md` sentence.
