---
type: "Change"
change_type: "fixed"
title: "A /code phase rejection is recorded, so the next review loop drops the repeat"
description: "An ask the session rejects with `phase_asks.py rule` is stored as a rejected ask, so the next review loop of that repo drops the same ask instead of raising it again."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T00:15:54-06:00"}
seq: 1
kind: "fix"
components: ["script/phase-asks", "script/review-asks", "script/review-fix", "script/handback-store"]
evidence: ["code-rejected-asks-are-not-recorded"]
watches: []
test: "tests/scripts/test_phase_asks_rejections.py::RejectedAskIsRecordedTest::test_the_next_loop_drops_the_ask_the_phase_ruling_rejected"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/phase_asks.py` `rule`: each ask ruled `rejected` is stored as a rejected-ask row before the outcome rows are logged, under the repo key the review loop reads (`handback_store.ruled_rows_repo`). The row goes to the ruling session and to each session whose open asks the ruling answers, once each.
- `review/review_asks.py` now owns `rejected_ask_text` and `record_rejected_asks`. `review/review_fix_asks.py` calls them and keeps no copy.
- `review/handback_store.py` `record_rejected_ask` adds no row for a text the session already holds as rejected in that repo. A withdrawn text is recorded again.

## Evidence

Queue item `code-rejected-asks-are-not-recorded`: only the review-fix path wrote the rejected-ask row, so a /code phase rejection left nothing for the next loop to match.

## Result

The named test fails on the old script (the next loop keeps the ask) and passes with the change. New `tests/scripts/test_phase_asks_rejections.py` has 16 tests: the next loop drops the repeat through the real store and the real match; an accepted ask writes no row; a rerun, and a rerun after a crash before the ruled row, add no row; a failing logger, a hanging logger and telemetry off still leave the row; an ask with no location; quotes, newlines and a 20,000-character question; an opener that differs from the ruler; two `rule` calls at once write one row per session; a linked worktree; a damaged store line and an unwritable store exit 1 and write no row. With the session list emptied, 13 of the 16 fail; the other 3 assert that nothing is written.

Suite: `bash tests/run.sh` passes, 4091 tests in 145 files, 0 failed.

## Watch

None. No intake number reads a repeated ask.

## Back-out

Revert the commit. The stored rejected-ask rows are read only by the review loop and expire with their session file.
