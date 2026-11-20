---
type: "Change"
change_type: "fixed"
title: "Relayed asks-done rules asks saved without a filed time"
description: "A relayed user ruling on user-only asks saved before filed times were stamped is now bounded by the review-fix state file's modification time instead of refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T00:50:17-06:00"}
seq: 1
kind: "fix"
components: ["script/review-fix", "script/ruling-relay"]
evidence: ["tests/scripts/test_ruling_relay.py::AsksDoneUnstampedAskTest::test_a_turn_after_the_state_was_written_rules_an_ask_with_no_filed_time"]
watches: []
test: "tests/scripts/test_ruling_relay.py::AsksDoneUnstampedAskTest::test_a_turn_after_the_state_was_written_rules_an_ask_with_no_filed_time"
---

## Change

`review_fix.py asks-done --by user --relayed-by <s> --quote <q>` no longer refuses a user-only ask that has no filed time; `read_state` stamps it with the state file's modification time (`stamp_legacy_filed_at`), read before any caller saves, and that time stands in as the bound: it is no earlier than the save that filed the ask, so a quote typed before it is refused.

## Evidence

tests/scripts/test_ruling_relay.py::AsksDoneUnstampedAskTest::test_a_turn_after_the_state_was_written_rules_an_ask_with_no_filed_time

## Result

A lane session can relay a ruling on asks saved before filed times were stamped; a turn older than the state file is still refused as older than the ask.

## Watch

—

## Back-out

Revert `stamp_legacy_filed_at` and its call from `read_state` in `review_fix_state.py`.
