---
type: "Change"
change_type: "fixed"
title: "A later /code review reviews the files the review loop's fix coder wrote instead of holding them"
description: "The review loop records the untracked files its claude -p fix coder wrote, and code_review_start reviews them as the run's own instead of holding them for another live session."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T21:31:24-06:00"}
seq: 38
kind: "fix"
components: ["script/review-loop", "script/code-review-start"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_file_the_review_loops_fix_coder_wrote_is_never_held"
asked: ""
proof: []
unmeasured: "a script fix; no intake number reads it"
---

## Change

`lib/fix_coder_written.py` owns one record, `<git dir>/code-phase/fix-coder-written.json`. `review_loop_untracked.record_loop_written` adds each new untracked path a fix coder call made; `code_review_start.phase_held_files` leaves recorded paths out of the held files; `phase_start.py --new-run` empties it.

## Evidence

Queue item review-loop-s-fix-coder-writes-are-not: the fix coder runs as `claude -p`, so no subagent transcript attributes its new files and /code held them while another session was live.

## Result

Both `test_a_file_the_review_loops_fix_coder_wrote_is_never_held` and `test_review_loop_coder.py::UntrackedDeletionTest::test_a_file_the_fix_coder_wrote_is_recorded_for_the_next_code_review_start` fail on the old code and pass now.

## Watch

None.

## Back-out

Revert the commit.

