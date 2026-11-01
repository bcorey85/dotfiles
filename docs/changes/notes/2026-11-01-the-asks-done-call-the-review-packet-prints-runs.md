---
type: "Change"
change_type: "fixed"
title: "The asks-done call the review packet prints runs once its outcomes are filled in"
description: "The review packet now prints one numbered outcome slot per ask (`<outcome-1> <outcome-2>`), so a session that fills in the slots runs the asks-done call right the first time, instead of copying a count marker (`x2`) that asks-done refused as an extra outcome."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T05:13:35-06:00"}
seq: 435
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_the_printed_asks_done_call_runs_once_each_outcome_is_filled_in"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_fix.asks_done_line` prints one `<outcome-N>` slot per ask, in ask order, in place of `<outcome> xN`, and says one outcome goes to each ask.

## Evidence

- Two sessions copied `x1` as typed; asks-done answered "1 ask(s) waiting but 2 outcome(s) given" and the session had to retry.

## Result

- The new test fills each printed slot with `accepted` and runs the call; it fails before the change and passes after.

## Watch

None: no intake number counts refused asks-done calls.

## Back-out

Revert the commit.
