---
type: "Change"
change_type: "fixed"
title: "asks-done needs --by; no default records a user sign-off"
description: "review_fix.py asks-done refuses a call with no --by and logs nothing, so an ask outcome is recorded as the user's only when the caller says the user gave it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T01:30:00-06:00"}
seq: 1
kind: "fix"
components: ["skill/review", "skill/fix"]
evidence: ["session report: asks-done-defaults-to-by-user-and-logs-a-session"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_without_by_exits_2_logs_nothing_and_names_both_values"
asked: ""
proof: []
unmeasured: "No skill text changed; every skill and agent caller already passed --by."
---

## Change

- `review_fix_asks.asks_done_options`: `--by` has no default; a call without it exits 2, logs nothing and names `--by user` and `--by session`. `log_fix_ask_outcomes` loses its `decided_by` default.
- `review_fix.py`: the printed asks-done command carries `--by user` (it relays the user's answer) and the present-asks text names `--by session` for a session ruling; the usage text drops "default user".

## Evidence

A session's own ruling on a resume ran asks-done without `--by` and was logged with `ask_decided_by=user`.

## Result

The new test fails before the change and passes after. `bash tests/run.sh`: 3423 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
