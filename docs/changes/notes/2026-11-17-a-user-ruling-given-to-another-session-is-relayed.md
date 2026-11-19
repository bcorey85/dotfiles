---
type: "Change"
change_type: "added"
title: "A user ruling given to another session is relayed with --relayed-by and --quote and checked against that session's transcript"
description: "asks-done and phase_asks.py rule take --by user --relayed-by <session name> --quote <words>; the script needs a real user turn of that live session whose whole text is the quote, typed after the asks were filed, and refuses otherwise."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-17T22:49:30-06:00"}
seq: 3
kind: "fix"
components: ["script/review-fix-asks", "script/phase-asks", "script/review-asks"]
evidence: ["review-loop-refuses-a-relayed-user-ruling-on-a"]
watches: []
test: "tests/scripts/test_ruling_relay.py::AsksDoneRelayTest::test_a_quote_no_turn_holds_is_refused"
asked: ""
proof: []
unmeasured: "No intake number counts relayed user rulings."
---

## Change

- `lib/human_turn_lookup.py` maps a session name to its one live registry row, finds the transcript under any project folder, and accepts a quote only in a turn that `user_prompts.prompt_text` reads as typed, with origin exactly `{"kind": "human"}`, whose whole text (reminders and pastes stripped by `user_words`) is the quote, typed after the ask was filed.
- `review/ruling_relay.py` parses `--relayed-by` and `--quote`, refuses them without `--by user`, and records an `ask-ruling-relayed` row in the hand-back store (ruler, relayed_by, quote, turn time, finding ids). Any failed lookup exits 2 with nothing logged.
- `review_fix.py save_packet_asks` stamps `filed_at` on each ask; `phase_asks.py` uses the open row's time.
- The refusal text of a session's user-only ruling names the option; the skill text is unchanged.

## Evidence

A session that did not receive the user's words could only rule a user-only ask with its own claim of what the user said.

## Result

A quote with no matching human turn, a peer message, an older turn, an unknown name, or a call without `--by user` is refused with nothing logged.

## Watch

None.

## Back-out

Revert the commit.
