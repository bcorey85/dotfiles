---
type: "Change"
change_type: "fixed"
title: "Branch review fixes for the review-put-back batch"
description: "A quoted line of a removed comment block keeps the whole block removed, a stale-dispatch refusal with no round open ends on a step, and the stray-file gate runs under the named-tests time limit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T22:38:51-06:00"}
seq: 8
kind: "fix"
components: ["script/review-loop-comment-removal", "script/reviewer-dispatch", "script/code-wait", "script/review-loop-stray-files"]
evidence: ["tests/scripts/test_review_loop_script.py", "tests/scripts/test_code_wait.py", "tests/scripts/test_review_loop_scope_guard.py"]
watches: []
test: "tests/scripts/test_review_loop_script.py::CommentRemovalUnitTest::test_a_quote_of_one_line_of_a_two_line_comment_block_keeps_the_whole_block_removed"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

review_loop_comment_removal.py adds the removed lines a finding quotes to the named lines before the block-span check, so one quoted line covers its comment block the way a line match does. reviewer_dispatch.py ends the no-open-round refusal with "run `<wait command>` with no pairs to get the next round or the packet". code_wait.py's docstring names the exit-1 refusal. review_loop_stray_files.py passes the named-tests budget (540 s) to the scoped run; a timeout reads as no result, so the loop stops.

## Evidence

New tests: a two-line comment block with one line quoted stays removed; the refusal's last line names a step and the wait exits 1; the stray gate passes a deadline and returns None on a timed-out run. The three test files pass (702 tests).

## Result

A half-restored comment block, a refusal with no next step and an unbounded stray gate no longer occur.

## Watch

None.

## Back-out

Revert the commit.
