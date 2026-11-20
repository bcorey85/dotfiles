---
type: "Change"
change_type: "fixed"
title: "asks-done records session rulings while a user-only ask stays held"
description: "A session asks-done call takes held on each user-only ask, logs the plain asks and prints their fix run, and moves the held asks to a kept packet a later --by user call rules."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 11
kind: "fix"
components: ["script/review-fix-asks", "script/review-asks", "script/approval-asks-store", "script/ask-outcome-words"]
evidence: ["a-user-only-ask-on-a-claude-md-owner-line-holds"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::HeldAskTest::test_a_session_call_logs_the_plain_asks_prints_the_fix_run_and_keeps_the_held_ask_waiting"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/ask_outcome_words.py` adds `held`, valid only on a user-only ask in a `--by session` call. The plain asks log and their fix run prints; the held asks move to a kept packet `<parent id>-held` with the parent's relaunch args, recorded in the packet repo's approval store. `held` on a plain ask, on every ask, on a retry of a partly logged call, or in a `--by user` call is refused; the refusal for another word on a user-only ask names `held`.

## Evidence

A session could not log the plain asks of a packet that also held a user-only ask, so they waited on a user who does not answer panes.

## Result

`HeldAskTest` in `test_review_fix_ask_ruler.py`.

## Watch

None.

## Back-out

Revert the commit.
