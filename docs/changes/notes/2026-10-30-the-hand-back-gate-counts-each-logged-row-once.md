---
type: "Change"
change_type: "fixed"
title: "The hand-back gate counts each logged row once"
description: "The loop transcript reader skips records that repeat a turn's blocks, so a review loop that logged 3 of 5 finding rows is denied at hand-back instead of passing on a count of 6."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T11:42:22-05:00"}
seq: 373
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_hand_back_with_three_of_five_rows_is_denied_when_the_transcript_repeats_each_call_in_a_blob"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `LoopTranscript.read_record` reads content blocks only from `user` and `assistant` records. An `api-request-blob` record repeats the turn's blocks, and the reader counted its Bash, send and hand-back calls a second time.

## Evidence

- One denied loop had 6 logged finding rows and read as 12. In the new test, 3 of 5 rows logged was read as 6, so the gate passed the hand-back.

## Result

- The new test fails before the change: the hook passes 3 of 5 rows. After it, the test passes and `OneCheckedHandBackTest` passes: 22 tests. `test_review_loop_gate`, `test_review_fix_script` and `test_review_loop_script` pass, and ruff passes.

## Watch

None: a denial that now fires leaves no intake number that separates it from any other ledger denial.

## Back-out

Revert the commit.
