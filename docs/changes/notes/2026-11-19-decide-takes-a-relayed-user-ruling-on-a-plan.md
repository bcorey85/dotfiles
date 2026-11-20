---
type: "Change"
change_type: "fixed"
title: "decide takes a relayed user ruling on a plan the user owns"
description: "`review_fix.py decide adopt|keep --by user --relayed-by <session> --quote \"<words>\"` records the user as the ruler, with the relaying session and the quote, after checking the quote against that session's transcript. A bare `--by session` call on a user-owned plan stays refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:00:00-06:00"}
seq: 6
kind: "fix"
components: ["script/review-fix", "script/plan-format", "shared/review-fork-run"]
evidence: ["decide-refuses-a-relayed-user-ruling-on-a-user"]
watches: []
test: "tests/scripts/test_ruling_relay.py::DecideRelayTest::test_a_relayed_user_ruling_on_a_user_owned_plan_is_logged_with_the_relayer_and_the_quote"
asked: ""
proof: []
unmeasured: ""
---

## Change

`decide` pops `--relayed-by` and `--quote` before parsing and verifies them through `ruling_relay.verify_relay`
against the time the impact was filed: the hand-back row's time, or the `plan_impact_filed_at` stamp the review-fix
state now carries (the state file's mtime for a state saved before the stamp). The `## Plan Deviations` entry names
the user, the relaying session and the quote, and a `plan-ruling-relayed` row goes to the hand-back store. The
review fork's resume passes the relay to `decide` when the stop holds a plan-impact question, and `DECIDE_BY_NOTE`
names the relay form.

## Evidence

The refusal of `--by session` on a user-owned plan left a resumed fork no way to pass on the user's relayed ruling.

## Result

New `DecideRelayTest` in `tests/scripts/test_ruling_relay.py`: a relayed ruling passes and clears the gate; a bare
session ruling, a relay under `--by session`, a quote no human turn holds and a turn older than the hand-back are
refused with nothing logged.

## Watch

None.

## Back-out

Revert the commit.
