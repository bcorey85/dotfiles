---
type: "Change"
title: "asks-done logs the outcome of an ask that names no file"
description: "An ask whose file_line is `unlocated` sent `line=0` to the finding writer, which refuses a line on an unlocated finding, so its ask row and its outcome row were lost; the row now carries no line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:54:45-05:00"}
seq: 192
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_logs_the_outcome_of_an_ask_that_names_no_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.ask_row_fields` sends `file=unlocated` and no `line=` when the ask's file_line is `unlocated`. Every other
  ask keeps `file=` and `line=`.
- `UNLOCATED` moves to handback; review_loop_script reads it from there.

## Evidence

- A queued report: asks-done refused to log `file=unlocated takes no line=`, so the user's rulings on those asks never
  reached the ledger.

## Result

- The new test logs one outcome row for an unlocated ask and reports no failure. It failed before the change.

## Watch

—

## Back-out

Revert the commit.
